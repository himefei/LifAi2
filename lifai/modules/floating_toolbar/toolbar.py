"""
Floating Toolbar Module for LifAi2.

Provides a floating, always-on-top toolbar for text enhancement, prompt selection, and
quick review using local LLMs (Ollama/LM Studio). Implements observer pattern for UI updates,
threaded selection and processing, and modular integration with the knowledge base and prompt system.

Features:
    - Floating, draggable, and minimizable toolbar UI (PyQt6)
    - Prompt selection and management (integrates with Prompt Editor)
    - Asynchronous text selection and processing (threaded, non-blocking)
    - Quick review drawer and animated UI elements
    - Observer pattern for UI state and signal/slot communication
    - Modular integration with LLM clients and knowledge base
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QPushButton, QFrame, QMessageBox,
                            QTextEdit, QApplication, QGraphicsDropShadowEffect,
                            QListWidget, QListWidgetItem, QAbstractItemView, QListView)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QEvent
from PyQt6.QtGui import QColor, QPalette, QDrag, QMouseEvent
from typing import Dict, List
from pynput import mouse
from lifai.utils.ollama_client import OllamaClient
from lifai.utils.logger_utils import get_module_logger
from lifai.config.prompts import llm_prompts, prompt_order, reload_prompts
from lifai.utils.clipboard_utils import ClipboardManager
# from lifai.utils.knowledge_base import KnowledgeBase # RAG Removed
import time
import threading
import logging

logger = get_module_logger(__name__)

class TextDisplayWindow(QMainWindow):
    """Popup window for displaying processed text results with dynamic positioning."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # Window setup
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Create title bar
        title_bar = QFrame()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 5, 10, 5)
        
        # Add spacer to push close button to right
        title_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #666;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #1976D2;
            }
        """)
        close_btn.clicked.connect(self.hide)
        title_layout.addWidget(close_btn)
        
        layout.addWidget(title_bar)
        
        # Text display
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setMinimumWidth(500)
        self.text_display.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 10px;
                font-size: 13px;
                font-family: "Segoe UI", sans-serif;
                color: #333;
            }
        """)
        layout.addWidget(self.text_display)
        
        # Window styling
        self.setStyleSheet("""
            QMainWindow {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
            }
        """)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 50))
        central_widget.setGraphicsEffect(shadow)
        
        # Set fixed width
        self.setFixedWidth(500)

    def setText(self, text: str):
        """Set text and adjust window height"""
        self.text_display.setText(text)
        
        # Calculate and set window height based on content
        doc_height = self.text_display.document().size().height()
        window_height = int(min(doc_height + 80, 600))  # +80 for margins and title bar, cast to int
        self.setFixedHeight(max(window_height, 150))  # Minimum height 150px

    def updatePosition(self):
        """Update window position relative to parent toolbar"""
        if not self.parent:
            return
            
        # Get the screen containing the toolbar
        toolbar_center = self.parent.geometry().center()
        current_screen = QApplication.screenAt(toolbar_center)
        if not current_screen:
            current_screen = QApplication.primaryScreen()
        
        # Get the geometry of the current screen
        screen = current_screen.geometry()
        toolbar = self.parent.geometry()
        
        logger.debug(f"Toolbar position: {toolbar.topLeft()}, Screen: {screen.topLeft()} -> {screen.bottomRight()}")
        
        # Calculate available space in each direction
        space_right = screen.right() - (toolbar.right() + 10)
        space_left = toolbar.left() - screen.left() - 10
        space_bottom = screen.bottom() - (toolbar.bottom() + 10)
        space_top = toolbar.top() - screen.top() - 10
        
        logger.debug(f"Available space - Right: {space_right}, Left: {space_left}, Bottom: {space_bottom}, Top: {space_top}")
        
        # Determine position based on available space
        if space_right >= self.width():
            # Place on right
            x = toolbar.right() + 10
            y = toolbar.top()
            logger.debug("Positioning on right")
        elif space_left >= self.width():
            # Place on left
            x = toolbar.left() - self.width() - 10
            y = toolbar.top()
            logger.debug("Positioning on left")
        elif space_bottom >= self.height():
            # Place below
            x = toolbar.left() - ((self.width() - toolbar.width()) // 2)
            y = toolbar.bottom() + 10
            logger.debug("Positioning below")
        else:
            # Place above
            x = toolbar.left() - ((self.width() - toolbar.width()) // 2)
            y = toolbar.top() - self.height() - 10
            logger.debug("Positioning above")
            
        # Ensure window stays within current screen bounds
        x = max(screen.left(), min(x, screen.right() - self.width()))
        y = max(screen.top(), min(y, screen.bottom() - self.height()))
        
        logger.debug(f"Final position: ({x}, {y})")
        self.move(x, y)

class FloatingToolbarModule(QMainWindow):
    # Define signals at class level
    text_processed = pyqtSignal(str)  # Signal for processed text
    selection_finished = pyqtSignal()
    show_error = pyqtSignal(str)  # Signal for error messages
    process_complete = pyqtSignal()  # Signal for process completion
    progress_updated = pyqtSignal(int)  # New signal for progress updates

    def __init__(self, settings: Dict, ollama_client: OllamaClient):
        super().__init__()
        self.settings = settings
        self.client = ollama_client  # Rename to be more generic
        self.client_type = "ollama" if isinstance(ollama_client, OllamaClient) else "lmstudio"
        self.processing = False
        self.clipboard = ClipboardManager()
        # self.knowledge_base = KnowledgeBase()  # RAG Removed: Initialize knowledge base
        self.llm_prompts = llm_prompts.copy() # Initialize instance variable
        # Initialize self.prompt_order as a list of names in the correct order
        # prompt_order (from import) is a list of IDs.
        # self.llm_prompts (from import, copied) is a dict of name:data.
        # We need to map the IDs in prompt_order to names using self.llm_prompts.
        initial_prompt_names_ordered = []
        if isinstance(prompt_order, list):
            # Create a temporary reverse map from ID to name from the initial llm_prompts
            id_to_name_map = {}
            for name, data in self.llm_prompts.items():
                if isinstance(data, dict) and "id" in data:
                    id_to_name_map[data["id"]] = name
            
            for p_id in prompt_order:
                if p_id in id_to_name_map:
                    initial_prompt_names_ordered.append(id_to_name_map[p_id])
                else:
                    logger.warning(f"Toolbar __init__: Prompt ID '{p_id}' from initial prompt_order not found in llm_prompts' ID map.")
            
            # Add any prompts from llm_prompts that weren't in prompt_order (e.g. if prompts.json was manually edited)
            for name in self.llm_prompts.keys():
                if name not in initial_prompt_names_ordered:
                    initial_prompt_names_ordered.append(name)
                    logger.warning(f"Toolbar __init__: Prompt name '{name}' from llm_prompts was not in initial_prompt_names_ordered, appending.")
        
        if not initial_prompt_names_ordered: # Fallback if mapping failed
            logger.warning("Toolbar __init__: Failed to create ordered list of names, falling back to llm_prompts keys.")
            initial_prompt_names_ordered = list(self.llm_prompts.keys())
            
        self.prompt_order = initial_prompt_names_ordered
        logger.debug(f"Toolbar __init__: self.prompt_order (list of names): {self.prompt_order}")
        self.setup_ui()
        self.setup_hotkeys()
        self.hide()
        
        # Connect signals
        self.text_processed.connect(self._handle_processed_text)
        self.selection_finished.connect(self._reset_ui)
        self.show_error.connect(self._show_error_dialog)
        self.process_complete.connect(self._reset_ui)
        
        # Add quick review drawer
        self.quick_review_drawer = None
        self.drawer_animation = None
        self.setup_quick_review_drawer()
        
        # Initialize text display window
        self.text_window = TextDisplayWindow(self)

    def setup_ui(self):
        """Setup the main toolbar UI"""
        # Window properties
        self.setWindowTitle("LifAi2 Toolbar")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(8)
        
        # Create main frame with fixed size
        self.main_frame = QFrame()
        self.main_frame.setObjectName("mainFrame")
        self.main_frame.setFixedSize(200, 180)  # Fixed width and height for main toolbar
        self.main_frame.setStyleSheet("""
            QFrame#mainFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
        """)
        frame_layout = QVBoxLayout(self.main_frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)
        frame_layout.setSpacing(8)
        
        # 创建标题栏
        title_frame = QFrame()
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("🤖 LifAi2")
        title_label.setStyleSheet("""
            QLabel {
                color: #1976D2;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        title_layout.addWidget(title_label)
        
        # 最小化按钮
        min_btn = QPushButton("⎯")
        min_btn.setFixedWidth(30)
        min_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #666;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #f0f0f0;
                border-radius: 4px;
            }
        """)
        min_btn.clicked.connect(self.minimize_toolbar)
        title_layout.addWidget(min_btn)
        
        frame_layout.addWidget(title_frame)
        
        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #e0e0e0;")
        frame_layout.addWidget(separator)
        
        # 创建提示选择下拉框
        self.prompt_combo = QComboBox()
        self._update_prompt_combo()
        self.prompt_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 5px;
                background: white;
            }
            QComboBox:hover {
                border: 1px solid #1976D2;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
        """)
        frame_layout.addWidget(self.prompt_combo)
        
        # Add progress label with a frame
        progress_frame = QFrame()
        progress_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background: #f5f5f5;
                min-height: 30px;
            }
        """)
        progress_layout = QHBoxLayout(progress_frame)
        progress_layout.setContentsMargins(5, 2, 5, 2)
        
        self.progress_label = QLabel("🚀 Ready")
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #1976D2;
                padding: 5px;
                min-width: 120px;
                background: #f5f5f5;
                border-radius: 5px;
            }
        """)
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        frame_layout.addWidget(progress_frame)
        
        # Breathing animation setup
        self.breathing_timer = QTimer()
        self.breathing_timer.timeout.connect(self._update_breathing)
        self.breathing_value = 255
        self.breathing_increasing = False
        self.gradient_position = 0.0
        self.breathing_timer.start(16)  # ~60fps
        
        # 创建处理按钮
        self.process_btn = QPushButton("✨ Process Selected Text")
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
            QPushButton:disabled {
                background-color: #90CAF9;
            }
        """)
        self.process_btn.clicked.connect(self.start_processing)
        frame_layout.addWidget(self.process_btn)
        
        # Add main frame to main layout
        self.main_layout.addWidget(self.main_frame)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.main_frame.setGraphicsEffect(shadow)
        
        # Connect progress signal
        self.progress_updated.connect(self._update_progress)
        
        # 拖动相关变量
        self.drag_position = None
        self.waiting_for_selection = False
        self.mouse_down = False
        self.mouse_down_time = None
        self.mini_window = None
        
        # 设置鼠标追踪
        title_frame.setMouseTracking(True)
        title_frame.mousePressEvent = self.start_drag
        title_frame.mouseMoveEvent = self.on_drag

    def setup_hotkeys(self):
        """设置快捷键"""
        pass  # 暂时不实现快捷键功能

    def minimize_toolbar(self):
        """最小化工具栏"""
        # Hide quick review drawer if visible
        if self.quick_review_drawer and self.quick_review_drawer.isVisible():
            self.quick_review_drawer.hide()
        
        self.hide()
        if not self.mini_window:
            self.mini_window = FloatingMiniWindow(self)
        self.mini_window.move(self.pos())
        self.mini_window.show()

    def restore_toolbar(self):
        """恢复工具栏"""
        if self.mini_window:
            self.move(self.mini_window.pos())
            self.mini_window.hide()
        self.show()
        
    def start_drag(self, event):
        """开始拖动窗口"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        
    def on_drag(self, event):
        """处理窗口拖动"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def start_processing(self):
        """Start text processing"""
        # Hide text window if visible
        if hasattr(self, 'text_window'):
            self.text_window.hide()
            
        if self.waiting_for_selection:
            return
            
        self.process_btn.setText("Select text now...")
        self.process_btn.setEnabled(False)
        self.waiting_for_selection = True
        
        # Start selection in a separate thread
        threading.Thread(target=self.wait_for_selection, daemon=True).start()

    def wait_for_selection(self):
        """等待文本选择并处理"""
        try:
            self.mouse_down = False
            self.is_selecting = False  # 标记是否正在进行选择操作
            
            def on_click(x, y, button, pressed):
                # Debounce/throttle logic:
                # Only trigger selection if the mouse is held for >0.5s (long press)
                # and the mouse is moved more than 10px before release.
                # This prevents rapid or accidental clicks from triggering selection.
                if button == mouse.Button.left:
                    if pressed:
                        # Record mouse down time and position
                        self.mouse_down = True
                        self.mouse_down_time = time.time()
                        self.mouse_down_pos = (x, y)

                        # Start a thread to check for long press
                        def check_long_press():
                            time.sleep(0.5)  # Wait 0.5s
                            if self.mouse_down:  # If still pressed, treat as long press
                                self.is_selecting = True
                                logger.debug("Long press detected, user is selecting text...")

                        threading.Thread(target=check_long_press, daemon=True).start()

                    else:  # Mouse released
                        if self.mouse_down and self.is_selecting:
                            # Calculate mouse movement distance
                            current_pos = (x, y)
                            move_distance = ((current_pos[0] - self.mouse_down_pos[0]) ** 2 +
                                          (current_pos[1] - self.mouse_down_pos[1]) ** 2) ** 0.5

                            # Only trigger if moved more than 10px (movement threshold)
                            if move_distance > 10:
                                selected_text = self.clipboard.get_selected_text()
                                if selected_text:
                                    logger.debug(f"Selection complete, moved {move_distance:.1f}px: {selected_text[:100]}...")
                                    self.waiting_for_selection = False
                                    # Process text in a new thread
                                    threading.Thread(
                                        target=self._process_text_thread,
                                        args=(selected_text,),
                                        daemon=True
                                    ).start()
                                    return False  # Stop listener
                            else:
                                logger.debug(f"Ignored selection without movement ({move_distance:.1f}px)")

                        # Reset state variables (note: thread safety may be needed if accessed from multiple threads)
                        self.mouse_down = False
                        self.is_selecting = False
                        self.mouse_down_time = None
                        self.mouse_down_pos = None
            
            # 启动鼠标监听
            with mouse.Listener(on_click=on_click) as listener:
                listener.join()
                
        except Exception as e:
            logger.error(f"Error waiting for selection: {e}")
            self.show_error.emit("Error", f"Error waiting for selection: {e}")
        finally:
            self.selection_finished.emit()

    def _process_text_thread(self, text: str):
        """Process text in a separate thread"""
        try:
            self.processing = True
            self.progress_updated.emit(0)  # Signal start
            logger.debug("Starting text processing...")
            
            # Get current prompt template
            current_prompt = self.prompt_combo.currentText()
            logger.debug(f"Selected prompt: {current_prompt}")
            
            if current_prompt not in self.llm_prompts:
                raise ValueError(f"Selected prompt '{current_prompt}' not found in available prompts")
                
            prompt_info = self.llm_prompts[current_prompt]
            if not isinstance(prompt_info, dict):
                raise ValueError(f"Invalid prompt format for '{current_prompt}'")
                
            template = prompt_info.get('template')
            # use_rag = prompt_info.get('use_rag', False) # RAG is being removed
            # logger.debug(f"Using template with RAG={use_rag}") # RAG is being removed
            
            # Get text from clipboard
            if not text:
                text = QApplication.clipboard().text()
            if not text:
                raise ValueError("No text selected")
            
            logger.debug(f"Processing text: {text[:100]}...")

            # Initialize messages array for the LLM
            messages = []
            
            # The template (from prompt_info.get('template')) is the system instruction.
            # No RAG context injection.
            system_message_content = template.strip()
            
            # If the template is empty, provide a default system prompt.
            # The previous logic for handling "{text}" in template is removed as RAG and its specific placeholder logic are gone.
            # The user is now guided by the PromptEditor help text to write the template as the full system instruction.
            if not system_message_content:
                system_message_content = "Process the following text based on your general knowledge and capabilities."

            # Add system prompt
            messages.append({"role": "system", "content": system_message_content})
            
            # Add user's selected text as a user message
            messages.append({"role": "user", "content": text})

            logger.debug(f"Constructed messages: {messages}")

            # Process with LLM
            logger.debug(f"Sending request to {self.client_type}")
            if self.client_type == "ollama":
                # Ensure OllamaClient's chat_completion_sync is used
                response = self.client.chat_completion_sync(
                    model=self.settings.get('model', 'mistral'),
                    messages=messages
                    # temperature removed - will be controlled from Ollama host
                )
                # Assuming chat_completion_sync returns a dict with 'message': {'content': ...}
                processed_text = response['message']['content']
            else:  # LM Studio
                response = self.client.chat_completion_sync(
                    messages=messages,
                    model=self.settings.get('model', 'mistral')
                    # temperature removed - will be controlled from LM Studio host
                )
                processed_text = response['choices'][0]['message']['content']
            
            logger.debug("Received response from LLM")
            
            # Emit processed text
            self.text_processed.emit(processed_text)
            self.progress_updated.emit(100)  # Signal completion
            
        except Exception as e:
            error_msg = f"Error processing text: {str(e)}"
            logger.error(error_msg)
            self.show_error.emit(error_msg)
        finally:
            self.processing = False
            self.process_complete.emit()

    def update_button_state(self):
        """Update button state"""
        try:
            if not self.processing:
                # Get current prompt data
                current_prompt = self.prompt_combo.currentText()
                prompt_data = llm_prompts.get(current_prompt, {})
                
                # Check prompt settings
                use_rag = False
                is_quick_review = False
                if isinstance(prompt_data, dict):
                    use_rag = prompt_data.get('use_rag', False)
                    is_quick_review = prompt_data.get('quick_review', False)
                
                # Update button text based on settings
                if is_quick_review:
                    button_text = "🔍 Quick Review Text"
                elif use_rag:
                    button_text = "💫 Process Text (with RAG)"
                else:
                    button_text = "⚡ Process Text"
                    
                self.process_btn.setText(button_text)
                self.process_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"Error updating button state: {e}")

    def _filter_reasoning_chain(self, text: str) -> str:
        """Filter out reasoning model's chain of thoughts.
        
        Args:
            text: Input text that may contain reasoning chains
            
        Returns:
            Text with reasoning chains removed
        """
        try:
            import re
            # Remove any text between <think> and </think> tags including the tags
            filtered_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            # Remove any extra whitespace that may have been left
            filtered_text = re.sub(r'\n\s*\n', '\n\n', filtered_text)
            filtered_text = filtered_text.strip()
            return filtered_text
        except Exception as e:
            logger.error(f"Error filtering reasoning chain: {e}")
            return text

    def _handle_processed_text(self, text: str):
        """Handle processed text in the main thread"""
        try:
            if not text:
                logger.warning("Received empty processed text")
                return
            
            # Get current prompt info
            current_prompt = self.prompt_combo.currentText()
            prompt_info = llm_prompts.get(current_prompt, {})
            is_quick_review = prompt_info.get('quick_review', False) if isinstance(prompt_info, dict) else False
            
            logger.debug(f"Handling processed text for prompt '{current_prompt}' (quick_review={is_quick_review})")
            
            # Filter out reasoning chains
            filtered_text = self._filter_reasoning_chain(text)
            
            if is_quick_review:
                # Show in text window
                self.text_window.setText(filtered_text)
                self.text_window.updatePosition()
                self.text_window.show()
                logger.debug("Showing text in display window")
            else:
                # Replace selected text as before
                logger.info("Replacing selected text...")
                self.clipboard.replace_selected_text(filtered_text)
                logger.info("Text replacement complete")
                
        except Exception as e:
            logger.error(f"Error handling processed text: {e}")
            self._show_error_dialog(f"Error handling text: {e}")

    def _reset_ui(self):
        """Reset UI state"""
        try:
            self.waiting_for_selection = False
            self.process_btn.setText("✨ Process Selected Text")
            self.process_btn.setEnabled(True)
            
            # Hide quick review with animation
            self.hide_quick_review()
            
        except Exception as e:
            logger.error(f"Error resetting UI: {e}")

    def _show_error_dialog(self, message: str):
        """Show error message dialog"""
        try:
            QMessageBox.critical(self, "Error", message)
        except Exception as e:
            logger.error(f"Error showing error dialog: {e}")

    def closeEvent(self, event):
        """Handle window close event"""
        try:
            if hasattr(self, 'text_window'):
                self.text_window.close()
            self.waiting_for_selection = False
            self.processing = False
            super().closeEvent(event)
        except Exception as e:
            logger.error(f"Error in close event: {e}")
            event.accept()

    def update_prompts(self, prompt_keys: List[str] = None, prompt_order_ids: List[str] = None):
        """
        Update available prompts and their order. Called by PromptEditor.
        Args:
            prompt_keys: List of prompt names in the new desired order (from editor).
            prompt_order_ids: List of prompt UUIDs in the new desired order (from editor).
        """
        logger.debug(f"Toolbar: update_prompts called. Editor sent prompt_keys: {prompt_keys}, prompt_order_ids: {prompt_order_ids}")

        # Step 1: Reload all prompt data to ensure self.llm_prompts is fresh.
        reloaded_prompts_data, _ = reload_prompts() # reload_prompts returns (dict_by_name, list_of_ids_ordered)
        self.llm_prompts = reloaded_prompts_data.copy()
        logger.debug(f"Toolbar: self.llm_prompts reloaded, now has {len(self.llm_prompts)} entries.")

        # Step 2: Determine the correct ordered list of prompt *names* for self.prompt_order.
        # Prioritize prompt_order_ids from the editor as the source of truth for order.
        ordered_names = []
        if prompt_order_ids and isinstance(prompt_order_ids, list):
            # Create a map from ID to Name using the reloaded self.llm_prompts
            # self.llm_prompts is {name: {id:..., template:...}}
            id_to_name_map = {}
            for name, data in self.llm_prompts.items():
                if isinstance(data, dict) and "id" in data:
                    id_to_name_map[data["id"]] = name
            
            for p_id in prompt_order_ids:
                if p_id in id_to_name_map:
                    prompt_name = id_to_name_map[p_id]
                    if prompt_name in self.llm_prompts: # Ensure the name actually exists in the current prompt data
                        ordered_names.append(prompt_name)
                    else:
                        logger.warning(f"Toolbar: Name '{prompt_name}' (for ID '{p_id}') not in self.llm_prompts. Skipping.")
                else:
                    logger.warning(f"Toolbar: Prompt ID '{p_id}' from editor's prompt_order_ids not found in id_to_name_map. Skipping.")
            
            if ordered_names: # If we successfully built an ordered list from IDs
                self.prompt_order = ordered_names
                logger.info(f"Toolbar: self.prompt_order successfully derived from editor's `prompt_order_ids`: {self.prompt_order}")
            else:
                # This means prompt_order_ids was empty, or all IDs were invalid.
                # The editor also sends prompt_keys (an unordered list of all current prompt names).
                # We should ensure all prompts are at least available, even if order is lost.
                logger.warning("Toolbar: Failed to derive ordered names from `prompt_order_ids`. Will use all available prompt names from reloaded data, order might be lost.")
                self.prompt_order = list(self.llm_prompts.keys()) # Fallback to all known prompt names, unordered.
        
        elif prompt_keys and isinstance(prompt_keys, list) and all(isinstance(name, str) for name in prompt_keys):
            # This case is if prompt_order_ids was NOT provided by the editor, but prompt_keys was.
            # This shouldn't happen with the current editor logic, but as a safeguard:
            logger.warning("Toolbar: `prompt_order_ids` not provided by editor, attempting to use `prompt_keys`. Order might not be as expected by user.")
            valid_names_from_keys = [name for name in prompt_keys if name in self.llm_prompts]
            if valid_names_from_keys:
                self.prompt_order = valid_names_from_keys
            else:
                logger.error("Toolbar: `prompt_keys` also empty or invalid. Falling back to all known prompt names, unordered.")
                self.prompt_order = list(self.llm_prompts.keys())
        else:
            # This means neither prompt_order_ids nor prompt_keys were usable.
            logger.error("Toolbar: Neither `prompt_order_ids` nor `prompt_keys` from editor were usable. Falling back to all known prompt names, unordered.")
            self.prompt_order = list(self.llm_prompts.keys())

        # Ensure self.prompt_order is never empty if self.llm_prompts is not.
        if not self.prompt_order and self.llm_prompts:
            logger.error("Toolbar: self.prompt_order is empty after processing, but self.llm_prompts is not. Critical fallback.")
            self.prompt_order = list(self.llm_prompts.keys())
            
        # Step 3: Update the ComboBox UI.
        self._update_prompt_combo()
        self.update_button_state()
        logger.info(f"Toolbar: Prompts updated. Final self.prompt_order: {self.prompt_order}. Combo items: {[self.prompt_combo.itemText(i) for i in range(self.prompt_combo.count())]}. Current selection: {self.prompt_combo.currentText()}")

    def _update_prompt_combo(self): # Removed prompt_keys_override
        """
        Update the prompt selection QComboBox using self.prompt_order (list of names)
        and self.llm_prompts (dict of prompt data).
        """
        current_selection = self.prompt_combo.currentText()
        self.prompt_combo.clear()
        
        logger.debug(f"Toolbar: _update_prompt_combo using self.prompt_order (names): {self.prompt_order}")

        if not isinstance(self.prompt_order, list) or not all(isinstance(name, str) for name in self.prompt_order):
            logger.error(f"Toolbar: _update_prompt_combo expects self.prompt_order to be a list of strings, but got: {type(self.prompt_order)}. Populating with unordered self.llm_prompts keys.")
            # Fallback if self.prompt_order is not a list of names
            prompts_to_display = list(self.llm_prompts.keys())
        else:
            prompts_to_display = self.prompt_order

        for name in prompts_to_display:
            if name in self.llm_prompts:  # Ensure the prompt name exists in our current data
                self.prompt_combo.addItem(name)
            else:
                logger.warning(f"Toolbar: Prompt name '{name}' from ordered list not found in self.llm_prompts during combo update. Skipping.")
                
        # Restore selection if possible
        if current_selection and self.prompt_combo.findText(current_selection) != -1:
            self.prompt_combo.setCurrentText(current_selection)
            logger.debug(f"Toolbar: Restored previous selection: {current_selection}")
        elif self.prompt_combo.count() > 0:
            self.prompt_combo.setCurrentIndex(0)
            logger.debug(f"Toolbar: Set selection to first item: {self.prompt_combo.currentText()}")
        else:
            logger.warning("Toolbar: Prompt combo is empty after _update_prompt_combo.")
        
        # No need to update stylesheet here unless specifically required for emojis again.
        # The original stylesheet is set in setup_ui.
        self.prompt_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 5px 10px;
                background: white;
                font-size: 14px;
                font-family: "Segoe UI Emoji", "Segoe UI", sans-serif;
            }
            QComboBox:hover {
                border: 1px solid #1976D2;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            QComboBox QAbstractItemView {
                padding: 8px;
                font-size: 14px;
                font-family: "Segoe UI Emoji", "Segoe UI", sans-serif;
                selection-background-color: #E3F2FD;
            }
            QComboBox QAbstractItemView::item {
                min-height: 24px;
                padding: 4px 8px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #E3F2FD;
            }
        """)

    def update_client(self, new_client):
        """Update the LLM client when backend changes"""
        try:
            self.client = new_client
            logging.info("Floating toolbar client updated successfully")
        except Exception as e:
            logging.error(f"Error updating floating toolbar client: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update client: {e}")

    def _update_breathing(self):
        """Update the breathing animation effect with rainbow colors"""
        if not hasattr(self, 'processing'):
            self.processing = False
            
        if self.processing:
            # Update gradient position for rainbow effect
            self.gradient_position = (self.gradient_position + 0.005) % 1.0
            
            # Calculate rainbow colors
            hue = self.gradient_position * 360
            r, g, b = self._hsl_to_rgb(hue, 1.0, 0.5)
            
            # Update breathing value
            if self.breathing_increasing:
                self.breathing_value = min(255, self.breathing_value + 0.5)
                if self.breathing_value >= 255:
                    self.breathing_increasing = False
            else:
                self.breathing_value = max(100, self.breathing_value - 0.5)
                if self.breathing_value <= 100:
                    self.breathing_increasing = True
            
            # Apply brightness to colors
            r, g, b = self._adjust_brightness(r, g, b)
            
            # Create gradient background with fixed dimensions
            base_style = """
                QLabel {
                    color: white;
                    padding: 5px;
                    min-width: 120px;
                    min-height: 20px;
                    height: 30px;
                    width: 120px;
                    margin: 0px;
                    border-radius: 5px;
                    font-weight: bold;
                }
            """
            
            gradient_style = base_style + f"""
                QLabel {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgb({r}, {g}, {b}),
                        stop:1 rgb({r//2}, {g//2}, {b//2}));
                }}
            """
            self.progress_label.setStyleSheet(gradient_style)
        else:
            # Reset to default style when not processing
            self.progress_label.setStyleSheet("""
                QLabel {
                    color: #1976D2;
                    padding: 5px;
                    min-width: 120px;
                    min-height: 20px;
                    height: 30px;
                    width: 120px;
                    margin: 0px;
                    background: #f5f5f5;
                    border-radius: 5px;
                    font-weight: bold;
                }
            """)
    
    def _hsl_to_rgb(self, h, s, l):
        """Convert HSL color values to RGB"""
        c = (1 - abs(2 * l - 1)) * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = l - c/2
        
        if 0 <= h < 60:
            r, g, b = c, x, 0
        elif 60 <= h < 120:
            r, g, b = x, c, 0
        elif 120 <= h < 180:
            r, g, b = 0, c, x
        elif 180 <= h < 240:
            r, g, b = 0, x, c
        elif 240 <= h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
            
        return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))
    
    def _adjust_brightness(self, r, g, b):
        """Adjust RGB color brightness"""
        brightness = self.breathing_value / 255
        return (
            int(r * brightness),
            int(g * brightness),
            int(b * brightness)
        )
    
    def _update_progress(self, progress: int):
        """Update the progress label"""
        base_style = """
            QLabel {
                color: #1976D2;
                padding: 5px;
                min-width: 120px;
                min-height: 20px;
                height: 30px;
                width: 120px;
                margin: 0px;
                border-radius: 5px;
                font-weight: bold;
            }
        """
        
        if progress == -1:  # Clear progress
            self.breathing_timer.stop()
            self.progress_label.setText("🚀 Ready")
            self.progress_label.setStyleSheet(base_style + """
                QLabel {
                    background: #f5f5f5;
                }
            """)
        elif progress == 0:  # Starting
            self.progress_label.setText("🔄 Processing")
            self.breathing_timer.start()  # Start breathing animation
            self.gradient_position = 0.0  # Reset gradient position
        elif progress == 100:  # Complete
            self.breathing_timer.stop()
            self.progress_label.setText("✨ Complete!")
            self.progress_label.setStyleSheet(base_style + """
                QLabel {
                    color: #4CAF50;
                    background: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 #E8F5E9,
                        stop: 0.5 #C8E6C9,
                        stop: 1 #E8F5E9
                    );
                }
            """)
        else:  # Processing
            if not self.breathing_timer.isActive():
                self.breathing_timer.start()
                self.gradient_position = 0.0  # Reset gradient position
            self.progress_label.setText("🔄 Processing")

    def setup_quick_review_drawer(self):
        """Setup the quick review panel with animation"""
        # Create container frame for the drawer
        self.drawer_container = QFrame(self.centralWidget())  # Attach to central widget
        self.drawer_container.setObjectName("drawerContainer")
        self.drawer_container.setFixedWidth(400)  # Double the main toolbar width
        
        # Create layout for the container
        container_layout = QVBoxLayout(self.drawer_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Create the review panel
        self.quick_review_panel = QFrame()
        self.quick_review_panel.setObjectName("quickReviewPanel")
        self.quick_review_panel.setMaximumHeight(0)  # Initially collapsed
        
        # Create layout for the panel
        panel_layout = QVBoxLayout(self.quick_review_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(8)
        
        # Create text display
        self.review_text = QTextEdit()
        self.review_text.setReadOnly(True)
        self.review_text.setMinimumWidth(380)  # Set minimum width for text area
        self.review_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 8px;
                font-size: 13px;
                font-family: "Segoe UI", sans-serif;
                color: #333;
            }
        """)
        panel_layout.addWidget(self.review_text)
        
        # Style the panel
        self.quick_review_panel.setStyleSheet("""
            QFrame#quickReviewPanel {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                margin: 5px;
            }
        """)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self.quick_review_panel)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.quick_review_panel.setGraphicsEffect(shadow)
        
        # Add panel to container
        container_layout.addWidget(self.quick_review_panel)
        
        # Add container to main layout
        self.main_layout.addWidget(self.drawer_container)
        
        # Setup animation
        self.drawer_animation = QPropertyAnimation(self.quick_review_panel, b"maximumHeight")
        self.drawer_animation.setDuration(300)  # 300ms animation
        self.drawer_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # Initialize state
        self.is_drawer_visible = False
        self.drawer_container.hide()

    def show_quick_review(self, text: str):
        """Show the quick review panel with animation"""
        try:
            if not hasattr(self, 'quick_review_panel'):
                logger.error("Quick review panel not initialized")
                return
            
            logger.debug(f"Showing quick review panel with text: {text[:100]}...")
            
            # Set the text first
            self.review_text.setText(text)
            
            # Show container and panel
            self.drawer_container.show()
            self.quick_review_panel.show()
            
            # Calculate required height based on text content
            doc_size = self.review_text.document().size()
            text_height = doc_size.height() + 40  # Add padding
            panel_height = min(max(text_height, 150), 600)  # Min 150px, Max 600px
            
            logger.debug(f"Calculated panel height: {panel_height}px")
            
            # Animate the drawer opening
            if not self.is_drawer_visible:
                self.drawer_animation.setStartValue(0)
                self.drawer_animation.setEndValue(panel_height)
                self.drawer_animation.finished.connect(lambda: self._animation_finished(True))
                self.drawer_animation.start()
            
        except Exception as e:
            logger.error(f"Error showing quick review: {e}")
            self._show_error_dialog(f"Error showing quick review: {e}")

    def hide_quick_review(self):
        """Hide the quick review panel with animation"""
        try:
            if self.is_drawer_visible:
                self.drawer_animation.setStartValue(self.quick_review_panel.height())
                self.drawer_animation.setEndValue(0)
                self.drawer_animation.finished.connect(lambda: self._animation_finished(False))
                self.drawer_animation.start()
                
        except Exception as e:
            logger.error(f"Error hiding quick review: {e}")

    def _animation_finished(self, is_open: bool):
        """Handle animation completion"""
        try:
            self.is_drawer_visible = is_open
            if not is_open:
                self.quick_review_panel.hide()
                self.drawer_container.hide()
            
            # Disconnect the finished signal
            self.drawer_animation.finished.disconnect()
            
            logger.debug(f"Drawer animation finished. Drawer is {'open' if is_open else 'closed'}")
            
        except Exception as e:
            logger.error(f"Error in animation finished handler: {e}")

    def moveEvent(self, event):
        """Handle toolbar movement"""
        super().moveEvent(event)
        # Update text window position if visible
        if hasattr(self, 'text_window') and self.text_window.isVisible():
            self.text_window.updatePosition()

class FloatingMiniWindow(QMainWindow):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        
        # 设置窗口属性
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建小按钮
        btn = QPushButton("✨")
        btn.setFixedWidth(30)
        btn.clicked.connect(self.parent.restore_toolbar)
        layout.addWidget(btn)
        
        # 拖动相关变量
        self.drag_position = None
        
        # 设置鼠标追踪
        self.setMouseTracking(True)
        
    def mousePressEvent(self, event):
        """开始拖动窗口"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """处理窗口拖动"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    