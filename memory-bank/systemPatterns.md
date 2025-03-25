# System Patterns

## Architecture
- Modular Python application
- Core framework with plugin-style modules
- Clear separation between:
  - Core functionality (app_hub.py, toggle_switch.py)
  - Modules (prompt_editor, knowledge_manager, etc.)
  - Utilities (ollama_client, lmstudio_client)

## Key Technical Decisions
1. Python as implementation language
2. Modular design for extensibility
3. Separate configuration (prompts.py)
4. Dedicated utility modules for common functions
5. Clear directory structure

## Design Patterns
- Plugin architecture for modules
- Facade pattern in client implementations (ollama_client, lmstudio_client)
- Observer pattern likely used in UI components
- Strategy pattern for different AI backends

## Component Relationships
- Core framework coordinates modules
- Modules interact through defined interfaces
- Utilities provide shared functionality
- Configuration centralizes prompt management
