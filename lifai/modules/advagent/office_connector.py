import requests
from typing import Dict, Optional
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class PowerAppsConnector:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
    def send_to_powerapp(self, data: Dict) -> bool:
        """Send data to PowerApp through Power Automate"""
        try:
            # Implementation depends on your PowerApps setup
            # Usually involves sending to a Power Automate HTTP trigger
            response = requests.post(
                self.connection_string,
                json=data
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error sending to PowerApp: {e}")
            return False 