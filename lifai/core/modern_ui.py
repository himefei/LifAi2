"""
Modern Toggle Switch Widget for PyQt6

A sleek, animated toggle switch with smooth transitions and modern styling.
Designed for LifAi2's minimalist UI refresh - LocalSend inspired design.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRectF, pyqtProperty, QSize
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont, QIcon


class ToggleSwitch(QWidget):
    """
    A modern pill-shaped toggle switch widget with smooth animation.
    Inspired by LocalSend's toggle design.
    """
    
    toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Dimensions - pill shape like LocalSend
        self._track_width = 52
        self._track_height = 28
        self._thumb_size = 22
        self._thumb_margin = 3
        
        # State
        self._checked = False
        self._thumb_position = self._get_thumb_position(False)
        
        # Colors - LocalSend teal palette
        self._track_color_off = QColor("#E0E0E0")
        self._track_color_on = QColor("#009688")  # Teal
        self._track_color_off_hover = QColor("#BDBDBD")
        self._track_color_on_hover = QColor("#00897B")
        self._thumb_color = QColor("#FFFFFF")
        
        self._hovering = False
        
        # Animation
        self._animation = QPropertyAnimation(self, b"thumb_position", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Widget setup
        self.setFixedSize(self._track_width, self._track_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        
    def _get_thumb_position(self, checked: bool) -> float:
        """Calculate thumb position based on checked state."""
        if checked:
            return self._track_width - self._thumb_size - self._thumb_margin
        return self._thumb_margin
    
    @pyqtProperty(float)
    def thumb_position(self) -> float:
        return self._thumb_position
    
    @thumb_position.setter
    def thumb_position(self, pos: float):
        self._thumb_position = pos
        self.update()
    
    def isChecked(self) -> bool:
        return self._checked
    
    def setChecked(self, checked: bool, animate: bool = True):
        """Set the checked state."""
        if self._checked != checked:
            self._checked = checked
            
            if animate:
                self._animation.setStartValue(self._thumb_position)
                self._animation.setEndValue(self._get_thumb_position(checked))
                self._animation.start()
            else:
                self._thumb_position = self._get_thumb_position(checked)
                self.update()
            
            self.toggled.emit(checked)
    
    def toggle(self):
        """Toggle the switch state."""
        self.setChecked(not self._checked)
    
    def sizeHint(self) -> QSize:
        return QSize(self._track_width, self._track_height)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Determine track color based on state and hover
        if self._checked:
            track_color = self._track_color_on_hover if self._hovering else self._track_color_on
        else:
            track_color = self._track_color_off_hover if self._hovering else self._track_color_off
        
        # Draw track (fully rounded pill shape)
        track_rect = QRectF(0, 0, self._track_width, self._track_height)
        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, self._track_height / 2, self._track_height / 2)
        painter.fillPath(track_path, track_color)
        
        # Draw thumb (circle)
        thumb_y = (self._track_height - self._thumb_size) / 2
        thumb_rect = QRectF(
            self._thumb_position,
            thumb_y,
            self._thumb_size,
            self._thumb_size
        )
        thumb_path = QPainterPath()
        thumb_path.addEllipse(thumb_rect)
        painter.fillPath(thumb_path, self._thumb_color)
        
        painter.end()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
    
    def enterEvent(self, event):
        self._hovering = True
        self.update()
    
    def leaveEvent(self, event):
        self._hovering = False
        self.update()
    
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            self.toggle()
        else:
            super().keyPressEvent(event)


class NavButton(QPushButton):
    """Navigation button for sidebar, LocalSend style."""
    
    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self._icon_text = icon_text
        self._label = label
        self._selected = False
        
        self.setText(f"  {icon_text}  {label}")
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 10))
        self._update_style()
    
    def setSelected(self, selected: bool):
        self._selected = selected
        self.setChecked(selected)
        self._update_style()
    
    def _update_style(self):
        if self._selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ModernTheme.PRIMARY};
                    color: white;
                    border: none;
                    border-radius: 10px;
                    text-align: left;
                    padding-left: 12px;
                    font-weight: 500;
                }}
            """)
        else:
            self.setStyleSheet(f"""
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
            """)


class SettingRow(QWidget):
    """A single setting row with label and control, LocalSend style."""
    
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(16)
        
        self.label = QLabel(label)
        self.label.setFont(QFont("Segoe UI", 10))
        self.label.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY};")
        
        layout.addWidget(self.label)
        layout.addStretch()
        
        # Placeholder for control widget
        self._control = None
    
    def setControl(self, widget: QWidget):
        """Set the control widget on the right side."""
        self._control = widget
        self.layout().addWidget(widget)


class Card(QFrame):
    """A card container with subtle shadow, LocalSend style."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            Card {{
                background-color: {ModernTheme.BG_CARD};
                border: none;
                border-radius: 16px;
            }}
        """)
        # Note: For proper shadow, we'd need QGraphicsDropShadowEffect
        # but keeping it simple for now


class SectionHeader(QLabel):
    """Section header label, LocalSend style."""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self.setStyleSheet(f"color: {ModernTheme.TEXT_PRIMARY}; padding: 8px 0;")


# Color scheme for consistent theming - LocalSend inspired
class ModernTheme:
    """Modern minimalist color scheme inspired by LocalSend."""
    
    # Primary colors - Teal like LocalSend
    PRIMARY = "#009688"
    PRIMARY_DARK = "#00796B"
    PRIMARY_LIGHT = "#B2DFDB"
    
    # Accent colors
    ACCENT = "#009688"
    ACCENT_DARK = "#00796B"
    
    # Background colors
    BG_WINDOW = "#F5F7F8"
    BG_SIDEBAR = "#FFFFFF"
    BG_CARD = "#FFFFFF"
    BG_HOVER = "#F0F0F0"
    
    # Text colors
    TEXT_PRIMARY = "#37474F"
    TEXT_SECONDARY = "#78909C"
    TEXT_DISABLED = "#B0BEC5"
    
    # Border colors
    BORDER = "#E8E8E8"
    BORDER_LIGHT = "#F0F0F0"
    
    # Status colors
    SUCCESS = "#4CAF50"
    WARNING = "#FF9800"
    ERROR = "#F44336"
    INFO = "#2196F3"
    
    @classmethod
    def get_stylesheet(cls) -> str:
        """Return the main application stylesheet."""
        return f"""
            /* Main Window */
            QMainWindow {{
                background-color: {cls.BG_WINDOW};
            }}
            
            /* Central Widget */
            QWidget {{
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }}
            
            /* Labels */
            QLabel {{
                color: {cls.TEXT_PRIMARY};
                background: transparent;
                border: none;
            }}
            
            /* Combo Boxes */
            QComboBox {{
                background-color: {cls.BG_CARD};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                padding: 10px 14px;
                padding-right: 30px;
                min-height: 18px;
                font-size: 13px;
                color: {cls.TEXT_PRIMARY};
            }}
            
            QComboBox:hover {{
                border-color: {cls.PRIMARY};
            }}
            
            QComboBox:focus {{
                border-color: {cls.PRIMARY};
                outline: none;
            }}
            
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 24px;
                border: none;
                background: transparent;
            }}
            
            QComboBox::down-arrow {{
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {cls.TEXT_SECONDARY};
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {cls.BG_CARD};
                border: 1px solid {cls.BORDER};
                border-radius: 4px;
                selection-background-color: {cls.PRIMARY_LIGHT};
                selection-color: {cls.TEXT_PRIMARY};
                padding: 4px;
                outline: none;
            }}
            
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                min-height: 24px;
            }}
            
            QComboBox QAbstractItemView::item:hover {{
                background-color: {cls.BG_HOVER};
            }}
            
            QComboBox QAbstractItemView::item:selected {{
                background-color: {cls.PRIMARY_LIGHT};
            }}
            
            /* Push Buttons */
            QPushButton {{
                background-color: {cls.BG_CARD};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 13px;
                color: {cls.TEXT_PRIMARY};
                min-height: 18px;
            }}
            
            QPushButton:hover {{
                background-color: {cls.BG_HOVER};
                border-color: {cls.PRIMARY};
            }}
            
            QPushButton:pressed {{
                background-color: {cls.PRIMARY_LIGHT};
            }}
            
            /* Frames / Cards */
            QFrame {{
                background-color: {cls.BG_CARD};
                border: none;
                border-radius: 16px;
            }}
            
            /* Text Edit / Log Widget */
            QTextEdit {{
                background-color: {cls.BG_CARD};
                border: 1px solid {cls.BORDER};
                border-radius: 12px;
                padding: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                color: {cls.TEXT_PRIMARY};
            }}
            
            /* Scrollbar */
            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                margin: 0;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: #D0D0D0;
                border-radius: 4px;
                min-height: 30px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: #B0B0B0;
            }}
            
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            
            QScrollBar:horizontal {{
                background-color: transparent;
                height: 8px;
                margin: 0;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: #D0D0D0;
                border-radius: 4px;
                min-width: 30px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: #B0B0B0;
            }}
            
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            
            /* Message Box */
            QMessageBox {{
                background-color: {cls.BG_CARD};
            }}
            
            /* Dialog */
            QDialog {{
                background-color: {cls.BG_WINDOW};
            }}
        """
    
    @classmethod
    def get_section_title_style(cls) -> str:
        """Style for section titles like LocalSend."""
        return f"""
            color: {cls.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 600;
            padding: 4px 0 8px 0;
        """
