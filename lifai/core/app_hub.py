from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QPushButton, QFrame, QTextEdit, QScrollArea,
                            QMessageBox, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QFont
import logging
import os
import sys
import json
from datetime import datetime

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from lifai.utils.ollama_client import OllamaClient
from lifai.utils.lmstudio_client import LMStudioClient
# from lifai.modules.text_improver.improver import TextImproverWindow
from lifai.modules.floating_toolbar.toolbar import FloatingToolbarModule
from lifai.modules.prompt_editor.editor import PromptEditorWindow
# from lifai.modules.knowledge_manager.manager import KnowledgeManagerWindow # RAG Removed
# from lifai.modules.AI_chat.ai_chat import ChatWindow
# from lifai.modules.agent_workspace.workspace import AgentWorkspaceWindow
# from lifai.modules.advagent.advagent_window import AdvAgentWindow

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

def create_robot_icon():
    """Create a robot icon using Windows' Segoe UI Emoji font"""
    # Create a pixmap and fill it with a transparent background
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    # Create a label with the robot emoji
    label = QLabel("🤖")
    
    # Use Segoe UI Emoji font for better Windows emoji rendering
    font = QFont("Segoe UI Emoji", 64)
    label.setFont(font)
    
    # Center the emoji in the pixmap
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFixedSize(128, 128)
    
    # Render the label onto the pixmap
    label.render(pixmap)
    
    return QIcon(pixmap)

class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        
    def append_log(self, msg, level):
        # 设置不同日志级别的颜色
        color = {
            logging.ERROR: '#FF5252',    # 红色
            logging.WARNING: '#FFA726',   # 橙色
            logging.INFO: '#4CAF50',      # 绿色
            logging.DEBUG: '#9E9E9E'      # 灰色
        }.get(level, '#000000')          # 默认黑色
        
        self.append(f'<span style="color: {color}">{msg}</span>')
        # Auto scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

class LogHandler(logging.Handler):
    def __init__(self, widget: LogWidget):
        super().__init__()
        self.widget = widget
        self.formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

    def emit(self, record):
        msg = self.formatter.format(record)
        self.widget.append_log(msg, record.levelno)

class ModuleToggle(QWidget):
    toggled = pyqtSignal(bool)
    
    def __init__(self, title, module_creator=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.title = QLabel(title)
        self.button = QPushButton("Enable")
        self.button.setCheckable(True)
        self.button.clicked.connect(self._on_toggle)
        
        layout.addWidget(self.title)
        layout.addStretch()
        layout.addWidget(self.button)
        
        self.module = None
        self.module_creator = module_creator
        
    def _on_toggle(self, checked):
        self.button.setText("Disable" if checked else "Enable")
        if checked and self.module_creator:
            if not self.module:
                self.module = self.module_creator()
            self.module.show()
        elif self.module:
            self.module.hide()
        self.toggled.emit(checked)
        
    def get(self):
        return self.button.isChecked()

class LifAi2Hub(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Set application icon
        self.setWindowIcon(create_robot_icon())
        
        # Remove default system icon and menu from title bar while keeping other window controls
        self.setWindowFlags(Qt.WindowType.Window | 
                          Qt.WindowType.WindowMinMaxButtonsHint | 
                          Qt.WindowType.WindowCloseButtonHint)
        
        # 初始化客户端
        self.ollama_client = OllamaClient()
        self.lmstudio_client = LMStudioClient()
        
        # 加载配置
        self.config_file = os.path.join(project_root, 'lifai', 'config', 'app_settings.json')
        last_config = self.load_last_config()
        
        # 共享设置
        self.settings = {
            'model': last_config.get('last_model', ''),
            'backend': last_config.get('backend', 'ollama'),
            'models_list': []
        }
        
        self.setup_ui()
        self.modules = {}
        self.initialize_modules()
        
        # 设置窗口标题和大小
        self.setWindowTitle("LifAi2 Control Hub")  # Remove emoji from title since it's in the taskbar
        self.resize(600, 650)
        
        # 日志初始化
        logging.info("LifAi2 Control Hub initialized")

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # === 全局设置面板 ===
        settings_group = QFrame()
        settings_group.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(10)
        
        # Backend 选择
        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel("Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(['ollama', 'lmstudio'])
        self.backend_combo.setCurrentText(self.settings['backend'])
        backend_layout.addWidget(self.backend_combo)
        
        # Add help button for prompt flow explanation
        help_btn = QPushButton("?")
        help_btn.setFixedSize(25, 25)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
                font-size: 12px;
                text-align: center;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        help_btn.setToolTip("Show how prompts are processed")
        help_btn.clicked.connect(self.show_prompt_flow_help)
        backend_layout.addWidget(help_btn)
        
        # Add confirm selection button
        confirm_btn = QPushButton("✓ Confirm Selection")
        confirm_btn.clicked.connect(self.confirm_backend_selection)
        backend_layout.addWidget(confirm_btn)
        
        settings_layout.addLayout(backend_layout)
        
        # Model 选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self.on_model_change)
        self.refresh_models()
        model_layout.addWidget(self.model_combo)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_models)
        model_layout.addWidget(refresh_btn)
        settings_layout.addLayout(model_layout)
        
        main_layout.addWidget(settings_group)
        
        # === 模块控制面板 ===
        modules_group = QFrame()
        modules_group.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        modules_layout = QVBoxLayout(modules_group)
        
        # Text Improver toggle
        # self.text_improver_toggle = ModuleToggle("Text Improver Window")
        # self.text_improver_toggle.toggled.connect(self.toggle_text_improver)
        # modules_layout.addWidget(self.text_improver_toggle)
        
        # Floating Toolbar toggle
        self.toolbar_toggle = ModuleToggle("Floating Toolbar")
        self.toolbar_toggle.toggled.connect(self.toggle_floating_toolbar)
        modules_layout.addWidget(self.toolbar_toggle)
        
        # Prompt Editor toggle
        self.prompt_editor_toggle = ModuleToggle("Prompt Editor")
        self.prompt_editor_toggle.toggled.connect(self.toggle_prompt_editor)
        modules_layout.addWidget(self.prompt_editor_toggle)
        
        # Knowledge Manager toggle # RAG Removed
        # self.knowledge_manager_toggle = ModuleToggle("Knowledge Manager") # RAG Removed
        # self.knowledge_manager_toggle.toggled.connect(self.toggle_knowledge_manager) # RAG Removed
        # modules_layout.addWidget(self.knowledge_manager_toggle) # RAG Removed
        
        main_layout.addWidget(modules_group)
        
        # === 日志面板 ===
        log_group = QFrame()
        log_group.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        log_layout = QVBoxLayout(log_group)
        
        # 日志显示区域
        self.log_widget = LogWidget()
        log_layout.addWidget(self.log_widget)
        
        # 日志控制
        log_controls = QHBoxLayout()
        
        # 日志级别选择
        log_controls.addWidget(QLabel("Log Level:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        self.log_level_combo.currentTextChanged.connect(self.change_log_level)
        log_controls.addWidget(self.log_level_combo)
        
        # 清除和保存按钮
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        save_btn = QPushButton("Save Logs")
        save_btn.clicked.connect(self.save_logs)
        
        log_controls.addStretch()
        log_controls.addWidget(clear_btn)
        log_controls.addWidget(save_btn)
        
        log_layout.addLayout(log_controls)
        main_layout.addWidget(log_group)
        
        # 配置日志处理器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # 移除现有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加自定义处理器
        log_handler = LogHandler(self.log_widget)
        root_logger.addHandler(log_handler)
        
        # 添加测试日志
        logging.debug("Debug message test")
        logging.info("Info message test")
        logging.warning("Warning message test")
        logging.error("Error message test")

    def get_active_client(self):
        """获取当前活动的客户端"""
        return self.lmstudio_client if self.settings['backend'] == 'lmstudio' else self.ollama_client

    def refresh_models(self):
        """刷新可用模型列表"""
        try:
            current_model = self.model_combo.currentText()
            client = self.get_active_client()
            self.settings['models_list'] = client.fetch_models_sync()
            
            self.model_combo.clear()
            self.model_combo.addItems(self.settings['models_list'])
            
            # 尝试保持当前选择
            if current_model in self.settings['models_list']:
                self.model_combo.setCurrentText(current_model)
                self.settings['model'] = current_model
            elif self.settings['models_list']:
                self.model_combo.setCurrentText(self.settings['models_list'][0])
                self.settings['model'] = self.settings['models_list'][0]
            
            logging.info("Models list refreshed successfully")
        except Exception as e:
            logging.error(f"Error refreshing models: {e}")
            QMessageBox.critical(self, "Error", f"Failed to refresh models: {e}")

    def on_backend_change(self, backend):
        """Handle backend selection change"""
        # Remove automatic update - will be handled by confirm button
        pass

    def on_model_change(self, model):
        """处理模型选择变更"""
        self.settings['model'] = model
        self.save_config()

    def initialize_modules(self):
        """初始化所有模块"""
        # 初始化 prompt editor
        self.modules['prompt_editor'] = PromptEditorWindow(
            settings=self.settings
        )
        
        # 初始化其他模块
        # self.modules['text_improver'] = TextImproverWindow(
        #     settings=self.settings,
        #     ollama_client=self.get_active_client()
        # )
        
        self.modules['floating_toolbar'] = FloatingToolbarModule(
            settings=self.settings,
            ollama_client=self.get_active_client()
        )
        
        # self.modules['knowledge_manager'] = KnowledgeManagerWindow( # RAG Removed
        #     settings=self.settings # RAG Removed
        # ) # RAG Removed
        
        # 注册 prompt 更新回调
        # if hasattr(self.modules['text_improver'], 'update_prompts'):
        #     self.modules['prompt_editor'].add_update_callback(
        #         self.modules['text_improver'].update_prompts
        #     )
            
        if hasattr(self.modules['floating_toolbar'], 'update_prompts'):
            self.modules['prompt_editor'].add_update_callback(
                self.modules['floating_toolbar'].update_prompts
            )

    def toggle_text_improver(self, enabled):
        pass
        # if enabled:
        #     self.modules['text_improver'].show()
        # else:
        #     self.modules['text_improver'].hide()

    def toggle_floating_toolbar(self, enabled):
        if enabled:
            self.modules['floating_toolbar'].show()
        else:
            self.modules['floating_toolbar'].hide()

    def toggle_prompt_editor(self, enabled):
        if enabled:
            self.modules['prompt_editor'].show()
        else:
            self.modules['prompt_editor'].hide()

    # def toggle_knowledge_manager(self, enabled): # RAG Removed
    #     if enabled: # RAG Removed
    #         self.modules['knowledge_manager'].show() # RAG Removed
    #     else: # RAG Removed
    #         self.modules['knowledge_manager'].hide() # RAG Removed

    def change_log_level(self, level):
        """更改日志级别"""
        logging.getLogger().setLevel(getattr(logging, level))
        logging.info(f"Log level changed to {level}")

    def clear_logs(self):
        """清除日志"""
        self.log_widget.clear()
        logging.info("Logs cleared")

    def save_logs(self):
        """保存日志"""
        try:
            # 创建日志目录
            os.makedirs('logs', exist_ok=True)
            
            # 生成带时间戳的文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'logs/lifai_log_{timestamp}.txt'
            
            # 保存日志
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_widget.toPlainText())
            
            logging.info(f"Logs saved to {filename}")
        except Exception as e:
            logging.error(f"Failed to save logs: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save logs: {e}")

    def load_last_config(self) -> dict:
        """加载上次的配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Error loading config: {e}")
        return {}

    def save_config(self):
        """保存当前配置"""
        try:
            config = {
                'last_model': self.model_combo.currentText(),
                'backend': self.settings['backend']
            }
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            logging.error(f"Error saving config: {e}")

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 保存当前配置
        self.save_config()
        
        # 销毁所有模块窗体
        for module in self.modules.values():
            if hasattr(module, 'destroy'):
                module.destroy()
        
        event.accept()

    def confirm_backend_selection(self):
        """Confirm and apply backend selection"""
        try:
            new_backend = self.backend_combo.currentText()
            self.settings['backend'] = new_backend
            
            # Update the active client
            active_client = self.get_active_client()
            
            # Update all modules with new client
            for module in self.modules.values():
                if hasattr(module, 'update_client'):
                    module.update_client(active_client)
            
            # Refresh models list
            self.refresh_models()
            
            # Save configuration
            self.save_config()
            
            logging.info(f"Backend switched to {new_backend} and updated in all modules")
            QMessageBox.information(self, "Success", f"Backend switched to {new_backend}")
        except Exception as e:
            logging.error(f"Error switching backend: {e}")
            QMessageBox.critical(self, "Error", f"Failed to switch backend: {e}")

    def show_prompt_flow_help(self):
        """Show user-friendly illustration of how prompts are processed for each backend"""
        current_backend = self.backend_combo.currentText()
        
        if current_backend == "ollama":
            title = "🦙 Ollama - Prompt Processing Flow"
            content = """
<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333;">

<h3 style="color: #2196F3; margin-bottom: 15px;">📋 How Your Prompts Are Sent to Ollama:</h3>

<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #4CAF50;">
<strong>1. System Prompt Setup:</strong><br/>
• Your selected prompt template becomes the <span style="color: #1976D2; font-weight: bold;">"system" message</span><br/>
• This tells Ollama how to behave and respond<br/>
• Example: "You are a helpful writing assistant..."
</div>

<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #FF9800;">
<strong>2. User Text Processing:</strong><br/>
• Your selected text becomes the <span style="color: #1976D2; font-weight: bold;">"user" message</span><br/>
• This is what you want Ollama to work with<br/>
• Example: Your selected email text to enhance
</div>

<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #9C27B0;">
<strong>3. API Communication:</strong><br/>
• Sent to: <code>http://localhost:11434/api/chat</code><br/>
• Format: JSON with "messages" array<br/>
• Uses latest Ollama chat completion API<br/>
• Enhanced with performance monitoring
</div>

<div style="background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 10px 0;">
<strong>🔄 Message Flow:</strong><br/>
<code style="background: #fff; padding: 2px 6px; border-radius: 3px;">System Prompt</code>
→
<code style="background: #fff; padding: 2px 6px; border-radius: 3px;">Your Text</code>
→
<code style="background: #fff; padding: 2px 6px; border-radius: 3px;">Ollama</code>
→
<code style="background: #fff; padding: 2px 6px; border-radius: 3px;">Enhanced Result</code>
</div>

<div style="background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0;">
<strong>💡 Pro Tip:</strong> Ollama applies prompt templates automatically and handles context efficiently with its native chat API.
</div>

</div>
            """
        else:  # lmstudio
            title = "🎬 LM Studio - Prompt Processing Flow"
            content = """
<div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333;">

<h3 style="color: #2196F3; margin-bottom: 15px;">📋 How Your Prompts Are Sent to LM Studio:</h3>

<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #4CAF50;">
<strong>1. System Prompt Setup:</strong><br/>
• Your selected prompt template becomes the <span style="color: #1976D2; font-weight: bold;">"system" message</span><br/>
• This instructs the model on its role and behavior<br/>
• Example: "You are an expert text editor..."
</div>

<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #FF9800;">
<strong>2. User Text Processing:</strong><br/>
• Your selected text becomes the <span style="color: #1976D2; font-weight: bold;">"user" message</span><br/>
• This contains the content to be processed<br/>
• Example: Your draft email that needs improvement
</div>

<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #9C27B0;">
<strong>3. Native API v0 Communication (Active):</strong><br/>
• Primary: <code>http://localhost:1234/api/v0/chat/completions</code> (Native API - Optimized)<br/>
• Fallback: <code>http://localhost:1234/v1/chat/completions</code> (OpenAI-compatible)<br/>
• 🚀 <strong>Performance boost:</strong> ~5-10% faster than v1 compatibility layer<br/>
• 🎯 <strong>Exclusive features:</strong> TTL auto-unload, enhanced metrics, model info
</div>

<div style="background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 10px 0;">
<strong>🔄 Optimized Message Flow:</strong><br/>
<code style="background: #fff; padding: 2px 6px; border-radius: 3px;">System Prompt</code>
→
<code style="background: #fff; padding: 2px 6px; border-radius: 3px;">Your Text</code>
→
<code style="background: #fff; padding: 2px 6px; border-radius: 3px;">LM Studio Native v0</code>
→
<code style="background: #fff; padding: 2px 6px; border-radius: 3px;">Enhanced Result + Metrics</code>
</div>

<div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 10px 0;">
<strong>⚡ Native API v0 Benefits:</strong><br/>
• <strong>TTL Management:</strong> Models auto-unload after 10 minutes (saves memory)<br/>
• <strong>Detailed Metrics:</strong> Real-time tokens/sec, first-token latency, model architecture<br/>
• <strong>Enhanced Performance:</strong> Direct engine access, reduced overhead<br/>
• <strong>Advanced Info:</strong> Quantization details, runtime info, context length
</div>

<div style="background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0;">
<strong>💡 Pro Tip:</strong> LifAi2 is now optimized for LM Studio's native API v0, providing superior performance and exclusive features compared to the OpenAI-compatible layer.
</div>

</div>
            """
        
        # Create custom dialog for better layout control
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.resize(700, 500)
        
        # Create layout
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Create content label with proper formatting
        content_label = QLabel(content)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setWordWrap(True)
        content_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_label.setStyleSheet("""
            QLabel {
                background-color: white;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
        """)
        
        # Add content to layout
        layout.addWidget(content_label)
        
        # Create OK button
        ok_button = QPushButton("OK")
        ok_button.setFixedSize(80, 30)
        ok_button.clicked.connect(dialog.accept)
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        # Create button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)
        
        # Set dialog stylesheet
        dialog.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
        """)
        
        dialog.exec()

def main():
    app = QApplication(sys.argv)
    window = LifAi2Hub()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 