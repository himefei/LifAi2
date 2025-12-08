"""
Floating Toolbar Module for LifAi2.

Provides a floating, always-on-top toolbar for text enhancement, prompt selection, and
quick review using local LLMs (Ollama/LM Studio). Implements observer pattern for UI updates,
threaded selection and processing, and modular integration with the knowledge base and prompt system.

Features:
    - Floating, draggable, and minimizable toolbar UI (PyQt6)
    - Prompt selection and management (integrates with Prompt Editor)
    - Asynchronous text selection and processing (threaded, non-blocking)
    - Quick review drawer and animated UI elements
    - Observer pattern for UI state and signal/slot communication
    - Modular integration with LLM clients and knowledge base
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QFrame, QMessageBox, QTextEdit, QApplication, 
    QGraphicsDropShadowEffect, QListWidget, QListWidgetItem, 
    QAbstractItemView, QListView, QToolButton
)
from PyQt6.QtCore import (
    Qt, QPoint, QTimer, pyqtSignal, QPropertyAnimation, 
    QEasingCurve, QRect, QEvent
)
from PyQt6.QtGui import QColor, QPalette, QDrag, QMouseEvent
from pynput import mouse

from lifai.utils.ollama_client import OllamaClient
from lifai.utils.logger_utils import get_module_logger
from lifai.config.prompts import llm_prompts, prompt_order, reload_prompts
from lifai.utils.clipboard_utils import ClipboardManager

logger = get_module_logger(__name__)

# Constants
TOOLBAR_WIDTH = 200
TOOLBAR_HEIGHT = 180
TEXT_WINDOW_WIDTH = 500
QUICK_REVIEW_WIDTH = 400
ANIMATION_DURATION = 300
BREATHING_TIMER_INTERVAL = 16  # ~60fps
MOUSE_MOVE_THRESHOLD = 10
LONG_PRESS_DURATION = 0.5

class ProcessingState(Enum):
    """Enumeration for processing states"""
    READY = "ready"
    WAITING_SELECTION = "waiting_selection"
    PROCESSING = "processing"
    COMPLETE = "complete"

@dataclass
class UIStyles:
    """Container for UI style constants"""
    MAIN_FRAME_STYLE = """
        QFrame#mainFrame {
            background-color: white;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
        }
    """
    
    COMBO_BOX_STYLE = """
        QComboBox {
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            padding: 5px 10px;
            background: white;
            font-size: 14px;
            font-family: "Segoe UI Emoji", "Segoe UI", sans-serif;
        }
        QComboBox:hover {
            border: 1px solid #1976D2;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox::down-arrow {
            image: none;
            border: none;
        }
        QComboBox QAbstractItemView {
            padding: 8px;
            font-size: 14px;
            font-family: "Segoe UI Emoji", "Segoe UI", sans-serif;
            selection-background-color: #E3F2FD;
        }
        QComboBox QAbstractItemView::item {
            min-height: 24px;
            padding: 4px 8px;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #E3F2FD;
        }
    """
    
    PROCESS_BUTTON_STYLE = """
        QPushButton {
            background-color: #1976D2;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 8px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1565C0;
        }
        QPushButton:disabled {
            background-color: #90CAF9;
        }
    """

class ColorManager:
    """Manages color operations for animations"""
    
    @staticmethod
    def hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
        """Convert HSL color values to RGB"""
        c = (1 - abs(2 * l - 1)) * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = l - c/2
        
        if 0 <= h < 60:
            r, g, b = c, x, 0
        elif 60 <= h < 120:
            r, g, b = x, c, 0
        elif 120 <= h < 180:
            r, g, b = 0, c, x
        elif 180 <= h < 240:
            r, g, b = 0, x, c
        elif 240 <= h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
            
        return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))
    
    @staticmethod
    def adjust_brightness(r: int, g: int, b: int, brightness: float) -> Tuple[int, int, int]:
        """Adjust RGB color brightness"""
        return (
            int(r * brightness),
            int(g * brightness),
            int(b * brightness)
        )

class TextFilter:
    """Handles text filtering operations"""
    
    @staticmethod
    def filter_reasoning_chain(text: str) -> str:
        """
        DEPRECATED: Legacy filter for reasoning chains.
        
        This method is kept for backward compatibility but should not be needed
        when using native reasoning token support from Ollama/LM Studio.
        
        Filter out reasoning model's chain of thoughts using regex as fallback.
        """
        try:
            import re
            logger.warning("Using legacy reasoning chain filtering. Consider enabling native thinking tokens in AI client.")
            # Remove any text between <think> and </think> tags including the tags
            filtered_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            # Remove any extra whitespace that may have been left
            filtered_text = re.sub(r'\n\s*\n', '\n\n', filtered_text)
            return filtered_text.strip()
        except Exception as e:
            logger.error(f"Error filtering reasoning chain: {e}")
            return text
    
    @staticmethod
    def should_filter_thinking(ai_response: dict) -> bool:
        """
        Check if legacy filtering should be applied.
        
        Returns False if native thinking tokens are available, True otherwise.
        """
        # Check if response has native thinking separation
        if isinstance(ai_response, dict):
            # Check for Ollama-style native thinking
            if 'thinking' in ai_response or ('message' in ai_response and
                isinstance(ai_response['message'], dict) and 'thinking' in ai_response['message']):
                logger.debug("Native thinking tokens detected, skipping legacy filtering")
                return False
        return True

class MouseSelectionHandler:
    """Handles mouse selection logic"""
    
    def __init__(self, parent):
        self.parent = parent
        self.mouse_down = False
        self.is_selecting = False
        self.mouse_down_time: Optional[float] = None
        self.mouse_down_pos: Optional[Tuple[int, int]] = None
    
    def on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> Optional[bool]:
        """Handle mouse click events"""
        if button != mouse.Button.left:
            return None
            
        if pressed:
            return self._handle_mouse_press(x, y)
        else:
            return self._handle_mouse_release(x, y)
    
    def _handle_mouse_press(self, x: int, y: int) -> None:
        """Handle mouse press event"""
        self.mouse_down = True
        self.mouse_down_time = time.time()
        self.mouse_down_pos = (x, y)
        
        # Start long press detection thread
        threading.Thread(target=self._check_long_press, daemon=True).start()
    
    def _handle_mouse_release(self, x: int, y: int) -> Optional[bool]:
        """Handle mouse release event"""
        if not (self.mouse_down and self.is_selecting):
            self._reset_state()
            return None
            
        # Calculate movement distance
        move_distance = self._calculate_movement_distance(x, y)
        
        if move_distance > MOUSE_MOVE_THRESHOLD:
            selected_text = self.parent.clipboard.get_selected_text()
            if selected_text:
                logger.debug(f"Selection complete, moved {move_distance:.1f}px: {selected_text[:100]}...")
                self.parent.waiting_for_selection = False
                self.parent._process_text_async(selected_text)
                return False  # Stop listener
        else:
            logger.debug(f"Ignored selection without movement ({move_distance:.1f}px)")
        
        self._reset_state()
        return None
    
    def _check_long_press(self) -> None:
        """Check for long press after delay"""
        time.sleep(LONG_PRESS_DURATION)
        if self.mouse_down:
            self.is_selecting = True
            logger.debug("Long press detected, user is selecting text...")
    
    def _calculate_movement_distance(self, x: int, y: int) -> float:
        """Calculate mouse movement distance"""
        if not self.mouse_down_pos:
            return 0.0
            
        current_pos = (x, y)
        return ((current_pos[0] - self.mouse_down_pos[0]) ** 2 +
                (current_pos[1] - self.mouse_down_pos[1]) ** 2) ** 0.5
    
    def _reset_state(self) -> None:
        """Reset mouse selection state"""
        self.mouse_down = False
        self.is_selecting = False
        self.mouse_down_time = None
        self.mouse_down_pos = None

class TextDisplayWindow(QMainWindow):
    """Popup window for displaying processed text results with dynamic positioning"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._setup_window()
        self._create_ui()
        self._apply_styling()
    
    def _setup_window(self) -> None:
        """Setup window properties"""
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(TEXT_WINDOW_WIDTH)
    
    def _create_ui(self) -> None:
        """Create the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Title bar with close button
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)
        
        # Text display
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setMinimumWidth(500)
        layout.addWidget(self.text_display)
    
    def _create_title_bar(self) -> QFrame:
        """Create title bar with close button"""
        title_bar = QFrame()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 5, 10, 5)
        title_layout.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #666;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #1976D2;
            }
        """)
        close_btn.clicked.connect(self.hide)
        title_layout.addWidget(close_btn)
        
        return title_bar
    
    def _apply_styling(self) -> None:
        """Apply window styling"""
        self.text_display.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 10px;
                font-size: 13px;
                font-family: "Segoe UI", sans-serif;
                color: #333;
            }
        """)
        
        self.setStyleSheet("""
            QMainWindow {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
            }
        """)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.centralWidget().setGraphicsEffect(shadow)
    
    def setText(self, text: str) -> None:
        """Set text and adjust window height"""
        self.text_display.setText(text)
        
        # Calculate and set window height based on content
        doc_height = self.text_display.document().size().height()
        window_height = int(min(doc_height + 80, 600))  # +80 for margins and title bar
        self.setFixedHeight(max(window_height, 150))  # Minimum height 150px
    
    def updatePosition(self) -> None:
        """Update window position relative to parent toolbar"""
        if not self.parent:
            return
            
        toolbar_center = self.parent.geometry().center()
        current_screen = QApplication.screenAt(toolbar_center)
        if not current_screen:
            current_screen = QApplication.primaryScreen()
        
        screen = current_screen.geometry()
        toolbar = self.parent.geometry()
        
        # Calculate position based on available space
        x, y = self._calculate_optimal_position(screen, toolbar)
        
        # Ensure window stays within screen bounds
        x = max(screen.left(), min(x, screen.right() - self.width()))
        y = max(screen.top(), min(y, screen.bottom() - self.height()))
        
        self.move(x, y)
    
    def _calculate_optimal_position(self, screen: QRect, toolbar: QRect) -> Tuple[int, int]:
        """Calculate optimal position for the text window"""
        space_right = screen.right() - (toolbar.right() + 10)
        space_left = toolbar.left() - screen.left() - 10
        space_bottom = screen.bottom() - (toolbar.bottom() + 10)
        
        if space_right >= self.width():
            return toolbar.right() + 10, toolbar.top()
        elif space_left >= self.width():
            return toolbar.left() - self.width() - 10, toolbar.top()
        elif space_bottom >= self.height():
            return toolbar.left() - ((self.width() - toolbar.width()) // 2), toolbar.bottom() + 10
        else:
            return toolbar.left() - ((self.width() - toolbar.width()) // 2), toolbar.top() - self.height() - 10

class PromptManager:
    """Manages prompt operations for the toolbar"""
    
    def __init__(self):
        self.llm_prompts = llm_prompts.copy()
        self.prompt_order = self._initialize_prompt_order()
    
    def _initialize_prompt_order(self) -> List[str]:
        """Initialize prompt order from configuration"""
        initial_prompt_names_ordered = []
        
        if isinstance(prompt_order, list):
            id_to_name_map = self._create_id_to_name_mapping()
            
            for p_id in prompt_order:
                if p_id in id_to_name_map:
                    initial_prompt_names_ordered.append(id_to_name_map[p_id])
                else:
                    logger.warning(f"Prompt ID '{p_id}' from initial prompt_order not found")
            
            # Add any missing prompts
            for name in self.llm_prompts.keys():
                if name not in initial_prompt_names_ordered:
                    initial_prompt_names_ordered.append(name)
                    logger.warning(f"Prompt name '{name}' was not in initial order, appending")
        
        return initial_prompt_names_ordered or list(self.llm_prompts.keys())
    
    def _create_id_to_name_mapping(self) -> Dict[str, str]:
        """Create mapping from prompt ID to name"""
        id_to_name_map = {}
        for name, data in self.llm_prompts.items():
            if isinstance(data, dict) and "id" in data:
                id_to_name_map[data["id"]] = name
        return id_to_name_map
    
    def update_prompts(self, prompt_keys: Optional[List[str]] = None, 
                      prompt_order_ids: Optional[List[str]] = None) -> None:
        """Update prompts from editor"""
        logger.debug(f"Updating prompts with keys: {prompt_keys}, order_ids: {prompt_order_ids}")
        
        # Reload prompt data
        reloaded_prompts_data, _ = reload_prompts()
        self.llm_prompts = reloaded_prompts_data.copy()
        
        # Update order
        if prompt_order_ids and isinstance(prompt_order_ids, list):
            self.prompt_order = self._order_from_ids(prompt_order_ids)
        elif prompt_keys and isinstance(prompt_keys, list):
            self.prompt_order = [name for name in prompt_keys if name in self.llm_prompts]
        else:
            self.prompt_order = list(self.llm_prompts.keys())
        
        # Ensure order is never empty
        if not self.prompt_order and self.llm_prompts:
            self.prompt_order = list(self.llm_prompts.keys())
    
    def _order_from_ids(self, prompt_order_ids: List[str]) -> List[str]:
        """Create ordered list of names from IDs"""
        id_to_name_map = self._create_id_to_name_mapping()
        ordered_names = []
        
        for p_id in prompt_order_ids:
            if p_id in id_to_name_map:
                prompt_name = id_to_name_map[p_id]
                if prompt_name in self.llm_prompts:
                    ordered_names.append(prompt_name)
                else:
                    logger.warning(f"Name '{prompt_name}' (for ID '{p_id}') not in prompts")
            else:
                logger.warning(f"Prompt ID '{p_id}' not found in mapping")
        
        return ordered_names
    
    def get_prompt_info(self, prompt_name: str) -> Dict[str, Any]:
        """Get prompt information by name"""
        return self.llm_prompts.get(prompt_name, {})

class FloatingToolbarModule(QMainWindow):
    """Main floating toolbar with improved architecture"""
    
    # Signals
    text_processed = pyqtSignal(str)
    selection_finished = pyqtSignal()
    show_error = pyqtSignal(str)
    process_complete = pyqtSignal()
    progress_updated = pyqtSignal(int)
    
    def __init__(self, settings: Dict[str, Any], ollama_client: OllamaClient):
        super().__init__()
        
        # Core components
        self.settings = settings
        self.client = ollama_client
        self.client_type = "ollama" if isinstance(ollama_client, OllamaClient) else "lmstudio"
        self.clipboard = ClipboardManager()
        self.prompt_manager = PromptManager()
        self.color_manager = ColorManager()
        self.text_filter = TextFilter()
        
        # State management
        self.processing_state = ProcessingState.READY
        self.waiting_for_selection = False
        
        # UI components
        self.styles = UIStyles()
        self.mini_window: Optional['FloatingMiniWindow'] = None
        self.text_window: Optional[TextDisplayWindow] = None
        self.quick_review_drawer = None
        self.drawer_animation = None
        
        # Animation properties
        self.breathing_timer = QTimer()
        self.breathing_value = 255
        self.breathing_increasing = False
        self.gradient_position = 0.0
        
        # Mouse handling
        self.mouse_handler = MouseSelectionHandler(self)
        self.drag_position: Optional[QPoint] = None
        
        self._setup_ui()
        self._setup_animations()
        self._connect_signals()
        self._setup_quick_review_drawer()
        
        self.text_window = TextDisplayWindow(self)
        self.hide()
    
    def _setup_ui(self) -> None:
        """Setup the main user interface"""
        self._configure_window()
        self._create_main_layout()
        self._create_toolbar_content()
        self._apply_main_styling()
    
    def _configure_window(self) -> None:
        """Configure window properties"""
        self.setWindowTitle("LifAi2 Toolbar")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    
    def _create_main_layout(self) -> None:
        """Create the main layout structure"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(8)
        
        # Main frame
        self.main_frame = QFrame()
        self.main_frame.setObjectName("mainFrame")
        self.main_frame.setFixedSize(TOOLBAR_WIDTH, TOOLBAR_HEIGHT)
        self.main_layout.addWidget(self.main_frame)
    
    def _create_toolbar_content(self) -> None:
        """Create toolbar content"""
        frame_layout = QVBoxLayout(self.main_frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)
        frame_layout.setSpacing(8)
        
        # Title bar
        title_frame = self._create_title_bar()
        frame_layout.addWidget(title_frame)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #e0e0e0;")
        frame_layout.addWidget(separator)
        
        # Prompt combo box
        self.prompt_combo = QComboBox()
        self._update_prompt_combo()
        frame_layout.addWidget(self.prompt_combo)
        
        # Progress indicator
        progress_frame = self._create_progress_frame()
        frame_layout.addWidget(progress_frame)
        
        # Process button
        self.process_btn = QPushButton("✨ Process Selected Text")
        self.process_btn.clicked.connect(self.start_processing)
        frame_layout.addWidget(self.process_btn)
    
    def _create_title_bar(self) -> QFrame:
        """Create title bar with minimize button"""
        title_frame = QFrame()
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("🤖 LifAi2")
        title_label.setStyleSheet("""
            QLabel {
                color: #1976D2;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        title_layout.addWidget(title_label)
        
        min_btn = QPushButton("⎯")
        min_btn.setFixedWidth(30)
        min_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #666;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #f0f0f0;
                border-radius: 4px;
            }
        """)
        min_btn.clicked.connect(self.minimize_toolbar)
        title_layout.addWidget(min_btn)
        
        # Setup drag functionality
        title_frame.setMouseTracking(True)
        title_frame.mousePressEvent = self.start_drag
        title_frame.mouseMoveEvent = self.on_drag
        
        return title_frame
    
    def _create_progress_frame(self) -> QFrame:
        """Create progress indicator frame"""
        progress_frame = QFrame()
        progress_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background: #f5f5f5;
                min-height: 30px;
            }
        """)
        
        progress_layout = QHBoxLayout(progress_frame)
        progress_layout.setContentsMargins(5, 2, 5, 2)
        
        self.progress_label = QLabel("🚀 Ready")
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #1976D2;
                padding: 5px;
                min-width: 120px;
                background: #f5f5f5;
                border-radius: 5px;
            }
        """)
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        return progress_frame
    
    def _apply_main_styling(self) -> None:
        """Apply main styling to components"""
        self.main_frame.setStyleSheet(self.styles.MAIN_FRAME_STYLE)
        self.prompt_combo.setStyleSheet(self.styles.COMBO_BOX_STYLE)
        self.process_btn.setStyleSheet(self.styles.PROCESS_BUTTON_STYLE)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.main_frame.setGraphicsEffect(shadow)
    
    def _setup_animations(self) -> None:
        """Setup animation timers and effects"""
        self.breathing_timer.timeout.connect(self._update_breathing)
        self.breathing_timer.start(BREATHING_TIMER_INTERVAL)
        self.progress_updated.connect(self._update_progress)
    
    def _connect_signals(self) -> None:
        """Connect internal signals"""
        self.text_processed.connect(self._handle_processed_text)
        self.selection_finished.connect(self._reset_ui)
        self.show_error.connect(self._show_error_dialog)
        self.process_complete.connect(self._reset_ui)
    
    def start_processing(self) -> None:
        """Start text processing workflow"""
        if hasattr(self, 'text_window'):
            self.text_window.hide()
            
        if self.waiting_for_selection:
            return
            
        self.process_btn.setText("Select text now...")
        self.process_btn.setEnabled(False)
        self.waiting_for_selection = True
        
        # Start selection in separate thread
        threading.Thread(target=self._wait_for_selection, daemon=True).start()
    
    def _wait_for_selection(self) -> None:
        """Wait for text selection and process"""
        try:
            self.mouse_handler._reset_state()
            
            # Start mouse listener
            with mouse.Listener(on_click=self.mouse_handler.on_click) as listener:
                listener.join()
                
        except Exception as e:
            logger.error(f"Error waiting for selection: {e}")
            self.show_error.emit(f"Error waiting for selection: {e}")
        finally:
            self.selection_finished.emit()
    
    def _process_text_async(self, text: str) -> None:
        """Process text in separate thread"""
        threading.Thread(
            target=self._process_text_thread,
            args=(text,),
            daemon=True
        ).start()
    
    def _process_text_thread(self, text: str) -> None:
        """Process text in a separate thread"""
        try:
            self.processing_state = ProcessingState.PROCESSING
            self.progress_updated.emit(0)
            
            # Get current prompt
            current_prompt = self.prompt_combo.currentText()
            prompt_info = self.prompt_manager.get_prompt_info(current_prompt)
            
            if not prompt_info:
                raise ValueError(f"Selected prompt '{current_prompt}' not found")
            
            # Prepare messages
            messages = self._prepare_messages(prompt_info, text)
            
            # Process with LLM
            processed_text = self._call_llm(messages)
            
            # Emit results
            self.text_processed.emit(processed_text)
            self.progress_updated.emit(100)
            
        except Exception as e:
            error_msg = f"Error processing text: {str(e)}"
            logger.error(error_msg)
            self.show_error.emit(error_msg)
        finally:
            self.processing_state = ProcessingState.READY
            self.process_complete.emit()
    
    def _prepare_messages(self, prompt_info: Dict[str, Any], text: str) -> List[Dict[str, str]]:
        """Prepare messages for LLM"""
        template = prompt_info.get('template', '').strip()
        
        if not template:
            template = "Process the following text based on your general knowledge and capabilities."
        
        return [
            {"role": "system", "content": template},
            {"role": "user", "content": text}
        ]
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM with prepared messages with native thinking support"""
        if self.client_type == "ollama":
            response = self.client.chat_completion_sync(
                model=self.settings.get('model', 'mistral'),
                messages=messages,
                think=True  # Enable native thinking tokens for reasoning models
            )
            # Store response for thinking token detection
            self._last_ai_response = response
            return response['message']['content']
        else:  # LM Studio
            response = self.client.chat_completion_sync(
                messages=messages,
                model=self.settings.get('model', 'mistral'),
                think=True  # Enable native thinking tokens for reasoning models
            )
            # Store response for thinking token detection
            self._last_ai_response = response
            return response['choices'][0]['message']['content']
    
    def _handle_processed_text(self, text: str) -> None:
        """Handle processed text in the main thread"""
        try:
            if not text:
                logger.warning("Received empty processed text")
                return
            
            # Get current prompt info
            current_prompt = self.prompt_combo.currentText()
            prompt_info = self.prompt_manager.get_prompt_info(current_prompt)
            is_quick_review = prompt_info.get('quick_review', False) if isinstance(prompt_info, dict) else False
            
            # Handle thinking tokens - use native separation if available, fallback to legacy filtering
            if hasattr(self, '_last_ai_response') and not self.text_filter.should_filter_thinking(self._last_ai_response):
                # Native thinking tokens are available, use content directly
                final_text = text
                logger.debug("Using native thinking token separation, no legacy filtering needed")
            else:
                # Fallback to legacy filtering for older models/APIs
                final_text = self.text_filter.filter_reasoning_chain(text)
            
            if is_quick_review:
                self.text_window.setText(final_text)
                self.text_window.updatePosition()
                self.text_window.show()
            else:
                self.clipboard.replace_selected_text(final_text)
                
        except Exception as e:
            logger.error(f"Error handling processed text: {e}")
            self._show_error_dialog(f"Error handling text: {e}")
    
    def _reset_ui(self) -> None:
        """Reset UI to ready state"""
        try:
            self.waiting_for_selection = False
            self.process_btn.setText("✨ Process Selected Text")
            self.process_btn.setEnabled(True)
            self.hide_quick_review()
        except Exception as e:
            logger.error(f"Error resetting UI: {e}")
    
    def _show_error_dialog(self, message: str) -> None:
        """Show error message dialog"""
        try:
            QMessageBox.critical(self, "Error", message)
        except Exception as e:
            logger.error(f"Error showing error dialog: {e}")
    
    def _update_breathing(self) -> None:
        """Update breathing animation effect"""
        if self.processing_state != ProcessingState.PROCESSING:
            return
            
        # Update gradient position for rainbow effect
        self.gradient_position = (self.gradient_position + 0.005) % 1.0
        
        # Calculate rainbow colors
        hue = self.gradient_position * 360
        r, g, b = self.color_manager.hsl_to_rgb(hue, 1.0, 0.5)
        
        # Update breathing value
        if self.breathing_increasing:
            self.breathing_value = min(255, self.breathing_value + 0.5)
            if self.breathing_value >= 255:
                self.breathing_increasing = False
        else:
            self.breathing_value = max(100, self.breathing_value - 0.5)
            if self.breathing_value <= 100:
                self.breathing_increasing = True
        
        # Apply brightness and update style
        brightness = self.breathing_value / 255
        r, g, b = self.color_manager.adjust_brightness(r, g, b, brightness)
        
        gradient_style = f"""
            QLabel {{
                color: white;
                padding: 5px;
                min-width: 120px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgb({r}, {g}, {b}),
                    stop:1 rgb({r//2}, {g//2}, {b//2}));
                border-radius: 5px;
                font-weight: bold;
            }}
        """
        self.progress_label.setStyleSheet(gradient_style)
    
    def _update_progress(self, progress: int) -> None:
        """Update progress indicator"""
        if progress == 0:  # Starting
            self.progress_label.setText("🔄 Processing")
            self.processing_state = ProcessingState.PROCESSING
        elif progress == 100:  # Complete
            self.progress_label.setText("✨ Complete!")
            self.processing_state = ProcessingState.COMPLETE
            self.progress_label.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    padding: 5px;
                    min-width: 120px;
                    background: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 #E8F5E9,
                        stop: 0.5 #C8E6C9,
                        stop: 1 #E8F5E9
                    );
                    border-radius: 5px;
                    font-weight: bold;
                }
            """)
        else:  # Reset to ready
            self.progress_label.setText("🚀 Ready")
            self.processing_state = ProcessingState.READY
            self.progress_label.setStyleSheet("""
                QLabel {
                    color: #1976D2;
                    padding: 5px;
                    min-width: 120px;
                    background: #f5f5f5;
                    border-radius: 5px;
                    font-weight: bold;
                }
            """)
    
    def _update_prompt_combo(self) -> None:
        """Update prompt combo box"""
        current_selection = self.prompt_combo.currentText()
        self.prompt_combo.clear()
        
        for name in self.prompt_manager.prompt_order:
            if name in self.prompt_manager.llm_prompts:
                self.prompt_combo.addItem(name)
        
        # Restore selection
        if current_selection and self.prompt_combo.findText(current_selection) != -1:
            self.prompt_combo.setCurrentText(current_selection)
        elif self.prompt_combo.count() > 0:
            self.prompt_combo.setCurrentIndex(0)
    
    def update_prompts(self, prompt_keys: Optional[List[str]] = None, 
                      prompt_order_ids: Optional[List[str]] = None) -> None:
        """Update prompts from editor"""
        self.prompt_manager.update_prompts(prompt_keys, prompt_order_ids)
        self._update_prompt_combo()
        logger.info(f"Prompts updated. Current order: {self.prompt_manager.prompt_order}")
    
    def update_client(self, new_client) -> None:
        """Update LLM client"""
        try:
            self.client = new_client
            self.client_type = "ollama" if isinstance(new_client, OllamaClient) else "lmstudio"
            logger.info("Floating toolbar client updated successfully")
        except Exception as e:
            logger.error(f"Error updating floating toolbar client: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update client: {e}")
    
    def minimize_toolbar(self) -> None:
        """Minimize toolbar to mini window"""
        if self.quick_review_drawer and self.quick_review_drawer.isVisible():
            self.quick_review_drawer.hide()
        
        self.hide()
        if not self.mini_window:
            self.mini_window = FloatingMiniWindow(self)
        self.mini_window.move(self.pos())
        self.mini_window.show()
    
    def restore_toolbar(self) -> None:
        """Restore toolbar from mini window"""
        if self.mini_window:
            self.move(self.mini_window.pos())
            self.mini_window.hide()
        self.show()
    
    def start_drag(self, event) -> None:
        """Start dragging the window"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def on_drag(self, event) -> None:
        """Handle window dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def _setup_quick_review_drawer(self) -> None:
        """Setup quick review drawer (placeholder for future implementation)"""
        # Placeholder for quick review drawer setup
        self.is_drawer_visible = False
    
    def show_quick_review(self, text: str) -> None:
        """Show quick review (placeholder)"""
        pass
    
    def hide_quick_review(self) -> None:
        """Hide quick review (placeholder)"""
        pass
    
    def moveEvent(self, event) -> None:
        """Handle toolbar movement"""
        super().moveEvent(event)
        if hasattr(self, 'text_window') and self.text_window.isVisible():
            self.text_window.updatePosition()
    
    def closeEvent(self, event) -> None:
        """Handle window close event"""
        try:
            if hasattr(self, 'text_window'):
                self.text_window.close()
            self.waiting_for_selection = False
            self.processing_state = ProcessingState.READY
            super().closeEvent(event)
        except Exception as e:
            logger.error(f"Error in close event: {e}")
            event.accept()

class FloatingMiniWindow(QMainWindow):
    """Minimized floating window"""
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.drag_position: Optional[QPoint] = None
        
        self._setup_window()
        self._create_ui()
    
    def _setup_window(self) -> None:
        """Setup window properties"""
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint
        )
        self.setMouseTracking(True)
    
    def _create_ui(self) -> None:
        """Create mini window UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        btn = QPushButton("✨")
        btn.setFixedWidth(30)
        btn.clicked.connect(self.parent.restore_toolbar)
        layout.addWidget(btn)
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()