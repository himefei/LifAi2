from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QPushButton, QFrame, QMessageBox,
                            QTextEdit, QApplication)
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
    process_complete = pyqtSignal()

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
        
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建标题栏
        title_frame = QFrame()
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("🤖 LifAi2")
        title_layout.addWidget(title_label)
        
        # 最小化按钮
        min_btn = QPushButton("⎯")
        min_btn.setFixedWidth(30)
        min_btn.clicked.connect(self.minimize_toolbar)
        title_layout.addWidget(min_btn)
        
        main_layout.addWidget(title_frame)
        
        # 创建提示选择下拉框
        self.prompt_combo = QComboBox()
        self.prompt_combo.addItems(list(llm_prompts.keys()))
        main_layout.addWidget(self.prompt_combo)
        
        # 创建测试按钮 (with RAG)
        self.test_btn = QPushButton("🔍 Analyze Ticket (with RAG)")
        self.test_btn.clicked.connect(self.start_test_enhancement)
        main_layout.addWidget(self.test_btn)
        
        # 创建增强按钮
        self.enhance_btn = QPushButton("💫 Enhance Text (with RAG)")
        self.enhance_btn.clicked.connect(self.start_enhancement)
        main_layout.addWidget(self.enhance_btn)
        
        # 创建直接处理按钮
        self.direct_enhance_btn = QPushButton("⚡ Quick Enhance (Direct)")
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
        """Process text in a separate thread with RAG support
        
        Args:
            text: Text to process
        """
        try:
            self.processing = True
            
            # Get current prompt template
            current_prompt = self.prompt_combo.currentText()
            prompt_template = llm_prompts[current_prompt]
            
            # Get relevant context from knowledge base
            try:
                doc_count = self.knowledge_base.get_document_count()
                logger.info(f"Current knowledge base contains {doc_count} documents")
                
                logger.info(f"Attempting to retrieve context for text: {text[:100]}...")
                context = self.knowledge_base.get_context(
                    text,
                    k=5,  # Retrieve top 5 most relevant documents
                    threshold=0.3  # Similarity threshold
                )
                
                if context:
                    logger.info(f"Successfully retrieved context: {context[:200]}...")
                else:
                    logger.warning("No relevant context found in knowledge base")
                    context = "No relevant context found in knowledge base."
                    
            except Exception as e:
                logger.error(f"Error retrieving context: {e}")
                context = "Error accessing knowledge base."
            
            # Build system prompt with RAG context
            system_prompt = f"""You are an AI assistant with access to a knowledge base that contains important reference information.

Retrieved Context from Knowledge Base:
{context}

Instructions for Using Knowledge Base:
1. Analyze the knowledge base context and identify relevant information
2. When you find relevant information:
   - Use it to better understand the context and requirements
   - Ensure your response is consistent with the knowledge base
3. For the rest of the text:
   - Process it according to the task description
   - Maintain consistency with the knowledge base information

Remember to maintain the overall flow and style while incorporating knowledge base information."""
            
            try:
                # Handle different client types
                if isinstance(self.client, OllamaClient):  # Ollama client
                    full_prompt = f"{system_prompt}\n\nUser Instructions: {prompt_template}\n\nText to Process: {text}"
                    response = self.client.generate_response(
                        prompt=full_prompt,
                        model=self.settings.get('model', 'mistral')
                    )
                    if response:
                        processed_text = response.strip()
                        logger.info("Successfully generated response from Ollama")
                        self.text_processed.emit(processed_text)
                    else:
                        raise Exception("Invalid response format from Ollama")
                else:  # LM Studio client (OpenAI compatible)
                    # Keep system message very concise
                    system_message = "You are an AI assistant. Here is relevant context (if any):\n" + (context[:500] if context else "No context available.")
                    
                    # Keep user message focused and brief
                    user_message = f"{prompt_template}\n\nText: {text[:1000]}"  # Limit text length
                    
                    messages = [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ]
                    
                    try:
                        response = self.client.chat_completion(
                            messages=messages,
                            model=self.settings.get('model', 'mistral'),
                            temperature=0.7
                        )
                        if response and 'choices' in response and len(response['choices']) > 0:
                            processed_text = response['choices'][0]['message']['content'].strip()
                            logger.info("Successfully generated response from LM Studio")
                            self.text_processed.emit(processed_text)
                        else:
                            raise Exception("Invalid response format from LM Studio")
                    except Exception as e:
                        error_msg = str(e)
                        if "GGML_ASSERT" in error_msg or "model has crashed" in error_msg:
                            logger.error("LM Studio model crashed due to context length")
                            self.show_error.emit("Error", "Text is too long for the model. Try with shorter text or less context.")
                        else:
                            logger.error(f"Error in LM Studio chat completion: {e}")
                            self.show_error.emit("Error", f"LM Studio error: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Error generating response: {e}")
                self.show_error.emit("Error", f"Failed to generate response: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            self.show_error.emit("Error", f"Failed to process text: {str(e)}")
        finally:
            self.processing = False
            self.process_complete.emit()

    def update_button_state(self):
        """更新按钮状态"""
        try:
            if not self.processing:
                self.test_btn.setText("🔍 Analyze Ticket (with RAG)")
                self.test_btn.setEnabled(True)
                self.enhance_btn.setText("💫 Enhance Text (with RAG)")
                self.enhance_btn.setEnabled(True)
                self.direct_enhance_btn.setText("⚡ Quick Enhance (Direct)")
                self.direct_enhance_btn.setEnabled(True)
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
            self.test_btn.setText("🔍 Analyze Ticket (with RAG)")
            self.test_btn.setEnabled(True)
            self.enhance_btn.setText("💫 Enhance Text (with RAG)")
            self.enhance_btn.setEnabled(True)
            self.direct_enhance_btn.setText("⚡ Quick Enhance (Direct)")
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
        """Process text directly without RAG in a separate thread"""
        try:
            self.processing = True
            
            # Get current prompt template
            current_prompt = self.prompt_combo.currentText()
            prompt_template = llm_prompts[current_prompt]
            
            logger.info(f"Using prompt template: {current_prompt}")
            
            # Build system prompt
            system_prompt = "You are an AI assistant that helps improve and enhance text."
            
            # Build user prompt
            user_prompt = f"{prompt_template}\n\nText to Process: {text}\nPlease explicitly follow the task instructions and guidelines to complete the task."
            
            logger.info("Sending prompts to LLM:")
            logger.info(f"System prompt: {system_prompt}")
            logger.info(f"User prompt: {user_prompt}")
            
            try:
                # Handle different client types
                if isinstance(self.client, OllamaClient):  # Ollama client
                    full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
                    response = self.client.generate_response(
                        prompt=full_prompt,
                        model=self.settings.get('model', 'mistral')
                    )
                    if response:
                        processed_text = response.strip()
                        logger.info("Successfully generated response")
                        self.text_processed.emit(processed_text)
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
                        processed_text = response['choices'][0]['message']['content'].strip()
                        logger.info("Successfully generated response from LM Studio")
                        self.text_processed.emit(processed_text)
                    else:
                        raise Exception("Invalid response format from LM Studio")
                    
                logger.info("Successfully processed text")
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
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")

    def start_test_enhancement(self):
        """Start test enhancement with RAG"""
        if self.waiting_for_selection:
            return
            
        self.test_btn.setText("Select text now...")
        self.test_btn.setEnabled(False)
        self.waiting_for_selection = True
        
        # Start selection in a separate thread
        threading.Thread(target=self.wait_for_test_selection, daemon=True).start()

    def wait_for_test_selection(self):
        """Wait for text selection and process with test function"""
        try:
            self.mouse_down = False
            self.is_selecting = False
            
            def on_click(x, y, button, pressed):
                if button == mouse.Button.left:
                    if pressed:
                        self.mouse_down = True
                        self.mouse_down_time = time.time()
                        self.mouse_down_pos = (x, y)
                        
                        def check_long_press():
                            time.sleep(0.5)
                            if self.mouse_down:
                                self.is_selecting = True
                                logger.debug("Long press detected, user is selecting text...")
                        
                        threading.Thread(target=check_long_press, daemon=True).start()
                        
                    else:  # Mouse released
                        if self.mouse_down and self.is_selecting:
                            current_pos = (x, y)
                            move_distance = ((current_pos[0] - self.mouse_down_pos[0]) ** 2 + 
                                          (current_pos[1] - self.mouse_down_pos[1]) ** 2) ** 0.5
                            
                            if move_distance > 10:
                                selected_text = self.clipboard.get_selected_text()
                                if selected_text:
                                    logger.debug(f"Selection complete, moved {move_distance:.1f}px: {selected_text[:100]}...")
                                    self.waiting_for_selection = False
                                    # Process text in a new thread
                                    threading.Thread(
                                        target=self._process_ticket_analysis_thread,  # Use new ticket analysis function
                                        args=(selected_text,),
                                        daemon=True
                                    ).start()
                                    return False
                            else:
                                logger.debug(f"Ignored selection without movement ({move_distance:.1f}px)")
                                
                        self.mouse_down = False
                        self.is_selecting = False
                        self.mouse_down_time = None
                        self.mouse_down_pos = None
            
            with mouse.Listener(on_click=on_click) as listener:
                listener.join()
                
        except Exception as e:
            logger.error(f"Error waiting for selection: {e}")
            self.show_error.emit("Error", f"Error waiting for selection: {e}")
        finally:
            self.selection_finished.emit()

    def _process_ticket_analysis_thread(self, text: str):
        """Process IT support ticket analysis in a separate thread"""
        try:
            self.processing = True
            
            # Get relevant context from knowledge base
            try:
                doc_count = self.knowledge_base.get_document_count()
                logger.info(f"Current knowledge base contains {doc_count} documents")
                
                logger.info(f"Attempting to retrieve context for ticket: {text[:100]}...")
                context = self.knowledge_base.get_context(
                    text,
                    k=5,  # Retrieve top 5 most relevant documents
                    threshold=0.3  # Similarity threshold
                )
                
                if context:
                    logger.info(f"Successfully retrieved context: {context[:200]}...")
                else:
                    logger.warning("No relevant context found in knowledge base")
                    context = "No relevant context found in knowledge base."
                    
            except Exception as e:
                logger.error(f"Error retrieving context: {e}")
                context = "Error accessing knowledge base."
            
            # Build specialized system prompt for IT ticket analysis
            system_prompt = f"""You are an experienced IT Support Analyst. Your task is to analyze customer support tickets and identify missing troubleshooting steps.

Retrieved Context from Knowledge Base:
{context}

Instructions:
1. Analyze the customer's problem description
2. Compare with the knowledge base context
3. Identify what troubleshooting steps have already been taken
4. List what essential troubleshooting steps are missing
5. Format your response as follows:

Original Ticket:
[Original text]

Steps Already Taken:
1. [Step]
2. [Step]
...

Missing Steps:
1. [Step]
2. [Step]
...

Remember to:
- Use proper IT terminology
- Be specific and clear in your recommendations
- Prioritize steps based on standard IT troubleshooting practices
- Consider both basic and advanced troubleshooting steps"""

            try:
                # Handle different client types
                if isinstance(self.client, OllamaClient):  # Ollama client
                    full_prompt = f"{system_prompt}\n\nTicket to Analyze: {text}"
                    response = self.client.generate_response(
                        prompt=full_prompt,
                        model=self.settings.get('model', 'mistral')
                    )
                    if response:
                        processed_text = response.strip()
                        logger.info("Successfully generated ticket analysis")
                        self.text_processed.emit(processed_text)
                    else:
                        raise Exception("Invalid response format from Ollama")
                else:  # LM Studio client (OpenAI compatible)
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Analyze this IT support ticket:\n\n{text}"}
                    ]
                    response = self.client.chat_completion(
                        messages=messages,
                        model=self.settings.get('model', 'mistral'),
                        temperature=0.7
                    )
                    if response and 'choices' in response and len(response['choices']) > 0:
                        processed_text = response['choices'][0]['message']['content'].strip()
                        logger.info("Successfully generated ticket analysis from LM Studio")
                        self.text_processed.emit(processed_text)
                    else:
                        raise Exception("Invalid response format from LM Studio")
                    
                logger.info("Successfully processed ticket analysis")
            except Exception as e:
                logger.error(f"Error calling LLM: {e}")
                self.show_error.emit("Error", f"Error analyzing ticket: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing ticket: {e}")
            logger.exception(e)
            self.show_error.emit("Error", f"Error processing ticket: {str(e)}")
            
        finally:
            try:
                self.processing = False
                self.process_complete.emit()
                self.update_button_state()
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")

    def update_button_state(self):
        """更新按钮状态"""
        try:
            if not self.processing:
                self.test_btn.setText("🔍 Analyze Ticket (with RAG)")
                self.test_btn.setEnabled(True)
                self.enhance_btn.setText("💫 Enhance Text (with RAG)")
                self.enhance_btn.setEnabled(True)
                self.direct_enhance_btn.setText("⚡ Quick Enhance (Direct)")
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

    