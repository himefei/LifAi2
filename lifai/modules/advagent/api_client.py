import requests
from typing import Dict, List, Optional
from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class AnythingLLMClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
    
    def get_workspaces(self) -> List[Dict]:
        """Fetch available workspaces"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/workspaces",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json().get("workspaces", [])
        except Exception as e:
            logger.error(f"Error fetching workspaces: {e}")
            return []
            
    def send_chat_message(self, workspace_slug: str, message: str, 
                         mode: str = "chat") -> Dict:
        """Send a chat message to a workspace"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/workspace/{workspace_slug}/chat",
                headers=self.headers,
                json={"message": message, "mode": mode}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error sending chat message: {e}")
            raise 