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
