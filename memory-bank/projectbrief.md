# Project Brief

## Overview
LifAi2 is an AI assistant/agent framework with multiple modules including:
- Prompt Editor - Create, edit, and manage system prompts with custom ordering and temperature settings
- Floating Toolbar - Quick-access AI actions that work with selected text
- AI Chat - Conversational interface for AI interactions
- Knowledge Manager - Document storage and retrieval for context

## Core Goals
1. Provide a modular AI assistant framework
2. Support multiple AI backends (Ollama, LM Studio) with feature parity
3. Enable robust prompt editing and management with custom ordering
4. Offer knowledge management capabilities
5. Provide intuitive UI components for seamless interaction

## Key Features
- **Modular Architecture**: Plugin-style modules that can be enabled/disabled
- **Multi-Backend AI**: Ollama and LM Studio with async HTTP clients
- **Customizable Prompts**: JSON storage with UUIDs, drag-drop ordering, per-prompt temperature
- **Vision Support**: Multimodal image+text conversations (with capable models)
- **Resource Management**: Model preload/unload, keep_alive/TTL settings
- **Async-First Design**: Non-blocking operations using httpx and asyncio
- **Floating Toolbar**: Stays on top, processes selected text with chosen prompt

## Technical Stack
- **Language**: Python 3.9+
- **UI Framework**: PyQt6
- **HTTP Client**: httpx (async)
- **AI Backends**: Ollama (localhost:11434), LM Studio (localhost:1234)
- **Configuration**: JSON-based (prompts.json, app_settings.json)

## File Structure
```
lifai/
├── config/           # App settings and prompts configuration
├── core/             # Core framework (app_hub.py, toggle_switch.py)
├── modules/          # Feature modules
│   ├── ai_agent/     # AI agent functionality
│   ├── ai_chat/      # Chat interface
│   ├── floating_toolbar/  # Quick action toolbar
│   ├── instructor/   # Teaching/instruction features
│   └── prompt_editor/     # Prompt management UI
└── utils/            # Shared utilities
    ├── ollama_client.py    # Ollama API client
    ├── lmstudio_client.py  # LM Studio API client
    ├── clipboard_utils.py  # Clipboard operations
    ├── logger_utils.py     # Logging configuration
    └── openai_client.py    # OpenAI API client
```

## Recent Milestones
- **2025-12-12**: Fixed prompt ordering bug, added vision support & model management to AI clients
- **2025-08-25**: Major AI client refactoring with Context7 optimizations
- **2025-06-27**: Added per-prompt temperature settings
- **2025-06-26**: Code refactoring following SOLID principles
- **2025-05-15**: Major async modernization and prompt editor overhaul

## Memory Bank Files
| File | Purpose |
|------|---------|
| `projectbrief.md` | This file - project overview |
| `activeContext.md` | Current work focus and recent changes |
| `progress.md` | Chronological progress log |
| `techContext.md` | Technology stack and API details |
| `systemPatterns.md` | Design patterns and architecture |
| `ai_clients_api_reference.md` | API documentation for AI clients |
