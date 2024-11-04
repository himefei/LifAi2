from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                            QPushButton, QLabel, QScrollArea, QFrame,
                            QFileDialog, QProgressBar)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QCloseEvent
from typing import Dict
import os
from datetime import datetime
from lifai.utils.ollama_client import OllamaClient
from lifai.utils.logger_utils import get_module_logger
import json
from pathlib import Path

logger = get_module_logger(__name__)

class MessageBubble(QFrame):
    def __init__(self, text: str, is_user: bool = True, parent=None):
        super().__init__(parent)
        self.setObjectName("messageBubble")
        
        # Main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 5, 10, 5)
        self.setLayout(main_layout)
        
        # Message container
        bubble_container = QFrame()
        bubble_container.setObjectName("bubbleContainer")
        bubble_layout = QHBoxLayout()
        bubble_container.setLayout(bubble_layout)
        
        # Message text
        message = QLabel(text)
        message.setWordWrap(True)
        message.setTextFormat(Qt.TextFormat.RichText)
        message.setFont(QFont("Segoe UI", 10))
        message.setObjectName("messageText")
        bubble_layout.addWidget(message)
        
        # Style based on sender
        if is_user:
            bubble_container.setStyleSheet("""
                QFrame#bubbleContainer {
                    background-color: #DCF8C6;
                    border-radius: 15px;
                    padding: 10px;
                    margin: 5px;
                }
                QLabel#messageText {
                    color: #000000;
                    background-color: transparent;
                }
            """)
            main_layout.addWidget(bubble_container)
            main_layout.addStretch()
        else:
            bubble_container.setStyleSheet("""
                QFrame#bubbleContainer {
                    background-color: #E8E8E8;
                    border-radius: 15px;
                    padding: 10px;
                    margin: 5px;
                }
                QLabel#messageText {
                    color: #000000;
                    background-color: transparent;
                }
            """)
            main_layout.addStretch()
            main_layout.addWidget(bubble_container)
        
        # Set frame style
        self.setStyleSheet("""
            QFrame#messageBubble {
                background-color: transparent;
                border: none;
            }
        """)

class ChatWindow(QWidget):
    def __init__(self, settings: Dict, ollama_client: OllamaClient):
        super().__init__(None)
        logger.info("Initializing AI Chat Window")
        self.settings = settings
        self.ollama_client = ollama_client
        self.chat_history = []
        
        # Create chat history directory
        self.history_dir = Path(__file__).parent / 'chat_history'
        self.history_dir.mkdir(exist_ok=True)
        
        # Setup UI first
        self.setup_ui()
        
        # Then load chat history
        self.load_chat_history()
        
        # Set window flags to prevent closing
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.hide()

    def save_chat_history(self):
        """Save chat history to file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'chat_session_{timestamp}.json'
            filepath = self.history_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.chat_history, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Chat history saved to {filepath}")
            
            # Clean up old history files (keep last 10)
            history_files = sorted(self.history_dir.glob('chat_session_*.json'))
            if len(history_files) > 10:
                for old_file in history_files[:-10]:
                    old_file.unlink()
                    
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")

    def load_chat_history(self):
        """Load most recent chat history"""
        try:
            history_files = sorted(self.history_dir.glob('chat_session_*.json'))
            if history_files:
                latest_file = history_files[-1]
                with open(latest_file, 'r', encoding='utf-8') as f:
                    self.chat_history = json.load(f)
                    
                # Restore messages from history
                for msg in self.chat_history:
                    self.add_message(msg['text'], msg['is_user'], save_history=False)
                    
                logger.info(f"Chat history loaded from {latest_file}")
                
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")
            self.chat_history = []

    def closeEvent(self, event: QCloseEvent):
        """Prevent window from closing when X is clicked"""
        logger.info("Close event intercepted - hiding window instead")
        event.ignore()
        self.hide()

    def setup_ui(self):
        """Setup the chat interface"""
        self.setWindowTitle("AI Chat")
        self.resize(800, 600)
        
        # Main layout
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Chat area with scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Container for messages
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout()
        self.chat_layout.setSpacing(10)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_container.setLayout(self.chat_layout)
        
        # Set background color for chat container
        self.chat_container.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
            }
        """)
        
        scroll.setWidget(self.chat_container)
        layout.addWidget(scroll)
        
        # Input area
        input_layout = QHBoxLayout()
        
        # File upload button with gray color
        self.upload_btn = QPushButton("📎")
        self.upload_btn.setObjectName("upload_btn")
        self.upload_btn.setFixedSize(40, 40)
        self.upload_btn.clicked.connect(self.upload_file)
        self.upload_btn.setStyleSheet("""
            QPushButton#upload_btn {
                background-color: #808080;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton#upload_btn:hover {
                background-color: #666666;
            }
        """)
        input_layout.addWidget(self.upload_btn)
        
        # Text input with Enter key support
        self.input_text = QTextEdit()
        self.input_text.setFixedHeight(40)
        self.input_text.setPlaceholderText("Type a message...")
        self.input_text.installEventFilter(self)
        input_layout.addWidget(self.input_text)
        
        # Send button
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedSize(60, 40)
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout)
        
        # Progress bar for file uploads
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Style the window
        self.setStyleSheet("""
            QWidget {
                background-color: #F0F0F0;
            }
            QScrollArea {
                border: none;
                background-color: #FFFFFF;
            }
            QPushButton {
                background-color: #128C7E;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #075E54;
            }
            QTextEdit {
                border: 1px solid #128C7E;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }
            QProgressBar {
                border: 1px solid #128C7E;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #128C7E;
            }
        """)

    def add_message(self, text: str, is_user: bool = True, save_history: bool = True):
        """Add a message to the chat"""
        bubble = MessageBubble(text, is_user)
        self.chat_layout.addWidget(bubble)
        
        if save_history:
            self.chat_history.append({"text": text, "is_user": is_user})
            self.save_chat_history()
        
        # Auto scroll to bottom
        QWidget.repaint(self.chat_container)
        scroll_area = self.chat_container.parent().parent()
        if isinstance(scroll_area, QScrollArea):
            scroll_bar = scroll_area.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())

    def send_message(self):
        """Send a message to the AI"""
        text = self.input_text.toPlainText().strip()
        if not text:
            return
            
        # Clear input
        self.input_text.clear()
        
        # Add user message
        self.add_message(text, True)
        
        try:
            # Get AI response
            response = self.ollama_client.generate_response(
                prompt=text,
                model=self.settings['model'].get()
            )
            
            if response:
                # Add AI response
                self.add_message(response, False)
            else:
                self.add_message("Sorry, I couldn't generate a response.", False)
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            self.add_message(f"Error: {str(e)}", False)

    def upload_file(self):
        """Handle file upload"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Text Files (*.txt);;PDF Files (*.pdf);;All Files (*.*)"
        )
        
        if file_path:
            try:
                self.progress_bar.show()
                self.progress_bar.setValue(0)
                
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                self.progress_bar.setValue(50)
                
                # Add file upload message
                filename = os.path.basename(file_path)
                self.add_message(f"📄 Uploaded: {filename}", True)
                
                # Process file content
                prompt = f"Please analyze this file content:\n\n{content}"
                response = self.ollama_client.generate_response(
                    prompt=prompt,
                    model=self.settings['model'].get()
                )
                
                self.progress_bar.setValue(100)
                
                if response:
                    self.add_message(response, False)
                else:
                    self.add_message("Sorry, I couldn't analyze the file.", False)
                    
            except Exception as e:
                logger.error(f"Error processing file: {e}")
                self.add_message(f"Error processing file: {str(e)}", False)
            finally:
                self.progress_bar.hide()

    def show(self):
        """Show the window"""
        super().show()
        self.raise_()

    def hide(self):
        """Hide the window"""
        super().hide()

    def destroy(self):
        """Clean up resources"""
        super().destroy()

    def eventFilter(self, source, event):
        """Handle Enter key press"""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent

        if (source is self.input_text and 
            event.type() == QEvent.Type.KeyPress and 
            isinstance(event, QKeyEvent)):
            
            # Check if Enter was pressed without Shift
            if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.send_message()
                return True
                
        return super().eventFilter(source, event)