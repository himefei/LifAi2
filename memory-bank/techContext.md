# Technology Context

## Core Technologies
- Python (primary implementation language, now leveraging 3.9+ features for `asyncio` and type hinting)
- Ollama (AI backend)
- LM Studio (alternative AI backend)
- Likely PyQt/PySide for UI (based on toolbar.py and toggle_switch.py)
- `httpx` (for asynchronous HTTP requests to AI backends and other services)
### LM Studio Native API v0 Optimization (2025-06-25)
- **Default Configuration**: Switched to native `/api/v0/` endpoints for optimal performance
- **TTL Management**: Default 600-second auto-unload for efficient memory management
- **Performance Boost**: ~5-10% improvement over OpenAI-compatible layer
- **Enhanced Metrics**: Real-time tokens/sec, first-token latency, model architecture details
- **Exclusive Features**: Quantization info, runtime details, context length specifications
- **Advanced Tracking**: Comprehensive performance monitoring with native API statistics
- `aiofiles` (for asynchronous file operations)

## Development Setup
1. Python environment (Python 3.9+ recommended; requirements.txt suggests virtualenv)
2. AI backends (Ollama/LM Studio running locally)
3. Module-based development structure
4. Separate configuration management

## Dependencies
- Core Python standard library
- AI client libraries (ollama_client.py, lmstudio_client.py, now using `httpx`)
- UI framework (likely PyQt/PySide)
- Utility libraries (clipboard, logging)
- `httpx` library (async HTTP)
- `aiofiles` library (async file I/O)

## Data Formats
- Prompt Storage: Prompts are now stored in a JSON format ([`prompts.json`](lifai/modules/prompt_editor/prompts.json)), with each prompt identified by a UUID.

## Technical Constraints
1. Requires local AI backends
2. Python 3.9+ environment setup
3. Module compatibility requirements
4. UI framework dependencies

## Latest API Updates (2025-06-25)

### LM Studio Enhanced Features
- **Native REST API**: Support for `/api/v0/*` endpoints alongside OpenAI-compatible `/v1/*`
- **TTL Support**: Automatic model unloading with configurable time-to-live
- **Structured Outputs**: JSON schema-based response formatting
- **Enhanced Model Management**: Loading, unloading, and detailed model information
- **Performance Metrics**: Comprehensive token tracking and generation speed monitoring
- **Improved Streaming**: Better chunk handling and error recovery

### Ollama Latest Capabilities
- **New Embedding Endpoint**: Migrated from deprecated `/api/embeddings` to `/api/embed`
- **Batch Embeddings**: Support for multiple text inputs in single request
- **Enhanced Model Management**: `/api/ps` for loaded models, `/api/version` for server info
- **Model Pulling**: Programmatic model download with progress tracking
- **Advanced Options**: Enhanced keep_alive, truncation, and model-specific parameters
- **Improved Error Handling**: Better timeout management and error reporting
## Latest API Updates (2025-12-12)

### Ollama Client Enhancements (Context7 Based)
- **Exception Hierarchy**: Custom exceptions (`OllamaError`, `OllamaConnectionError`, `OllamaTimeoutError`, `OllamaModelNotFoundError`) for granular error handling
- **Keep Alive Support**: `keep_alive` parameter on generate/chat methods to control model memory residence (e.g., "5m", "1h", "0" for immediate unload)
- **Model Preloading**: `preload_model(model)` method sends empty prompt to warm up model for faster first response
- **Model Unloading**: `unload_model(model)` method immediately releases model from memory
- **Vision/Multimodal**: `chat_with_vision(model, messages, images)` for image+text conversations with models like LLaVA
- **Image Processing**: `_process_images(images)` converts file paths, bytes, or base64 strings to proper format

### LM Studio Client Enhancements (Context7 Based)
- **Exception Hierarchy**: Custom exceptions for connection, timeout, and model errors
- **Vision Support**: `chat_with_vision(model, messages, images)` with automatic MIME type detection
- **Model Loading**: `load_model(model, gpu_offload, context_length, ttl)` for programmatic model management with GPU acceleration options
- **Model Unloading**: `unload_model(model)` for clean resource release
- **Server Status**: `get_server_status()` returns server information and health status
- **Sync Wrapper**: `generate_response_sync()` for use in non-async contexts

### Cross-Client Improvements
- **Backward Compatibility**: All new features are additive; existing code continues to work
- **Consistent Error Handling**: Unified exception patterns across both clients
- **Resource Management**: Explicit control over model memory lifecycle
- **Multimodal Ready**: Both clients support vision models when available