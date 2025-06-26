"""
Prompt Editor Module for LifAi2

This module provides a robust, GUI-based prompt editor for managing AI prompts in LifAi2.
Prompts are stored in a JSON file for transparency, backup, and easy customization.
The editor supports drag-and-drop reordering, emoji labeling, and advanced template editing.
Implements modular, plugin-style architecture and robust error handling.
"""

import os
import json
import uuid
import glob
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QListWidget, QFrame, QMessageBox, QCheckBox, QMenu, QToolButton, QListWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

# Constants
DEFAULT_MAX_BACKUPS = 5
MIN_PROMPT_LENGTH = 10
PROMPTS_FILENAME = "prompts.json"

@dataclass
class PromptData:
    """Data class for prompt information"""
    id: str
    name: str
    template: str
    quick_review: bool = False
    emoji: str = "✨"

class PromptStorageManager:
    """Handles all prompt storage operations including backup management"""
    
    def __init__(self, prompts_file: str, settings: Dict[str, Any]):
        self.prompts_file = Path(prompts_file)
        self.settings = settings
        
    def load_prompts(self) -> Dict[str, Any]:
        """Load prompts from JSON file with error handling"""
        if not self.prompts_file.exists():
            logger.warning("Prompt JSON file not found, initializing empty prompt set.")
            return {"prompts": [], "order": []}
            
        try:
            with open(self.prompts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if not self._validate_structure(data):
                raise ValueError("Invalid prompt JSON structure")
                
            return data
        except Exception as e:
            logger.error(f"Failed to load prompts.json: {e}")
            return {"prompts": [], "order": []}
    
    def save_prompts(self, prompts_data: Dict[str, Any]) -> bool:
        """Save prompts with backup rotation"""
        try:
            if self.prompts_file.exists() and self.settings.get("prompt_backups", True):
                self._create_backup()
                self._cleanup_old_backups()
                
            with open(self.prompts_file, "w", encoding="utf-8") as f:
                json.dump(prompts_data, f, indent=2, ensure_ascii=False)
                
            logger.info("Saved prompts to JSON successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving prompts to JSON: {e}")
            return False
    
    def _validate_structure(self, data: Dict[str, Any]) -> bool:
        """Validate JSON structure"""
        return isinstance(data, dict) and "prompts" in data and "order" in data
    
    def _create_backup(self) -> None:
        """Create timestamped backup of current file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{self.prompts_file}.{timestamp}.bak"
        os.rename(str(self.prompts_file), backup_path)
    
    def _cleanup_old_backups(self, max_backups: int = DEFAULT_MAX_BACKUPS) -> None:
        """Remove old backup files, keeping only the most recent ones"""
        try:
            backup_pattern = f"{self.prompts_file}.*.bak"
            backup_files = glob.glob(str(backup_pattern))
            
            if len(backup_files) <= max_backups:
                return
                
            # Sort by modification time (newest first)
            backup_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            # Remove oldest backups beyond the limit
            for old_backup in backup_files[max_backups:]:
                try:
                    os.remove(old_backup)
                    logger.info(f"Removed old backup: {os.path.basename(old_backup)}")
                except OSError as e:
                    logger.warning(f"Could not remove old backup {old_backup}: {e}")
                    
        except Exception as e:
            logger.warning(f"Error during backup cleanup: {e}")

class OrderedListWidget(QListWidget):
    """Custom QListWidget that supports drag and drop reordering"""
    
    def __init__(self):
        super().__init__()
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

class PromptValidator:
    """Handles prompt validation logic"""
    
    @staticmethod
    def validate_prompt_name(name: str) -> tuple[bool, str]:
        """Validate prompt name"""
        if not name or not name.strip():
            return False, "Please enter a name for the prompt"
        return True, ""
    
    @staticmethod
    def validate_prompt_template(template: str) -> tuple[bool, str]:
        """Validate prompt template"""
        if not template or len(template.strip()) < MIN_PROMPT_LENGTH:
            return False, "Prompt template is too short"
        return True, ""
    
    @staticmethod
    def validate_name_uniqueness(name: str, prompt_id: str, existing_prompts: List[Dict[str, Any]]) -> tuple[bool, str]:
        """Check if prompt name is unique"""
        for prompt in existing_prompts:
            if prompt["name"] == name and prompt["id"] != prompt_id:
                return False, "A prompt with this name already exists"
        return True, ""

class EmojiManager:
    """Manages emoji functionality for prompts"""
    
    DEFAULT_EMOJIS = {
        "Default Enhance": "✨",
        "Default RAG": "🔍",
        "enhance": "⚡",
        "enhance rag": "🚀",
        "rag 3": "🎯"
    }
    
    COMMON_EMOJIS = [
        "✨", "🔍", "⚡", "🚀", "🎯", "💫", "🤖", "📝", "💡", "🎨",
        "🔮", "⭐", "🌟", "💪", "🎭", "🎬", "📚", "🎓", "🎪", "🎼"
    ]
    
    @classmethod
    def extract_emoji_from_name(cls, name: str) -> Optional[str]:
        """Extract emoji from prompt name if present"""
        if name and name[0] in cls.DEFAULT_EMOJIS.values():
            return name[0]
        return None
    
    @classmethod
    def get_common_emojis(cls) -> List[str]:
        """Get list of common emojis for selection"""
        return cls.COMMON_EMOJIS.copy()

class PromptEditorWindow(QMainWindow):
    """Main window for the Prompt Editor with improved architecture"""
    
    def __init__(self, settings: Dict[str, Any]):
        super().__init__()
        self.settings = settings
        self.prompts_file = os.path.join(os.path.dirname(__file__), PROMPTS_FILENAME)
        
        # Initialize components
        self.storage_manager = PromptStorageManager(self.prompts_file, settings)
        self.validator = PromptValidator()
        self.emoji_manager = EmojiManager()
        
        # Load data
        self.prompts_data = self.storage_manager.load_prompts()
        self.update_callbacks: List[Callable] = []
        self.has_unsaved_changes = False
        
        # UI components (will be initialized in setup_ui)
        self.prompts_list: Optional[OrderedListWidget] = None
        self.name_entry: Optional[QLineEdit] = None
        self.template_text: Optional[QPlainTextEdit] = None
        self.quick_review_checkbox: Optional[QCheckBox] = None
        self.emoji_btn: Optional[QToolButton] = None
        self.status_label: Optional[QLabel] = None
        self.apply_btn: Optional[QPushButton] = None
        
        self._setup_ui()
        self.hide()
    
    def _setup_ui(self) -> None:
        """Setup the user interface"""
        self.setWindowTitle("Prompt Editor")
        self.resize(800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create left and right panels
        self._create_left_panel(main_layout)
        self._create_right_panel(main_layout)
        
        # Set layout proportions
        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 2)
    
    def _create_left_panel(self, main_layout: QHBoxLayout) -> None:
        """Create the left panel with prompts list"""
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        left_layout = QVBoxLayout(left_panel)
        
        left_layout.addWidget(QLabel("Prompts:"))
        
        self.prompts_list = OrderedListWidget()
        self.prompts_list.currentItemChanged.connect(self._on_prompt_select)
        self.prompts_list.model().rowsMoved.connect(self._on_prompts_reordered)
        left_layout.addWidget(self.prompts_list)
        
        self._refresh_list()
        main_layout.addWidget(left_panel)
    
    def _create_right_panel(self, main_layout: QHBoxLayout) -> None:
        """Create the right panel with editor controls"""
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        right_layout = QVBoxLayout(right_panel)
        
        # Name field with emoji picker
        self._create_name_section(right_layout)
        
        # Help section
        self._create_help_section(right_layout)
        
        # Template editor
        self._create_template_section(right_layout)
        
        # Buttons
        self._create_button_section(right_layout)
        
        # Status section
        self._create_status_section(right_layout)
        
        main_layout.addWidget(right_panel)
    
    def _create_name_section(self, layout: QVBoxLayout) -> None:
        """Create the name input section"""
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        
        self.emoji_btn = QToolButton()
        self.emoji_btn.setText("😀")
        self.emoji_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.emoji_btn.clicked.connect(self._show_emoji_menu)
        name_layout.addWidget(self.emoji_btn)
        
        self.name_entry = QLineEdit()
        name_layout.addWidget(self.name_entry)
        
        # Checkboxes
        checkbox_layout = QVBoxLayout()
        self.quick_review_checkbox = QCheckBox("Display as Quick Review")
        checkbox_layout.addWidget(self.quick_review_checkbox)
        name_layout.addLayout(checkbox_layout)
        
        layout.addLayout(name_layout)
    
    def _create_help_section(self, layout: QVBoxLayout) -> None:
        """Create the help section"""
        help_frame = QFrame()
        help_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        help_layout = QVBoxLayout(help_frame)
        
        help_text = """<b>Understanding Prompts:</b>
Your prompt template acts as the <b>System Instructions</b> for the AI. The text you select in other applications will be provided to the AI as the <b>User Input</b>.

<b>How it Works:</b>
1. Your template becomes the System Instructions.
2. The text you select in an application becomes the User Input.
3. The AI processes the User Input based on the System Instructions.

The <code>{text}</code> placeholder is <b>not applicable</b> for defining where selected text goes within the template itself; the selected text is always sent as a separate User Input. Your template should be written as a complete set of instructions for the AI, telling it how to handle the upcoming User Input.

<b>Example System Instruction Template:</b>
You are an expert copy editor. Your task is to proofread and improve the clarity of the user's text. Focus on conciseness and active voice. If the user's text is a question, provide a comprehensive answer.

<i>(When you select text, it will be sent to the AI after these instructions.)</i>

<b>Minimal Template Example:</b>
If your template is empty, a default instruction like "Process the following text based on your general knowledge and capabilities" will be used as the system instruction."""
        
        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        help_layout.addWidget(help_label)
        layout.addWidget(help_frame)
    
    def _create_template_section(self, layout: QVBoxLayout) -> None:
        """Create the template editor section"""
        layout.addWidget(QLabel("Prompt Template:"))
        
        self.template_text = QPlainTextEdit()
        self.template_text.setPlaceholderText(
            "Enter your prompt template here...\n"
            "Use {text} for selected text\n"
            "Use {context1}, {context2}, etc. for specific knowledge slots\n"
            "Or use {context} for all knowledge combined"
        )
        self.template_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        
        font = QFont("Consolas")
        self.template_text.setFont(font)
        layout.addWidget(self.template_text)
    
    def _create_button_section(self, layout: QVBoxLayout) -> None:
        """Create the button section"""
        button_layout = QHBoxLayout()
        
        new_btn = QPushButton("New Prompt")
        new_btn.clicked.connect(self._new_prompt)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_prompt)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_prompt)
        
        button_layout.addWidget(new_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(delete_btn)
        layout.addLayout(button_layout)
    
    def _create_status_section(self, layout: QVBoxLayout) -> None:
        """Create the status section"""
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("")
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self._apply_changes)
        self.apply_btn.setEnabled(False)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.apply_btn)
        layout.addLayout(status_layout)
    
    def _get_prompt_by_id(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get prompt by ID"""
        return next((p for p in self.prompts_data["prompts"] if p["id"] == prompt_id), None)
    
    def _refresh_list(self) -> None:
        """Refresh the prompts list"""
        self.prompts_list.clear()
        for prompt_id in self.prompts_data["order"]:
            prompt = self._get_prompt_by_id(prompt_id)
            if prompt:
                item = QListWidgetItem(prompt["name"])
                item.setData(Qt.ItemDataRole.UserRole, prompt_id)
                self.prompts_list.addItem(item)
    
    def _on_prompt_select(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """Handle prompt selection"""
        if not current:
            return
            
        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self._get_prompt_by_id(prompt_id)
        if not prompt:
            return
            
        self.name_entry.setText(prompt["name"])
        self.template_text.setPlainText(prompt.get("template", ""))
        self.quick_review_checkbox.setChecked(prompt.get("quick_review", False))
    
    def _new_prompt(self) -> None:
        """Create a new prompt"""
        base_name = "New Prompt"
        existing_names = {p["name"] for p in self.prompts_data["prompts"]}
        
        # Generate unique name
        name = f"✨ {base_name}"
        counter = 1
        while name in existing_names:
            counter += 1
            name = f"✨ {base_name} {counter}"
        
        # Create new prompt
        prompt_id = str(uuid.uuid4())
        prompt = {
            "id": prompt_id,
            "name": name,
            "template": "",
            "quick_review": False,
            "emoji": "✨"
        }
        
        self.prompts_data["prompts"].append(prompt)
        self.prompts_data["order"].append(prompt_id)
        self._refresh_list()
        
        # Select the new prompt
        self._select_prompt_by_id(prompt_id)
        self.name_entry.setFocus()
        self._mark_unsaved_changes()
    
    def _select_prompt_by_id(self, prompt_id: str) -> None:
        """Select prompt by ID"""
        for i in range(self.prompts_list.count()):
            item = self.prompts_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == prompt_id:
                self.prompts_list.setCurrentItem(item)
                break
    
    def _save_prompt(self) -> None:
        """Save current prompt"""
        name = self.name_entry.text().strip()
        template = self.template_text.toPlainText().strip()
        
        # Validation
        valid, error = self.validator.validate_prompt_name(name)
        if not valid:
            self._show_error(error)
            return
            
        valid, error = self.validator.validate_prompt_template(template)
        if not valid:
            self._show_error(error)
            return
        
        current_item = self.prompts_list.currentItem()
        if not current_item:
            self._show_error("No prompt selected")
            return
            
        prompt_id = current_item.data(Qt.ItemDataRole.UserRole)
        prompt = self._get_prompt_by_id(prompt_id)
        if not prompt:
            self._show_error("Prompt not found")
            return
        
        # Check name uniqueness
        valid, error = self.validator.validate_name_uniqueness(name, prompt_id, self.prompts_data["prompts"])
        if not valid:
            self._show_error(error)
            return
        
        # Update prompt
        prompt["name"] = name
        prompt["template"] = template
        prompt["quick_review"] = self.quick_review_checkbox.isChecked()
        
        # Update emoji if present in name
        emoji = self.emoji_manager.extract_emoji_from_name(name)
        if emoji:
            prompt["emoji"] = emoji
        
        self._refresh_list()
        self._select_prompt_by_id(prompt_id)
        self._mark_unsaved_changes()
        
        QMessageBox.information(self, "Success", "Prompt saved successfully! Click 'Apply Changes' to update all modules.")
    
    def _delete_prompt(self) -> None:
        """Delete current prompt"""
        current = self.prompts_list.currentItem()
        if not current:
            return
            
        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self._get_prompt_by_id(prompt_id)
        if not prompt:
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete prompt '{prompt['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.prompts_data["prompts"] = [p for p in self.prompts_data["prompts"] if p["id"] != prompt_id]
            if prompt_id in self.prompts_data["order"]:
                self.prompts_data["order"].remove(prompt_id)
                
            self._refresh_list()
            self._clear_form()
            self._mark_unsaved_changes()
            self.status_label.setText("Prompt deleted. Click 'Apply Changes' to update all modules.")
    
    def _clear_form(self) -> None:
        """Clear the form fields"""
        self.name_entry.clear()
        self.template_text.clear()
        self.quick_review_checkbox.setChecked(False)
    
    def _mark_unsaved_changes(self) -> None:
        """Mark that there are unsaved changes"""
        self.has_unsaved_changes = True
        self.status_label.setText("Changes need to be applied")
        self.status_label.setStyleSheet("color: #1976D2")
        self.apply_btn.setEnabled(True)
    
    def _apply_changes(self) -> None:
        """Apply changes and notify callbacks"""
        try:
            if not self.storage_manager.save_prompts(self.prompts_data):
                logger.error("Prompt saving failed. Aborting apply_changes.")
                return
            
            # Notify callbacks
            self._notify_callbacks()
            
            self.has_unsaved_changes = False
            self.status_label.setText("Changes applied and saved successfully")
            self.status_label.setStyleSheet("color: #4CAF50")
            self.apply_btn.setEnabled(False)
            
            logger.info(f"Applied changes to {len(self.update_callbacks)} modules with {len(self.prompts_data['prompts'])} prompts")
            
        except Exception as e:
            logger.error(f"Error applying changes: {e}")
            self._show_error(f"Failed to apply changes: {e}")
    
    def _notify_callbacks(self) -> None:
        """Notify all registered callbacks"""
        # Create ordered prompt names
        id_to_name_map = {p["id"]: p["name"] for p in self.prompts_data["prompts"]}
        ordered_prompt_names = [id_to_name_map[pid] for pid in self.prompts_data["order"] if pid in id_to_name_map]
        
        # Add any missing prompts
        current_names = set(ordered_prompt_names)
        for prompt in self.prompts_data["prompts"]:
            if prompt["name"] not in current_names:
                ordered_prompt_names.append(prompt["name"])
                logger.warning(f"Prompt '{prompt['name']}' was in prompts list but not in order. Appending.")
        
        # Notify callbacks
        for callback in self.update_callbacks:
            try:
                if callback.__code__.co_argcount > 2:
                    callback(ordered_prompt_names, self.prompts_data["order"])
                elif callback.__code__.co_argcount > 1:
                    callback(ordered_prompt_names)
                else:
                    callback()
                    
                logger.debug(f"Successfully notified callback: {callback.__qualname__}")
            except Exception as e:
                logger.error(f"Error in callback {callback.__qualname__}: {e}")
    
    def _on_prompts_reordered(self) -> None:
        """Handle prompt reordering"""
        new_order = []
        for i in range(self.prompts_list.count()):
            item = self.prompts_list.item(i)
            prompt_id = item.data(Qt.ItemDataRole.UserRole)
            new_order.append(prompt_id)
            
        self.prompts_data["order"] = new_order
        self._mark_unsaved_changes()
        self.status_label.setText("Prompt order changed. Click 'Apply Changes' to update all modules.")
    
    def _show_error(self, message: str) -> None:
        """Show error message"""
        QMessageBox.critical(self, "Error", message)
    
    def _show_emoji_menu(self) -> None:
        """Show emoji selection menu"""
        menu = QMenu(self)
        
        for emoji in self.emoji_manager.get_common_emojis():
            action = menu.addAction(emoji)
            action.triggered.connect(lambda checked, e=emoji: self._insert_emoji(e))
            
        menu.exec(self.emoji_btn.mapToGlobal(self.emoji_btn.rect().bottomLeft()))
    
    def _insert_emoji(self, emoji: str) -> None:
        """Insert emoji into name field"""
        current_text = self.name_entry.text()
        
        if not current_text.strip().startswith(tuple(self.emoji_manager.DEFAULT_EMOJIS.values())):
            new_text = f"{emoji} {current_text.lstrip()}"
        else:
            words = current_text.split()
            if words:
                words[0] = emoji
                new_text = " ".join(words)
            else:
                new_text = emoji
                
        self.name_entry.setText(new_text)
        self.name_entry.setCursorPosition(len(emoji) + 1)
    
    def add_update_callback(self, callback: Callable) -> None:
        """Add callback for prompt updates"""
        if callback not in self.update_callbacks:
            self.update_callbacks.append(callback)
            logger.info(f"Added prompt update callback: {callback.__qualname__}")
            
            try:
                callback([p["name"] for p in self.prompts_data["prompts"]])
            except Exception as e:
                logger.error(f"Error in initial callback {callback.__qualname__}: {e}")
