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
from datetime import datetime
from typing import Dict, Callable
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QListWidget, QFrame, QMessageBox, QCheckBox, QMenu, QToolButton, QListWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

PROMPTS_JSON = os.path.join(os.path.dirname(__file__), "prompts.json")

class OrderedListWidget(QListWidget):
    """
    Custom QListWidget that supports drag and drop reordering.

    Used in the prompt editor to allow users to reorder prompts visually.
    """
    def __init__(self):
        super().__init__()
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

class PromptEditorWindow(QMainWindow):
    """
    Main window for the Prompt Editor.

    Provides a GUI for creating, editing, reordering, and managing AI prompts.
    Integrates with JSON storage for persistence and backup.
    Supports emoji labeling, RAG/Quick Review toggles, and modular update callbacks.
    """
    def __init__(self, settings: Dict):
        """
        Initialize the Prompt Editor window.

        Args:
            settings (Dict): Application settings, including backup preferences.
        """
        super().__init__()
        self.settings = settings
        self.prompts_file = PROMPTS_JSON
        self.prompts_data = self.load_prompts_json()
        self.update_callbacks = []  # List of functions to notify on prompt changes
        self.has_unsaved_changes = False

        # Default emojis for prompt types
        self.default_emojis = {
            "Default Enhance": "✨",
            "Default RAG": "🔍",
            "enhance": "⚡",
            "enhance rag": "🚀",
            "rag 3": "🎯"
        }

        self.setup_ui()
        self.hide()

    def load_prompts_json(self):
        """
        Load prompts from the JSON file, or initialize if missing/corrupt.

        Returns:
            dict: Dictionary with 'prompts' and 'order' keys.
        """
        if not os.path.exists(self.prompts_file):
            logger.warning("Prompt JSON file not found, initializing empty prompt set.")
            return {"prompts": [], "order": []}
        try:
            with open(self.prompts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Validate structure
            if "prompts" not in data or "order" not in data:
                raise ValueError("Invalid prompt JSON structure")
            return data
        except Exception as e:
            logger.error(f"Failed to load prompts.json: {e}")
            # Return empty structure on error to avoid crashing the editor
            return {"prompts": [], "order": []}

    def save_prompts_json(self):
        """
        Save prompts to the JSON file, with optional backup.

        If backups are enabled in settings, the previous file is renamed with a timestamp.
        Handles errors gracefully and notifies the user if saving fails.

        Returns:
            bool: True if save succeeded, False otherwise.
        """
        try:
            if os.path.exists(self.prompts_file) and self.settings.get("prompt_backups", True):
                backup_path = f"{self.prompts_file}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                os.rename(self.prompts_file, backup_path)
            with open(self.prompts_file, "w", encoding="utf-8") as f:
                json.dump(self.prompts_data, f, indent=2, ensure_ascii=False)
            logger.info("Saved prompts to JSON successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving prompts to JSON: {e}")
            self.show_error(f"Failed to save prompts: {e}")
            return False

    def setup_ui(self):
        self.setWindowTitle("Prompt Editor")
        self.resize(800, 600)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left panel (Prompts list)
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Prompts:"))
        self.prompts_list = OrderedListWidget()
        self.prompts_list.currentItemChanged.connect(self.on_prompt_select)
        self.prompts_list.model().rowsMoved.connect(self.on_prompts_reordered)
        left_layout.addWidget(self.prompts_list)
        self.refresh_list()
        main_layout.addWidget(left_panel)

        # Right panel (Editor)
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        right_layout = QVBoxLayout(right_panel)

        # Name field with emoji picker
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.emoji_btn = QToolButton()
        self.emoji_btn.setText("😀")
        self.emoji_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.emoji_btn.clicked.connect(self.show_emoji_menu)
        name_layout.addWidget(self.emoji_btn)
        self.name_entry = QLineEdit()
        name_layout.addWidget(self.name_entry)

        # Add checkboxes in a vertical layout
        checkbox_layout = QVBoxLayout()
        # self.rag_checkbox = QCheckBox("Use RAG (Retrieval)") # RAG Removed
        # checkbox_layout.addWidget(self.rag_checkbox) # RAG Removed
        self.quick_review_checkbox = QCheckBox("Display as Quick Review")
        checkbox_layout.addWidget(self.quick_review_checkbox)
        name_layout.addLayout(checkbox_layout)
        right_layout.addLayout(name_layout)

        # Help section for placeholders
        help_frame = QFrame()
        help_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        help_layout = QVBoxLayout(help_frame)
        help_label = QLabel("""<b>Understanding Prompts:</b>
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
If your template is empty, a default instruction like "Process the following text based on your general knowledge and capabilities" will be used as the system instruction.
""")
        help_label.setWordWrap(True)
        help_layout.addWidget(help_label)
        right_layout.addWidget(help_frame)

        # Template editor
        right_layout.addWidget(QLabel("Prompt Template:"))
        self.template_text = QPlainTextEdit()
        self.template_text.setPlaceholderText(
            "Enter your prompt template here...\nUse {text} for selected text\nUse {context1}, {context2}, etc. for specific knowledge slots\nOr use {context} for all knowledge combined"
        )
        self.template_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        font = QFont("Consolas")
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
        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 2)

    def get_prompt_by_id(self, prompt_id):
        for prompt in self.prompts_data["prompts"]:
            if prompt["id"] == prompt_id:
                return prompt
        return None

    def get_prompt_id_by_name(self, name):
        for prompt in self.prompts_data["prompts"]:
            if prompt["name"] == name:
                return prompt["id"]
        return None

    def refresh_list(self):
        self.prompts_list.clear()
        for prompt_id in self.prompts_data["order"]:
            prompt = self.get_prompt_by_id(prompt_id)
            if prompt:
                item = QListWidgetItem(prompt["name"])
                item.setData(Qt.ItemDataRole.UserRole, prompt_id)
                self.prompts_list.addItem(item)

    def on_prompt_select(self, current, previous):
        if not current:
            return
        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            return
        self.name_entry.setText(prompt["name"])
        self.template_text.setPlainText(prompt.get("template", ""))
        # self.rag_checkbox.setChecked(prompt.get("use_rag", False)) # RAG Removed
        self.quick_review_checkbox.setChecked(prompt.get("quick_review", False))

    def new_prompt(self):
        base_name = "New Prompt"
        counter = 1
        temp_name = f"✨ {base_name}"
        existing_names = {p["name"] for p in self.prompts_data["prompts"]}
        while temp_name in existing_names:
            counter += 1
            temp_name = f"✨ {base_name} {counter}"
        prompt_id = str(uuid.uuid4())
        prompt = {
            "id": prompt_id,
            "name": temp_name,
            "template": "",
            # "use_rag": False, # RAG Removed
            "quick_review": False,
            "emoji": "✨"
        }
        self.prompts_data["prompts"].append(prompt)
        self.prompts_data["order"].append(prompt_id)
        self.refresh_list()
        # Select the new prompt
        for i in range(self.prompts_list.count()):
            item = self.prompts_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == prompt_id:
                self.prompts_list.setCurrentItem(item)
                break
        self.name_entry.setFocus()
        self.mark_unsaved_changes()

    def validate_prompt(self, prompt: str) -> bool:
        if not prompt or len(prompt.strip()) < 10:
            self.show_error("Prompt is too short")
            return False
        return True

    def save_prompt(self):
        name = self.name_entry.text().strip()
        prompt_text = self.template_text.toPlainText().strip()
        if not name:
            self.show_error("Please enter a name for the prompt")
            return
        if not self.validate_prompt(prompt_text):
            return
        current_item = self.prompts_list.currentItem()
        if not current_item:
            self.show_error("No prompt selected")
            return
        prompt_id = current_item.data(Qt.ItemDataRole.UserRole)
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            self.show_error("Prompt not found")
            return
        # Check for name collision
        for p in self.prompts_data["prompts"]:
            if p["name"] == name and p["id"] != prompt_id:
                self.show_error("A prompt with this name already exists")
                return
        # Update prompt fields
        prompt["name"] = name
        prompt["template"] = prompt_text
        # prompt["use_rag"] = self.rag_checkbox.isChecked() # RAG Removed
        prompt["quick_review"] = self.quick_review_checkbox.isChecked()
        # Optionally update emoji if present in name
        if name and name[0] in self.default_emojis.values():
            prompt["emoji"] = name[0]
        self.refresh_list()
        # Reselect the prompt
        for i in range(self.prompts_list.count()):
            item = self.prompts_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == prompt_id:
                self.prompts_list.setCurrentItem(item)
                break
        self.mark_unsaved_changes()
        QMessageBox.information(self, "Success", "Prompt saved successfully! Click 'Apply Changes' to update all modules.")

    def delete_prompt(self):
        current = self.prompts_list.currentItem()
        if not current:
            return
        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            return
        reply = QMessageBox.question(self, "Confirm Delete",
                                    f"Delete prompt '{prompt['name']}'?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.prompts_data["prompts"] = [p for p in self.prompts_data["prompts"] if p["id"] != prompt_id]
            if prompt_id in self.prompts_data["order"]:
                self.prompts_data["order"].remove(prompt_id)
            self.refresh_list()
            self.name_entry.clear()
            self.template_text.clear()
            # self.rag_checkbox.setChecked(False) # RAG functionality removed
            self.quick_review_checkbox.setChecked(False)
            self.mark_unsaved_changes()
            self.status_label.setText("Prompt deleted. Click 'Apply Changes' to update all modules.")

    def mark_unsaved_changes(self):
        self.has_unsaved_changes = True
        self.status_label.setText("Changes need to be applied")
        self.status_label.setStyleSheet("color: #1976D2")
        self.apply_btn.setEnabled(True)

    def apply_changes(self):
        try:
            if not self.save_prompts_json():
                # Save failed, error already shown by save_prompts_json. Do not proceed.
                logger.error("Prompt saving failed. Aborting apply_changes.")
                return

            # Notify all registered callbacks with the updated prompt list and order
            # Ensure prompt_keys are derived from the current state of prompts_data,
            # and are in an order consistent with self.prompts_data["order"] if possible,
            # though toolbar primarily uses the ID list for ordering.
            
            # Create a name list that respects the order in self.prompts_data["order"]
            id_to_name_map = {p["id"]: p["name"] for p in self.prompts_data["prompts"]}
            ordered_prompt_names = [id_to_name_map[pid] for pid in self.prompts_data["order"] if pid in id_to_name_map]

            # Fallback for any names in prompts_data["prompts"] but not in ordered_prompt_names (should not happen if data is consistent)
            current_prompt_names_set = set(ordered_prompt_names)
            for p in self.prompts_data["prompts"]:
                if p["name"] not in current_prompt_names_set:
                    ordered_prompt_names.append(p["name"]) # Append unordered ones at the end
                    logger.warning(f"Prompt '{p['name']}' was in prompts list but not derived from order. Appending.")

            prompt_keys_to_send = ordered_prompt_names
            prompt_order_ids_to_send = self.prompts_data["order"]

            logger.debug(f"Editor apply_changes: Sending prompt_keys_to_send: {prompt_keys_to_send}")
            logger.debug(f"Editor apply_changes: Sending prompt_order_ids_to_send: {prompt_order_ids_to_send}")

            for callback in self.update_callbacks:
                try:
                    # Toolbar's update_prompts expects (self, prompt_keys, prompt_order_ids)
                    if callback.__code__.co_argcount > 2: # Check for 3 args: self, keys, ids
                        callback(prompt_keys_to_send, prompt_order_ids_to_send)
                    elif callback.__code__.co_argcount > 1: # Check for 2 args: self, keys
                         callback(prompt_keys_to_send) # Older callback signature
                    else: # callback(self) - unlikely for prompt updates
                        logger.warning(f"Callback {callback.__qualname__} has unexpected argcount {callback.__code__.co_argcount}")
                        callback()

                    logger.debug(f"Successfully notified callback: {callback.__qualname__}")
                except Exception as e:
                    logger.error(f"Error in callback {callback.__qualname__}: {e}") # This could be where the crash occurs

            self.has_unsaved_changes = False
            self.status_label.setText("Changes applied and saved successfully")
            self.status_label.setStyleSheet("color: #4CAF50")
            self.apply_btn.setEnabled(False)
            logger.info(f"Applied changes to {len(self.update_callbacks)} modules with {len(prompt_keys_to_send)} prompts")
        except Exception as e:
            logger.error(f"Error applying changes: {e}")
            self.show_error(f"Failed to apply changes: {e}")

    def on_prompts_reordered(self):
        new_order = []
        for i in range(self.prompts_list.count()):
            item = self.prompts_list.item(i)
            prompt_id = item.data(Qt.ItemDataRole.UserRole)
            new_order.append(prompt_id)
        self.prompts_data["order"] = new_order
        self.mark_unsaved_changes()
        self.status_label.setText("Prompt order changed. Click 'Apply Changes' to update all modules.")

    def show_error(self, message: str):
        QMessageBox.critical(self, "Error", message)

    def show_emoji_menu(self):
        menu = QMenu(self)
        common_emojis = [
            "✨", "🔍", "⚡", "🚀", "🎯", "💫", "🤖", "📝", "💡", "🎨",
            "🔮", "⭐", "🌟", "💪", "🎭", "🎬", "📚", "🎓", "🎪", "🎼"
        ]
        for emoji in common_emojis:
            action = menu.addAction(emoji)
            action.triggered.connect(lambda checked, e=emoji: self.insert_emoji(e))
        menu.exec(self.emoji_btn.mapToGlobal(self.emoji_btn.rect().bottomLeft()))

    def insert_emoji(self, emoji: str):
        current_text = self.name_entry.text()
        if not current_text.strip().startswith(tuple(self.default_emojis.values())):
            new_text = f"{emoji} {current_text.lstrip()}"
            self.name_entry.setText(new_text)
            self.name_entry.setCursorPosition(len(emoji) + 1)
        else:
            words = current_text.split()
            if words:
                words[0] = emoji
                new_text = " ".join(words)
            else:
                new_text = emoji
            self.name_entry.setText(new_text)
            self.name_entry.setCursorPosition(len(emoji) + 1)

    def add_update_callback(self, callback: Callable):
        if callback not in self.update_callbacks:
            self.update_callbacks.append(callback)
            logger.info(f"Added prompt update callback: {callback.__qualname__}")
            try:
                callback([p["name"] for p in self.prompts_data["prompts"]])
            except Exception as e:
                logger.error(f"Error in initial callback {callback.__qualname__}: {e}")
