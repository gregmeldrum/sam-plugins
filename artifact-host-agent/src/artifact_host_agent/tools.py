import logging
import asyncio
import inspect
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id

from .web_server import get_web_server

logger = logging.getLogger(__name__)


async def host_artifact(
    artifact_filename: str,
    custom_filename: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Host an artifact on the web server for easy access.

    Copies an artifact from the artifact service to the web server's hosting
    directory and returns a URL for accessing it.

    Args:
        artifact_filename: Artifact filename with optional version (e.g., "photo.jpg" or "photo.jpg:2")
        custom_filename: Optional custom name for the hosted file (default: use original name)
        tool_context: Framework context for accessing artifact service
        tool_config: Optional configuration:
            - base_url: Custom base URL for generated URLs (for firewall/proxy scenarios)

    Returns:
        Dictionary with status, message, hosted filename, and URL
    """
    log_identifier = f"[ArtifactHost:host_artifact:{artifact_filename}]"
    logger.info(f"{log_identifier} Hosting artifact")

    if not tool_context:
        logger.error(f"{log_identifier} ToolContext is missing.")
        return {"status": "error", "message": "ToolContext is required"}

    # Get web server instance
    web_server = get_web_server()
    if not web_server:
        logger.error(f"{log_identifier} Web server is not initialized")
        return {
            "status": "error",
            "message": "Web server is not running. Please check agent configuration."
        }

    try:
        # Extract invocation context
        inv_context = tool_context._invocation_context
        if not inv_context:
            raise ValueError("InvocationContext is not available.")

        app_name = getattr(inv_context, "app_name", None)
        user_id = getattr(inv_context, "user_id", None)
        session_id = get_original_session_id(inv_context)
        artifact_service = getattr(inv_context, "artifact_service", None)

        if not all([app_name, user_id, session_id, artifact_service]):
            raise ValueError("Missing required context parts")

        # Parse artifact filename and version
        parts = artifact_filename.rsplit(":", 1)
        filename_base = parts[0]
        version_str = parts[1] if len(parts) > 1 else None
        version_to_load = int(version_str) if version_str else None

        # Get latest version if not specified
        if version_to_load is None:
            list_versions_method = getattr(artifact_service, "list_versions")
            if inspect.iscoroutinefunction(list_versions_method):
                versions = await list_versions_method(
                    app_name=app_name, user_id=user_id, session_id=session_id, filename=filename_base
                )
            else:
                versions = await asyncio.to_thread(
                    list_versions_method, app_name=app_name, user_id=user_id,
                    session_id=session_id, filename=filename_base
                )
            if not versions:
                raise FileNotFoundError(f"Artifact '{filename_base}' not found.")
            version_to_load = max(versions)

        logger.debug(f"{log_identifier} Loading artifact version {version_to_load}")

        # Load artifact
        load_artifact_method = getattr(artifact_service, "load_artifact")
        if inspect.iscoroutinefunction(load_artifact_method):
            artifact = await load_artifact_method(
                app_name=app_name, user_id=user_id, session_id=session_id,
                filename=filename_base, version=version_to_load
            )
        else:
            artifact = await asyncio.to_thread(
                load_artifact_method, app_name=app_name, user_id=user_id,
                session_id=session_id, filename=filename_base, version=version_to_load
            )

        if not artifact or not artifact.inline_data:
            raise FileNotFoundError(f"Content for '{filename_base}' v{version_to_load} not found.")

        artifact_bytes = artifact.inline_data.data
        logger.debug(f"{log_identifier} Loaded artifact: {len(artifact_bytes)} bytes")

        # Determine hosted filename
        hosted_filename = custom_filename if custom_filename else filename_base

        # Ensure filename has extension
        if custom_filename and '.' not in custom_filename and '.' in filename_base:
            # Preserve original extension if custom name doesn't have one
            extension = Path(filename_base).suffix
            hosted_filename = f"{custom_filename}{extension}"

        # Write artifact to web server directory
        hosted_path = web_server.host_directory / hosted_filename

        # Write file (in thread pool to avoid blocking)
        await asyncio.to_thread(_write_file, hosted_path, artifact_bytes)

        logger.info(f"{log_identifier} Artifact written to {hosted_path}")

        # Get configuration
        current_tool_config = tool_config if tool_config is not None else {}
        base_url = current_tool_config.get("base_url")

        # Generate URL
        url = web_server.get_url(hosted_filename, base_url)

        logger.info(f"{log_identifier} Artifact hosted successfully at {url}")

        return {
            "status": "success",
            "message": f"Artifact hosted successfully",
            "artifact_filename": filename_base,
            "artifact_version": version_to_load,
            "hosted_filename": hosted_filename,
            "url": url,
        }

    except FileNotFoundError as e:
        logger.warning(f"{log_identifier} File not found: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.exception(f"{log_identifier} Unexpected error: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}


def _write_file(path: Path, content: bytes) -> None:
    """
    Write content to a file (synchronous).

    Args:
        path: Path to write to
        content: Content bytes
    """
    with open(path, 'wb') as f:
        f.write(content)
