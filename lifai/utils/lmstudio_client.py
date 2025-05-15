"""
LMStudioClient: Async Python client for interacting with LM Studio's local LLM API.

This module provides asynchronous methods for model listing, chat completions, and embeddings
using LM Studio's HTTP API. Designed for robust error handling, performance, and integration
with LifAi2's modular architecture.

Features:
    - Async HTTP requests for non-blocking UI and fast response.
    - Comprehensive error handling and logging.
    - Support for streaming responses and flexible API parameters.
"""

import httpx
import json
import logging
import asyncio
from typing import List, Dict, Optional, Union

logger = logging.getLogger(__name__)

class LMStudioClient:
    """Async client for LM Studio's local LLM API (chat, models, embeddings)."""
    def __init__(self, base_url="http://localhost:1234/v1"):
        self.base_url = base_url
        self.default_headers = {
            "Content-Type": "application/json"
        }

    async def fetch_models(self) -> List[str]:
        """
        Asynchronously fetch available models from LM Studio API.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/models", timeout=10)
                response.raise_for_status()
                models_data = response.json()
                model_names = []
                for model in models_data.get('data', []):
                    model_id = model.get('id', '')
                    if model_id:
                        model_names.append(model_id)
                logger.info(f"Found {len(model_names)} models in LM Studio")
                return model_names if model_names else ["No models found"]
        except httpx.RequestError as e:
            logger.error(f"HTTP error connecting to LM Studio: {e}")
            return ["LM Studio connection error"]
        except Exception as e:
            logger.error(f"Error connecting to LM Studio: {e}")
            return ["LM Studio not running"]

    async def generate_response(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False,
        format: Optional[Union[str, Dict]] = None
    ) -> str:
        """
        Asynchronously generate a response using LM Studio's API with enhanced features.
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

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.default_headers,
                    json=data,
                    timeout=30
                )
                response.raise_for_status()

                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content'].strip()
                else:
                    raise Exception("No response content received from LM Studio")
        except httpx.RequestError as e:
            logger.error(f"HTTP request error: {e}")
            raise Exception(f"LM Studio request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating response from LM Studio: {e}")
            raise

    async def chat_completion(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False,
        format: Optional[Union[str, Dict]] = None
    ) -> Dict:
        """
        Asynchronously generate a chat completion with enhanced features.
        """
        try:
            data = {
                "messages": messages,
                "temperature": temperature,
                "stream": stream
            }
            if format:
                data["response_format"] = {"type": format} if isinstance(format, str) else format

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.default_headers,
                    json=data,
                    timeout=30
                )
                response.raise_for_status()

                if stream:
                    return await self._handle_stream_response(response)
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"HTTP request error in LM Studio chat completion: {e}")
            raise Exception(f"LM Studio chat completion failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error in LM Studio chat completion: {e}")
            raise

    async def generate_embeddings(
        self,
        input_text: Union[str, List[str]],
        model: Optional[str] = None
    ) -> Dict:
        """
        Asynchronously generate embeddings using LM Studio's API.
        """
        try:
            data = {
                "input": input_text if isinstance(input_text, list) else [input_text]
            }
            if model:
                data["model"] = model

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=self.default_headers,
                    json=data,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"HTTP request error generating embeddings: {e}")
            raise Exception(f"LM Studio embeddings request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    async def _handle_stream_response(self, response: httpx.Response) -> str:
        """
        Asynchronously handle streaming responses from the API.
        """
        try:
            full_response = ""
            async for line in response.aiter_lines():
                if line:
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