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
                background-color: #ddd;
                border: 1px solid #bbb;
                border-radius: 4px;
            }
            QFrame:hover {
                background-color: #1976D2;
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
    """Worker thread for AI chat completion"""
    
    response_received = pyqtSignal(str, str)  # response, session_id
    error_occurred = pyqtSignal(str)
    thinking_update = pyqtSignal(str)  # For reasoning models
    
    def __init__(self, ai_client, model: str, messages: List[Dict], session_id: str):
        super().__init__()
        self.ai_client = ai_client
        self.model = model
        self.messages = messages
        self.session_id = session_id
        self._is_cancelled = False
    
    def cancel(self):
        """Cancel the request"""
        self._is_cancelled = True
    
    def run(self):
        """Execute the chat completion"""
        try:
            if self._is_cancelled:
                return
            
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
            logger.error(f"Error in chat completion: {e}")
            self.error_occurred.emit(str(e))

class TypingAnimationWidget(QFrame):
    """Widget that shows AI is typing with animated dots"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dots_count = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the typing animation UI"""
        # Main container with proper alignment (left side for AI)
        container_layout = QHBoxLayout(self)
        container_layout.setContentsMargins(10, 5, 10, 5)
        
        # Message content frame
        message_frame = QFrame()
        message_layout = QVBoxLayout(message_frame)
        message_layout.setContentsMargins(10, 8, 10, 8)
        
        # AI label
        header_layout = QHBoxLayout()
        role_label = QLabel("Assistant")
        role_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        role_label.setStyleSheet("color: #388E3C;")
        header_layout.addWidget(role_label)
        header_layout.addStretch()
        message_layout.addLayout(header_layout)
        
        # Typing indicator
        self.typing_label = QLabel("AI is thinking")
        self.typing_label.setStyleSheet("""
            color: #666;
            font-family: 'Segoe UI';
            font-size: 14px;
            font-style: italic;
        """)
        message_layout.addWidget(self.typing_label)
        
        # Set maximum width for consistency
        message_frame.setMaximumWidth(500)
        
        # Style similar to AI messages
        message_frame.setStyleSheet("""
            QFrame {
                background-color: #F0F8FF;
                border-radius: 15px;
                margin: 2px;
                border: 1px solid #B3D9FF;
            }
        """)
        
        # AI messages on the left
        container_layout.addWidget(message_frame)
        container_layout.addStretch()
    
    def start_animation(self):
        """Start the typing animation"""
        self.timer.start(500)  # Update every 500ms
    
    def stop_animation(self):
        """Stop the typing animation"""
        self.timer.stop()
        self.hide()
    
    def update_animation(self):
        """Update the typing animation"""
        self.dots_count = (self.dots_count + 1) % 4
        dots = "." * self.dots_count
        self.typing_label.setText(f"AI is thinking{dots}")

class MessageWidget(QFrame):
    """Widget for displaying a single chat message"""
    
    def __init__(self, message: ChatMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the message UI"""
        # Main container with proper alignment
        container_layout = QHBoxLayout(self)
        container_layout.setContentsMargins(10, 5, 10, 5)
        
        # Message content frame
        message_frame = QFrame()
        message_layout = QVBoxLayout(message_frame)
        message_layout.setContentsMargins(10, 8, 10, 8)
        
        # Message header
        header_layout = QHBoxLayout()
        
        # Role label
        role_label = QLabel(self.message.role.title())
        role_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        
        if self.message.role == "user":
            role_label.setStyleSheet("color: #1976D2;")
        elif self.message.role == "assistant":
            role_label.setStyleSheet("color: #388E3C;")
        else:
            role_label.setStyleSheet("color: #666;")
        
        # Timestamp
        timestamp_label = QLabel(self.message.timestamp.strftime("%H:%M"))
        timestamp_label.setStyleSheet("color: #999; font-size: 11px;")
        
        if self.message.role == "user":
            header_layout.addStretch()
            header_layout.addWidget(timestamp_label)
            header_layout.addWidget(role_label)
        else:
            header_layout.addWidget(role_label)
            header_layout.addWidget(timestamp_label)
            header_layout.addStretch()
        
        message_layout.addLayout(header_layout)
        
        # Message content
        content_text = QTextEdit()
        content_text.setPlainText(self.message.content)
        content_text.setReadOnly(True)
        content_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Auto-adjust height based on content - no height restrictions
        content_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)  # Enable word wrapping
        
        # Calculate proper height for content
        document = content_text.document()
        document.setTextWidth(content_text.viewport().width())
        height = document.size().height() + 20
        content_text.setFixedHeight(max(30, int(height)))
        
        # Set maximum width but allow more space (70% of chat area)
        message_frame.setMaximumWidth(700)
        message_frame.setMinimumWidth(200)
        
        # Style and position based on role
        if self.message.role == "user":
            message_frame.setStyleSheet("""
                QFrame {
                    background-color: #F1F8E9;
                    border-radius: 15px;
                    margin: 2px;
                    border: 1px solid #E8F5E8;
                }
                QTextEdit {
                    background-color: transparent;
                    border: none;
                    font-family: 'Segoe UI';
                    font-size: 14px;
                    color: #2E7D32;
                }
            """)
            role_label.setStyleSheet("color: #388E3C;")
            timestamp_label.setStyleSheet("color: #81C784; font-size: 11px;")
            
            # User messages on the right with some margin
            container_layout.addStretch(2)  # More stretch on left
            container_layout.addWidget(message_frame)
            container_layout.addStretch(1)  # Less stretch on right
        else:
            message_frame.setStyleSheet("""
                QFrame {
                    background-color: #F5F5F5;
                    border-radius: 15px;
                    margin: 2px;
                    border: 1px solid #E0E0E0;
                }
                QTextEdit {
                    background-color: transparent;
                    border: none;
                    font-family: 'Segoe UI';
                    font-size: 14px;
                    color: #333;
                }
            """)
            
            # AI messages on the left with some margin
            container_layout.addStretch(1)  # Less stretch on left
            container_layout.addWidget(message_frame)
            container_layout.addStretch(2)  # More stretch on right
        
        message_layout.addWidget(content_text)
        
        # Images if present
        if self.message.images:
            self.add_images(message_layout)
    
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
                    scaled_pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    
                    image_label = QLabel()
                    image_label.setPixmap(scaled_pixmap)
                    image_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
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
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #fafafa;
            }
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px;
                background-color: white;
            }
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
                font-family: 'Consolas', monospace;
                font-size: 11px;
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
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header_label = QLabel("💬 AI Chat")
        header_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)
        
        # New chat button
        new_chat_btn = QPushButton("+ New Chat")
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
        
        # Temperature
        
        # Max tokens (placeholder)
        layout.addWidget(QLabel("Max Tokens:"), 2, 0)
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 32000)
        self.max_tokens_spin.setValue(2000)
        layout.addWidget(self.max_tokens_spin, 2, 1)
        
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
        layout.setContentsMargins(10, 5, 10, 10)
        
        # Input controls
        controls_layout = QHBoxLayout()
        
        # Attach button
        attach_btn = QToolButton()
        attach_btn.setText("📎")
        attach_btn.setToolTip("Attach image")
        attach_btn.clicked.connect(self.attach_image)
        controls_layout.addWidget(attach_btn)
        
        # Paste button
        paste_btn = QToolButton()
        paste_btn.setText("📋")
        paste_btn.setToolTip("Paste from clipboard")
        paste_btn.clicked.connect(self.paste_from_clipboard)
        controls_layout.addWidget(paste_btn)
        
        controls_layout.addStretch()
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_chat)
        controls_layout.addWidget(clear_btn)
        
        layout.addLayout(controls_layout)
        
        # Resizable text input with send button
        input_layout = QHBoxLayout()
        
        # Custom resizable text edit
        self.message_input = ResizableTextEdit()
        self.message_input.installEventFilter(self)
        input_layout.addWidget(self.message_input)
        
        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setFixedSize(80, self.message_input.height())
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
    
    def apply_styles(self):
        """Apply modern styling"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
            }
            QFrame {
                background-color: #ffffff;
            }
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                font-family: 'Segoe UI';
                font-size: 14px;
                background-color: #ffffff;
            }
            QTextEdit:focus {
                border: 2px solid #1976D2;
            }
            QComboBox {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
    
    def eventFilter(self, obj, event):
        """Handle key events for message input"""
        if obj == self.message_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.send_message()
                return True
        elif obj == self.message_input.text_edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.send_message()
                return True
        return super().eventFilter(obj, event)
    
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
                item.setBackground(QColor("#E3F2FD"))
            
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
        
        # Start worker thread
        self.current_worker = ChatWorker(
            self.ai_client,
            current_model,
            messages,
            self.current_session.session_id
        )
        
        self.current_worker.response_received.connect(self.on_response_received)
        self.current_worker.error_occurred.connect(self.on_error_occurred)
        self.current_worker.start()
    
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