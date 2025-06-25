# Technology Context

## Core Technologies
- Python (primary implementation language, now leveraging 3.9+ features for `asyncio` and type hinting)
- Ollama (AI backend)
- LM Studio (alternative AI backend)
- Likely PyQt/PySide for UI (based on toolbar.py and toggle_switch.py)
- `httpx` (for asynchronous HTTP requests to AI backends and other services)
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
