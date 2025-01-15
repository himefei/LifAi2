from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QPushButton, QFrame, QMessageBox,
                            QTextEdit, QApplication, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor
from typing import Dict
from pynput import mouse
from lifai.utils.ollama_client import OllamaClient
from lifai.utils.logger_utils import get_module_logger
from lifai.config.prompts import llm_prompts
from lifai.utils.clipboard_utils import ClipboardManager
from lifai.utils.knowledge_base import KnowledgeBase
import time
import threading
import logging

logger = get_module_logger(__name__)

class FloatingToolbarModule(QMainWindow):
    # Define signals at class level
    text_processed = pyqtSignal(str)
    selection_finished = pyqtSignal()
    show_error = pyqtSignal(str, str)
    process_complete = pyqtSignal()
    progress_updated = pyqtSignal(int)  # New signal for progress updates

    def __init__(self, settings: Dict, ollama_client: OllamaClient):
        super().__init__()
        self.settings = settings
        self.client = ollama_client  # Rename to be more generic
        self.processing = False
        self.clipboard = ClipboardManager()
        self.knowledge_base = KnowledgeBase()  # Initialize knowledge base
        self.setup_ui()
        self.setup_hotkeys()
        self.hide()
        
        # Connect signals
        self.text_processed.connect(self._handle_processed_text)
        self.selection_finished.connect(self._reset_ui)
        self.show_error.connect(self._show_error_dialog)
        self.process_complete.connect(self._reset_ui)

    def setup_ui(self):
        """设置界面"""
        # 设置窗口属性
        self.setWindowTitle("LifAi2 Toolbar")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # Enable transparency for rounded corners
        
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)  # Increased spacing for modern look
        
        # Create main frame with rounded corners and shadow
        main_frame = QFrame()
        main_frame.setObjectName("mainFrame")
        main_frame.setStyleSheet("""
            QFrame#mainFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
        """)
        frame_layout = QVBoxLayout(main_frame)
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
        self.prompt_combo.addItems(list(llm_prompts.keys()))
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
                background: white;
            }
        """)
        progress_layout = QHBoxLayout(progress_frame)
        progress_layout.setContentsMargins(5, 2, 5, 2)
        
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #1976D2;
                font-weight: bold;
                min-height: 20px;
                background-color: #f5f5f5;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        progress_layout.addWidget(self.progress_label)
        frame_layout.addWidget(progress_frame)
        
        # Setup breathing and rainbow animation
        self.breathing_timer = QTimer()
        self.breathing_timer.timeout.connect(self._update_breathing)
        self.breathing_timer.setInterval(16)  # ~60fps for smoother animation
        self.breathing_in = True
        self.breathing_value = 245
        self.gradient_position = 0.0  # Position for gradient animation
        
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
        main_layout.addWidget(main_frame)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 50))
        main_frame.setGraphicsEffect(shadow)
        
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
                if button == mouse.Button.left:
                    if pressed:
                        # 记录鼠标按下的时间和位置
                        self.mouse_down = True
                        self.mouse_down_time = time.time()
                        self.mouse_down_pos = (x, y)
                        
                        # 启动一个线程来检测长按
                        def check_long_press():
                            time.sleep(0.5)  # 等待0.5秒
                            if self.mouse_down:  # 如果鼠标还在按下状态
                                self.is_selecting = True
                                logger.debug("Long press detected, user is selecting text...")
                        
                        threading.Thread(target=check_long_press, daemon=True).start()
                        
                    else:  # 鼠标释放
                        if self.mouse_down and self.is_selecting:
                            # 计算鼠标移动距离
                            current_pos = (x, y)
                            move_distance = ((current_pos[0] - self.mouse_down_pos[0]) ** 2 + 
                                          (current_pos[1] - self.mouse_down_pos[1]) ** 2) ** 0.5
                            
                            # 如果确实发生了移动
                            if move_distance > 10:  # 10像素的移动阈值
                                selected_text = self.clipboard.get_selected_text()
                                if selected_text:
                                    logger.debug(f"Selection complete, moved {move_distance:.1f}px: {selected_text[:100]}...")
                                    self.waiting_for_selection = False
                                    # 在新线程中处理文本
                                    threading.Thread(
                                        target=self._process_text_thread,
                                        args=(selected_text,),
                                        daemon=True
                                    ).start()
                                    return False  # 停止监听
                            else:
                                logger.debug(f"Ignored selection without movement ({move_distance:.1f}px)")
                                
                        # 重置状态
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
        """Process text in a separate thread using the selected prompt template"""
        try:
            self.processing = True
            self.progress_updated.emit(0)  # Start progress
            
            # Get current prompt template
            current_prompt = self.prompt_combo.currentText()
            prompt_data = llm_prompts[current_prompt]
            
            self.progress_updated.emit(10)  # Got prompt
            
            # Check if prompt is in new format
            if isinstance(prompt_data, dict):
                prompt_template = prompt_data['template']
                use_rag = prompt_data.get('use_rag', False)
            else:  # Legacy format
                prompt_template = prompt_data
                use_rag = False
            
            self.progress_updated.emit(20)  # Checked format
            
            context = ""
            # Only retrieve context if RAG is enabled for this prompt
            if use_rag:
                try:
                    doc_count = self.knowledge_base.get_document_count()
                    logger.info(f"Current knowledge base contains {doc_count} documents")
                    
                    self.progress_updated.emit(30)  # Starting RAG
                    
                    logger.info(f"Attempting to retrieve context for text: {text[:100]}...")
                    context = self.knowledge_base.get_context(
                        text,
                        k=5,  # Retrieve top 5 most relevant documents
                        threshold=0.3  # Similarity threshold
                    )
                    
                    self.progress_updated.emit(50)  # Got RAG context
                    
                    if context:
                        logger.info(f"Successfully retrieved context: {context[:200]}...")
                    else:
                        logger.warning("No relevant context found in knowledge base")
                        context = "No relevant context found in knowledge base."
                        
                except Exception as e:
                    logger.error(f"Error retrieving context: {e}")
                    context = "Error accessing knowledge base."
            else:
                self.progress_updated.emit(50)  # Skip RAG progress
            
            # Replace placeholders in the prompt template
            formatted_prompt = prompt_template.format(
                text=text,
                context=context
            )
            
            self.progress_updated.emit(60)  # Formatted prompt
            
            try:
                # Handle different client types
                if isinstance(self.client, OllamaClient):  # Ollama client
                    self.progress_updated.emit(70)  # Starting LLM
                    response = self.client.generate_response(
                        prompt=formatted_prompt,
                        model=self.settings.get('model', 'mistral')
                    )
                    if response:
                        processed_text = response.strip()
                        logger.info("Successfully generated response")
                        self.progress_updated.emit(90)  # Got response
                        self.text_processed.emit(processed_text)
                    else:
                        raise Exception("Invalid response format from Ollama")
                else:  # LM Studio client (OpenAI compatible)
                    self.progress_updated.emit(70)  # Starting LLM
                    messages = [
                        {"role": "system", "content": "You are an AI assistant that helps process text."},
                        {"role": "user", "content": formatted_prompt}
                    ]
                    response = self.client.chat_completion(
                        messages=messages,
                        model=self.settings.get('model', 'mistral'),
                        temperature=0.7
                    )
                    if response and 'choices' in response and len(response['choices']) > 0:
                        processed_text = response['choices'][0]['message']['content'].strip()
                        logger.info("Successfully generated response from LM Studio")
                        self.progress_updated.emit(90)  # Got response
                        self.text_processed.emit(processed_text)
                    else:
                        raise Exception("Invalid response format from LM Studio")
                    
                logger.info("Successfully processed text")
                self.progress_updated.emit(100)  # Complete
            except Exception as e:
                logger.error(f"Error calling LLM: {e}")
                self.show_error.emit("Error", f"Error calling language model: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing text: {e}")
            logger.exception(e)
            self.show_error.emit("Error", f"Error processing text: {str(e)}")
            
        finally:
            try:
                self.processing = False
                self.process_complete.emit()
                self.update_button_state()
                self.progress_updated.emit(-1)  # Clear progress
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")

    def update_button_state(self):
        """更新按钮状态"""
        try:
            if not self.processing:
                # Get current prompt data to check if RAG is enabled
                current_prompt = self.prompt_combo.currentText()
                prompt_data = llm_prompts.get(current_prompt, {})
                
                # Check if RAG is enabled for this prompt
                use_rag = False
                if isinstance(prompt_data, dict):
                    use_rag = prompt_data.get('use_rag', False)
                
                # Update button text based on RAG status
                button_text = "💫 Process Text (with RAG)" if use_rag else "⚡ Process Text"
                self.process_btn.setText(button_text)
                self.process_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"Error updating button state: {e}")

    def _handle_processed_text(self, text: str):
        """Handle processed text in the main thread"""
        try:
            if not text:
                logger.warning("Received empty processed text")
                return
                
            logger.info("Replacing selected text...")
            self.clipboard.replace_selected_text(text)
            logger.info("Text replacement complete")
        except Exception as e:
            logger.error(f"Error replacing text: {e}")
            self.show_error.emit("Error", f"Error replacing text: {e}")

    def _reset_ui(self):
        """在主线程中重置 UI 状态"""
        try:
            self.waiting_for_selection = False
            self.process_btn.setText("✨ Process Selected Text")
            self.process_btn.setEnabled(True)
            self.show()
        except Exception as e:
            logger.error(f"Error resetting UI: {e}")

    def _show_error_dialog(self, title: str, message: str):
        """在主线程中显示错误对话框"""
        try:
            QMessageBox.critical(self, title, message)
        except Exception as e:
            logger.error(f"Error showing error dialog: {e}")

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        try:
            # 清理资源
            self.waiting_for_selection = False
            self.processing = False
            super().closeEvent(event)
        except Exception as e:
            logger.error(f"Error in close event: {e}")
            event.accept()

    def update_prompts(self, prompt_keys=None):
        """更新提示词列表
        
        Args:
            prompt_keys: 可选的提示词键列表，如果为None则使用全局llm_prompts
        """
        try:
            # 保存当前选择
            current_text = self.prompt_combo.currentText()
            
            # 清空并重新填充
            self.prompt_combo.clear()
            if prompt_keys is not None:
                self.prompt_combo.addItems(prompt_keys)
            else:
                self.prompt_combo.addItems(list(llm_prompts.keys()))
            
            # 尝试恢复之前的选择
            index = self.prompt_combo.findText(current_text)
            if index >= 0:
                self.prompt_combo.setCurrentIndex(index)
            elif self.prompt_combo.count() > 0:
                self.prompt_combo.setCurrentIndex(0)
            
            # Update button text based on current prompt
            self.update_button_state()
                
            logger.info("Prompts list updated in floating toolbar")
        except Exception as e:
            logger.error(f"Error updating prompts in floating toolbar: {e}")

    def update_client(self, new_client):
        """Update the LLM client when backend changes"""
        try:
            self.client = new_client
            logging.info("Floating toolbar client updated successfully")
        except Exception as e:
            logging.error(f"Error updating floating toolbar client: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update client: {e}")

    def _update_breathing(self):
        """Update the breathing and rainbow gradient animation effect"""
        # Update breathing effect
        if self.breathing_in:
            self.breathing_value = max(235, self.breathing_value - 0.5)  # Even slower breathing
            if self.breathing_value <= 235:
                self.breathing_in = False
        else:
            self.breathing_value = min(245, self.breathing_value + 0.5)  # Even slower breathing
            if self.breathing_value >= 245:
                self.breathing_in = True
        
        # Update gradient position (complete cycle in 5 seconds)
        self.gradient_position = (self.gradient_position + 0.012) % 1.0  # 16ms * ~312 steps = 5000ms
        
        def get_rainbow_color(pos):
            """Get rainbow color for position (0-1)"""
            pos = pos % 1.0
            # Use more color stops for smoother transitions
            if pos < 0.166:  # Red to Yellow
                r = 255
                g = int(pos * 6 * 255)
                b = 0
            elif pos < 0.332:  # Yellow to Green
                r = int((0.332 - pos) * 6 * 255)
                g = 255
                b = 0
            elif pos < 0.498:  # Green to Cyan
                r = 0
                g = 255
                b = int((pos - 0.332) * 6 * 255)
            elif pos < 0.664:  # Cyan to Blue
                r = 0
                g = int((0.664 - pos) * 6 * 255)
                b = 255
            elif pos < 0.83:  # Blue to Purple
                r = int((pos - 0.664) * 6 * 255)
                g = 0
                b = 255
            else:  # Purple to Red
                r = 255
                g = 0
                b = int((1.0 - pos) * 6 * 255)
            return r, g, b

        def adjust_brightness(r, g, b):
            """Adjust RGB color brightness"""
            brightness = self.breathing_value / 255
            return (
                int(r * brightness),
                int(g * brightness),
                int(b * brightness)
            )
        
        # Calculate colors for gradient (use 5 points for smoother transition)
        positions = [
            self.gradient_position,
            (self.gradient_position + 0.2) % 1.0,
            (self.gradient_position + 0.4) % 1.0,
            (self.gradient_position + 0.6) % 1.0,
            (self.gradient_position + 0.8) % 1.0
        ]
        
        colors = [get_rainbow_color(pos) for pos in positions]
        
        # Apply brightness based on breathing
        colors = [adjust_brightness(*c) for c in colors]
        
        # Create smooth gradient effect with more color stops
        gradient_stops = ", ".join([
            f"stop: {i/4} rgb({r}, {g}, {b})"
            for i, (r, g, b) in enumerate(colors)
        ])
        
        gradient = f"""
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                {gradient_stops}
            );
        """
        
        self.progress_label.setStyleSheet(f"""
            QLabel {{
                color: #1976D2;
                font-weight: bold;
                min-height: 20px;
                {gradient}
                border-radius: 3px;
                padding: 2px;
            }}
        """)

    def _update_progress(self, progress: int):
        """Update the progress label"""
        if progress == -1:  # Clear progress
            self.breathing_timer.stop()
            self.progress_label.setText("🚀 Ready")
            self.progress_label.setStyleSheet("""
                QLabel {
                    color: #1976D2;
                    font-weight: bold;
                    min-height: 20px;
                    background-color: #f5f5f5;
                    border-radius: 3px;
                    padding: 2px;
                }
            """)
        elif progress == 0:  # Starting
            self.progress_label.setText("🔄 Processing")
            self.breathing_timer.start()  # Start breathing animation
            self.gradient_position = 0.0  # Reset gradient position
        elif progress == 100:  # Complete
            self.breathing_timer.stop()
            self.progress_label.setText("✨ Complete!")
            self.progress_label.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-weight: bold;
                    min-height: 20px;
                    background: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 #E8F5E9,
                        stop: 0.5 #C8E6C9,
                        stop: 1 #E8F5E9
                    );
                    border-radius: 3px;
                    padding: 2px;
                }
            """)
        else:  # Processing
            if not self.breathing_timer.isActive():
                self.breathing_timer.start()
                self.gradient_position = 0.0  # Reset gradient position
            self.progress_label.setText("🔄 Processing")

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

    