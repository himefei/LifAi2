#!/usr/bin/env python3
"""
LifAi2 Splash Screen - Shows a modern loading animation while the app starts
"""
import sys
import os
import subprocess
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QFont, QLinearGradient, QPen, QBrush

class LoadingDot(QWidget):
    """A single animated dot"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.3
        self.setFixedSize(12, 12)
    
    @pyqtProperty(float)
    def opacity(self):
        return self._opacity
    
    @opacity.setter
    def opacity(self, value):
        self._opacity = value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)
        painter.setBrush(QColor(0, 150, 136))  # Teal
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 12, 12)


class SplashScreen(QWidget):
    """Modern splash screen with loading animation"""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(280, 180)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
        
        self._setup_ui()
        self._setup_animation()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main container
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(30, 25, 30, 25)
        container_layout.setSpacing(15)
        
        # App name with emoji
        title = QLabel("✨ LifAi2")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #009688;
                font-size: 28px;
                font-weight: bold;
                background: transparent;
            }
        """)
        container_layout.addWidget(title)
        
        # Tagline
        tagline = QLabel("Your local AI writing assistant")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                font-style: italic;
                background: transparent;
            }
        """)
        container_layout.addWidget(tagline)
        
        # Loading text
        self.loading_label = QLabel("Starting up...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 13px;
                background: transparent;
            }
        """)
        container_layout.addWidget(self.loading_label)
        
        # Dots container
        dots_widget = QWidget()
        dots_widget.setStyleSheet("background: transparent;")
        dots_layout = QVBoxLayout(dots_widget)
        dots_layout.setContentsMargins(0, 5, 0, 0)
        dots_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create horizontal dots container
        dots_row = QWidget()
        dots_row.setStyleSheet("background: transparent;")
        from PyQt6.QtWidgets import QHBoxLayout
        row_layout = QHBoxLayout(dots_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create 3 dots
        self.dots = []
        for i in range(3):
            dot = LoadingDot()
            self.dots.append(dot)
            row_layout.addWidget(dot)
        
        dots_layout.addWidget(dots_row)
        container_layout.addWidget(dots_widget)
    
    def _setup_animation(self):
        """Setup the bouncing dot animation"""
        self.animations = []
        
        for i, dot in enumerate(self.dots):
            # Fade animation for each dot
            anim = QPropertyAnimation(dot, b"opacity", self)
            anim.setDuration(600)
            anim.setStartValue(0.3)
            anim.setKeyValueAt(0.5, 1.0)
            anim.setEndValue(0.3)
            anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            anim.setLoopCount(-1)  # Infinite loop
            self.animations.append(anim)
        
        # Start animations with staggered delays
        for i, anim in enumerate(self.animations):
            QTimer.singleShot(i * 200, anim.start)
    
    def paintEvent(self, event):
        """Draw shadow effect"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw subtle shadow
        for i in range(5):
            opacity = 0.02 * (5 - i)
            painter.setOpacity(opacity)
            painter.setBrush(QColor(0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            offset = i * 2
            painter.drawRoundedRect(
                offset, offset,
                self.width() - offset * 2,
                self.height() - offset * 2,
                16, 16
            )


def main():
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create splash app
    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()
    
    # Launch the main app after a brief delay
    def launch_main_app():
        pythonw = os.path.join(script_dir, ".venv", "Scripts", "pythonw.exe")
        run_script = os.path.join(script_dir, "run.pyw")
        
        if os.path.exists(pythonw):
            subprocess.Popen([pythonw, run_script], 
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        else:
            subprocess.Popen(["pythonw", run_script],
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    
    # Launch main app after 500ms (let splash be visible)
    QTimer.singleShot(500, launch_main_app)
    
    # Close splash after 3 seconds (main app should be loading by then)
    QTimer.singleShot(3000, app.quit)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
