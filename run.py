#!/usr/bin/env python3
import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.append(project_root)

# Initialize QApplication before importing any QWidgets
from PyQt6.QtWidgets import QApplication
from lifai.core.app_hub import main, create_robot_icon

# Create QApplication
qt_app = QApplication.instance()
if not qt_app:
    qt_app = QApplication(sys.argv)
    # Set the application icon globally
    qt_app.setWindowIcon(create_robot_icon())

if __name__ == "__main__":
    main() 