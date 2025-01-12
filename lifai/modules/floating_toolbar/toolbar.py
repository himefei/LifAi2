from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QPushButton, QFrame, QMessageBox,
                            QTextEdit)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from typing import Dict
from pynput import mouse
from lifai.utils.ollama_client import OllamaClient
from lifai.utils.logger_utils import get_module_logger
from lifai.config.saved_prompts import llm_prompts
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

    def setup_ui(self):
        """设置界面"""
        # 设置窗口属性
        self.setWindowTitle("LifAi2 Toolbar")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建标题栏
        title_frame = QFrame()
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("✨ LifAi2")
        title_layout.addWidget(title_label)
        
        # 最小化按钮
        min_btn = QPushButton("—")
        min_btn.setFixedWidth(30)
        min_btn.clicked.connect(self.minimize_toolbar)
        title_layout.addWidget(min_btn)
        
        main_layout.addWidget(title_frame)
        
        # 创建提示选择下拉框
        self.prompt_combo = QComboBox()
        self.prompt_combo.addItems(list(llm_prompts.keys()))  # 直接使用 llm_prompts 的键
        main_layout.addWidget(self.prompt_combo)
        
        # 创建增强按钮
        self.enhance_btn = QPushButton("✨ Select & Enhance (with RAG)")
        self.enhance_btn.clicked.connect(self.start_enhancement)
        main_layout.addWidget(self.enhance_btn)
        
        # 创建直接处理按钮
        self.direct_enhance_btn = QPushButton("✨ Select & Enhance (Direct)")
        self.direct_enhance_btn.clicked.connect(self.start_direct_enhancement)
        main_layout.addWidget(self.direct_enhance_btn)
        
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

    def start_enhancement(self):
        """开始文本增强"""
        if self.waiting_for_selection:
            return
            
        self.enhance_btn.setText("Select text now...")
        self.enhance_btn.setEnabled(False)
        self.waiting_for_selection = True
        
        # 在单独的线程中等待选择
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
        """Process text in a separate thread
        
        Args:
            text: Text to process
        """
        try:
            self.processing = True
            
            # Get current prompt template
            current_prompt = self.prompt_combo.currentText()
            prompt_template = llm_prompts[current_prompt]
            
            # Handle different client types
            if isinstance(self.client, OllamaClient):  # Ollama client
                # Build prompt with system and user messages
                full_prompt = f"System: {prompt_template}\n\nUser: {text}"
                response = self.client.generate_response(
                    prompt=full_prompt,
                    model=self.settings.get('model', 'mistral')
                )
                if response:
                    processed_text = response.strip()
                else:
                    raise Exception("Invalid response format from Ollama")
            else:  # LM Studio client (OpenAI compatible)
                messages = [
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": text}
                ]
                response = self.client.chat_completion(
                    messages=messages,
                    model=self.settings.get('model', 'mistral'),
                    temperature=0.7
                )
                if response and 'choices' in response and len(response['choices']) > 0:
                    processed_text = response['choices'][0]['message']['content'].strip()
                else:
                    raise Exception("Invalid response format from LM Studio")
            
            QApplication.instance().postEvent(
                self,
                CustomEvent(lambda: self._handle_processed_text(processed_text))
            )
                
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            QApplication.instance().postEvent(
                self,
                CustomEvent(lambda: self.show_error.emit("Error", f"Failed to process text: {e}"))
            )
        finally:
            self.processing = False
            QApplication.instance().postEvent(
                self,
                CustomEvent(self._reset_ui)
            )

    def update_button_state(self):
        """更新按钮状态"""
        try:
            if not self.processing:
                self.enhance_btn.setText("✨ Select & Enhance (with RAG)")
                self.enhance_btn.setEnabled(True)
                self.direct_enhance_btn.setText("✨ Select & Enhance (Direct)")
                self.direct_enhance_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"Error updating button state: {e}")

    def _handle_processed_text(self, text: str):
        """在主线程中处理处理后的文本"""
        try:
            if not text:
                logger.warning("Received empty processed text")
                return
                
            logger.debug("Replacing selected text...")
            self.clipboard.replace_selected_text(text)
            logger.debug("Text replacement complete")
        except Exception as e:
            logger.error(f"Error replacing text: {e}")
            self.show_error.emit("Error", f"Error replacing text: {e}")

    def _reset_ui(self):
        """在主线程中重置 UI 状态"""
        try:
            self.waiting_for_selection = False
            self.enhance_btn.setText("✨ Select & Enhance (with RAG)")
            self.enhance_btn.setEnabled(True)
            self.direct_enhance_btn.setText("✨ Select & Enhance (Direct)")
            self.direct_enhance_btn.setEnabled(True)
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

    def start_direct_enhancement(self):
        """开始直接文本增强（不使用知识库）"""
        if self.waiting_for_selection:
            return
            
        self.direct_enhance_btn.setText("Select text now...")
        self.direct_enhance_btn.setEnabled(False)
        self.waiting_for_selection = True
        
        # 在单独的线程中等待选择
        threading.Thread(target=self.wait_for_direct_selection, daemon=True).start()
        
    def wait_for_direct_selection(self):
        """等待文本选择并直接处理（不使用知识库）"""
        try:
            self.mouse_down = False
            self.is_selecting = False
            
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
                                        target=self._process_text_direct_thread,
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
            
    def _process_text_direct_thread(self, text: str):
        """Process text directly in a separate thread (without using knowledge base)
        
        Args:
            text: Text to process
        """
        try:
            # Get current prompt template
            try:
                current_prompt = self.prompt_combo.currentText()
                logger.info(f"Using prompt template: {current_prompt}")
                prompt_template = llm_prompts.get(current_prompt, "Please improve this text.")
            except Exception as e:
                logger.error(f"Error getting prompt template: {e}")
                prompt_template = "Please improve this text."
            
            # Build system prompt
            system_prompt = """You are an AI assistant that helps improve and enhance text."""
            
            # Build user prompt
            user_prompt = f"""Task Instructions and Guidelines:
{prompt_template}

Text to Process:
{text}

Please explicitly follow the task instructions and guidelines to complete the task."""
            
            # Call model for response
            try:
                logger.info("Sending prompts to LLM:")
                logger.info(f"System prompt:\n{system_prompt}")
                logger.info(f"User prompt:\n{user_prompt}")
                
                # Handle different client types
                if isinstance(self.client, OllamaClient):  # Ollama client
                    # Combine prompts for Ollama
                    full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
                    response = self.client.generate_response(
                        prompt=full_prompt,
                        model=self.settings.get('model', 'mistral')
                    )
                    if response:
                        result = response.strip()
                    else:
                        raise Exception("Invalid response format from Ollama")
                else:  # LM Studio client (OpenAI compatible)
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                    response = self.client.chat_completion(
                        messages=messages,
                        model=self.settings.get('model', 'mistral'),
                        temperature=0.7
                    )
                    if response and 'choices' in response and len(response['choices']) > 0:
                        result = response['choices'][0]['message']['content'].strip()
                    else:
                        raise Exception("Invalid response format from LM Studio")
                
                logger.info("Successfully processed text")
                self.text_processed.emit(result)
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
                self.update_button_state()
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")
                
    def update_button_state(self):
        """更新按钮状态"""
        try:
            if not self.processing:
                self.enhance_btn.setText("✨ Select & Enhance (with RAG)")
                self.enhance_btn.setEnabled(True)
                self.direct_enhance_btn.setText("✨ Select & Enhance (Direct)")
                self.direct_enhance_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"Error updating button state: {e}")

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

    