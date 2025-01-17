from typing import Optional, List
import requests
import logging
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

    def generate_response(self, prompt: str, model: str) -> Optional[str]:
        try:
            if not prompt:
                raise ValueError("Prompt cannot be empty")
            if not model:
                raise ValueError("Model name cannot be empty")

            logger.debug(f"Generating response using model: {model}")
            logger.debug(f"Prompt: {prompt[:100]}...")  # Log first 100 chars of prompt

            # Prepare request data
            request_data = {
                "model": model,
                "prompt": prompt,
                "stream": False  # Get complete response at once
            }
            
            logger.debug(f"Sending request to {self.base_url}/api/generate")
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=request_data,
                timeout=30  # 30 second timeout
            )

            if response.status_code == 200:
                try:
                    response_json = response.json()
                    result = response_json.get('response', '')
                    if not result:
                        raise ValueError("Empty response from server")
                    
                    logger.info("Successfully generated response")
                    logger.debug(f"Response length: {len(result)} characters")
                    return result.strip()
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    raise ValueError("Invalid response format from server")
            else:
                error_msg = f"Failed to generate response. Status code: {response.status_code}"
                try:
                    error_details = response.json()
                    if 'error' in error_details:
                        error_msg += f". Error: {error_details['error']}"
                except:
                    pass
                logger.error(error_msg)
                raise ValueError(error_msg)

        except requests.exceptions.ConnectionError:
            error_msg = "Could not connect to Ollama server. Is it running?"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        except requests.exceptions.Timeout:
            error_msg = "Request timed out. The server took too long to respond."
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)