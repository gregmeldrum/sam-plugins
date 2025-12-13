# Local TTS - SAM Agent Plugin

A Solace Agent Mesh (SAM) plugin that provides local text-to-speech capabilities using Microsoft's VibeVoice framework. This agent converts text to natural-sounding speech with local inference for maximum privacy.

## Overview

This plugin enables SAM agents to generate high-quality speech from text using the VibeVoice-Realtime-0.5B model. All inference runs locally, ensuring data privacy.

### Key Features

- **Local Inference**: Runs entirely on-device
- **Privacy First**: No data sent to external services
- **High-Quality Speech**: Natural-sounding voices using VibeVoice
- **Multiple Voices**: Support for different voice profiles
- **Audio Artifacts**: Generates audio files as SAM artifacts

## Installation

### 1. Build the Plugin

From the plugin directory:

```bash
sam plugin build
```

### 2. Install in Your SAM Project

```bash
cd /path/to/your/sam/project
sam plugin add tts-agent --plugin /path/to/local-tts/dist/local_tts-0.1.0-py3-none-any.whl
```

### 3. Download the Model (Recommended)

Pre-download the model to avoid delays during agent startup:

```bash
# Install Hugging Face CLI if not already installed
pip install "huggingface_hub[cli]"

# Download the VibeVoice model
hf download microsoft/VibeVoice-Realtime-0.5B
```

Alternatively, the model will download automatically on first use, but this may cause a delay during the first agent invocation.