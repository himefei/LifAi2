from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTextEdit, QLineEdit, QPushButton, QComboBox, 
                            QLabel, QFrame, QSplitter, QProgressBar,
                            QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QTimer
import pyqtgraph as pg
from typing import Dict
import requests
import time
import logging
import traceback

from .performance_monitor import PerformanceMonitor
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class AdvAgentWindow(QMainWindow):
    def __init__(self, settings: Dict):
        super().__init__()
        self.settings = settings
        
        # API Configuration
        self.base_url = "http://localhost:3001"
        self.api_key = "6R9718K-GJ84M70-K0NH23Z-M0GY9K6"
        
        # Define default headers with Bearer authentication
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",  # Added Bearer prefix
            "Content-Type": "application/json"
        }
        
        logger.info("Initializing Advanced Agent Window")
        logger.debug(f"Base URL: {self.base_url}")
        logger.debug(f"Headers configured: {self.headers}")
        
        self.setWindowTitle("Advanced Agent Interface")
        self.setGeometry(100, 100, 1400, 800)
        
        # Initialize performance monitor
        self.perf_monitor = PerformanceMonitor()
        self.perf_monitor.update_signal.connect(self.update_performance_display)
        self.perf_monitor.start()
        
        self.setup_ui()
        self.load_workspaces()

    def setup_ui(self):
        """Setup the main UI components"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        # Create left panel (Chat Interface)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Add workspace selector
        workspace_layout = QHBoxLayout()
        workspace_layout.addWidget(QLabel("Select Workspace:"))
        self.workspace_combo = QComboBox()
        workspace_layout.addWidget(self.workspace_combo)
        left_layout.addLayout(workspace_layout)
        
        # Create main chat container with splitter
        chat_container = QSplitter(Qt.Orientation.Vertical)
        
        # Add chat display with larger font
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        font = self.chat_display.font()
        font.setPointSize(font.pointSize() + 2)
        self.chat_display.setFont(font)
        chat_container.addWidget(self.chat_display)
        
        # Add input text box (using QTextEdit instead of QLineEdit for multi-line)
        self.message_input = QTextEdit()  # Changed to QTextEdit
        self.message_input.setFont(font)
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.setMinimumHeight(150)  # Increased minimum height
        chat_container.addWidget(self.message_input)
        
        # Add send button below the input
        send_button = QPushButton("Send")
        send_button.clicked.connect(self.send_message)
        
        # Create layout for the entire chat section
        chat_layout = QVBoxLayout()
        chat_layout.addWidget(chat_container)
        chat_layout.addWidget(send_button)
        
        # Add the chat layout to the main left layout
        left_layout.addLayout(chat_layout)
        
        # Create right panel (Performance Monitoring)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # GPU Metrics
        metrics_group = QFrame()
        metrics_layout = QVBoxLayout(metrics_group)
        
        # GPU Usage
        self.gpu_util_bar = QProgressBar()
        self.gpu_util_bar.setFormat("GPU Usage: %p%")
        metrics_layout.addWidget(QLabel("GPU Utilization:"))
        metrics_layout.addWidget(self.gpu_util_bar)
        
        # VRAM Usage
        self.vram_bar = QProgressBar()
        self.vram_bar.setFormat("VRAM Usage: %p%")
        metrics_layout.addWidget(QLabel("VRAM Usage:"))
        metrics_layout.addWidget(self.vram_bar)
        
        # Response Time Metrics
        self.response_metrics = QTableWidget(3, 2)
        self.response_metrics.setHorizontalHeaderLabels(["Metric", "Value"])
        self.response_metrics.verticalHeader().setVisible(False)
        self.response_metrics.setItem(0, 0, QTableWidgetItem("Min Response Time"))
        self.response_metrics.setItem(1, 0, QTableWidgetItem("Max Response Time"))
        self.response_metrics.setItem(2, 0, QTableWidgetItem("Avg Response Time"))
        metrics_layout.addWidget(QLabel("Response Times:"))
        metrics_layout.addWidget(self.response_metrics)
        
        # Success Rate
        self.success_rate_bar = QProgressBar()
        self.success_rate_bar.setFormat("Success Rate: %p%")
        metrics_layout.addWidget(QLabel("Success Rate:"))
        metrics_layout.addWidget(self.success_rate_bar)
        
        # Token Metrics
        self.token_metrics = QTableWidget(2, 2)
        self.token_metrics.setHorizontalHeaderLabels(["Metric", "Count"])
        self.token_metrics.verticalHeader().setVisible(False)
        self.token_metrics.setItem(0, 0, QTableWidgetItem("Tokens Sent"))
        self.token_metrics.setItem(1, 0, QTableWidgetItem("Tokens Received"))
        metrics_layout.addWidget(QLabel("Token Usage:"))
        metrics_layout.addWidget(self.token_metrics)
        
        # Response Time Graph
        self.response_plot = pg.PlotWidget()
        self.response_plot.setTitle("Response Times")
        self.response_curve = self.response_plot.plot(pen='b')
        metrics_layout.addWidget(self.response_plot)
        
        right_layout.addWidget(metrics_group)
        
        # Add panels to main layout with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)

    def load_workspaces(self):
        """Load available workspaces from the API"""
        try:
            logger.info("Attempting to load workspaces...")
            self.chat_display.append("Loading workspaces...")
            
            logger.debug(f"Request URL: {self.base_url}/api/v1/workspaces")
            logger.debug(f"Request Headers: {self.headers}")
            
            response = requests.get(
                f"{self.base_url}/api/v1/workspaces",
                headers=self.headers
            )
            
            logger.debug(f"Response Status: {response.status_code}")
            logger.debug(f"Response Headers: {response.headers}")
            logger.debug(f"Response Body: {response.text}")
            
            if response.status_code == 200:
                workspaces = response.json().get("workspaces", [])
                logger.info(f"Successfully loaded {len(workspaces)} workspaces")
                logger.debug(f"Workspaces: {workspaces}")
                
                self.workspace_combo.clear()
                for workspace in workspaces:
                    self.workspace_combo.addItem(workspace["name"], workspace["slug"])
                self.chat_display.append(f"Loaded {len(workspaces)} workspaces successfully\n")
            else:
                error_msg = f"Failed to load workspaces. Status code: {response.status_code}"
                logger.error(f"{error_msg}. Response: {response.text}")
                self.chat_display.append(f"{error_msg}\n")
                
        except Exception as e:
            error_msg = f"Error loading workspaces: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_display.append(f"{error_msg}\n")
            QMessageBox.critical(self, "Error", error_msg)

    def send_message(self):
        """Send a message to the selected workspace"""
        message = self.message_input.toPlainText().strip()
        if not message:
            logger.warning("Attempted to send empty message")
            return
        
        workspace_slug = self.workspace_combo.currentData()
        if not workspace_slug:
            error_msg = "Error: No workspace selected"
            logger.error(error_msg)
            self.chat_display.append(f"{error_msg}\n")
            return
        
        logger.info(f"Sending message to workspace: {workspace_slug}")
        logger.debug(f"Message content: {message}")
        
        self.chat_display.append(f"\nYou: {message}")
        self.message_input.clear()
        
        try:
            start_time = time.time()
            
            data = {
                "message": message,
                "mode": "chat"
            }
            
            logger.debug(f"Request URL: {self.base_url}/api/v1/workspace/{workspace_slug}/chat")
            logger.debug(f"Request Headers: {self.headers}")
            logger.debug(f"Request Data: {data}")
            
            response = requests.post(
                f"{self.base_url}/api/v1/workspace/{workspace_slug}/chat",
                headers=self.headers,
                json=data
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            logger.debug(f"Response Status: {response.status_code}")
            logger.debug(f"Response Time: {response_time:.2f}s")
            logger.debug(f"Response Body: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                bot_response = result.get("textResponse", "No response received")
                self.chat_display.append(f"\nBot: {bot_response}")
                
                if result.get("sources"):
                    self.chat_display.append("\nSources:")
                    for source in result["sources"]:
                        self.chat_display.append(f"- {source['title']}")
                
                logger.info("Message sent and response received successfully")
                
                # Update performance metrics
                self.perf_monitor.add_request_metric(
                    response_time=response_time,
                    success=True,
                    tokens_sent=len(message.split()),
                    tokens_received=len(bot_response.split())
                )
            else:
                error_msg = f"\nError: Failed to get response (Status code: {response.status_code})"
                logger.error(f"{error_msg}. Response: {response.text}")
                self.chat_display.append(error_msg)
                self.perf_monitor.add_request_metric(
                    response_time=response_time,
                    success=False,
                    tokens_sent=len(message.split()),
                    tokens_received=0
                )
            
        except Exception as e:
            error_msg = f"\nError: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.chat_display.append(error_msg)
            QMessageBox.critical(self, "Error", f"Failed to send message: {str(e)}")
        
        # Scroll to bottom
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        """Handle window close event"""
        event.ignore()
        self.hide()

    def show(self):
        """Show the window"""
        super().show()
        self.raise_()

    def hide(self):
        """Hide the window"""
        super().hide()

    def update_performance_display(self, metrics: Dict):
        """Update the performance display with new metrics"""
        try:
            # Update GPU metrics
            self.gpu_util_bar.setValue(int(metrics.get('gpu_util', 0)))
            if metrics.get('vram_total', 0) > 0:
                vram_percentage = (metrics.get('vram_used', 0) / metrics.get('vram_total', 1)) * 100
                self.vram_bar.setValue(int(vram_percentage))
            
            # Update response time metrics
            if hasattr(self, 'response_metrics'):
                self.response_metrics.setItem(0, 1, QTableWidgetItem(f"{metrics.get('min_response_time', 0):.2f}s"))
                self.response_metrics.setItem(1, 1, QTableWidgetItem(f"{metrics.get('max_response_time', 0):.2f}s"))
                self.response_metrics.setItem(2, 1, QTableWidgetItem(f"{metrics.get('avg_response_time', 0):.2f}s"))
            
            # Update success rate
            if hasattr(self, 'success_rate_bar'):
                success_rate = metrics.get('success_rate', 0)
                self.success_rate_bar.setValue(int(success_rate))
            
            # Update token metrics
            if hasattr(self, 'token_metrics'):
                self.token_metrics.setItem(0, 1, QTableWidgetItem(str(metrics.get('tokens_sent', 0))))
                self.token_metrics.setItem(1, 1, QTableWidgetItem(str(metrics.get('tokens_received', 0))))
            
            # Update response time graph
            if hasattr(self, 'response_curve'):
                response_times = metrics.get('response_times', [])
                if response_times:
                    self.response_curve.setData(list(response_times))
            
        except Exception as e:
            logger.error(f"Error updating performance display: {e}")