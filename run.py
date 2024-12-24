#!/usr/bin/env python3
import os
import sys
import ctypes

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.append(project_root)

# Set Qt attributes before creating QApplication
from PyQt6.QtCore import Qt, QCoreApplication

# Set high DPI attributes
# PyQt6 已经默认启用了高 DPI 缩放
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_Use96Dpi)

# Initialize QApplication before importing any QWidgets
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QGuiApplication

# Set DPI scaling policy before creating QApplication
QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

# Set Windows DPI awareness
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

# Create QApplication
qt_app = QApplication.instance()
if not qt_app:
    qt_app = QApplication(sys.argv)

from lifai.core.app_hub import main

if __name__ == "__main__":
    main() 