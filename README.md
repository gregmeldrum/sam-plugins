# SAM Agent Plugins

A collection of specialized agent plugins for Solace Agent Mesh (SAM), providing vision, web automation, image processing, and artifact hosting capabilities.

## Agent Plugins

### Object Detection
**YOLO-based object detection agent** that identifies and locates objects in images using the YOLOv12 model. Processes image artifacts, returns bounding boxes with confidence scores, and can filter detections by class or confidence threshold. Ideal for computer vision pipelines requiring real-time object recognition.

### Local MLX Vision
**Local vision language model agent** running on Apple Silicon using the MLX framework. Performs OCR, image description, and structured data extraction using the Qwen3-VL model. All inference runs on-device for maximum privacy. Supports both image artifacts and direct file paths. Perfect for receipt OCR, form extraction, and visual question answering. **Requires Apple Silicon Mac with at least 8GB of unified memory.**

### Artifact Host Agent
**Web server agent** that makes artifacts accessible via HTTP URLs. Automatically hosts HTML files and their referenced assets (images, CSS, JS) by parsing SAM's artifact references and converting them to standard relative paths. Provides a directory listing interface and direct file access at `http://localhost:8080`.

### ImageMagick Agent
**Image manipulation agent** powered by ImageMagick. Provides tools for resizing, format conversion, rotation, cropping, filters, and compositing. Handles common image processing tasks through a simple tool interface. Supports all ImageMagick-compatible formats. **Requires ImageMagick to be installed** on the system.

### Web Agent
**Web search and request agent** that fetches web content and searches the web. Uses DuckDuckGo for text, image, video, and news searches. Includes built-in web request tool for fetching and processing web pages. Returns structured search results and web content as JSON artifacts.

### Local TTS
**Text-to-speech agent** powered by Microsoft's VibeVoice framework. Converts text to natural-sounding speech with local inference. Generates high-quality audio artifacts from text input, supporting multiple voices and languages. All processing runs locally for privacy.

### Video Editor Agent
**Video editing agent** using FFmpeg for video manipulation. Provides tools for trimming, concatenating, format conversion, adding audio, applying filters, and extracting frames. Handles complex video processing tasks through a simple tool interface. Supports all FFmpeg-compatible formats. **Requires FFmpeg to be installed** on the system.

## Pre-download Models (Recommended)

For agents using local models, download the models first to avoid delays during agent startup:

### Install Hugging Face CLI

```bash
pip install "huggingface_hub[cli]"
```

### Download Models

```bash
# For Local MLX Vision agent
hf download mlx-community/Qwen3-VL-2B-Instruct-4bit

# For Local TTS agent
hf download microsoft/VibeVoice-Realtime-0.5B
```

## Installing plugins using pip

Edit the plugin_list to control which plugins get installed

```bash
#!/bin/bash
plugin_list=("web-agent" "artifact-host-agent" "imagemagick" "local-mlx-vision" "local-tts" "video-editor-agent" "object-detection")

for plugin in "${plugin_list[@]}"; do
    sam plugin install git+https://github.com/gregmeldrum/sam-plugins#subdirectory=${plugin}"
    sam plugin add ${plugin} --plugin ${plugin}
done
```

## Installing plugins using uv pip

Edit the plugin_list to control which plugins get installed

```bash
#!/bin/bash

plugin_list=("web-agent" "artifact-host-agent" "imagemagick" "local-mlx-vision" "local-tts" "video-editor-agent" "object-detection")

for plugin in "${plugin_list[@]}"; do
    sam plugin install git+https://github.com/gregmeldrum/sam-plugins#subdirectory=${plugin} --install-command "uv pip install git+https://github.com/gregmeldrum/sam-plugins#subdirectory=${plugin}"
    sam plugin add ${plugin} --plugin ${plugin}
done
```
