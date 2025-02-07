from typing import Optional, List, Dict, Union
import requests
import logging
from lifai.utils.logger_utils import get_module_logger
import json
import base64

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
        """Fetch available models from Ollama server"""
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

    def generate_response(self, model: str, prompt: str, stream: bool = False,
                          format: Optional[Union[str, Dict]] = None,
                          options: Optional[Dict] = None,
                          temperature: Optional[float] = None) -> str:
        """Generate a response from the model with enhanced features"""
        try:
            url = f"{self.base_url}/api/generate"
            data = {
                "model": model,
                "prompt": prompt,
                "stream": stream
            }
            
            # Add optional parameters if provided
            if format:
                data["format"] = format

            # Initialize options dictionary if not provided
            if not options:
                options = {}
            
            # Add temperature to options if provided
            if temperature is not None:
                options["temperature"] = temperature
            
            # Add options to data if not empty
            if options:
                data["options"] = options
            
            # Increased timeout to 120 seconds for longer text processing
            response = requests.post(url, json=data, timeout=120)
            
            if response.status_code == 200:
                if stream:
                    return self._handle_stream_response(response)
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

    def chat_completion(self, model: str, messages: List[Dict],
                        stream: bool = False,
                        format: Optional[Union[str, Dict]] = None,
                        options: Optional[Dict] = None,
                        temperature: Optional[float] = None) -> Dict:
        """Generate a chat completion using the new chat API"""
        try:
            url = f"{self.base_url}/api/chat"
            data = {
                "model": model,
                "messages": messages,
                "stream": stream
            }
            
            if format:
                data["format"] = format
            
            # Initialize options dictionary if not provided
            if not options:
                options = {}
            
            # Add temperature to options if provided
            if temperature is not None:
                options["temperature"] = temperature
            
            # Add options to data if not empty
            if options:
                data["options"] = options

            response = requests.post(url, json=data, timeout=120)
            
            if response.status_code == 200:
                if stream:
                    return self._handle_stream_response(response)
                return response.json()
            else:
                error_msg = f"Chat completion failed with status {response.status_code}"
                if response.text:
                    error_msg += f": {response.text}"
                raise Exception(error_msg)

        except Exception as e:
            raise Exception(f"Error in chat completion: {str(e)}")

    def _handle_stream_response(self, response) -> str:
        """Handle streaming responses from the API"""
        try:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    json_response = json.loads(line)
                    if "response" in json_response:
                        full_response += json_response["response"]
            return full_response
        except Exception as e:
            raise Exception(f"Error handling stream response: {str(e)}")

    def generate_embeddings(self, model: str, input_text: Union[str, List[str]], 
                          options: Optional[Dict] = None) -> Dict:
        """Generate embeddings for text using the embeddings API"""
        try:
            url = f"{self.base_url}/api/embed"
            data = {
                "model": model,
                "input": input_text
            }
            
            if options:
                data["options"] = options

            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"Embeddings generation failed with status {response.status_code}"
                if response.text:
                    error_msg += f": {response.text}"
                raise Exception(error_msg)

        except Exception as e:
            raise Exception(f"Error generating embeddings: {str(e)}")