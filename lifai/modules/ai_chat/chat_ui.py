"""
AI Chat Interface - Modern ChatGPT-style UI with prompt integration
"""

import os
import json
import asyncio
import base64
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import threading
import io
from PIL import Image

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QComboBox, QLabel, QFrame, QScrollArea, QMessageBox,
    QSplitter, QFileDialog, QApplication, QMenu, QToolButton, QCheckBox,
    QSpinBox, QDoubleSpinBox, QGroupBox, QGridLayout, QListWidget, QListWidgetItem,
    QSizeGrip, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QMimeData, QUrl
from PyQt6.QtGui import (
    QFont, QPixmap, QIcon, QTextCursor, QTextImageFormat, QTextDocument,
    QDragEnterEvent, QDropEvent, QPalette, QColor, QAction, QCursor
)

from lifai.utils.logger_utils import get_module_logger
from lifai.utils.clipboard_utils import ClipboardManager
from lifai.core.modern_ui import ModernTheme, ToggleSwitch

logger = get_module_logger(__name__)

class ResizableTextEdit(QFrame):
    """Custom resizable text edit with drag handle"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)  # Initial height
        self.setup_ui()
        self.is_resizing = False
        self.resize_start_y = 0
        self.resize_start_height = 0
        
    def setup_ui(self):
        """Setup the resizable text edit UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Text edit
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Type your message here... (Ctrl+Enter to send)")
        self.text_edit.setAcceptDrops(True)
        layout.addWidget(self.text_edit)
        
        # Resize handle
        self.resize_handle = QFrame()
        self.resize_handle.setFixedHeight(8)
        self.resize_handle.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        self.resize_handle.setStyleSheet("""
            QFrame {
                background-color: #E8E8E8;
                border: none;
                border-radius: 4px;
            }
            QFrame:hover {
                background-color: #009688;
            }
        """)
        self.resize_handle.mousePressEvent = self.start_resize
        self.resize_handle.mouseMoveEvent = self.do_resize
        self.resize_handle.mouseReleaseEvent = self.end_resize
        layout.addWidget(self.resize_handle)
        
    def start_resize(self, event):
        """Start resizing"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_resizing = True
            self.resize_start_y = event.globalPosition().y()
            self.resize_start_height = self.height()
            
    def do_resize(self, event):
        """Handle resize drag"""
        if self.is_resizing:
            delta_y = event.globalPosition().y() - self.resize_start_y
            new_height = max(60, min(400, self.resize_start_height + int(delta_y)))
            self.setFixedHeight(new_height)
            
    def end_resize(self, event):
        """End resizing"""
        self.is_resizing = False
        
    def toPlainText(self):
        """Get plain text from text edit"""
        return self.text_edit.toPlainText()
        
    def setPlainText(self, text):
        """Set plain text in text edit"""
        self.text_edit.setPlainText(text)
        
    def clear(self):
        """Clear the text edit"""
        self.text_edit.clear()
        
    def installEventFilter(self, filter_obj):
        """Install event filter on text edit"""
        self.text_edit.installEventFilter(filter_obj)
        
    def setAcceptDrops(self, accept):
        """Set accept drops on text edit"""
        self.text_edit.setAcceptDrops(accept)

class ChatMessage:
    """Represents a single chat message"""
    
    def __init__(self, role: str, content: str, timestamp: datetime = None, images: List[str] = None):
        self.role = role  # 'user', 'assistant', or 'system'
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.images = images or []  # List of base64 encoded images
        self.message_id = f"{role}_{int(self.timestamp.timestamp())}"

@dataclass
class ChatSession:
    """Represents a chat session"""
    session_id: str
    title: str
    messages: List[ChatMessage]
    selected_prompt: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class ChatWorker(QThread):
    """Worker thread for AI chat completion with streaming support"""
    
    response_received = pyqtSignal(str, str)  # response, session_id
    chunk_received = pyqtSignal(str, str)  # chunk, session_id (for streaming)
    stream_finished = pyqtSignal(str, str)  # full_response, session_id
    error_occurred = pyqtSignal(str)
    thinking_update = pyqtSignal(str)  # For reasoning models
    
    def __init__(self, ai_client, model: str, messages: List[Dict], session_id: str, stream: bool = True):
        super().__init__()
        self.ai_client = ai_client
        self.model = model
        self.messages = messages
        self.session_id = session_id
        self.stream = stream
        self._is_cancelled = False
    
    def cancel(self):
        """Cancel the request"""
        self._is_cancelled = True
    
    def run(self):
        """Execute the chat completion"""
        try:
            if self._is_cancelled:
                return
            
            if self.stream:
                self._run_streaming()
            else:
                self._run_non_streaming()
                
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            self.error_occurred.emit(str(e))
    
    def _run_streaming(self):
        """Run streaming chat completion"""
        import httpx
        import json
        
        try:
            # Determine the endpoint based on client type
            if hasattr(self.ai_client, 'native_base'):
                # LM Studio
                if self.ai_client.use_native_api:
                    endpoint = f"{self.ai_client.native_base}/chat/completions"
                else:
                    endpoint = f"{self.ai_client.openai_base}/chat/completions"
            elif hasattr(self.ai_client, 'base_url'):
                # Ollama
                endpoint = f"{self.ai_client.base_url}/api/chat"
            else:
                # Fallback to non-streaming
                self._run_non_streaming()
                return
            
            # Build request data
            data = {
                "messages": self.messages,
                "model": self.model,
                "stream": True
            }
            
            full_response = ""
            
            # Use synchronous httpx for streaming in thread
            with httpx.Client(timeout=180) as client:
                with client.stream('POST', endpoint, json=data, headers={"Content-Type": "application/json"}) as response:
                    response.raise_for_status()
                    
                    for line in response.iter_lines():
                        if self._is_cancelled:
                            return
                        
                        if not line:
                            continue
                        
                        # Handle SSE format (data: {...})
                        if line.startswith('data: '):
                            json_str = line[6:]
                            if json_str.strip() == "[DONE]":
                                break
                        else:
                            json_str = line
                        
                        try:
                            chunk = json.loads(json_str)
                            content = ""
                            
                            # Handle OpenAI/LM Studio format
                            if 'choices' in chunk and chunk['choices']:
                                choice = chunk['choices'][0]
                                if 'delta' in choice and choice['delta']:
                                    content = choice['delta'].get('content', '')
                                elif 'message' in choice and choice['message']:
                                    content = choice['message'].get('content', '')
                            # Handle Ollama format
                            elif 'message' in chunk and chunk['message']:
                                content = chunk['message'].get('content', '')
                            elif 'response' in chunk:
                                content = chunk.get('response', '')
                            
                            if content:
                                full_response += content
                                self.chunk_received.emit(content, self.session_id)
                                
                        except json.JSONDecodeError:
                            continue
            
            if not self._is_cancelled:
                self.stream_finished.emit(full_response, self.session_id)
                
        except Exception as e:
            logger.error(f"Error in streaming chat completion: {e}")
            # Fall back to non-streaming on error
            self._run_non_streaming()
    
    def _run_non_streaming(self):
        """Run non-streaming chat completion"""
        try:
            # Check if we have an LM Studio client
            if hasattr(self.ai_client, 'chat_completion_sync'):
                # Use sync method for LM Studio
                response = self.ai_client.chat_completion_sync(
                    model=self.model,
                    messages=self.messages,
                    stream=False
                )
            else:
                # Use asyncio to run the async chat completion for Ollama
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    response = loop.run_until_complete(
                        self.ai_client.chat_completion(
                            model=self.model,
                            messages=self.messages,
                            stream=False
                        )
                    )
                finally:
                    loop.close()
            
            if self._is_cancelled:
                return
            
            # Extract response content
            if isinstance(response, dict):
                if 'choices' in response and response['choices']:
                    content = response['choices'][0]['message']['content']
                elif 'message' in response:
                    content = response['message']['content']
                else:
                    content = str(response)
            else:
                content = str(response)
            
            self.response_received.emit(content, self.session_id)
            
        except Exception as e:
            logger.error(f"Error in non-streaming chat completion: {e}")
            self.error_occurred.emit(str(e))

class TypingDot(QWidget):
    """A single animated dot for typing indicator"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.3
        self.setFixedSize(8, 8)
    
    @property
    def opacity(self):
        return self._opacity
    
    @opacity.setter
    def opacity(self, value):
        self._opacity = value
        self.update()
    
    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)
        painter.setBrush(QColor(158, 158, 158))  # Gray color
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 8, 8)


class TypingAnimationWidget(QFrame):
    """Simple 3-dot typing indicator - ChatGPT style"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dot_index = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the typing animation UI"""
        self.setStyleSheet("background: transparent; border: none;")
        
        # Main layout - left aligned like assistant messages
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(12)
        
        # Bubble container
        bubble = QFrame()
        bubble.setFixedSize(60, 40)
        bubble.setStyleSheet("""
            QFrame {
                background-color: #F0F0F0;
                border-radius: 18px;
                border-bottom-left-radius: 4px;
            }
        """)
        
        # Dots layout inside bubble
        dots_layout = QHBoxLayout(bubble)
        dots_layout.setContentsMargins(16, 0, 16, 0)
        dots_layout.setSpacing(4)
        dots_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create 3 dots
        self.dots = []
        for i in range(3):
            dot = TypingDot()
            self.dots.append(dot)
            dots_layout.addWidget(dot)
        
        main_layout.addWidget(bubble)
        main_layout.addStretch(1)
    
    def start_animation(self):
        """Start the typing animation"""
        self.dot_index = 0
        self.timer.start(300)  # Update every 300ms
    
    def stop_animation(self):
        """Stop the typing animation"""
        self.timer.stop()
        # Reset all dots
        for dot in self.dots:
            dot.opacity = 0.3
        self.hide()
    
    def update_animation(self):
        """Update the typing animation - bounce effect"""
        # Reset all dots to dim
        for dot in self.dots:
            dot.opacity = 0.3
        
        # Highlight current dot
        if self.dots:
            self.dots[self.dot_index].opacity = 1.0
            self.dot_index = (self.dot_index + 1) % len(self.dots)

class MessageWidget(QFrame):
    """Widget for displaying a single chat message - ChatGPT style"""
    
    def __init__(self, message: ChatMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the message UI - ChatGPT style layout"""
        self.setStyleSheet("background: transparent; border: none;")
        
        # Main horizontal layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(12)
        
        is_user = self.message.role == "user"
        
        if is_user:
            # User messages: push to right
            main_layout.addStretch(1)
        
        # Message bubble
        bubble = QFrame()
        bubble.setMaximumWidth(600)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 12, 16, 12)
        bubble_layout.setSpacing(8)
        
        # Message content - using QLabel for cleaner rendering
        self.content_label = QLabel()
        self.content_label.setText(self.message.content)
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | 
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.content_label.setFont(QFont("Segoe UI", 10))
        
        if is_user:
            # User bubble - teal background, right aligned
            bubble.setStyleSheet("""
                QFrame {
                    background-color: #009688;
                    border-radius: 18px;
                    border-bottom-right-radius: 4px;
                }
            """)
            self.content_label.setStyleSheet("""
                QLabel {
                    color: #FFFFFF;
                    background: transparent;
                    padding: 0;
                }
            """)
        else:
            # Assistant bubble - light gray background, left aligned
            bubble.setStyleSheet("""
                QFrame {
                    background-color: #F0F0F0;
                    border-radius: 18px;
                    border-bottom-left-radius: 4px;
                }
            """)
            self.content_label.setStyleSheet("""
                QLabel {
                    color: #1A1A1A;
                    background: transparent;
                    padding: 0;
                }
            """)
        
        bubble_layout.addWidget(self.content_label)
        
        # Images if present
        if self.message.images:
            self.add_images(bubble_layout)
        
        # Timestamp below the bubble
        timestamp_label = QLabel(self.message.timestamp.strftime("%H:%M"))
        timestamp_label.setStyleSheet("color: #9E9E9E; font-size: 10px; background: transparent;")
        
        if is_user:
            timestamp_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            timestamp_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Wrapper to hold bubble and timestamp
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(4)
        wrapper_layout.addWidget(bubble)
        wrapper_layout.addWidget(timestamp_label)
        
        main_layout.addWidget(wrapper)
        
        if not is_user:
            # Assistant messages: push to left
            main_layout.addStretch(1)
    
    def add_images(self, layout):
        """Add image displays to the message"""
        for img_data in self.message.images:
            try:
                # Decode base64 image
                img_bytes = base64.b64decode(img_data)
                pixmap = QPixmap()
                pixmap.loadFromData(img_bytes)
                
                # Scale image
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        200, 200, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    
                    image_label = QLabel()
                    image_label.setPixmap(scaled_pixmap)
                    image_label.setStyleSheet("""
                        QLabel {
                            border-radius: 8px;
                            background: transparent;
                        }
                    """)
                    layout.addWidget(image_label)
                    
            except Exception as e:
                logger.error(f"Error displaying image: {e}")

class PromptSelectorWidget(QFrame):
    """Widget for selecting prompts from the prompt editor"""
    
    prompt_selected = pyqtSignal(str, dict)  # prompt_name, prompt_data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prompts_data = {"prompts": [], "order": []}
        self.setup_ui()
        self.load_prompts()
    
    def setup_ui(self):
        """Setup the prompt selector UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header_label = QLabel("System Prompt")
        header_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(header_label)
        
        # Prompt selection
        self.prompt_combo = QComboBox()
        self.prompt_combo.currentTextChanged.connect(self.on_prompt_changed)
        layout.addWidget(self.prompt_combo)
        
        # Prompt preview
        self.prompt_preview = QTextEdit()
        self.prompt_preview.setReadOnly(True)
        self.prompt_preview.setMaximumHeight(100)
        self.prompt_preview.setPlaceholderText("Selected prompt will appear here...")
        layout.addWidget(self.prompt_preview)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Prompts")
        refresh_btn.clicked.connect(self.load_prompts)
        layout.addWidget(refresh_btn)
        
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #E8E8E8;
                border-radius: 12px;
                background-color: #FFFFFF;
            }
            QComboBox {
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 8px 12px;
                background-color: #FFFFFF;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #009688;
            }
            QComboBox:focus {
                border-color: #009688;
            }
            QTextEdit {
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                background-color: #FFFFFF;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
    
    def load_prompts(self):
        """Load prompts from the prompt editor JSON file"""
        try:
            prompts_file = os.path.join(os.path.dirname(__file__), "..", "prompt_editor", "prompts.json")
            
            if os.path.exists(prompts_file):
                with open(prompts_file, "r", encoding="utf-8") as f:
                    self.prompts_data = json.load(f)
            else:
                self.prompts_data = {"prompts": [], "order": []}
            
            self.refresh_prompt_list()
            logger.info(f"Loaded {len(self.prompts_data['prompts'])} prompts")
            
        except Exception as e:
            logger.error(f"Error loading prompts: {e}")
            self.prompts_data = {"prompts": [], "order": []}
    
    def refresh_prompt_list(self):
        """Refresh the prompt combo box"""
        self.prompt_combo.clear()
        self.prompt_combo.addItem("None", None)
        
        # Add prompts in order
        for prompt_id in self.prompts_data.get("order", []):
            prompt = self.get_prompt_by_id(prompt_id)
            if prompt:
                display_name = prompt.get("name", "Unnamed")
                self.prompt_combo.addItem(display_name, prompt)
    
    def get_prompt_by_id(self, prompt_id: str) -> Optional[Dict]:
        """Get prompt by ID"""
        for prompt in self.prompts_data.get("prompts", []):
            if prompt.get("id") == prompt_id:
                return prompt
        return None
    
    def on_prompt_changed(self, prompt_name: str):
        """Handle prompt selection change"""
        current_data = self.prompt_combo.currentData()
        
        if current_data:
            template = current_data.get("template", "")
            self.prompt_preview.setPlainText(template)
            self.prompt_selected.emit(prompt_name, current_data)
        else:
            self.prompt_preview.clear()
            self.prompt_selected.emit("", {})
    
    def get_selected_prompt(self) -> Optional[Dict]:
        """Get the currently selected prompt"""
        return self.prompt_combo.currentData()

class ChatInterface(QMainWindow):
    """Main ChatGPT-style interface"""
    
    def __init__(self, settings: Dict[str, Any], ai_client=None):
        super().__init__()
        self.settings = settings
        self.ai_client = ai_client
        self.current_session = None
        self.chat_sessions = {}
        self.current_worker = None
        self.clipboard_manager = ClipboardManager()
        
        self.setup_ui()
        self.create_new_session()
        
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle("LifAi2 - AI Chat")
        self.setMinimumSize(900, 700)
        self.resize(1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left sidebar
        self.create_sidebar(splitter)
        
        # Main chat area
        self.create_chat_area(splitter)
        
        # Set splitter proportions
        splitter.setSizes([300, 900])
        
        # Apply modern styling
        self.apply_styles()
    
    def create_sidebar(self, parent):
        """Create the left sidebar"""
        sidebar = QFrame()
        sidebar.setMaximumWidth(320)
        sidebar.setMinimumWidth(280)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {ModernTheme.BG_CARD};
                border-right: 1px solid {ModernTheme.BORDER};
            }}
        """)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header_label = QLabel("💬 AI Chat")
        header_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header_label.setStyleSheet(f"color: {ModernTheme.PRIMARY};")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)
        
        # New chat button
        new_chat_btn = QPushButton("+ New Chat")
        new_chat_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ModernTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {ModernTheme.PRIMARY_DARK};
            }}
        """)
        new_chat_btn.clicked.connect(self.create_new_session)
        layout.addWidget(new_chat_btn)
        
        # Prompt selector
        self.prompt_selector = PromptSelectorWidget()
        self.prompt_selector.prompt_selected.connect(self.on_prompt_selected)
        layout.addWidget(self.prompt_selector)
        
        # Model settings
        self.create_model_settings(layout)
        
        # Chat history section
        self.create_chat_history(layout)
        
        layout.addStretch()
        
        parent.addWidget(sidebar)
    
    def create_model_settings(self, parent_layout):
        """Create model settings section"""
        settings_group = QGroupBox("Model Settings")
        layout = QGridLayout(settings_group)
        
        # Model selection (will be populated from settings)
        layout.addWidget(QLabel("Model:"), 0, 0)
        self.model_label = QLabel(self.settings.get('model', 'Not selected'))
        self.model_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.model_label, 0, 1)
        
        parent_layout.addWidget(settings_group)
    
    def create_chat_history(self, parent_layout):
        """Create chat history section"""
        history_group = QGroupBox("Chat History")
        layout = QVBoxLayout(history_group)
        
        # Sessions list
        self.sessions_list = QListWidget()
        self.sessions_list.setMaximumHeight(150)
        self.sessions_list.itemClicked.connect(self.load_session)
        layout.addWidget(self.sessions_list)
        
        # History controls
        history_controls = QHBoxLayout()
        
        delete_session_btn = QPushButton("Delete")
        delete_session_btn.clicked.connect(self.delete_session)
        history_controls.addWidget(delete_session_btn)
        
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.export_session)
        history_controls.addWidget(export_btn)
        
        layout.addLayout(history_controls)
        
        parent_layout.addWidget(history_group)
    
    def create_chat_area(self, parent):
        """Create the main chat area with resizable sections"""
        chat_widget = QWidget()
        main_layout = QVBoxLayout(chat_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create vertical splitter for chat display and input area
        chat_splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(chat_splitter)
        
        # Chat display area
        chat_display_widget = QWidget()
        chat_display_layout = QVBoxLayout(chat_display_widget)
        chat_display_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(10, 10, 10, 10)
        self.chat_layout.addStretch()
        
        # Add typing animation widget (initially hidden)
        self.typing_animation = TypingAnimationWidget()
        self.typing_animation.hide()
        self.chat_layout.insertWidget(-1, self.typing_animation)  # Insert before stretch
        
        scroll_area.setWidget(self.chat_container)
        chat_display_layout.addWidget(scroll_area)
        
        self.scroll_area = scroll_area
        
        # Input area widget
        input_widget = QWidget()
        self.create_input_area(input_widget)
        
        # Add widgets to splitter
        chat_splitter.addWidget(chat_display_widget)
        chat_splitter.addWidget(input_widget)
        
        # Set initial splitter proportions (chat area larger)
        chat_splitter.setSizes([500, 200])
        chat_splitter.setCollapsible(0, False)  # Chat area cannot be collapsed
        chat_splitter.setCollapsible(1, False)  # Input area cannot be collapsed
        
        parent.addWidget(chat_widget)
    
    def create_input_area(self, parent_widget):
        """Create the message input area"""
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(12, 8, 12, 12)
        
        # Input controls
        controls_layout = QHBoxLayout()
        
        # Tool button style
        tool_btn_style = f"""
            QToolButton {{
                background-color: {ModernTheme.BG_CARD};
                border: 1px solid {ModernTheme.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 16px;
            }}
            QToolButton:hover {{
                background-color: {ModernTheme.BG_HOVER};
                border-color: {ModernTheme.PRIMARY};
            }}
        """
        
        # Attach button
        attach_btn = QToolButton()
        attach_btn.setText("📎")
        attach_btn.setToolTip("Attach image")
        attach_btn.setStyleSheet(tool_btn_style)
        attach_btn.clicked.connect(self.attach_image)
        controls_layout.addWidget(attach_btn)
        
        # Paste button
        paste_btn = QToolButton()
        paste_btn.setText("📋")
        paste_btn.setToolTip("Paste from clipboard")
        paste_btn.setStyleSheet(tool_btn_style)
        paste_btn.clicked.connect(self.paste_from_clipboard)
        controls_layout.addWidget(paste_btn)
        
        controls_layout.addStretch()
        
        # Enter to send toggle
        enter_label = QLabel("Enter to send")
        enter_label.setStyleSheet(f"""
            QLabel {{
                color: {ModernTheme.TEXT_SECONDARY};
                font-size: 12px;
                background: transparent;
            }}
        """)
        controls_layout.addWidget(enter_label)
        
        self.enter_to_send_toggle = ToggleSwitch()
        self.enter_to_send_toggle.setChecked(False)  # Default: Ctrl+Enter to send
        self.enter_to_send_toggle.setToolTip("Toggle: Enter to send or Ctrl+Enter to send")
        self.enter_to_send_toggle.toggled.connect(self.update_placeholder_text)
        controls_layout.addWidget(self.enter_to_send_toggle)
        
        # Add some spacing before Clear button
        controls_layout.addSpacing(12)
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ModernTheme.BG_CARD};
                color: {ModernTheme.TEXT_PRIMARY};
                border: 1px solid {ModernTheme.BORDER};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {ModernTheme.BG_HOVER};
                border-color: {ModernTheme.PRIMARY};
            }}
        """)
        clear_btn.clicked.connect(self.clear_chat)
        controls_layout.addWidget(clear_btn)
        
        layout.addLayout(controls_layout)
        
        # Resizable text input with send button
        input_layout = QHBoxLayout()
        
        # Custom resizable text edit
        self.message_input = ResizableTextEdit()
        self.message_input.installEventFilter(self)
        self.message_input.text_edit.installEventFilter(self)  # Also filter the inner text edit
        self.message_input.text_edit.textChanged.connect(self.on_input_changed)  # Update token count as user types
        input_layout.addWidget(self.message_input)
        
        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ModernTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {ModernTheme.PRIMARY_DARK};
            }}
            QPushButton:disabled {{
                background-color: {ModernTheme.PRIMARY_LIGHT};
            }}
        """)
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setFixedSize(100, self.message_input.height())
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        
        # Token usage indicator (bottom right)
        token_layout = QHBoxLayout()
        token_layout.setContentsMargins(0, 4, 0, 0)
        
        token_layout.addStretch()  # Push everything to the right
        
        # Token progress bar
        from PyQt6.QtWidgets import QProgressBar
        self.token_progress = QProgressBar()
        self.token_progress.setFixedSize(100, 6)
        self.token_progress.setTextVisible(False)
        self.token_progress.setRange(0, 100)
        self.token_progress.setValue(0)
        self.token_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #E8E8E8;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {ModernTheme.PRIMARY};
                border-radius: 3px;
            }}
        """)
        token_layout.addWidget(self.token_progress)
        
        self.token_label = QLabel("~0")
        self.token_label.setStyleSheet(f"""
            QLabel {{
                color: {ModernTheme.TEXT_SECONDARY};
                font-size: 11px;
                background: transparent;
            }}
        """)
        token_layout.addWidget(self.token_label)
        
        layout.addLayout(token_layout)
    
    def apply_styles(self):
        """Apply modern styling"""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {ModernTheme.BG_WINDOW};
            }}
            QFrame {{
                background-color: {ModernTheme.BG_CARD};
            }}
            QPushButton {{
                background-color: {ModernTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {ModernTheme.PRIMARY_DARK};
            }}
            QPushButton:pressed {{
                background-color: #00695C;
            }}
            QTextEdit {{
                border: 1px solid {ModernTheme.BORDER};
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI';
                font-size: 14px;
                background-color: {ModernTheme.BG_CARD};
                color: {ModernTheme.TEXT_PRIMARY};
            }}
            QTextEdit:focus {{
                border: 2px solid {ModernTheme.PRIMARY};
            }}
            QComboBox {{
                border: 1px solid {ModernTheme.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                background-color: {ModernTheme.BG_CARD};
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {ModernTheme.PRIMARY};
            }}
            QGroupBox {{
                font-weight: 600;
                border: 1px solid {ModernTheme.BORDER};
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: {ModernTheme.BG_CARD};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px 0 6px;
                color: {ModernTheme.TEXT_PRIMARY};
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background-color: #D0D0D0;
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #B0B0B0;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
    
    def update_placeholder_text(self, checked=None):
        """Update placeholder text based on Enter to send setting"""
        if self.enter_to_send_toggle.isChecked():
            self.message_input.text_edit.setPlaceholderText("Type your message here... (Enter to send, Shift+Enter for new line)")
        else:
            self.message_input.text_edit.setPlaceholderText("Type your message here... (Ctrl+Enter to send)")
    
    def eventFilter(self, obj, event):
        """Handle key events for message input"""
        if obj == self.message_input.text_edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return:
                # Check if Enter to send is enabled
                if self.enter_to_send_toggle.isChecked():
                    # Enter to send mode
                    if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                        # Shift+Enter: insert new line (let it pass through)
                        return False
                    elif event.modifiers() == Qt.KeyboardModifier.NoModifier:
                        # Just Enter: send message
                        self.send_message()
                        return True
                else:
                    # Ctrl+Enter to send mode
                    if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                        self.send_message()
                        return True
        elif obj == self.message_input and event.type() == event.Type.KeyPress:
            # Fallback for the container
            if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.send_message()
                return True
        return super().eventFilter(obj, event)
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation: ~4 chars per token)"""
        return len(text) // 4 + 1
    
    def update_token_usage(self):
        """Update the token usage display"""
        # Use a reasonable default context size (most models support at least 4k-8k)
        max_tokens = 8192
        
        if not self.current_session:
            self.token_label.setText("~0")
            self.token_progress.setValue(0)
            self.token_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 11px; background: transparent;")
            self.token_progress.setStyleSheet(f"""
                QProgressBar {{ background-color: #E8E8E8; border: none; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {ModernTheme.PRIMARY}; border-radius: 3px; }}
            """)
            return
        
        # Calculate total tokens from all messages
        total_tokens = 0
        for msg in self.current_session.messages:
            total_tokens += self.estimate_tokens(msg.content)
        
        # Add current input text
        current_input = self.message_input.toPlainText()
        if current_input:
            total_tokens += self.estimate_tokens(current_input)
        
        # Calculate percentage
        percentage = min(100, int((total_tokens / max_tokens) * 100))
        
        # Update label with compact format
        self.token_label.setText(f"~{total_tokens:,}")
        
        # Update progress bar
        self.token_progress.setValue(percentage)
        
        # Change color based on usage
        if percentage >= 90:
            color = "#F44336"  # Red - danger
            self.token_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold; background: transparent;")
        elif percentage >= 75:
            color = "#FF9800"  # Orange - warning
            self.token_label.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")
        else:
            color = ModernTheme.PRIMARY  # Teal - normal
            self.token_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        
        self.token_progress.setStyleSheet(f"""
            QProgressBar {{ background-color: #E8E8E8; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}
        """)
    
    def on_input_changed(self):
        """Handle input text changes to update token count in real-time"""
        self.update_token_usage()
    
    def create_new_session(self):
        """Create a new chat session"""
        session_id = f"session_{int(datetime.now().timestamp())}"
        session = ChatSession(
            session_id=session_id,
            title="New Chat",
            messages=[]
        )
        
        self.chat_sessions[session_id] = session
        self.current_session = session
        self.clear_chat_display()
        self.update_sessions_list()
        self.update_token_usage()  # Reset token display
        pass  # Session created successfully
        
        logger.info(f"Created new chat session: {session_id}")
    
    def clear_chat_display(self):
        """Clear the chat display"""
        # Remove all message widgets except the stretch
        for i in reversed(range(self.chat_layout.count() - 1)):
            child = self.chat_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
    
    def update_sessions_list(self):
        """Update the sessions list"""
        self.sessions_list.clear()
        
        for session_id, session in self.chat_sessions.items():
            item = QListWidgetItem(session.title)
            item.setData(Qt.ItemDataRole.UserRole, session_id)
            
            # Highlight current session
            if session == self.current_session:
                item.setBackground(QColor("#B2DFDB"))  # Teal light
            
            self.sessions_list.addItem(item)
    
    def load_session(self, item):
        """Load a selected session"""
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id in self.chat_sessions:
            self.current_session = self.chat_sessions[session_id]
            self.clear_chat_display()
            
            # Display all messages in the session
            for message in self.current_session.messages:
                self.add_message_to_display(message)
            
            self.update_sessions_list()  # Refresh highlighting
            self.update_token_usage()  # Update token display
            pass  # Session loaded successfully
    
    def delete_session(self):
        """Delete selected session"""
        current_item = self.sessions_list.currentItem()
        if not current_item:
            return
        
        session_id = current_item.data(Qt.ItemDataRole.UserRole)
        if session_id in self.chat_sessions:
            del self.chat_sessions[session_id]
            
            # If we deleted the current session, create a new one
            if self.current_session and self.current_session.session_id == session_id:
                self.create_new_session()
            else:
                self.update_sessions_list()
    
    def export_session(self):
        """Export current session to file"""
        if not self.current_session:
            return
        
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Export Chat Session", 
                f"chat_session_{self.current_session.session_id}.txt",
                "Text Files (*.txt);;JSON Files (*.json)"
            )
            
            if file_path:
                if file_path.endswith('.json'):
                    # Export as JSON
                    session_data = {
                        'session_id': self.current_session.session_id,
                        'title': self.current_session.title,
                        'created_at': self.current_session.created_at.isoformat(),
                        'messages': [
                            {
                                'role': msg.role,
                                'content': msg.content,
                                'timestamp': msg.timestamp.isoformat()
                            }
                            for msg in self.current_session.messages
                        ]
                    }
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(session_data, f, indent=2, ensure_ascii=False)
                else:
                    # Export as plain text
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(f"Chat Session: {self.current_session.title}\n")
                        f.write(f"Created: {self.current_session.created_at}\n")
                        f.write("=" * 50 + "\n\n")
                        
                        for msg in self.current_session.messages:
                            f.write(f"[{msg.timestamp.strftime('%H:%M:%S')}] {msg.role.upper()}:\n")
                            f.write(f"{msg.content}\n\n")
                
                QMessageBox.information(self, "Export Complete", f"Session exported to {file_path}")
                
        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Failed to export session: {e}")
    
    def on_prompt_selected(self, prompt_name: str, prompt_data: Dict):
        """Handle prompt selection"""
        if self.current_session:
            self.current_session.selected_prompt = prompt_name
            logger.info(f"Selected prompt: {prompt_name}")
    
    def attach_image(self):
        """Attach an image file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Image", 
            "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()
                
                # Add image indicator to input
                current_text = self.message_input.toPlainText()
                self.message_input.setPlainText(current_text + f"\n[Image: {os.path.basename(file_path)}]")
                
                # Store image data (simplified - in real implementation, you'd want better storage)
                if not hasattr(self, 'attached_images'):
                    self.attached_images = []
                self.attached_images.append(img_data)
                
                logger.info(f"Attached image: {file_path}")
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to attach image: {e}")
    
    def paste_from_clipboard(self):
        """Paste content from clipboard"""
        try:
            # Get clipboard data
            clipboard_data = self.clipboard_manager.get_clipboard_data()
            
            if clipboard_data.get('text'):
                current_text = self.message_input.toPlainText()
                if current_text:
                    self.message_input.setPlainText(current_text + "\n\n" + clipboard_data['text'])
                else:
                    self.message_input.setPlainText(clipboard_data['text'])
            
            if clipboard_data.get('images'):
                # Handle clipboard images
                for img_data in clipboard_data['images']:
                    if not hasattr(self, 'attached_images'):
                        self.attached_images = []
                    self.attached_images.append(img_data)
                
                current_text = self.message_input.toPlainText()
                self.message_input.setPlainText(current_text + "\n[Clipboard Image]")
            
            logger.info("Pasted content from clipboard")
            
        except Exception as e:
            logger.error(f"Error pasting from clipboard: {e}")
            QMessageBox.warning(self, "Error", f"Failed to paste from clipboard: {e}")
    
    def send_message(self):
        """Send a message"""
        if not self.current_session:
            return
        
        message_text = self.message_input.toPlainText().strip()
        if not message_text:
            return
        
        # Get attached images
        images = getattr(self, 'attached_images', [])
        
        # Create user message
        user_message = ChatMessage(
            role="user",
            content=message_text,
            images=images
        )
        
        # Add to session
        self.current_session.messages.append(user_message)
        
        # Display user message
        self.add_message_to_display(user_message)
        
        # Clear input
        self.message_input.clear()
        self.attached_images = []
        
        # Update token usage
        self.update_token_usage()
        
        # Update session title if this is the first message
        if len(self.current_session.messages) == 1:
            # Use first few words as title
            title_words = message_text.split()[:5]
            self.current_session.title = " ".join(title_words) + ("..." if len(title_words) == 5 else "")
            self.update_sessions_list()
        
        # Send to AI
        self.process_ai_response()
    
    def add_message_to_display(self, message: ChatMessage):
        """Add a message to the chat display"""
        message_widget = MessageWidget(message)
        
        # Insert before the stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, message_widget)
        
        # Scroll to bottom
        QTimer.singleShot(100, self.scroll_to_bottom)
    
    def scroll_to_bottom(self):
        """Scroll chat to bottom"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def process_ai_response(self):
        """Process AI response"""
        if not self.ai_client or not self.current_session:
            QMessageBox.warning(self, "Error", "No AI client available")
            return
        
        # Update model label
        current_model = self.settings.get('model', '')
        self.model_label.setText(current_model)
        
        if not current_model:
            QMessageBox.warning(self, "Error", "No model selected")
            return
        
        # Disable send button and show typing animation
        self.send_button.setEnabled(False)
        self.typing_animation.show()
        self.typing_animation.start_animation()
        
        # Prepare messages for AI
        messages = []
        
        # Add system prompt if selected
        selected_prompt = self.prompt_selector.get_selected_prompt()
        if selected_prompt:
            system_content = selected_prompt.get('template', '')
            if system_content:
                messages.append({
                    "role": "system",
                    "content": system_content
                })
        
        # Add conversation history
        for msg in self.current_session.messages:
            ai_message = {
                "role": msg.role,
                "content": msg.content
            }
            
            # Add images if present (for vision models)
            if msg.images and hasattr(self.ai_client, 'supports_vision'):
                ai_message["images"] = msg.images
            
            messages.append(ai_message)
        
        # Start worker thread with streaming enabled
        self.current_worker = ChatWorker(
            self.ai_client,
            current_model,
            messages,
            self.current_session.session_id,
            stream=True  # Enable streaming
        )
        
        # Initialize streaming state
        self.streaming_content = ""
        self.streaming_message_widget = None
        
        # Connect signals
        self.current_worker.chunk_received.connect(self.on_chunk_received)
        self.current_worker.stream_finished.connect(self.on_stream_finished)
        self.current_worker.response_received.connect(self.on_response_received)
        self.current_worker.error_occurred.connect(self.on_error_occurred)
        self.current_worker.start()
    
    def on_chunk_received(self, chunk: str, session_id: str):
        """Handle streaming chunk received"""
        if session_id != self.current_session.session_id:
            return
        
        # Hide typing animation on first chunk
        if not self.streaming_content:
            self.typing_animation.stop_animation()
            
            # Create a streaming message widget
            streaming_message = ChatMessage(role="assistant", content="")
            self.streaming_message_widget = MessageWidget(streaming_message)
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, self.streaming_message_widget)
        
        # Accumulate content
        self.streaming_content += chunk
        
        # Update the message widget content
        if self.streaming_message_widget:
            self.streaming_message_widget.content_label.setText(self.streaming_content)
            
        # Scroll to bottom
        QTimer.singleShot(10, self.scroll_to_bottom)
    
    def on_stream_finished(self, full_response: str, session_id: str):
        """Handle streaming completion"""
        if session_id != self.current_session.session_id:
            return
        
        # Stop typing animation (in case no chunks were received)
        self.typing_animation.stop_animation()
        
        # Create assistant message with full content
        assistant_message = ChatMessage(
            role="assistant",
            content=full_response
        )
        
        # Add to session
        self.current_session.messages.append(assistant_message)
        
        # Update token usage
        self.update_token_usage()
        
        # Re-enable controls
        self.send_button.setEnabled(True)
        
        # Update sessions list
        self.update_sessions_list()
        
        # Reset streaming state
        self.streaming_content = ""
        self.streaming_message_widget = None
        
        logger.info(f"Completed streaming response for session {session_id}")
    
    def on_response_received(self, response: str, session_id: str):
        """Handle AI response"""
        if session_id != self.current_session.session_id:
            return
        
        # Stop typing animation
        self.typing_animation.stop_animation()
        
        # Create assistant message
        assistant_message = ChatMessage(
            role="assistant",
            content=response
        )
        
        # Add to session
        self.current_session.messages.append(assistant_message)
        
        # Display message
        self.add_message_to_display(assistant_message)
        
        # Update token usage
        self.update_token_usage()
        
        # Re-enable controls
        self.send_button.setEnabled(True)
        
        # Update sessions list
        self.update_sessions_list()
        
        logger.info(f"Received AI response for session {session_id}")
    
    def on_error_occurred(self, error: str):
        """Handle AI error"""
        # Stop typing animation
        self.typing_animation.stop_animation()
        
        # Re-enable controls
        self.send_button.setEnabled(True)
        
        QMessageBox.warning(self, "AI Error", f"Failed to get AI response:\n{error}")
        logger.error(f"AI error: {error}")
    
    def clear_chat(self):
        """Clear the current chat"""
        if self.current_session:
            self.current_session.messages.clear()
            self.clear_chat_display()
            self.update_token_usage()
            pass  # Chat cleared successfully
    
    def update_client(self, client):
        """Update the AI client"""
        self.ai_client = client
        logger.info("Updated AI client")
    
    def update_prompts(self):
        """Update prompts from prompt editor"""
        self.prompt_selector.load_prompts()
        logger.info("Updated prompts from prompt editor")
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.wait(3000)  # Wait up to 3 seconds
        
        event.accept()