import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import logging
import os
import sys
import json
from datetime import datetime

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from lifai.utils.ollama_client import OllamaClient
from lifai.modules.text_improver.improver import TextImproverWindow
from lifai.modules.floating_toolbar.toolbar import FloatingToolbarModule
from lifai.core.toggle_switch import ToggleSwitch
from lifai.modules.prompt_editor.editor import PromptEditorWindow
from lifai.modules.AI_chat.ai_chat import ChatWindow
from lifai.modules.agent_workspace.workspace import AgentWorkspaceWindow

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

class LogHandler(logging.Handler):
    def __init__(self, text_widget: scrolledtext.ScrolledText):
        super().__init__()
        self.text_widget = text_widget
        
        # Create a formatter
        self.formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

    def emit(self, record):
        msg = self.formatter.format(record)
        self.text_widget.configure(state='normal')
        
        # Add color tags based on log level
        if record.levelno >= logging.ERROR:
            tag = 'error'
            color = '#FF5252'  # Red
        elif record.levelno >= logging.WARNING:
            tag = 'warning'
            color = '#FFA726'  # Orange
        elif record.levelno >= logging.INFO:
            tag = 'info'
            color = '#4CAF50'  # Green
        else:
            tag = 'debug'
            color = '#9E9E9E'  # Gray
            
        # Configure tag if it doesn't exist
        if tag not in self.text_widget.tag_names():
            self.text_widget.tag_configure(tag, foreground=color)
        
        # Insert the message with appropriate tag
        self.text_widget.insert(tk.END, msg + '\n', tag)
        self.text_widget.see(tk.END)  # Auto-scroll to bottom
        self.text_widget.configure(state='disabled')

class LifAiHub:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LifAi Control Hub")
        self.root.geometry("600x500")
        
        # Configure background color
        self.root.configure(bg='#ffffff')
        self.style = ttk.Style()
        self.style.configure('TFrame', background='#ffffff')
        self.style.configure('TLabelframe', background='#ffffff')
        self.style.configure('TLabelframe.Label', background='#ffffff')
        
        # Initialize Ollama client
        self.ollama_client = OllamaClient()
        
        # Load last selected model
        self.config_file = os.path.join(project_root, 'lifai', 'config', 'app_settings.json')
        last_model = self.load_last_model()
        
        # Shared settings
        self.settings = {
            'model': tk.StringVar(value=last_model),
            'models_list': []
        }
        
        self.setup_ui()
        self.modules = {}
        self.initialize_modules()
        
        # Log initialization
        logging.info("LifAi Control Hub initialized")
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bind model selection change
        self.settings['model'].trace_add('write', self.on_model_change)

    def load_last_model(self) -> str:
        """Load the last selected model from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('last_model', '')
        except Exception as e:
            logging.error(f"Error loading last model: {e}")
        return ''

    def save_last_model(self):
        """Save the current model selection to config file"""
        try:
            config = {'last_model': self.settings['model'].get()}
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            logging.error(f"Error saving last model: {e}")

    def on_model_change(self, *args):
        """Handle model selection change"""
        self.save_last_model()

    def refresh_models(self):
        """Refresh the list of available models"""
        try:
            current_model = self.settings['model'].get()
            self.models_list = self.ollama_client.fetch_models()
            self.model_dropdown['values'] = self.models_list
            
            # Try to keep the current selection if it still exists
            if current_model in self.models_list:
                self.settings['model'].set(current_model)
            elif self.models_list:
                self.settings['model'].set(self.models_list[0])
            else:
                self.settings['model'].set('')
                
            logging.info("Models list refreshed successfully")
        except Exception as e:
            logging.error(f"Error refreshing models: {e}")
            messagebox.showerror("Error", f"Failed to refresh models: {e}")

    def setup_ui(self):
        # Settings panel with padding
        self.settings_frame = ttk.LabelFrame(
            self.root, 
            text="Global Settings",
            padding=10
        )
        self.settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Model selection container
        model_container = ttk.Frame(self.settings_frame)
        model_container.pack(fill=tk.X, expand=True)
        
        # Model label
        model_label = ttk.Label(model_container, text="Model:")
        model_label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Model selection with longer width
        self.models_list = self.ollama_client.fetch_models()
        self.model_dropdown = ttk.Combobox(
            model_container, 
            textvariable=self.settings['model'],
            values=self.models_list,
            state='readonly'
        )
        self.model_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Refresh button
        refresh_btn = ttk.Button(
            model_container,
            text="🔄 Refresh",
            command=self.refresh_models,
            width=10
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Set initial model selection
        if self.settings['model'].get() in self.models_list:
            self.model_dropdown.set(self.settings['model'].get())
        elif self.models_list:
            self.model_dropdown.current(0)
        
        # Module controls
        self.modules_frame = ttk.LabelFrame(
            self.root, 
            text="Module Controls",
            padding=10
        )
        self.modules_frame.pack(fill=tk.X, padx=10, pady=5)

        # Text Improver toggle
        self.text_improver_toggle = ToggleSwitch(
            self.modules_frame,
            "Text Improver Window",
            self.toggle_text_improver
        )
        self.text_improver_toggle.pack(fill=tk.X, pady=5)

        # Floating Toolbar toggle
        self.toolbar_toggle = ToggleSwitch(
            self.modules_frame,
            "Floating Toolbar",
            self.toggle_floating_toolbar
        )
        self.toolbar_toggle.pack(fill=tk.X, pady=5)

        # Prompt Editor toggle
        self.prompt_editor_toggle = ToggleSwitch(
            self.modules_frame,
            "Prompt Editor",
            self.toggle_prompt_editor
        )
        self.prompt_editor_toggle.pack(fill=tk.X, pady=5)

        # AI Chat toggle
        self.chat_toggle = ToggleSwitch(
            self.modules_frame,
            "AI Chat",
            self.toggle_chat
        )
        self.chat_toggle.pack(fill=tk.X, pady=5)
        
        # Agent Workspace toggle
        self.agent_workspace_toggle = ToggleSwitch(
            self.modules_frame,
            "Agent Workspace",
            self.toggle_agent_workspace
        )
        self.agent_workspace_toggle.pack(fill=tk.X, pady=5)
        
        # Debug log panel
        self.debug_frame = ttk.LabelFrame(
            self.root,
            text="Debug Logs",
            padding=10
        )
        self.debug_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Add scrolled text widget for logs
        self.log_widget = scrolledtext.ScrolledText(
            self.debug_frame,
            height=10,
            wrap=tk.WORD
        )
        self.log_widget.pack(fill=tk.BOTH, expand=True)
        self.log_widget.configure(state='disabled')
        
        # Configure logging to use our widget
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add our custom handler
        log_handler = LogHandler(self.log_widget)
        root_logger.addHandler(log_handler)
        
        # Create log controls at the bottom
        self.create_log_controls()
        
        # Add initial test logs
        logging.debug("Debug message test")
        logging.info("Info message test")
        logging.warning("Warning message test")
        logging.error("Error message test")

    def create_log_controls(self):
        control_frame = ttk.Frame(self.debug_frame)
        control_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Log level selector
        ttk.Label(control_frame, text="Log Level:").pack(side=tk.LEFT, padx=(0, 5))
        self.log_level = tk.StringVar(value="INFO")
        level_combo = ttk.Combobox(
            control_frame,
            textvariable=self.log_level,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            state='readonly',
            width=10
        )
        level_combo.pack(side=tk.LEFT, padx=5)
        
        # Bind log level change
        level_combo.bind('<<ComboboxSelected>>', self.change_log_level)
        
        # Clear logs button
        ttk.Button(
            control_frame,
            text="Clear Logs",
            command=self.clear_logs
        ).pack(side=tk.RIGHT, padx=5)
        
        # Save logs button
        ttk.Button(
            control_frame,
            text="Save Logs",
            command=self.save_logs
        ).pack(side=tk.RIGHT, padx=5)

    def change_log_level(self, event=None):
        level = getattr(logging, self.log_level.get())
        logging.getLogger().setLevel(level)
        logging.info(f"Log level changed to {self.log_level.get()}")

    def clear_logs(self):
        self.log_widget.configure(state='normal')
        self.log_widget.delete(1.0, tk.END)
        self.log_widget.configure(state='disabled')
        logging.info("Logs cleared")

    def save_logs(self):
        try:
            # Create logs directory if it doesn't exist
            os.makedirs('logs', exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'logs/lifai_log_{timestamp}.txt'
            
            # Save logs
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_widget.get(1.0, tk.END))
            
            logging.info(f"Logs saved to {filename}")
        except Exception as e:
            logging.error(f"Failed to save logs: {e}")

    def initialize_modules(self):
        # Initialize prompt editor first
        self.modules['prompt_editor'] = PromptEditorWindow(
            settings=self.settings
        )
        
        # Initialize other modules
        self.modules['text_improver'] = TextImproverWindow(
            settings=self.settings,
            ollama_client=self.ollama_client
        )
        
        self.modules['floating_toolbar'] = FloatingToolbarModule(
            settings=self.settings,
            ollama_client=self.ollama_client
        )

        # Initialize AI Chat module
        self.modules['chat'] = ChatWindow(
            settings=self.settings,
            ollama_client=self.ollama_client
        )

        # Initialize Agent Workspace module
        self.modules['agent_workspace'] = AgentWorkspaceWindow(
            settings=self.settings,
            ollama_client=self.ollama_client
        )

        # Register prompt update callbacks
        if hasattr(self.modules['text_improver'], 'update_prompts'):
            self.modules['prompt_editor'].add_update_callback(
                self.modules['text_improver'].update_prompts
            )
            
        if hasattr(self.modules['floating_toolbar'], 'update_prompts'):
            self.modules['prompt_editor'].add_update_callback(
                self.modules['floating_toolbar'].update_prompts
            )

    def toggle_text_improver(self):
        if self.text_improver_toggle.get():
            self.modules['text_improver'].show()
        else:
            self.modules['text_improver'].hide()

    def toggle_floating_toolbar(self):
        if self.toolbar_toggle.get():
            self.modules['floating_toolbar'].enable()
        else:
            self.modules['floating_toolbar'].disable()

    def toggle_prompt_editor(self):
        if self.prompt_editor_toggle.get():
            self.modules['prompt_editor'].show()
        else:
            self.modules['prompt_editor'].hide()

    def toggle_chat(self):
        if self.chat_toggle.get():
            self.modules['chat'].show()
        else:
            self.modules['chat'].hide()

    def toggle_agent_workspace(self):
        if self.agent_workspace_toggle.get():
            self.modules['agent_workspace'].show()
        else:
            self.modules['agent_workspace'].hide()

    def run(self):
        # Make sure the hub window stays on top
        self.root.attributes('-topmost', True)
        self.root.mainloop()

    def on_closing(self):
        """Handle application closing"""
        # Save current model selection
        self.save_last_model()
        
        # Destroy all module windows
        for module in self.modules.values():
            if hasattr(module, 'destroy'):
                module.destroy()
        
        self.root.destroy()

if __name__ == "__main__":
    app = LifAiHub()
    app.run() 