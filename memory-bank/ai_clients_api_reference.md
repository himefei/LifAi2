# AI Clients API Reference

> Last Updated: 2025-12-12

This document provides a comprehensive API reference for the Ollama and LM Studio clients used in LifAi2.

---

## Ollama Client (`lifai/utils/ollama_client.py`)

### Exception Classes

```python
class OllamaError(Exception):
    """Base exception for Ollama client errors"""

class OllamaConnectionError(OllamaError):
    """Raised when unable to connect to Ollama server"""

class OllamaTimeoutError(OllamaError):
    """Raised when request times out"""

class OllamaModelNotFoundError(OllamaError):
    """Raised when specified model is not found"""
```

### Constructor

```python
OllamaClient(
    base_url: str = "http://localhost:11434",
    default_keep_alive: str = "5m",      # Model memory residence time
    default_timeout: float = 120.0        # Request timeout in seconds
)
```

### Core Methods

#### `test_connection() -> bool`
Tests if Ollama server is reachable.

#### `fetch_models() -> List[str]`
Returns list of available model names.

#### `generate_response(prompt, model, temperature, stream, keep_alive) -> str`
Generates text completion.
- `keep_alive`: Optional override for model memory time ("5m", "1h", "0" to unload)

#### `chat_completion(messages, model, temperature, stream, keep_alive) -> str`
Chat-style conversation.
- `messages`: List of `{"role": "user/assistant/system", "content": "..."}`

#### `generate_embeddings(text, model) -> List[float]`
Generates embedding vector for text.

### New Methods (2025-12-12)

#### `preload_model(model: str) -> bool`
Loads model into memory without generating. Useful for warming up before first request.

```python
# Usage
await client.preload_model("llama3.2")  # Model now in memory, ready for fast response
```

#### `unload_model(model: str) -> bool`
Immediately unloads model from memory (sets keep_alive=0).

```python
# Usage
await client.unload_model("llama3.2")  # Free GPU/RAM immediately
```

#### `chat_with_vision(model, messages, images, temperature, stream, keep_alive) -> str`
Multimodal chat with image support.

```python
# Usage
response = await client.chat_with_vision(
    model="llava:13b",
    messages=[{"role": "user", "content": "What's in this image?"}],
    images=["path/to/image.jpg"],  # or [bytes_data] or [base64_string]
    temperature=0.7
)
```

---

## LM Studio Client (`lifai/utils/lmstudio_client.py`)

### Exception Classes

```python
class LMStudioError(Exception):
    """Base exception for LM Studio client errors"""

class LMStudioConnectionError(LMStudioError):
    """Raised when unable to connect to LM Studio server"""

class LMStudioTimeoutError(LMStudioError):
    """Raised when request times out"""

class LMStudioModelNotFoundError(LMStudioError):
    """Raised when specified model is not found"""
```

### Constructor

```python
LMStudioClient(
    base_url: str = "http://localhost:1234",
    use_native_api: bool = True,    # Use /api/v0/ (faster) vs /v1/ (OpenAI-compatible)
    default_ttl: int = 600          # Model auto-unload time in seconds
)
```

### Core Methods

#### `test_connection() -> bool`
Tests if LM Studio server is reachable.

#### `fetch_models() -> List[str]`
Returns list of available model identifiers.

#### `generate_response(prompt, model, temperature, stream) -> str`
Generates text completion. Async method.

#### `chat_completion(messages, model, temperature, stream) -> str`
Chat-style conversation. Async method.

#### `generate_embeddings(text, model) -> List[float]`
Generates embedding vector.

### New Methods (2025-12-12)

#### `generate_response_sync(prompt, model, temperature) -> str`
Synchronous wrapper for `generate_response`. Use in non-async contexts.

```python
# Usage (no await needed)
response = client.generate_response_sync(
    prompt="Hello, world!",
    model="my-model",
    temperature=0.7
)
```

#### `get_server_status() -> dict`
Returns server information including version and status.

```python
# Usage
status = await client.get_server_status()
# Returns: {"status": "ok", "version": "1.x.x", ...}
```

#### `load_model(model, gpu_offload, context_length, ttl) -> bool`
Programmatically loads a model into memory.

```python
# Usage
await client.load_model(
    model="lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF",
    gpu_offload="max",      # "max", "off", or specific layer count
    context_length=4096,    # Optional context window size
    ttl=600                 # Auto-unload after 600 seconds of inactivity
)
```

#### `unload_model(model: str) -> bool`
Unloads model from memory.

```python
# Usage
await client.unload_model("my-model")
```

#### `chat_with_vision(model, messages, images, temperature, stream) -> str`
Multimodal chat with image support.

```python
# Usage
response = await client.chat_with_vision(
    model="llava-model",
    messages=[{"role": "user", "content": "Describe this image"}],
    images=["path/to/photo.png"],
    temperature=0.7
)
```

---

## Image Processing

Both clients support multiple image input formats:

| Format | Example | Notes |
|--------|---------|-------|
| File path | `"C:/images/photo.jpg"` | Auto-read and base64 encode |
| Bytes | `open(file, 'rb').read()` | Raw image bytes |
| Base64 | `"iVBORw0KGgo..."` | Pre-encoded string |

### Supported Image Types
- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- GIF (`.gif`)
- WebP (`.webp`)

---

## Keep Alive / TTL Reference

### Ollama `keep_alive` Values
| Value | Meaning |
|-------|---------|
| `"5m"` | Keep in memory for 5 minutes |
| `"1h"` | Keep in memory for 1 hour |
| `"-1"` | Keep in memory forever |
| `"0"` | Unload immediately after request |

### LM Studio `ttl` Values
| Value | Meaning |
|-------|---------|
| `600` | Unload after 600 seconds (10 min) of inactivity |
| `-1` | Keep in memory until manual unload |
| `0` | Unload immediately after request |

---

## Error Handling Best Practices

```python
from lifai.utils.ollama_client import (
    OllamaClient, 
    OllamaConnectionError, 
    OllamaTimeoutError,
    OllamaModelNotFoundError
)

client = OllamaClient()

try:
    response = await client.generate_response(prompt, model)
except OllamaConnectionError:
    print("Cannot connect to Ollama. Is it running?")
except OllamaTimeoutError:
    print("Request timed out. Try a smaller prompt or increase timeout.")
except OllamaModelNotFoundError:
    print(f"Model '{model}' not found. Run: ollama pull {model}")
except OllamaError as e:
    print(f"Ollama error: {e}")
```

---

## Performance Tips

1. **Preload models** before first use to eliminate cold-start latency
2. **Use keep_alive/TTL** wisely - balance memory usage vs response time
3. **Prefer native API** for LM Studio (`use_native_api=True`) for ~5-10% speed boost
4. **Batch embeddings** when possible to reduce request overhead
5. **Stream responses** for better UX on long generations
