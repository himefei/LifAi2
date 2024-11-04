import tkinter as tk
from tkinter import ttk, messagebox
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
                            QPushButton, QComboBox, QLabel, QFrame, QToolBar,
                            QProgressBar)
from PyQt6.QtGui import QTextCharFormat, QFont, QColor, QTextCursor
from PyQt6.QtCore import Qt
from typing import Dict
from lifai.utils.ollama_client import OllamaClient
from lifai.config.prompts import improvement_options, llm_prompts
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class TextImproverWindow(QWidget):
    def __init__(self, settings: Dict, ollama_client: OllamaClient):
        super().__init__()
        logger.info("Initializing Text Improver Window")
        self.settings = settings
        self.ollama_client = ollama_client
        self.selected_improvement = None
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self.setup_ui()
        self.hide()  # Start hidden
        
    def setup_ui(self):
        """Setup the main UI components"""
        self.setWindowTitle("Text Improver")
        self.resize(1200, 800)
        
        # Main layout
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Editor container
        editor_layout = QHBoxLayout()
        layout.addLayout(editor_layout)
        
        # Left side (Input)
        input_frame = QFrame()
        input_layout = QVBoxLayout()
        input_frame.setLayout(input_layout)
        
        # Input toolbar
        input_toolbar = QToolBar()
        self.setup_formatting_toolbar(input_toolbar)
        input_layout.addWidget(input_toolbar)
        
        # Input editor
        self.input_text = QTextEdit()
        self.setup_editor(self.input_text)
        input_layout.addWidget(self.input_text)
        
        editor_layout.addWidget(input_frame)
        
        # Right side (Output)
        output_frame = QFrame()
        output_layout = QVBoxLayout()
        output_frame.setLayout(output_layout)
        
        # Output toolbar (for consistency with input side)
        output_toolbar = QToolBar()
        self.setup_formatting_toolbar(output_toolbar)
        output_layout.addWidget(output_toolbar)
        
        # Output editor
        self.output_text = QTextEdit()
        self.setup_editor(self.output_text)
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)
        
        editor_layout.addWidget(output_frame)
        
        # Bottom controls
        controls_layout = QHBoxLayout()
        
        # Improvement selection
        controls_layout.addWidget(QLabel("Select Prompts:"))
        self.improvement_dropdown = QComboBox()
        self.improvement_dropdown.addItems(improvement_options)
        controls_layout.addWidget(self.improvement_dropdown)
        
        # Process button
        self.enhance_button = QPushButton("Process")
        self.enhance_button.clicked.connect(self.process_text)
        controls_layout.addWidget(self.enhance_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(200)  # Set fixed width
        controls_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        controls_layout.addWidget(self.status_label)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

    def setup_editor(self, editor: QTextEdit):
        """Configure editor settings"""
        editor.setAcceptRichText(True)
        editor.setFont(QFont('Arial', 11))
        # Enable HTML formatting
        editor.setHtml("")
        
    def setup_formatting_toolbar(self, toolbar: QToolBar):
        """Setup formatting toolbar actions"""
        # Font formatting
        bold_action = toolbar.addAction("Bold")
        bold_action.setCheckable(True)
        bold_action.toggled.connect(lambda x: self.format_text('bold', x))
        
        italic_action = toolbar.addAction("Italic")
        italic_action.setCheckable(True)
        italic_action.toggled.connect(lambda x: self.format_text('italic', x))
        
        underline_action = toolbar.addAction("Underline")
        underline_action.setCheckable(True)
        underline_action.toggled.connect(lambda x: self.format_text('underline', x))
        
        toolbar.addSeparator()
        
        # Alignment
        left_align = toolbar.addAction("Left")
        left_align.triggered.connect(lambda: self.align_text(Qt.AlignmentFlag.AlignLeft))
        
        center_align = toolbar.addAction("Center")
        center_align.triggered.connect(lambda: self.align_text(Qt.AlignmentFlag.AlignCenter))
        
        right_align = toolbar.addAction("Right")
        right_align.triggered.connect(lambda: self.align_text(Qt.AlignmentFlag.AlignRight))

    def format_text(self, format_type: str, enabled: bool):
        """Apply formatting to selected text"""
        cursor = self.input_text.textCursor()
        char_format = cursor.charFormat()
        
        if format_type == 'bold':
            char_format.setFontWeight(QFont.Weight.Bold if enabled else QFont.Weight.Normal)
        elif format_type == 'italic':
            char_format.setFontItalic(enabled)
        elif format_type == 'underline':
            char_format.setFontUnderline(enabled)
            
        cursor.mergeCharFormat(char_format)
        self.input_text.setTextCursor(cursor)

    def align_text(self, alignment):
        """Set text alignment"""
        self.input_text.setAlignment(alignment)

    def process_text(self):
        """Process the text while preserving formatting"""
        text = self.input_text.toPlainText().strip()
        if not text:
            return

        self.status_label.setText("Processing...")
        self.enhance_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.repaint()

        try:
            # Simulate progress (since we can't get real-time progress from ollama)
            self.progress_bar.setValue(20)
            
            improvement = self.improvement_dropdown.currentText()
            prompt = llm_prompts.get(improvement, "Please improve this text:")
            prompt = prompt.format(text=text)
            
            self.progress_bar.setValue(40)
            
            improved_text = self.ollama_client.generate_response(
                prompt=prompt,
                model=self.settings['model'].get()
            )
            
            self.progress_bar.setValue(80)
            
            if improved_text:
                # Preserve formatting by copying HTML format
                self.output_text.setHtml(improved_text)
                self.status_label.setText("Text processed successfully!")
                self.progress_bar.setValue(100)
            else:
                self.show_error("Failed to generate improved text")
                self.progress_bar.setValue(0)
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            self.show_error(f"An error occurred: {e}")
            self.progress_bar.setValue(0)
        finally:
            self.enhance_button.setEnabled(True)

    def show_error(self, message: str):
        """Show error message"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Error", message)

    def update_prompts(self, new_options):
        """Update available improvement options"""
        current = self.improvement_dropdown.currentText()
        
        # Update dropdown values
        self.improvement_dropdown.clear()
        self.improvement_dropdown.addItems(new_options)
        
        # Try to restore previous selection
        index = self.improvement_dropdown.findText(current)
        if index >= 0:
            self.improvement_dropdown.setCurrentIndex(index)
        
        logger.info(f"Updated improver prompts: {len(new_options)} options available")

    def show(self):
        """Show the window"""
        super().show()
        self.raise_()

    def hide(self):
        """Hide the window"""
        super().hide()

    def isVisible(self):
        """Check if window is visible"""
        return super().isVisible()

    def closeEvent(self, event):
        event.ignore()  # This prevents the window from being closed
        self.hide()    # Instead, we just hide the window