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

logger = get_module_logger(__name__)

class FloatingToolbarModule(QMainWindow):
    # 定义信号
    text_processed = pyqtSignal(str)
    selection_finished = pyqtSignal()
    show_error = pyqtSignal(str, str)

    def __init__(self, settings: Dict, ollama_client: OllamaClient):
        super().__init__()
        self.settings = settings
        self.ollama_client = ollama_client
        self.knowledge_base = KnowledgeBase()  # 初始化知识库
        self.clipboard = ClipboardManager()  # 初始化剪贴板管理器
        self.setup_ui()
        self.setup_hotkeys()
        self.hide()
        
        # 连接信号
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
        """在单独的线程中处理文本
        
        Args:
            text: 要处理的文本
        """
        try:
            # 检查知识库状态
            doc_count = self.knowledge_base.get_document_count()
            logger.info(f"Current knowledge base contains {doc_count} documents")
            
            # 获取相关上下文，使用更宽松的参数以获取更多结果
            logger.info(f"Attempting to retrieve context for text: {text[:100]}...")
            
            try:
                # 使用更宽松的参数
                context = self.knowledge_base.get_context(
                    text,
                    k=50,  # 检索更多文档
                    threshold=0.01  # 非常低的阈值，几乎不过滤任何结果
                )
            except Exception as e:
                logger.error(f"Error retrieving context: {e}")
                context = None
            
            if context:
                logger.info(f"Successfully retrieved context: {context[:200]}...")
            else:
                logger.warning("No context retrieved from knowledge base")
            
            # 获取当前选择的提示模板
            try:
                current_prompt = self.prompt_combo.currentText()
                logger.info(f"Using prompt template: {current_prompt}")
                prompt_template = llm_prompts.get(current_prompt, "Please improve this text.")
            except Exception as e:
                logger.error(f"Error getting prompt template: {e}")
                prompt_template = "Please improve this text."
            
            # 构建系统提示词
            system_prompt = """You are an AI assistant with access to a knowledge base that contains important reference information.

Instructions for Using Knowledge Base:
1. FIRST, carefully analyze the knowledge base context and identify relevant information
2. When you find relevant information:
   - Use it to better understand the context and requirements
   - Ensure your response is consistent with the knowledge base
3. For the rest of the text:
   - Process it according to the task description
   - Maintain consistency with the knowledge base information

Remember:
- The knowledge base contains authoritative information - always prefer it when available
- Maintain the overall flow and style while incorporating knowledge base information
- Ensure all terms and concepts are correctly interpreted according to the knowledge base"""
            
            # 构建用户提示词，始终包含上下文部分
            user_prompt = f"""Knowledge Base Context:
{context if context else "No relevant context found in knowledge base."}

Task Instructions and Guidelines:
{prompt_template}

Text to Process:
{text}

Please explicitly follow the task instructions and guidelines, and incorporating any relevant knowledge base information to complete the task."""
            
            # 调用模型生成回复
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                logger.info("Sending prompts to LM Studio:")
                logger.info(f"System prompt:\n{system_prompt}")
                logger.info(f"User prompt:\n{user_prompt}")
                
                response = self.ollama_client.chat_completion(
                    messages=messages,
                    model=self.settings.get('model', 'mistral')
                )
                
                if response and 'choices' in response and len(response['choices']) > 0:
                    result = response['choices'][0]['message']['content'].strip()
                    logger.info("Successfully processed text")
                    self.text_processed.emit(result)  # 使用信号发送结果
                else:
                    logger.error("Failed to process text: Invalid response format")
                    self.show_error.emit("Error", "Failed to generate improved text")
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
        """在单独的线程中直接处理文本（不使用知识库）
        
        Args:
            text: 要处理的文本
        """
        try:
            # 获取当前选择的提示模板
            try:
                current_prompt = self.prompt_combo.currentText()
                logger.info(f"Using prompt template: {current_prompt}")
                prompt_template = llm_prompts.get(current_prompt, "Please improve this text.")
            except Exception as e:
                logger.error(f"Error getting prompt template: {e}")
                prompt_template = "Please improve this text."
            
            # 构建系统提示词
            system_prompt = """You are an AI assistant that helps improve and enhance text."""
            
            # 构建用户提示词
            user_prompt = f"""Task Instructions and Guidelines:
{prompt_template}

Text to Process:
{text}

Please explicitly follow the task instructions and guidelines to complete the task."""
            
            # 调用模型生成回复
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                logger.info("Sending prompts to LM Studio:")
                logger.info(f"System prompt:\n{system_prompt}")
                logger.info(f"User prompt:\n{user_prompt}")
                
                response = self.ollama_client.chat_completion(
                    messages=messages,
                    model=self.settings.get('model', 'mistral')
                )
                
                if response and 'choices' in response and len(response['choices']) > 0:
                    result = response['choices'][0]['message']['content'].strip()
                    logger.info("Successfully processed text")
                    self.text_processed.emit(result)  # 使用信号发送结果
                else:
                    logger.error("Failed to process text: Invalid response format")
                    self.show_error.emit("Error", "Failed to generate improved text")
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

    