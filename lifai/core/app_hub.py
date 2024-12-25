from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QPushButton, QFrame, QTextEdit, QScrollArea,
                            QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
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
from lifai.modules.knowledge_manager.manager import KnowledgeManagerWindow
# from lifai.modules.AI_chat.ai_chat import ChatWindow
# from lifai.modules.agent_workspace.workspace import AgentWorkspaceWindow
# from lifai.modules.advagent.advagent_window import AdvAgentWindow

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

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
        self.setWindowTitle("LifAi2 Control Hub")
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
        self.backend_combo.currentTextChanged.connect(self.on_backend_change)
        backend_layout.addWidget(self.backend_combo)
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
        
        # Knowledge Manager toggle
        self.knowledge_manager_toggle = ModuleToggle("Knowledge Manager")
        self.knowledge_manager_toggle.toggled.connect(self.toggle_knowledge_manager)
        modules_layout.addWidget(self.knowledge_manager_toggle)
        
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
            self.settings['models_list'] = client.fetch_models()
            
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
        """处理后端选择变更"""
        self.settings['backend'] = backend
        self.refresh_models()
        self.save_config()

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
        
        self.modules['knowledge_manager'] = KnowledgeManagerWindow(
            settings=self.settings
        )
        
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

    def toggle_knowledge_manager(self, enabled):
        if enabled:
            self.modules['knowledge_manager'].show()
        else:
            self.modules['knowledge_manager'].hide()

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

def main():
    # Set Qt DPI settings before creating QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    window = LifAi2Hub()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 