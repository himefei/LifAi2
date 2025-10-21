# AI Chat Module

A modern ChatGPT-style interface for LifAi2 with integrated prompt selection and image support.

## Features

### 🎯 Core Functionality
- **Modern Chat Interface**: Clean, responsive ChatGPT-like design
- **Prompt Integration**: Select and use prompts from the Prompt Editor
- **Multi-Session Support**: Create, manage, and switch between chat sessions
- **Image Support**: Attach images and paste from clipboard (for vision-enabled models)
- **Copy/Paste**: Rich clipboard integration for text and images

### 🔧 Technical Features
- **AI Client Integration**: Works with Ollama, LM Studio, and OpenAI
- **Async Processing**: Non-blocking AI requests with threaded workers
- **Auto-sizing Input**: Text input area adjusts height as you type
- **Chat History**: Session management with export functionality
- **Error Handling**: Comprehensive error handling and user feedback

## Usage

### Getting Started
1. **Enable the Module**: In the LifAi2 Control Hub, toggle "AI Chat" to enable
2. **Select a Model**: Ensure a model is selected in the main hub
3. **Choose a Prompt** (optional): Select a system prompt from the dropdown
4. **Start Chatting**: Type your message and press Ctrl+Enter or click Send

### Interface Layout

#### Left Sidebar
- **New Chat**: Create new chat sessions
- **System Prompt**: Select prompts from Prompt Editor
- **Model Settings**: Temperature and token controls
- **Chat History**: Manage previous conversations

#### Main Chat Area
- **Message Display**: Scrollable conversation view
- **Input Area**: Resizable text input with file attachments
- **Status Bar**: Shows current operation status

### Key Shortcuts
- **Ctrl+Enter**: Send message
- **📎 Button**: Attach image files
- **📋 Button**: Paste from clipboard

## Technical Architecture

### Class Structure

```python
ChatInterface(QMainWindow)
├── PromptSelectorWidget      # Prompt selection and preview
├── MessageWidget             # Individual message display
├── ChatWorker(QThread)       # Async AI processing
└── ChatSession/ChatMessage   # Data models
```

### Integration Points

#### Prompt Editor Integration
- Loads prompts from `../prompt_editor/prompts.json`
- Automatic refresh when prompts are updated
- System prompts are sent as first message to AI

#### AI Client Integration
- **Ollama**: Uses async `chat_completion()` method
- **LM Studio**: Uses sync `chat_completion_sync()` method
- **OpenAI**: Compatible with OpenAI API format

#### Hub Integration
- Registered in `lifai/core/app_hub.py`
- Receives client updates when backend changes
- Prompt update callbacks from Prompt Editor

## Configuration

### Model Settings
- **Temperature**: 0.0 (deterministic) to 2.0 (very creative)
- **Max Tokens**: 1 to 32,000 tokens
- **Model**: Automatically uses selected model from main hub

### Session Management
- **Auto-titling**: Uses first message words as session title
- **Export Options**: Plain text or JSON format
- **Delete Protection**: Confirms before deleting sessions

## Image Support

### Supported Formats
- PNG, JPG, JPEG, BMP, GIF
- Base64 encoding for storage and transmission
- Automatic scaling for display

### Usage
1. **File Attachment**: Click 📎 to select image files
2. **Clipboard Paste**: Click 📋 to paste copied images
3. **Visual Indicators**: Images show as `[Image: filename]` in input

### Vision Models
- Images are included in AI requests for vision-capable models
- Automatic detection of vision support in AI clients
- Graceful fallback for text-only models

## Error Handling

### Common Issues
- **No Model Selected**: Prompts user to select model in main hub
- **Connection Errors**: Shows clear error messages for AI client issues
- **Timeout Errors**: Handles long-running AI requests gracefully

### Status Indicators
- **Ready**: System ready for input
- **Generating response...**: AI processing in progress
- **Error: [message]**: Specific error information

## Development

### Adding New Features

#### Custom Message Types
```python
class CustomMessage(ChatMessage):
    def __init__(self, role, content, custom_data=None):
        super().__init__(role, content)
        self.custom_data = custom_data
```

#### New AI Clients
Implement these methods:
- `chat_completion()` or `chat_completion_sync()`
- `fetch_models_sync()`
- Optional: `supports_vision` attribute

#### UI Customization
- Modify styles in `apply_styles()` method
- Add new widgets to sidebar or main area
- Extend `MessageWidget` for custom message display

### Dependencies
- PyQt6: UI framework
- PIL (Pillow): Image processing
- Base64: Image encoding
- JSON: Data serialization
- Threading: Async processing

## Troubleshooting

### Chat Not Responding
1. Check if AI backend (Ollama/LM Studio) is running
2. Verify model is selected in main hub
3. Check status bar for error messages
4. Review logs in main hub for detailed errors

### Images Not Working
1. Ensure model supports vision (e.g., llava, gpt-4-vision)
2. Check image file format is supported
3. Verify clipboard contains image data

### Performance Issues
1. Reduce temperature for faster responses
2. Lower max tokens setting
3. Use smaller/faster models
4. Check system resources

## Future Enhancements

### Planned Features
- [ ] Conversation templates
- [ ] Message search and filtering
- [ ] Export to multiple formats
- [ ] Advanced image processing
- [ ] Plugin system for extensions
- [ ] Collaborative chat sessions
- [ ] Voice input/output support

### API Extensions
- [ ] Streaming responses with real-time display
- [ ] Function calling support
- [ ] Multi-modal input (audio, video)
- [ ] RAG integration with knowledge base