from PyQt6.QtCore import QThread, pyqtSignal
from collections import deque
import time
from datetime import datetime
import csv
import GPUtil
from typing import Dict

class PerformanceMonitor(QThread):
    update_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.metrics = {
            'response_times': deque(maxlen=100),
            'success_count': 0,
            'failed_count': 0,
            'tokens_sent': 0,
            'tokens_received': 0,
            'min_response_time': float('inf'),
            'max_response_time': 0,
            'avg_response_time': 0
        }
        
    # ... [Rest of the PerformanceMonitor implementation from sample code] 