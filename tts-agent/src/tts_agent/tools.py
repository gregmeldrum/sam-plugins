import logging
import asyncio
import inspect
import subprocess
import tempfile
import os
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from solace_agent_mesh.agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    DEFAULT_SCHEMA_MAX_KEYS,
)
from solace_agent_mesh.agent.utils.context_helpers import get_original_session_id

logger = logging.getLogger(__name__)

# Model file URLs
MODEL_URLS = {
    "kokoro-v1.0.onnx": "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin",
}

# Voice catalog organized by language and gender
VOICE_CATALOG = {
    "en-us": {
        "female": ["af_alloy", "af_bella", "af_nicole", "af_sarah", "af_sky", "af_star", "af_nova", "af_jessica", "af_emma", "af_isabella", "af_river"],
        "male": ["am_adam", "am_echo", "am_liam", "am_michael", "am_eric", "am_lewis", "am_danny", "am_matthew"],
    },
    "en-gb": {
        "female": ["bf_alice", "bf_emma", "bf_isabella", "bf_lily"],
        "male": ["bm_daniel", "bm_george", "bm_lewis", "bm_william"],
    },
    "fr": {
        "female": ["ff_siwis"],
        "male": [],
    },
    "it": {
        "female": ["if_sara"],
        "male": ["im_nicola"],
    },
    "ja": {
        "female": ["jf_alpha", "jf_ema", "jf_hina"],
        "male": ["jm_kumo", "jm_yuki"],
    },
    "zh": {
        "female": ["zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_yunxi"],
        "male": ["zm_yunxi", "zm_yunxia", "zm_yunyang", "zm_yunjian"],
    },
}


def _get_model_directory(tool_config: Optional[Dict[str, Any]] = None) -> Path:
    """Get the directory where model files should be stored."""
    if tool_config and "model_directory" in tool_config:
        return Path(tool_config["model_directory"])

    # Default to plugin directory
    plugin_dir = Path(__file__).parent
    return plugin_dir / "models"


async def _ensure_models_downloaded(model_dir: Path, log_identifier: str) -> None:
    """
    Download model files if they don't exist.

    Args:
        model_dir: Directory to store model files
        log_identifier: Logging identifier
    """
    model_dir.mkdir(parents=True, exist_ok=True)

    for filename, url in MODEL_URLS.items():
        file_path = model_dir / filename

        if file_path.exists():
            logger.debug(f"{log_identifier} Model file exists: {filename}")
            continue

        logger.info(f"{log_identifier} Downloading model file: {filename} from {url}")

        try:
            # Download in thread pool to avoid blocking
            await asyncio.to_thread(_download_file, url, file_path)
            logger.info(f"{log_identifier} Successfully downloaded: {filename}")
        except Exception as e:
            logger.error(f"{log_identifier} Failed to download {filename}: {e}")
            raise Exception(f"Failed to download model file {filename}: {e}")


def _download_file(url: str, destination: Path) -> None:
    """
    Download a file from URL to destination (synchronous).

    Args:
        url: URL to download from
        destination: Path to save the file
    """
    urllib.request.urlretrieve(url, destination)


async def text_to_speech(
    text: Optional[str] = None,
    text_file: Optional[str] = None,
    voice: str = "af_sarah",
    output_format: str = "mp3",
    output_filename: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert text to speech using Kokoro TTS.

    Supports multiple languages and voices. Model files are automatically
    downloaded on first use.

    Args:
        text: Text to convert to speech (required if text_file not provided)
        text_file: Artifact filename containing text (required if text not provided)
        voice: Voice to use (e.g., "af_sarah", "am_adam", "bf_alice")
               Available voices by language:
               - en-us: af_alloy, af_bella, af_nicole, af_sarah, af_sky, am_adam, am_echo, etc.
               - en-gb: bf_alice, bf_emma, bm_daniel, bm_george, etc.
               - fr: ff_siwis
               - it: if_sara, im_nicola
               - ja: jf_alpha, jf_ema, jm_kumo, jm_yuki
               - zh: zf_xiaobei, zf_xiaoni, zm_yunxi, etc.
        output_format: Audio format - "mp3" (default) or "wav"
        output_filename: Optional custom output filename
        tool_context: Framework context for accessing artifact service
        tool_config: Optional configuration:
            - model_directory: Path to store model files (default: plugin/models)

    Returns:
        Dictionary with status, message, and output file information
    """
    log_identifier = f"[TTS:text_to_speech:{voice}]"
    logger.info(f"{log_identifier} Starting text-to-speech conversion")

    # Validate inputs
    if not text and not text_file:
        return {
            "status": "error",
            "message": "Either 'text' or 'text_file' must be provided"
        }

    if text and text_file:
        return {
            "status": "error",
            "message": "Provide either 'text' or 'text_file', not both"
        }

    # Validate output format
    if output_format not in ["mp3", "wav"]:
        return {
            "status": "error",
            "message": f"Invalid output_format '{output_format}'. Must be 'mp3' or 'wav'"
        }

    try:
        # Get model directory and ensure models are downloaded
        current_tool_config = tool_config if tool_config is not None else {}
        model_dir = _get_model_directory(current_tool_config)

        logger.info(f"{log_identifier} Using model directory: {model_dir}")
        await _ensure_models_downloaded(model_dir, log_identifier)

        # Get text content
        text_content = text
        source_description = "direct input"

        if text_file:
            # Load text from artifact
            if not tool_context:
                return {
                    "status": "error",
                    "message": "ToolContext is required when using text_file parameter"
                }

            text_content = await _load_text_from_artifact(
                text_file, tool_context, log_identifier
            )
            source_description = f"artifact: {text_file}"

        logger.info(f"{log_identifier} Text source: {source_description}, length: {len(text_content)} chars")

        # Create temporary files for input text and output audio
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_input:
            tmp_input.write(text_content)
            tmp_input_path = tmp_input.name

        try:
            tmp_output_path = tempfile.mktemp(suffix=f'.{output_format}')

            # Build kokoro-tts command
            # Note: kokoro-tts needs to run in the model directory
            cmd = [
                "kokoro-tts",
                tmp_input_path,
                tmp_output_path,
                "--voice", voice,
                "--format", output_format,
            ]

            logger.debug(f"{log_identifier} Running command: {' '.join(cmd)}")
            logger.debug(f"{log_identifier} Working directory: {model_dir}")

            # Run kokoro-tts command in model directory
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                cwd=str(model_dir),
                capture_output=True,
                text=True,
                check=True
            )

            # Check if output file was created
            if not os.path.exists(tmp_output_path):
                raise Exception("TTS command succeeded but output file was not created")

            # Read the output audio file
            with open(tmp_output_path, "rb") as f:
                audio_bytes = f.read()

            logger.info(f"{log_identifier} Generated audio: {len(audio_bytes)} bytes")

            # Save as artifact if tool_context is available
            if tool_context:
                artifact_result = await _save_audio_artifact(
                    audio_bytes=audio_bytes,
                    voice=voice,
                    output_format=output_format,
                    text_preview=text_content[:100],
                    output_filename=output_filename,
                    tool_context=tool_context,
                    log_identifier=log_identifier,
                )

                logger.info(f"{log_identifier} Saved as artifact: {artifact_result['filename']}")

                return {
                    "status": "success",
                    "message": f"Text-to-speech conversion successful using voice '{voice}'",
                    "voice": voice,
                    "output_format": output_format,
                    "audio_size_bytes": len(audio_bytes),
                    "output_filename": artifact_result['filename'],
                    "output_version": artifact_result['version'],
                }
            else:
                return {
                    "status": "success",
                    "message": "Text-to-speech conversion successful (no artifact saved - missing tool_context)",
                    "voice": voice,
                    "output_format": output_format,
                    "audio_size_bytes": len(audio_bytes),
                }

        finally:
            # Clean up temporary files
            if os.path.exists(tmp_input_path):
                os.unlink(tmp_input_path)
            if os.path.exists(tmp_output_path):
                os.unlink(tmp_output_path)

    except subprocess.CalledProcessError as e:
        logger.error(f"{log_identifier} kokoro-tts command failed: {e.stderr}")
        return {
            "status": "error",
            "message": f"TTS conversion failed: {e.stderr}",
            "voice": voice,
        }
    except Exception as e:
        logger.exception(f"{log_identifier} Unexpected error: {e}")
        return {
            "status": "error",
            "message": f"An unexpected error occurred: {e}",
            "voice": voice,
        }


async def _load_text_from_artifact(
    text_file: str,
    tool_context: ToolContext,
    log_identifier: str,
) -> str:
    """
    Load text content from an artifact file.

    Args:
        text_file: Filename with optional version
        tool_context: Framework context
        log_identifier: Log identifier string

    Returns:
        Text content as string
    """
    inv_context = tool_context._invocation_context
    if not inv_context:
        raise ValueError("InvocationContext is not available.")

    app_name = getattr(inv_context, "app_name", None)
    user_id = getattr(inv_context, "user_id", None)
    session_id = get_original_session_id(inv_context)
    artifact_service = getattr(inv_context, "artifact_service", None)

    if not all([app_name, user_id, session_id, artifact_service]):
        raise ValueError("Missing required context parts for loading artifact")

    # Parse filename and version
    parts = text_file.rsplit(":", 1)
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
                list_versions_method, app_name=app_name, user_id=user_id, session_id=session_id, filename=filename_base
            )
        if not versions:
            raise FileNotFoundError(f"Text artifact '{filename_base}' not found.")
        version_to_load = max(versions)

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

    # Decode text content
    text_bytes = artifact.inline_data.data
    text_content = text_bytes.decode("utf-8")

    logger.debug(f"{log_identifier} Loaded text artifact: {len(text_content)} chars")
    return text_content


async def _save_audio_artifact(
    audio_bytes: bytes,
    voice: str,
    output_format: str,
    text_preview: str,
    output_filename: Optional[str],
    tool_context: ToolContext,
    log_identifier: str,
) -> Dict[str, Any]:
    """
    Save audio output as an artifact.

    Args:
        audio_bytes: Audio file bytes
        voice: Voice used
        output_format: Audio format (mp3 or wav)
        text_preview: Preview of the text (first 100 chars)
        output_filename: Optional custom filename
        tool_context: Framework context
        log_identifier: Log identifier string

    Returns:
        Dictionary with filename and version
    """
    inv_context = tool_context._invocation_context
    if not inv_context:
        raise ValueError("InvocationContext is not available.")

    app_name = getattr(inv_context, "app_name", None)
    user_id = getattr(inv_context, "user_id", None)
    session_id = get_original_session_id(inv_context)
    artifact_service = getattr(inv_context, "artifact_service", None)

    if not all([app_name, user_id, session_id, artifact_service]):
        raise ValueError("Missing required context parts for artifact saving")

    # Determine filename
    if not output_filename:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_filename = f"tts_{voice}_{timestamp_str}.{output_format}"
    elif not output_filename.endswith(f".{output_format}"):
        output_filename = f"{output_filename}.{output_format}"

    # Determine MIME type
    mime_type = "audio/mpeg" if output_format == "mp3" else "audio/wav"

    # Prepare metadata
    timestamp = datetime.now(timezone.utc)
    metadata_dict = {
        "description": f"Text-to-speech audio generated with voice '{voice}'",
        "source_tool": "text_to_speech",
        "voice": voice,
        "format": output_format,
        "text_preview": text_preview,
        "creation_timestamp_iso": timestamp.isoformat(),
    }

    # Save artifact
    save_result = await save_artifact_with_metadata(
        artifact_service=artifact_service,
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        filename=output_filename,
        content_bytes=audio_bytes,
        mime_type=mime_type,
        metadata_dict=metadata_dict,
        timestamp=timestamp,
        schema_max_keys=DEFAULT_SCHEMA_MAX_KEYS,
        tool_context=tool_context,
    )

    if save_result.get("status") == "error":
        raise Exception(f"Failed to save artifact: {save_result.get('message')}")

    return {
        "filename": output_filename,
        "version": save_result["data_version"],
    }
