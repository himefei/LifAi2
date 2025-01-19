from typing import Optional, List, Dict, Union
import requests
import logging
import base64
from lifai.utils.logger_utils import get_module_logger
import json

logger = get_module_logger(__name__)

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        logger.info(f"Initializing OllamaClient with base URL: {base_url}")
        # Test connection on init
        self.test_connection()

    def test_connection(self) -> bool:
        """Test connection to Ollama server"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info("Successfully connected to Ollama server")
                return True
            else:
                logger.error(f"Failed to connect to Ollama server. Status code: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to Ollama server. Is it running?")
            return False
        except Exception as e:
            logger.error(f"Error testing connection: {str(e)}")
            return False

    def fetch_models(self) -> List[str]:
        try:
            logger.debug("Fetching available models from Ollama")
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = [model['name'] for model in response.json()['models']]
                logger.info(f"Successfully fetched {len(models)} models")
                return models
            else:
                logger.error(f"Failed to fetch models. Status code: {response.status_code}")
                return []
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to Ollama server. Is it running?")
            return []
        except Exception as e:
            logger.error(f"Error fetching models: {str(e)}")
            return []

    def generate_response(self, prompt: str, model: str = "mistral", 
                         images: Optional[List[str]] = None,
                         format: Optional[Union[str, Dict]] = None,
                         stream: bool = False) -> str:
        """Generate a response from the model with enhanced features

        Args:
            prompt: The prompt to generate a response for
            model: The model to use
            images: Optional list of base64 encoded images for multimodal models
            format: Optional format specification ('json' or a JSON schema)
            stream: Whether to stream the response
        """
        try:
            url = f"{self.base_url}/api/generate"
            data = {
                "model": model,
                "prompt": prompt,
                "stream": stream
            }

            # Add optional parameters if provided
            if images:
                data["images"] = images
            if format:
                data["format"] = format
            
            # Increased timeout to 120 seconds for longer text processing
            response = requests.post(url, json=data, timeout=120)
            
            if response.status_code == 200:
                return response.json()["response"]
            else:
                error_msg = f"Request failed with status {response.status_code}"
                if response.text:
                    error_msg += f": {response.text}"
                raise Exception(error_msg)
                
        except requests.exceptions.Timeout:
            raise Exception("Request timed out. The server took too long to respond.")
        except Exception as e:
            raise Exception(f"Error generating response: {str(e)}")

    def chat_completion(self, messages: List[Dict], model: str = "mistral",
                       stream: bool = False, 
                       format: Optional[Union[str, Dict]] = None) -> Dict:
        """Generate a chat completion using the new chat endpoint
        
        Args:
            messages: List of message dictionaries with role and content
            model: The model to use
            stream: Whether to stream the response
            format: Optional format specification ('json' or a JSON schema)
        """
        try:
            url = f"{self.base_url}/api/chat"
            data = {
                "model": model,
                "messages": messages,
                "stream": stream
            }

            if format:
                data["format"] = format

            response = requests.post(url, json=data, timeout=120)
            response.raise_for_status()
            
            return response.json()

        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise