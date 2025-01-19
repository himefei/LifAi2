import requests
import json
import logging
from typing import List, Dict, Optional, Union

logger = logging.getLogger(__name__)

class LMStudioClient:
    def __init__(self, base_url="http://localhost:1234/v1"):
        self.base_url = base_url
        self.default_headers = {
            "Content-Type": "application/json"
        }

    def fetch_models(self) -> List[str]:
        """
        Fetch available models from LM Studio API
        """
        try:
            response = requests.get(f"{self.base_url}/models")
            if response.status_code == 200:
                models_data = response.json()
                model_names = []
                for model in models_data.get('data', []):
                    model_id = model.get('id', '')
                    if model_id:
                        model_names.append(model_id)
                logging.info(f"Found {len(model_names)} models in LM Studio")
                return model_names if model_names else ["No models found"]
            else:
                logging.error(f"Failed to fetch models from LM Studio: {response.status_code}")
                return ["LM Studio connection error"]
        except Exception as e:
            logging.error(f"Error connecting to LM Studio: {e}")
            return ["LM Studio not running"]

    def generate_response(self, prompt: str, model: Optional[str] = None, 
                         temperature: float = 0.7, stream: bool = False,
                         format: Optional[Union[str, Dict]] = None) -> str:
        """
        Generate a response using LM Studio's API with enhanced features
        """
        try:
            messages = [{"role": "user", "content": prompt}]
            data = {
                "messages": messages,
                "temperature": temperature,
                "stream": stream
            }

            if format:
                data["response_format"] = {"type": format} if isinstance(format, str) else format

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.default_headers,
                json=data,
                stream=stream
            )
            response.raise_for_status()

            if stream:
                return self._handle_stream_response(response)
            
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content'].strip()
            else:
                raise Exception("No response content received from LM Studio")
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {e}")
            raise Exception(f"LM Studio request failed: {str(e)}")
        except Exception as e:
            logging.error(f"Error generating response from LM Studio: {e}")
            raise

    def chat_completion(self, messages: List[Dict], model: Optional[str] = None,
                       temperature: float = 0.7, stream: bool = False,
                       format: Optional[Union[str, Dict]] = None) -> Dict:
        """
        Generate a chat completion with enhanced features
        """
        try:
            data = {
                "messages": messages,
                "temperature": temperature,
                "stream": stream
            }

            if format:
                data["response_format"] = {"type": format} if isinstance(format, str) else format

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.default_headers,
                json=data,
                stream=stream
            )
            response.raise_for_status()

            if stream:
                return self._handle_stream_response(response)
            return response.json()

        except Exception as e:
            logging.error(f"Error in LM Studio chat completion: {e}")
            raise

    def generate_embeddings(self, input_text: Union[str, List[str]], 
                          model: Optional[str] = None) -> Dict:
        """
        Generate embeddings using LM Studio's API
        """
        try:
            data = {
                "input": input_text if isinstance(input_text, list) else [input_text]
            }
            if model:
                data["model"] = model

            response = requests.post(
                f"{self.base_url}/embeddings",
                headers=self.default_headers,
                json=data
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logging.error(f"Error generating embeddings: {e}")
            raise

    def _handle_stream_response(self, response) -> str:
        """Handle streaming responses from the API"""
        try:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        json_str = line[6:]  # Remove 'data: ' prefix
                        try:
                            chunk = json.loads(json_str)
                            if 'choices' in chunk and chunk['choices']:
                                content = chunk['choices'][0].get('delta', {}).get('content', '')
                                if content:
                                    full_response += content
                        except json.JSONDecodeError:
                            continue
            return full_response
        except Exception as e:
            raise Exception(f"Error handling stream response: {str(e)}") 