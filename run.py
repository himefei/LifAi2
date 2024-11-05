#!/usr/bin/env python3
import os
import sys
import ctypes

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.append(project_root)

# Set DPI awareness before creating QApplication
if sys.platform == 'win32':
    try:
        # Enable Per Monitor V2 DPI awareness
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE_V2
    except Exception:
        try:
            # Fall back to Per Monitor DPI awareness
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception as e:
            print(f"Failed to set DPI awareness: {e}")

# Initialize QApplication before importing any QWidgets
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Create QApplication with appropriate DPI scaling
qt_app = QApplication.instance()
if not qt_app:
    qt_app = QApplication(sys.argv)
    # In PyQt6, high DPI scaling is enabled by default
    # We can adjust the scaling policy if needed
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

from lifai.core.app_hub import LifAiHub

if __name__ == "__main__":
    app = LifAiHub()
    app.run() 