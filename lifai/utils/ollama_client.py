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

    def fetch_models(self) -> List[str]:
        try:
            logger.debug("Fetching available models from Ollama")
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = [model['name'] for model in response.json()['models']]
                logger.info(f"Successfully fetched {len(models)} models")
                return models
            else:
                logger.error(f"Failed to fetch models. Status code: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching models: {str(e)}")
            return []

    def generate_response(self, prompt: str, model: str) -> Optional[str]:
        try:
            logger.debug(f"Generating response using model: {model}")
            logger.debug(f"Prompt: {prompt[:100]}...")

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False  # Get complete response at once
                }
            )

            if response.status_code == 200:
                # Extract just the response text from the JSON response
                response_json = response.json()
                result = response_json.get('response', '')
                
                logger.info("Successfully generated response")
                logger.debug(f"Response length: {len(result)} characters")
                return result.strip()
            else:
                logger.error(f"Failed to generate response. Status code: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return None