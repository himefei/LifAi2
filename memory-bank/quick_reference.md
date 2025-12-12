# Quick Reference & Troubleshooting

> Last Updated: 2025-12-12

## Common Tasks

### Running the Application

```bash
# Console-free (recommended)
python run.pyw
# or double-click run.pyw in File Explorer

# With console (for debugging)
python run.py
```

### AI Backend Setup

**Ollama:**
```bash
# Install Ollama from https://ollama.ai
# Pull a model
ollama pull llama3.2
# Start server (usually auto-starts)
ollama serve
```

**LM Studio:**
1. Download from https://lmstudio.ai
2. Load a model in the app
3. Start the local server (default: localhost:1234)

### Testing AI Connections

```python
# Quick test script
import asyncio
from lifai.utils.ollama_client import OllamaClient
from lifai.utils.lmstudio_client import LMStudioClient

async def test():
    ollama = OllamaClient()
    lmstudio = LMStudioClient()
    
    print(f"Ollama: {await ollama.test_connection()}")
    print(f"LM Studio: {await lmstudio.test_connection()}")

asyncio.run(test())
```

---

## Troubleshooting

### Prompt Ordering Issues

**Symptom:** Prompts appear in wrong order after restart

**Solution:** Fixed in 2025-12-12 update. If issue persists:
1. Check `lifai/modules/prompt_editor/prompts.json` has valid `order` array
2. Ensure all IDs in `order` array exist in `prompts` object
3. Delete corrupted `prompts.json` and restart (will recreate defaults)

### Cannot Connect to Ollama

**Error:** `OllamaConnectionError: Unable to connect to Ollama server`

**Solutions:**
1. Verify Ollama is running: `ollama serve` or check system tray
2. Check URL: default is `http://localhost:11434`
3. Test manually: `curl http://localhost:11434/api/tags`

### Cannot Connect to LM Studio

**Error:** `LMStudioConnectionError`

**Solutions:**
1. Ensure LM Studio is running with server started
2. Check "Developer" tab → "Local Server" is enabled
3. Default port is 1234: `http://localhost:1234`

### Model Not Found

**Error:** `OllamaModelNotFoundError` or model missing from list

**Solutions:**
```bash
# Ollama
ollama pull <model-name>

# LM Studio
# Download model through the app's "Discover" tab
```

### Slow First Response

**Cause:** Model needs to load into memory

**Solutions:**
```python
# Preload model at startup
await ollama_client.preload_model("llama3.2")
await lmstudio_client.load_model("my-model", gpu_offload="max")
```

### Out of Memory (GPU/RAM)

**Solutions:**
1. Unload unused models:
   ```python
   await client.unload_model("large-model")
   ```
2. Use smaller quantization (Q4_K_M instead of Q8)
3. Reduce context length
4. Set shorter `keep_alive` / `ttl`

### UI Freezes During AI Call

**Cause:** Blocking call in UI thread

**Solution:** All AI calls should be async. Use `QThread` or `asyncio.create_task()`:
```python
# Wrong (blocks UI)
response = client.generate_response_sync(prompt, model)

# Right (non-blocking)
response = await client.generate_response(prompt, model)
```

---

## Configuration Files

### `lifai/config/app_settings.json`
User preferences (ignored by git):
- Selected AI backend
- Default model
- UI preferences

### `lifai/modules/prompt_editor/prompts.json`
Custom prompts (ignored by git):
- Prompt definitions with UUIDs
- Order array for display sequence
- Per-prompt temperature settings

---

## Key Code Locations

| Feature | File |
|---------|------|
| Main entry point | `run.py` / `run.pyw` |
| App coordinator | `lifai/core/app_hub.py` |
| Prompt editor UI | `lifai/modules/prompt_editor/editor.py` |
| Floating toolbar | `lifai/modules/floating_toolbar/toolbar.py` |
| Ollama API client | `lifai/utils/ollama_client.py` |
| LM Studio API client | `lifai/utils/lmstudio_client.py` |

---

## Useful Commands

```bash
# Check Python version (need 3.9+)
python --version

# Install dependencies
pip install -r requirements.txt

# Test syntax of modified files
python -m py_compile lifai/utils/ollama_client.py

# Run with verbose logging
python run.py --debug
```
