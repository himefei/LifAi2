import pyperclip
import keyboard
import time
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class ClipboardManager:
    def __init__(self):
        self.previous_clipboard = None

    def get_selected_text(self) -> str:
        """Get the currently selected text."""
        try:
            # Save current clipboard content
            current_clipboard = pyperclip.paste()
            
            # Try to copy selected text
            keyboard.send('ctrl+c')
            time.sleep(0.1)  # Small delay for copy operation
            
            # Get the selected text
            selected_text = pyperclip.paste()
            
            # If nothing changed in clipboard, no text was selected
            if selected_text == current_clipboard:
                return ""
                
            return selected_text
                
        except Exception as e:
            logger.error(f"Error getting selected text: {e}")
            return ""

    def replace_selected_text(self, new_text: str):
        """Replace the currently selected text with new text."""
        try:
            # Copy new text to clipboard
            pyperclip.copy(new_text)
            time.sleep(0.1)
            
            # Simulate Ctrl+V to paste
            keyboard.send('ctrl+v')
            
            logger.debug("Successfully replaced selected text")
        except Exception as e:
            logger.error(f"Error replacing selected text: {e}")