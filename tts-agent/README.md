# TTS Agent Plugin

An agent plugin for Solace Agent Mesh that provides text-to-speech capabilities using Kokoro TTS.

## Description

This plugin enables agents to convert text into natural-sounding audio using the Kokoro TTS model. It supports multiple languages, various voices, and automatically downloads required model files on first use.

## Features

### Text-to-Speech Conversion

- **Multiple Languages**: English (US/UK), French, Italian, Japanese, Chinese
- **Various Voices**: Male and female voice options for each language
- **Flexible Input**: Direct text or text from artifact files
- **Audio Formats**: MP3 (default) or WAV output
- **Auto Model Download**: Model files are automatically downloaded on first use

### Supported Languages & Voices

#### English (US) - `en-us`
**Female Voices:**
- `af_alloy`, `af_bella`, `af_nicole`, `af_sarah` (default), `af_sky`, `af_star`, `af_nova`, `af_jessica`, `af_emma`, `af_isabella`, `af_river`

**Male Voices:**
- `am_adam`, `am_echo`, `am_liam`, `am_michael`, `am_eric`, `am_lewis`, `am_danny`, `am_matthew`

#### English (UK) - `en-gb`
**Female Voices:**
- `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`

**Male Voices:**
- `bm_daniel`, `bm_george`, `bm_lewis`, `bm_william`

#### French - `fr`
**Female Voices:**
- `ff_siwis`

#### Italian - `it`
**Female Voices:**
- `if_sara`

**Male Voices:**
- `im_nicola`

#### Japanese - `ja`
**Female Voices:**
- `jf_alpha`, `jf_ema`, `jf_hina`

**Male Voices:**
- `jm_kumo`, `jm_yuki`

#### Chinese - `zh`
**Female Voices:**
- `zf_xiaobei`, `zf_xiaoni`, `zf_xiaoxiao`, `zf_yunxi`

**Male Voices:**
- `zm_yunxi`, `zm_yunxia`, `zm_yunyang`, `zm_yunjian`

## Requirements

- Python >= 3.10
- `kokoro-tts` package
- Solace Agent Mesh framework
- Model files (automatically downloaded on first use):
  - `kokoro-v1.0.onnx` (~200MB)
  - `voices-v1.0.bin` (~100MB)

## Installation

1. Build the plugin:
```bash
cd tts-agent
sam plugin build
```

2. Install in your SAM project:
```bash
cd /path/to/your/sam-project
sam plugin add tts-agent --plugin /path/to/tts-agent/dist/tts_agent-0.1.0-py3-none-any.whl
```

3. The plugin configuration will be created at `configs/agents/tts-agent.yaml`

## Usage

### Running the Agent

```bash
sam run configs/agents/tts-agent.yaml
```

Or run all agents:
```bash
sam run
```

### Example Interactions

**Basic TTS with default voice:**
```
User: Convert this text to speech: "Hello, how are you today?"
Agent: [Uses text_to_speech with default voice af_sarah]
Response: Created audio file tts_af_sarah_20240101_120000.mp3
```

**Specify a different voice:**
```
User: Convert "Bonjour tout le monde" to speech using a French voice
Agent: [Uses text_to_speech with voice ff_siwis]
Response: Created audio file with French voice
```

**Request specific gender and language:**
```
User: Create a male British English voice saying "Good afternoon"
Agent: [Selects bm_daniel or another UK male voice]
Response: Created audio with British male voice
```

**From text file:**
```
User: Convert the text in story.txt to speech
Agent: [Uses text_to_speech with text_file="story.txt"]
Response: Created audio file from story.txt content
```

**WAV format output:**
```
User: Convert this to speech in WAV format: "Testing audio quality"
Agent: [Uses text_to_speech with output_format="wav"]
Response: Created WAV audio file
```

## Tool Details

### text_to_speech

Converts text to speech using Kokoro TTS.

**Parameters:**
- `text` (str, optional): Direct text to convert (required if text_file not provided)
- `text_file` (str, optional): Artifact filename containing text (required if text not provided)
- `voice` (str, optional): Voice to use (default: "af_sarah")
- `output_format` (str, optional): Audio format - "mp3" (default) or "wav"
- `output_filename` (str, optional): Custom output filename

**Returns:**
- `status`: "success" or "error"
- `message`: Human-readable message
- `voice`: Voice used for generation
- `output_format`: Audio format
- `audio_size_bytes`: Size of generated audio
- `output_filename`: Name of saved artifact
- `output_version`: Version of saved artifact

**Example Return:**
```json
{
  "status": "success",
  "message": "Text-to-speech conversion successful using voice 'af_sarah'",
  "voice": "af_sarah",
  "output_format": "mp3",
  "audio_size_bytes": 45678,
  "output_filename": "tts_af_sarah_20240101_120000.mp3",
  "output_version": 1
}
```

## Configuration

### Model File Storage

By default, model files are stored in `{plugin_directory}/models/`. You can customize this in the tool_config:

```yaml
tools:
  - tool_type: python
    component_module: tts_agent.tools
    function_name: text_to_speech
    tool_config:
      model_directory: "/path/to/custom/models"
```

### First Use

On first use, the plugin will automatically download:
- `kokoro-v1.0.onnx` from GitHub releases
- `voices-v1.0.bin` from GitHub releases

This is a one-time download (~300MB total). Subsequent uses will reuse the downloaded files.

## Development

### Debug Mode

For rapid development without rebuilding:

```bash
cd tts-agent/src
sam run ../config.yaml
```

Changes to `tools.py` will be reflected immediately.

### Testing the TTS Tool

You can test the tool independently:

```python
import asyncio
from tts_agent.tools import text_to_speech

async def test_tts():
    result = await text_to_speech(
        text="Hello, this is a test",
        voice="af_sarah",
        output_format="mp3",
        tool_context=None  # Will skip artifact saving
    )
    print(result)

asyncio.run(test_tts())
```

## Architecture

The plugin follows the function-based tool pattern:
- `text_to_speech` is an async function in `src/tts_agent/tools.py`
- Automatically downloads model files using `urllib`
- Uses `kokoro-tts` command-line tool via subprocess
- Integrates with SAM artifact service for audio file storage
- Supports both direct text input and artifact file input
- Generated audio saved as MP3 or WAV artifacts

## Model Files

The plugin uses the Kokoro ONNX model:
- **Model**: `kokoro-v1.0.onnx` - The TTS neural network model
- **Voices**: `voices-v1.0.bin` - Voice data for all supported voices
- **Source**: https://github.com/thewh1teagle/kokoro-onnx
- **License**: MIT License

## Troubleshooting

**Model download fails:**
- Check internet connectivity
- Verify GitHub is accessible
- Check disk space (need ~300MB)

**TTS generation fails:**
- Ensure `kokoro-tts` package is installed
- Verify model files are downloaded
- Check voice name is valid
- Verify text input is not empty

**Audio artifact not created:**
- Ensure `tool_context` is provided
- Check artifact service is configured
- Verify write permissions

## License

See project license.

## Author

Greg Meldrum <greg.meldrum@solace.com>
