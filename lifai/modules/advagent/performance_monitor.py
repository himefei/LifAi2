from PyQt6.QtCore import QThread, pyqtSignal
from collections import deque
import time
from datetime import datetime
import csv
import GPUtil
from typing import Dict
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

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

    def add_request_metric(self, response_time: float, success: bool, 
                         tokens_sent: int = 0, tokens_received: int = 0):
        """Add metrics for a single request"""
        try:
            logger.debug(f"Adding metrics - Time: {response_time:.2f}s, Success: {success}, "
                        f"Tokens sent: {tokens_sent}, Tokens received: {tokens_received}")
            
            # Update response times
            self.metrics['response_times'].append(response_time)
            
            # Update success/failure counts
            if success:
                self.metrics['success_count'] += 1
            else:
                self.metrics['failed_count'] += 1
            
            # Update token counts (estimated from word count)
            self.metrics['tokens_sent'] += tokens_sent
            self.metrics['tokens_received'] += tokens_received
            
            # Update response time stats
            if response_time < self.metrics['min_response_time']:
                self.metrics['min_response_time'] = response_time
            if response_time > self.metrics['max_response_time']:
                self.metrics['max_response_time'] = response_time
            
            # Calculate average response time
            if self.metrics['response_times']:
                self.metrics['avg_response_time'] = sum(self.metrics['response_times']) / len(self.metrics['response_times'])
            
            logger.debug(f"Updated metrics: {self.metrics}")
            
        except Exception as e:
            logger.error(f"Error adding request metric: {e}")

    def run(self):
        """Monitor performance metrics"""
        while self.running:
            try:
                # Get GPU metrics if available
                gpu_metrics = {}
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]  # Get first GPU
                        gpu_metrics = {
                            'gpu_util': gpu.load * 100,
                            'vram_used': gpu.memoryUsed,
                            'vram_total': gpu.memoryTotal
                        }
                except Exception as e:
                    logger.warning(f"Could not get GPU metrics: {e}")
                    gpu_metrics = {
                        'gpu_util': 0,
                        'vram_used': 0,
                        'vram_total': 0
                    }

                # Calculate success rate
                total_requests = self.metrics['success_count'] + self.metrics['failed_count']
                success_rate = (self.metrics['success_count'] / total_requests * 100) if total_requests > 0 else 0

                # Combine all metrics
                current_metrics = {
                    **self.metrics,
                    **gpu_metrics,
                    'success_rate': success_rate
                }
                
                self.update_signal.emit(current_metrics)
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
            
            time.sleep(1)  # Update every second

    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        self.wait()