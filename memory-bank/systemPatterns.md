# System Patterns

## Architecture
- Modular Python application
- Core framework with plugin-style modules
- Clear separation between:
  - Core functionality (app_hub.py, toggle_switch.py)
  - Modules (prompt_editor, knowledge_manager, etc.)
  - Utilities (ollama_client, lmstudio_client)
- Adoption of asynchronous programming (`async/await`) for I/O-bound operations (network calls, file access) leveraging Python 3.9+ features.
- JSON-based prompt storage mechanism using UUIDs for identification in the prompt editor.

## Key Technical Decisions
1. Python as implementation language (now leveraging 3.9+ features)
2. Modular design for extensibility
3. Separate configuration (prompts.py)
4. Dedicated utility modules for common functions
5. Clear directory structure
6. Asynchronous programming for performance and scalability
7. JSON-based prompt storage with UUIDs

## Design Patterns
- Plugin architecture for modules
- Facade pattern in client implementations (ollama_client, lmstudio_client, now using `httpx`)
- Observer pattern in UI components
- Strategy pattern for different AI backends
- Asynchronous patterns for I/O-bound operations

## Component Relationships
- Core framework coordinates modules
- Modules interact through defined interfaces (now supporting async operations)
- Utilities provide shared functionality
- Configuration centralizes prompt management

## Example Async Flow

```mermaid
sequenceDiagram
    participant UserAction
    participant Module
    participant AI_Client
    participant ExternalAPI

    UserAction->>Module: Perform AI Task
    Module->>AI_Client: make_async_request(prompt)
    AI_Client->>ExternalAPI: ASYNC HTTP POST (httpx)
    ExternalAPI-->>AI_Client: ASYNC Response
    AI_Client-->>Module: Processed Result
    Module-->>UserAction: Display Result
end

## Enhanced AI Client Architecture (2025-06-25)

### LM Studio Client Enhancements
- **Dual API Support**: Configurable choice between native REST API (`/api/v0/`) and OpenAI-compatible (`/v1/`) endpoints
- **TTL Pattern**: Automatic resource management with time-to-live for model unloading
- **Structured Response Pattern**: JSON schema validation for consistent output formatting
- **Performance Monitoring Pattern**: Built-in metrics collection for tokens/sec and response times
- **Enhanced Error Recovery**: Comprehensive HTTP status code handling with contextual error messages

### Ollama Client Modernization
- **API Evolution Pattern**: Seamless migration from deprecated to current endpoints (`/api/embeddings` → `/api/embed`)
- **Batch Processing Pattern**: Efficient handling of multiple inputs in single requests
- **Progressive Enhancement**: Graceful fallback for older Ollama versions
- **Resource Tracking Pattern**: Real-time monitoring of loaded models and memory usage
- **Download Management**: Asynchronous model pulling with progress tracking

### Cross-Client Consistency
- **Unified Response Structure**: Consistent message object format across all AI providers
- **Error Handling Standardization**: Uniform exception types and error reporting
- **Performance Metrics**: Standardized token counting and speed measurements
- **Async-First Design**: Non-blocking operations throughout the client layer

## Patterns Added 2025-12-12

### Exception Hierarchy Pattern
Both AI clients now implement a proper exception hierarchy:
```
BaseClientError (abstract)
├── ConnectionError - Server unreachable
├── TimeoutError - Request timed out
└── ModelNotFoundError - Specified model unavailable
```
This enables calling code to catch specific exceptions for targeted error handling.

### Resource Lifecycle Management Pattern
New methods for explicit model memory control:
- `preload_model()` / `load_model()` - Warm start models
- `unload_model()` - Free resources immediately
- `keep_alive` parameter - Control memory residence time

### Multimodal Adapter Pattern
Image processing abstraction that accepts multiple input formats:
- File paths (automatically read and converted)
- Raw bytes (base64 encoded)
- Pre-encoded base64 strings (passed through)
- MIME type auto-detection for proper data URLs

### Callback Ordering Pattern (Prompt Editor)
Fixed pattern for maintaining order consistency:
```python
# Correct: Use saved order array
ordered_names = [prompts[id]["name"] for id in saved_order if id in prompts]

# Wrong: Use dictionary iteration order
names = [p["name"] for p in prompts.values()]  # Order not guaranteed
```

### Synchronous Wrapper Pattern
For async methods in non-async contexts:
```python
def sync_method(self, *args):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(self.async_method(*args))
    finally:
        loop.close()
```