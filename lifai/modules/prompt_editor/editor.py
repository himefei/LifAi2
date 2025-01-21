from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QLineEdit, QPlainTextEdit, QPushButton, QListWidget,
                            QFrame, QMessageBox, QFileDialog, QCheckBox, QListWidgetItem,
                            QMenu, QToolButton)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent
from typing import Dict, Callable
import json
import os
from datetime import datetime
from lifai.utils.logger_utils import get_module_logger
from lifai.config.prompts import llm_prompts

logger = get_module_logger(__name__)

# Get available prompts from llm_prompts
improvement_options = list(llm_prompts.keys())

class OrderedListWidget(QListWidget):
    """Custom QListWidget that supports drag and drop reordering"""
    def __init__(self):
        super().__init__()
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

class PromptEditorWindow(QMainWindow):
    def __init__(self, settings: Dict):
        super().__init__()
        self.settings = settings
        self.prompts_file = os.path.join(os.path.dirname(__file__), '../../config/prompts.py')
        
        # Load saved prompts or use defaults
        self.prompts_data = {
            'templates': self.load_saved_prompts(),
            'order': []  # Store prompt order
        }
        self.update_callbacks = []
        self.has_unsaved_changes = False
        
        # Add default emojis for prompts without them
        self.default_emojis = {
            "Default Enhance": "✨",
            "Default RAG": "🔍",
            "enhance": "⚡",
            "enhance rag": "🚀",
            "rag 3": "🎯"
        }
        
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
                    # Load order if available
                    if hasattr(namespace, 'prompt_order'):
                        self.prompts_data['order'] = namespace['prompt_order']
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
        self.prompts_list = OrderedListWidget()
        self.prompts_list.currentItemChanged.connect(self.on_prompt_select)
        self.prompts_list.model().rowsMoved.connect(self.on_prompts_reordered)
        left_layout.addWidget(self.prompts_list)
        
        # Populate list in saved order if available
        self.refresh_list()
        
        main_layout.addWidget(left_panel)
        
        # Right panel (Editor)
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        right_layout = QVBoxLayout(right_panel)
        
        # Name field with emoji picker
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        
        # Add emoji picker button
        self.emoji_btn = QToolButton()
        self.emoji_btn.setText("😀")
        self.emoji_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.emoji_btn.clicked.connect(self.show_emoji_menu)
        name_layout.addWidget(self.emoji_btn)
        
        self.name_entry = QLineEdit()
        name_layout.addWidget(self.name_entry)
        
        # Add checkboxes in a vertical layout
        checkbox_layout = QVBoxLayout()
        
        # Add RAG checkbox
        self.rag_checkbox = QCheckBox("Use RAG (Retrieval)")
        checkbox_layout.addWidget(self.rag_checkbox)
        
        # Add quick review checkbox
        self.quick_review_checkbox = QCheckBox("Display as Quick Review")
        checkbox_layout.addWidget(self.quick_review_checkbox)
        
        # Add checkbox layout to name layout
        name_layout.addLayout(checkbox_layout)
        
        right_layout.addLayout(name_layout)
        
        # Help section for placeholders
        help_frame = QFrame()
        help_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        help_layout = QVBoxLayout(help_frame)
        
        help_label = QLabel("""<b>Available Placeholders:</b>
• {text} - The selected text to process
• {context} - All retrieved knowledge combined
• {context1} - Knowledge from first relevant slot
• {context2} - Knowledge from second relevant slot
• {context3} - Knowledge from third relevant slot
...and so on for each knowledge slot

<b>Example Prompt Structure:</b>
You are an AI assistant. Here is relevant context:

Technical knowledge:
{context1}

Product knowledge:
{context2}

Support history:
{context3}

Please process this text:
{text}

[Your additional instructions here]""")
        help_label.setWordWrap(True)
        help_layout.addWidget(help_label)
        right_layout.addWidget(help_frame)
        
        # Template editor
        right_layout.addWidget(QLabel("Prompt Template:"))
        self.template_text = QPlainTextEdit()
        self.template_text.setPlaceholderText("Enter your prompt template here...\nUse {text} for selected text\nUse {context1}, {context2}, etc. for specific knowledge slots\nOr use {context} for all knowledge combined")
        self.template_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        font = QFont("Consolas")  # Use monospace font for better readability
        self.template_text.setFont(font)
        right_layout.addWidget(self.template_text)
        
        # Add save and delete buttons
        button_layout = QHBoxLayout()
        new_btn = QPushButton("New Prompt")
        new_btn.clicked.connect(self.new_prompt)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_prompt)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_prompt)
        button_layout.addWidget(new_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(delete_btn)
        right_layout.addLayout(button_layout)
        
        # Add status label and apply changes button
        status_layout = QHBoxLayout()
        self.status_label = QLabel("")
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.apply_changes)
        self.apply_btn.setEnabled(False)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.apply_btn)
        right_layout.addLayout(status_layout)
        
        main_layout.addWidget(right_panel)
        
        # Set size ratio between panels
        main_layout.setStretch(0, 1)  # Left panel
        main_layout.setStretch(1, 2)  # Right panel

    def on_prompt_select(self, current, previous):
        """Handle prompt selection"""
        if not current:
            return
            
        name = current.text()
        prompt_data = self.prompts_data['templates'].get(name, {})
        
        if isinstance(prompt_data, str):  # Handle legacy format
            template = prompt_data
            use_rag = False
            quick_review = False
        else:
            template = prompt_data.get('template', '')
            use_rag = prompt_data.get('use_rag', False)
            quick_review = prompt_data.get('quick_review', False)
        
        self.name_entry.setText(name)
        self.template_text.setPlainText(template)
        self.rag_checkbox.setChecked(use_rag)
        self.quick_review_checkbox.setChecked(quick_review)

    def new_prompt(self):
        """Clear the editor for a new prompt"""
        self.name_entry.clear()
        self.template_text.clear()
        self.rag_checkbox.setChecked(False)
        self.quick_review_checkbox.setChecked(False)
        self.prompts_list.clearSelection()

    def show_error(self, message: str):
        """Show error message dialog"""
        QMessageBox.critical(self, "Error", message)
        
    def validate_prompt(self, prompt: str) -> bool:
        """Validate if prompt is valid"""
        if not prompt or len(prompt.strip()) < 10:
            self.show_error("Prompt is too short")
            return False
            
        return True

    def save_prompt(self):
        """Save current prompt"""
        name = self.name_entry.text().strip()
        prompt = self.template_text.toPlainText().strip()
        
        if not name:
            self.show_error("Please enter a name for the prompt")
            return
            
        if not self.validate_prompt(prompt):
            return
            
        try:
            # Add default emoji if none exists
            if not name.strip().startswith(tuple(self.default_emojis.values())):
                base_name = name.strip()
                if base_name in self.default_emojis:
                    name = f"{self.default_emojis[base_name]} {base_name}"
            
            # Update prompt with RAG and quick review settings
            self.prompts_data['templates'][name] = {
                'template': prompt,
                'use_rag': self.rag_checkbox.isChecked(),
                'quick_review': self.quick_review_checkbox.isChecked()
            }
            
            # Update list
            self.refresh_list()
            
            # Mark changes as unsaved
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
            
            # Update improvement_options with just the prompt names
            improvement_options.clear()
            improvement_options.extend(list(llm_prompts.keys()))
            
            # Notify all registered callbacks with the updated prompt keys and order
            prompt_keys = list(llm_prompts.keys())
            for callback in self.update_callbacks:
                try:
                    if callback.__code__.co_argcount > 1:  # Check if callback accepts more than one argument
                        callback(prompt_keys, self.prompts_data['order'])
                    else:
                        callback(prompt_keys)  # Maintain backward compatibility
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
        """Save prompts and their order to file"""
        try:
            # Create backup
            if os.path.exists(self.prompts_file):
                backup_path = f"{self.prompts_file}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                os.rename(self.prompts_file, backup_path)
            
            # Write new content
            with open(self.prompts_file, 'w', encoding='utf-8') as f:
                f.write("# Auto-generated prompt templates\n\n")
                f.write("llm_prompts = ")
                # Format the dictionary with proper Python syntax
                f.write("llm_prompts = {\n")
                for name, data in self.prompts_data['templates'].items():
                    f.write(f"    {repr(name)}: {{\n")
                    f.write(f"        'template': {repr(data['template'])},\n")
                    f.write(f"        'use_rag': {str(data['use_rag'])},\n")
                    f.write(f"        'quick_review': {str(data['quick_review'])}\n")
                    f.write("    },\n")
                f.write("}\n")
                f.write("\n\n# Prompt display order\n")
                f.write("prompt_order = ")
                f.write("prompt_order = [\n")
                for name in self.prompts_data['order']:
                    f.write(f"    {repr(name)},\n")
                f.write("]\n")
                
            logger.info("Saved prompts successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving prompts: {e}")
            self.show_error(f"Failed to save prompts: {e}")
            return False

    def refresh_list(self):
        """Refresh the prompts list while maintaining order"""
        self.prompts_list.clear()
        
        # If order is not set, initialize it
        if not self.prompts_data['order']:
            self.prompts_data['order'] = list(self.prompts_data['templates'].keys())
        
        # Add items in order, including any new items at the end
        added_items = set()
        for name in self.prompts_data['order']:
            if name in self.prompts_data['templates']:
                # Add default emoji if none exists
                if not name.strip().startswith(tuple(self.default_emojis.values())):
                    base_name = name.strip()
                    if base_name in self.default_emojis:
                        name = f"{self.default_emojis[base_name]} {base_name}"
                
                self.prompts_list.addItem(name)
                added_items.add(name)
        
        # Add any new items that weren't in the order
        for name in self.prompts_data['templates'].keys():
            if name not in added_items:
                # Add default emoji if none exists
                if not name.strip().startswith(tuple(self.default_emojis.values())):
                    base_name = name.strip()
                    if base_name in self.default_emojis:
                        name = f"{self.default_emojis[base_name]} {base_name}"
                
                self.prompts_list.addItem(name)
                self.prompts_data['order'].append(name)

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

    def on_prompts_reordered(self):
        """Handle reordering of prompts"""
        new_order = []
        for i in range(self.prompts_list.count()):
            new_order.append(self.prompts_list.item(i).text())
        self.prompts_data['order'] = new_order
        self.mark_unsaved_changes()
        self.status_label.setText("Prompt order changed. Click 'Apply Changes' to update all modules.")

    def show_emoji_menu(self):
        """Show emoji picker menu"""
        menu = QMenu(self)
        common_emojis = [
            "✨", "🔍", "⚡", "🚀", "🎯", "💫", "🤖", "📝", "💡", "🎨",
            "🔮", "⭐", "🌟", "💪", "🎭", "🎬", "📚", "🎓", "🎪", "🎼"
        ]
        
        for emoji in common_emojis:
            action = menu.addAction(emoji)
            action.triggered.connect(lambda checked, e=emoji: self.insert_emoji(e))
        
        # Position menu under the button
        menu.exec(self.emoji_btn.mapToGlobal(self.emoji_btn.rect().bottomLeft()))

    def insert_emoji(self, emoji: str):
        """Insert emoji at cursor position in name field"""
        current_text = self.name_entry.text()
        current_item = self.prompts_list.currentItem()
        
        if current_item:
            old_name = current_item.text()
            # If this is an existing prompt, we need to update it rather than create a new one
            if old_name in self.prompts_data['templates']:
                # Create new name with new emoji
                words = current_text.split()
                if words:
                    words[0] = emoji
                    new_name = " ".join(words)
                else:
                    new_name = emoji
                
                # Move the template data to the new name
                self.prompts_data['templates'][new_name] = self.prompts_data['templates'].pop(old_name)
                
                # Update the order list
                if old_name in self.prompts_data['order']:
                    index = self.prompts_data['order'].index(old_name)
                    self.prompts_data['order'][index] = new_name
                
                # Update the name entry and list item
                self.name_entry.setText(new_name)
                current_item.setText(new_name)
                
                # Mark changes as unsaved
                self.mark_unsaved_changes()
                return
        
        # If not editing an existing prompt, just insert the emoji at the start
        if not current_text.strip().startswith(tuple(self.default_emojis.values())):
            new_text = f"{emoji} {current_text.lstrip()}"
            self.name_entry.setText(new_text)
            self.name_entry.setCursorPosition(len(emoji) + 1)
        else:
            # Replace existing emoji
            words = current_text.split()
            if words:
                words[0] = emoji
                new_text = " ".join(words)
            else:
                new_text = emoji
            self.name_entry.setText(new_text)
            self.name_entry.setCursorPosition(len(emoji) + 1)

    