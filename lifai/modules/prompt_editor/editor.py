from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QLineEdit, QTextEdit, QPushButton, QListWidget,
                            QFrame, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt
from typing import Dict, Callable
import json
import os
from datetime import datetime
from lifai.utils.logger_utils import get_module_logger
from lifai.config.prompts import improvement_options, llm_prompts

logger = get_module_logger(__name__)

class PromptEditorWindow(QMainWindow):
    def __init__(self, settings: Dict):
        super().__init__()
        self.settings = settings
        self.prompts_file = os.path.join(os.path.dirname(__file__), '../../config/saved_prompts.py')
        
        # Load saved prompts or use defaults
        self.prompts_data = {
            'templates': self.load_saved_prompts()
        }
        self.update_callbacks = []
        self.has_unsaved_changes = False
        
        self.setup_ui()
        self.hide()

    def load_saved_prompts(self):
        """Load prompts from saved file or return defaults"""
        try:
            if os.path.exists(self.prompts_file):
                namespace = {}
                with open(self.prompts_file, 'r', encoding='utf-8') as f:
                    exec(f.read(), namespace)
                if 'llm_prompts' in namespace:
                    logger.info("Loaded saved prompts successfully")
                    return namespace['llm_prompts']
        except Exception as e:
            logger.error(f"Error loading saved prompts: {e}")
        return llm_prompts.copy()

    def setup_ui(self):
        """Create the editor window"""
        self.setWindowTitle("Prompt Editor")
        self.resize(800, 600)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel (Prompts list)
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        left_layout = QVBoxLayout(left_panel)
        
        # Prompts list
        left_layout.addWidget(QLabel("Prompts:"))
        self.prompts_list = QListWidget()
        self.prompts_list.currentItemChanged.connect(self.on_prompt_select)
        left_layout.addWidget(self.prompts_list)
        
        # Populate list
        for option in self.prompts_data['templates'].keys():
            self.prompts_list.addItem(option)
        
        main_layout.addWidget(left_panel)
        
        # Right panel (Editor)
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        right_layout = QVBoxLayout(right_panel)
        
        # Name field
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_entry = QLineEdit()
        name_layout.addWidget(self.name_entry)
        right_layout.addLayout(name_layout)
        
        # Template editor
        right_layout.addWidget(QLabel("Prompt Template:"))
        self.template_text = QTextEdit()
        right_layout.addWidget(self.template_text)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save Prompt")
        save_btn.clicked.connect(self.save_prompt)
        buttons_layout.addWidget(save_btn)
        
        delete_btn = QPushButton("Delete Prompt")
        delete_btn.clicked.connect(self.delete_prompt)
        buttons_layout.addWidget(delete_btn)
        
        new_btn = QPushButton("New Prompt")
        new_btn.clicked.connect(self.new_prompt)
        buttons_layout.addWidget(new_btn)
        
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.export_prompts)
        buttons_layout.addWidget(export_btn)
        
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self.import_prompts)
        buttons_layout.addWidget(import_btn)
        
        right_layout.addLayout(buttons_layout)
        
        # Apply changes button
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.apply_changes)
        self.apply_btn.setEnabled(False)
        right_layout.addWidget(self.apply_btn)
        
        # Status label
        self.status_label = QLabel("")
        right_layout.addWidget(self.status_label)
        
        main_layout.addWidget(right_panel)
        
        # Set size ratio between panels
        main_layout.setStretch(0, 1)  # Left panel
        main_layout.setStretch(1, 2)  # Right panel

    def on_prompt_select(self, current, previous):
        """Handle prompt selection"""
        if not current:
            return
            
        name = current.text()
        template = self.prompts_data['templates'].get(name, '')
        
        self.name_entry.setText(name)
        self.template_text.setPlainText(template)

    def new_prompt(self):
        """Clear the editor for a new prompt"""
        self.name_entry.clear()
        self.template_text.clear()
        self.prompts_list.clearSelection()

    def show_error(self, message: str):
        """显示错误消息对话框"""
        QMessageBox.critical(self, "Error", message)
        
    def validate_prompt(self, prompt: str) -> bool:
        """验证提示词是否有效"""
        if not prompt or len(prompt.strip()) < 10:
            self.show_error("Prompt is too short")
            return False
            
        return True

    def save_prompt(self):
        """保存当前提示词"""
        name = self.name_entry.text().strip()
        prompt = self.template_text.toPlainText().strip()
        
        if not name:
            self.show_error("Please enter a name for the prompt")
            return
            
        if not self.validate_prompt(prompt):
            return
            
        try:
            # 更新提示词
            self.prompts_data['templates'][name] = prompt
            
            # 更新列表
            self.refresh_list()
            
            # 标记需要应用更改
            self.mark_unsaved_changes()
            
            QMessageBox.information(self, "Success", "Prompt saved successfully! Click 'Apply Changes' to update all modules.")
            
        except Exception as e:
            self.show_error(f"Failed to save prompt: {e}")

    def delete_prompt(self):
        """Delete the selected prompt"""
        current = self.prompts_list.currentItem()
        if not current:
            return
            
        name = current.text()
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Delete prompt '{name}'?",
                                   QMessageBox.StandardButton.Yes | 
                                   QMessageBox.StandardButton.No)
                                   
        if reply == QMessageBox.StandardButton.Yes:
            self.prompts_data['templates'].pop(name, None)
            self.prompts_list.takeItem(self.prompts_list.row(current))
            self.new_prompt()
            self.mark_unsaved_changes()
            self.status_label.setText("Prompt deleted. Click 'Apply Changes' to update all modules.")

    def mark_unsaved_changes(self):
        """Mark that there are changes that need to be applied"""
        self.has_unsaved_changes = True
        self.status_label.setText("Changes need to be applied")
        self.status_label.setStyleSheet("color: #1976D2")  # Blue color
        self.apply_btn.setEnabled(True)

    def apply_changes(self):
        """Apply changes to all modules"""
        try:
            # First save to file to ensure persistence
            self.save_prompts_to_file()
            
            # Update the global prompt variables
            llm_prompts.clear()
            llm_prompts.update(self.prompts_data['templates'])
            
            # Notify all registered callbacks with the updated prompt keys
            prompt_keys = list(llm_prompts.keys())
            for callback in self.update_callbacks:
                try:
                    callback(prompt_keys)
                    logger.debug(f"Successfully notified callback: {callback.__qualname__}")
                except Exception as e:
                    logger.error(f"Error in callback {callback.__qualname__}: {e}")
            
            # Reset status
            self.has_unsaved_changes = False
            self.status_label.setText("Changes applied and saved successfully")
            self.status_label.setStyleSheet("color: #4CAF50")  # Green color
            self.apply_btn.setEnabled(False)
            
            logger.info(f"Applied changes to {len(self.update_callbacks)} modules with {len(prompt_keys)} prompts")
            
        except Exception as e:
            logger.error(f"Error applying changes: {e}")
            self.show_error(f"Failed to apply changes: {e}")

    def save_prompts_to_file(self):
        """保存所有提示词到文件"""
        try:
            content = "llm_prompts = " + json.dumps(self.prompts_data['templates'], indent=4, ensure_ascii=False)
            with open(self.prompts_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info("Prompts saved to file successfully")
        except Exception as e:
            logger.error(f"Error saving prompts to file: {e}")
            raise

    def export_prompts(self):
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'prompts_export_{timestamp}.py'
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("llm_prompts = {\n")
                for name, template in self.prompts_data['templates'].items():
                    f.write(f"    \"{name}\": \"\"\"{template}\"\"\",\n")
                f.write("}\n\n")
                f.write("# Get options from llm_prompts keys\n")
                f.write("improvement_options = list(llm_prompts.keys())\n")
            QMessageBox.information(self, "Success", f"Prompts exported to {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def import_prompts(self):
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Import Prompts",
                "",
                "Python files (*.py);;JSON files (*.json)"
            )
            if filename:
                if filename.endswith('.json'):
                    with open(filename) as f:
                        data = json.load(f)
                        self.prompts_data = {'templates': data['templates']}
                else:  # Python file
                    namespace = {}
                    with open(filename) as f:
                        exec(f.read(), namespace)
                    self.prompts_data = {'templates': namespace.get('llm_prompts', {})}
                
                if self.prompts_data['templates']:
                    self.refresh_list()
                    self.notify_prompt_updates()
                    QMessageBox.information(self, "Success", "Prompts imported successfully")
                else:
                    raise ValueError("Invalid prompts file format")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import: {e}")

    def refresh_list(self):
        self.prompts_list.clear()
        for option in self.prompts_data['templates'].keys():
            self.prompts_list.addItem(option)

    def add_update_callback(self, callback: Callable):
        """Add a callback to be notified of prompt updates
        
        Args:
            callback: A function that takes a list of prompt keys as argument
        """
        if callback not in self.update_callbacks:
            self.update_callbacks.append(callback)
            logger.info(f"Added prompt update callback: {callback.__qualname__}")
            # Immediately call the callback with current prompts
            try:
                callback(list(self.prompts_data['templates'].keys()))
            except Exception as e:
                logger.error(f"Error in initial callback {callback.__qualname__}: {e}")

    def notify_prompt_updates(self):
        """Update the global prompts"""
        # Update global variables
        llm_prompts.clear()
        llm_prompts.update(self.prompts_data['templates'])
        
        # Get the list of options
        options = list(llm_prompts.keys())
        
        # Update improvement_options
        improvement_options.clear()
        improvement_options.extend(options)
        
        # Notify all callbacks with the new options
        for callback in self.update_callbacks:
            try:
                callback(options)
            except Exception as e:
                logger.error(f"Error notifying prompt update: {e}")

    