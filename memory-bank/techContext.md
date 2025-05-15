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
