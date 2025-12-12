from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QComboBox, QPushButton, QFrame, QTextEdit, QScrollArea,
                            QMessageBox, QDialog, QSpacerItem, QSizePolicy, QStackedWidget,
                            QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QFont, QColor

from lifai.core.modern_ui import ToggleSwitch, ModernTheme
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
from lifai.modules.ai_chat.chat_ui import ChatInterface
# from lifai.modules.knowledge_manager.manager import KnowledgeManagerWindow # RAG Removed
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
        self.setWindowTitle("LifAi2")
        self.resize(720, 580)
        
        # 日志初始化
        logging.info("LifAi2 Control Hub initialized")

    def setup_ui(self):
        # Apply modern theme
        self.setStyleSheet(ModernTheme.get_stylesheet())
        
        central_widget = QWidget()
        central_widget.setStyleSheet(f"background-color: {ModernTheme.BG_WINDOW};")
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout: Sidebar + Content
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === SIDEBAR ===
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {ModernTheme.BG_SIDEBAR};
                border: none;
                border-radius: 0;
                border-right: 1px solid {ModernTheme.BORDER};
            }}
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 24)
        sidebar_layout.setSpacing(8)
        
        # App title in sidebar
        title_label = QLabel("LifAi2")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; padding-bottom: 16px;")
        sidebar_layout.addWidget(title_label)
        
        # Navigation buttons
        self.nav_modules = self._create_nav_button("🔧", "Modules")
        self.nav_modules.setChecked(True)
        self.nav_modules.clicked.connect(lambda: self._switch_page(0))
        sidebar_layout.addWidget(self.nav_modules)
        
        self.nav_settings = self._create_nav_button("⚙", "Settings")
        self.nav_settings.clicked.connect(lambda: self._switch_page(1))
        sidebar_layout.addWidget(self.nav_settings)
        
        self.nav_logs = self._create_nav_button("📋", "Logs")
        self.nav_logs.clicked.connect(lambda: self._switch_page(2))
        sidebar_layout.addWidget(self.nav_logs)
        
        sidebar_layout.addStretch()
        
        # Version at bottom of sidebar
        version_label = QLabel("v2.0")
        version_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY}; font-size: 11px;")
        sidebar_layout.addWidget(version_label)
        
        main_layout.addWidget(sidebar)
        
        # === CONTENT AREA ===
        content_area = QWidget()
        content_area.setStyleSheet(f"background-color: {ModernTheme.BG_WINDOW};")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(0)
        
        # Stacked widget for different pages
        self.page_stack = QStackedWidget()
        self.page_stack.setStyleSheet("background: transparent;")
        
        # Page 0: Modules
        self.page_stack.addWidget(self._create_modules_page())
        
        # Page 1: Settings
        self.page_stack.addWidget(self._create_settings_page())
        
        # Page 2: Logs
        self.page_stack.addWidget(self._create_logs_page())
        
        content_layout.addWidget(self.page_stack)
        main_layout.addWidget(content_area)
        
        # Configure logging
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        log_handler = LogHandler(self.log_widget)
        root_logger.addHandler(log_handler)
        logging.info("LifAi2 started")
    
    def _create_nav_button(self, icon: str, text: str) -> QPushButton:
        """Create a sidebar navigation button."""
        btn = QPushButton(f"  {icon}   {text}")
        btn.setFont(QFont("Segoe UI", 10))
        btn.setFixedHeight(44)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setCheckable(True)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ModernTheme.TEXT_PRIMARY};
                border: none;
                border-radius: 10px;
                text-align: left;
                padding-left: 12px;
            }}
            QPushButton:hover {{
                background-color: {ModernTheme.BG_HOVER};
            }}
            QPushButton:checked {{
                background-color: {ModernTheme.PRIMARY};
                color: white;
            }}
        """)
        return btn
    
    def _switch_page(self, index: int):
        """Switch to a different page in the stack."""
        self.page_stack.setCurrentIndex(index)
        # Update nav button states
        self.nav_modules.setChecked(index == 0)
        self.nav_settings.setChecked(index == 1)
        self.nav_logs.setChecked(index == 2)
    
    def _create_modules_page(self) -> QWidget:
        """Create the Modules page."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        
        # Page title
        title = QLabel("Modules")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY};")
        layout.addWidget(title)
        
        # Modules card
        card = self._create_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(0)
        
        # Floating Toolbar row
        self.toolbar_toggle = self._create_setting_row("Floating Toolbar", "Quick AI actions on selected text")
        card_layout.addWidget(self.toolbar_toggle)
        card_layout.addWidget(self._create_separator())
        
        # Prompt Editor row
        self.prompt_editor_toggle = self._create_setting_row("Prompt Editor", "Create and manage system prompts")
        card_layout.addWidget(self.prompt_editor_toggle)
        card_layout.addWidget(self._create_separator())
        
        # AI Chat row
        self.ai_chat_toggle = self._create_setting_row("AI Chat", "Conversational AI interface")
        card_layout.addWidget(self.ai_chat_toggle)
        
        layout.addWidget(card)
        layout.addStretch()
        
        return page
    
    def _create_settings_page(self) -> QWidget:
        """Create the Settings page."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        
        # Page title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY};")
        layout.addWidget(title)
        
        # AI Backend card
        card = self._create_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(16)
        
        # Section header
        section = QLabel("AI Backend")
        section.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        section.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY};")
        card_layout.addWidget(section)
        
        # Provider row
        provider_row = QHBoxLayout()
        provider_row.setSpacing(16)
        provider_label = QLabel("Provider")
        provider_label.setFont(QFont("Segoe UI", 10))
        provider_label.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY};")
        provider_row.addWidget(provider_label)
        provider_row.addStretch()
        
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(['ollama', 'lmstudio'])
        self.backend_combo.setCurrentText(self.settings['backend'])
        self.backend_combo.setMinimumWidth(160)
        self.backend_combo.currentTextChanged.connect(self._on_backend_changed)
        provider_row.addWidget(self.backend_combo)
        
        # Help button
        help_btn = QPushButton("?")
        help_btn.setFixedSize(36, 36)
        help_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ModernTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 18px;
                font-weight: bold;
                font-size: 16px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {ModernTheme.PRIMARY_DARK};
            }}
        """)
        help_btn.clicked.connect(self.show_prompt_flow_help)
        provider_row.addWidget(help_btn)
        
        card_layout.addLayout(provider_row)
        card_layout.addWidget(self._create_separator())
        
        # Model row
        model_row = QHBoxLayout()
        model_row.setSpacing(16)
        model_label = QLabel("Model")
        model_label.setFont(QFont("Segoe UI", 10))
        model_label.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY};")
        model_row.addWidget(model_label)
        model_row.addStretch()
        
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(280)
        self.model_combo.currentTextChanged.connect(self.on_model_change)
        model_row.addWidget(self.model_combo)
        
        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.setFont(QFont("Segoe UI Symbol", 14))
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ModernTheme.BG_HOVER};
                color: {ModernTheme.TEXT_PRIMARY};
                border: none;
                border-radius: 18px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {ModernTheme.BORDER};
            }}
        """)
        refresh_btn.clicked.connect(self.refresh_models)
        model_row.addWidget(refresh_btn)
        
        card_layout.addLayout(model_row)
        
        layout.addWidget(card)
        layout.addStretch()
        
        # Refresh models after UI is built
        self.refresh_models()
        
        return page
    
    def _create_logs_page(self) -> QWidget:
        """Create the Logs page."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        
        # Page title
        title = QLabel("Activity Log")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY};")
        layout.addWidget(title)
        
        # Logs card - this should expand
        card = self._create_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)
        
        # Log widget - set to expand
        self.log_widget = LogWidget()
        self.log_widget.setMinimumHeight(150)
        self.log_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout.addWidget(self.log_widget, 1)  # stretch factor 1
        
        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(12)
        
        level_label = QLabel("Level:")
        level_label.setFont(QFont("Segoe UI", 10))
        level_label.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY};")
        controls.addWidget(level_label)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        self.log_level_combo.currentTextChanged.connect(self.change_log_level)
        self.log_level_combo.setFixedWidth(100)
        controls.addWidget(self.log_level_combo)
        
        controls.addStretch()
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_logs)
        controls.addWidget(clear_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_logs)
        controls.addWidget(save_btn)
        
        card_layout.addLayout(controls)
        layout.addWidget(card, 1)  # stretch factor 1 to fill space
        
        return page
    
    def _create_card(self) -> QFrame:
        """Create a card container with shadow."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {ModernTheme.BG_CARD};
                border: none;
                border-radius: 16px;
            }}
        """)
        # Add subtle shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 2)
        card.setGraphicsEffect(shadow)
        return card
    
    def _create_separator(self) -> QFrame:
        """Create a horizontal separator line."""
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {ModernTheme.BORDER}; border: none; border-radius: 0;")
        return sep
    
    def _create_setting_row(self, title: str, description: str) -> QWidget:
        """Create a setting row with title, description, and toggle switch."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(16)
        
        # Text section
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 10))
        title_label.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY};")
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Segoe UI", 9))
        desc_label.setStyleSheet(f"color: {ModernTheme.TEXT_SECONDARY};")
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Toggle switch
        switch = ToggleSwitch()
        layout.addWidget(switch)
        
        # Store switch reference
        row.switch = switch
        return row
    
    def _on_backend_changed(self, backend: str):
        """Handle backend combo change and auto-apply."""
        self.confirm_backend_selection()

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
        
        # 初始化 AI Chat
        self.modules['ai_chat'] = ChatInterface(
            settings=self.settings,
            ai_client=self.get_active_client()
        )
        
        self.modules['floating_toolbar'] = FloatingToolbarModule(
            settings=self.settings,
            ollama_client=self.get_active_client()
        )
        
        # Connect toggle switches to module visibility
        self.toolbar_toggle.switch.toggled.connect(self.toggle_floating_toolbar)
        self.prompt_editor_toggle.switch.toggled.connect(self.toggle_prompt_editor)
        self.ai_chat_toggle.switch.toggled.connect(self.toggle_ai_chat)
        
        # 注册 prompt 更新回调
        if hasattr(self.modules['floating_toolbar'], 'update_prompts'):
            self.modules['prompt_editor'].add_update_callback(
                self.modules['floating_toolbar'].update_prompts
            )
            
        if hasattr(self.modules['ai_chat'], 'update_prompts'):
            self.modules['prompt_editor'].add_update_callback(
                self.modules['ai_chat'].update_prompts
            )

    def toggle_floating_toolbar(self, enabled):
        """Toggle floating toolbar visibility."""
        if enabled:
            self.modules['floating_toolbar'].show()
        else:
            self.modules['floating_toolbar'].hide()

    def toggle_prompt_editor(self, enabled):
        """Toggle prompt editor visibility."""
        if enabled:
            self.modules['prompt_editor'].show()
        else:
            self.modules['prompt_editor'].hide()

    def toggle_ai_chat(self, enabled):
        """Toggle AI chat visibility."""
        if enabled:
            self.modules['ai_chat'].show()
        else:
            self.modules['ai_chat'].hide()

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
            for module_name, module in self.modules.items():
                if hasattr(module, 'update_client'):
                    module.update_client(active_client)
                # Special handling for AI chat module
                elif module_name == 'ai_chat' and hasattr(module, 'ai_client'):
                    module.ai_client = active_client
            
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