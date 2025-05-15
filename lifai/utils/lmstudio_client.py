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
            
    def fetch_models_sync(self) -> List[str]:
        """
        Synchronous wrapper for fetch_models.
        Uses asyncio to run the async method in the current thread.
        """
        try:
            # Always create a new event loop for thread safety
            # This handles the case where we're in a new thread without an event loop
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(self.fetch_models())
            finally:
                new_loop.close()
        except Exception as e:
            logger.error(f"Error in fetch_models_sync: {e}")
            return ["Error fetching models"]

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
        temperature: Optional[float] = None,  # Changed from default 0.7 to None
        stream: bool = False,
        format: Optional[Union[str, Dict]] = None
    ) -> Dict:
        """
        Asynchronously generate a chat completion with enhanced features.
        """
        try:
            # Build request data with only non-None parameters
            data = {
                "messages": messages,
                "stream": stream
            }
            
            # Only include temperature if it's provided
            if temperature is not None:
                data["temperature"] = temperature
                
            # Include model if provided
            if model:
                data["model"] = model
                
            if format:
                data["response_format"] = {"type": format} if isinstance(format, str) else format

            # Increase timeout for reasoning models which may take longer
            timeout = 120  # Increased from 30 to 120 seconds
            
            logger.debug(f"Sending request to LM Studio with data: {data}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.default_headers,
                    json=data,
                    timeout=timeout
                )
                
                # Log response status
                logger.debug(f"LM Studio response status: {response.status_code}")
                
                # Raise for HTTP errors
                response.raise_for_status()

                if stream:
                    return await self._handle_stream_response(response)
                    
                # Parse JSON response
                json_response = response.json()
                logger.debug(f"Received valid JSON response from LM Studio")
                return json_response
                
        except httpx.RequestError as e:
            logger.error(f"HTTP request error in LM Studio chat completion: {e}")
            raise Exception(f"LM Studio chat completion failed: {str(e)}")
        except httpx.HTTPStatusError as e:
            # More specific error for HTTP status errors
            logger.error(f"HTTP status error in LM Studio chat completion: {e.response.status_code} - {e.response.text}")
            raise Exception(f"LM Studio returned error status {e.response.status_code}: {e.response.text}")
        except json.JSONDecodeError as e:
            # Handle invalid JSON responses
            logger.error(f"Invalid JSON response from LM Studio: {e}")
            raise Exception(f"LM Studio returned invalid JSON response: {str(e)}")
        except Exception as e:
            logger.error(f"Error in LM Studio chat completion: {e}")
            raise

    def chat_completion_sync(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,  # Changed from default 0.7 to None
        stream: bool = False,
        format: Optional[Union[str, Dict]] = None
    ) -> Dict:
        """
        Synchronous wrapper for chat_completion.
        Uses asyncio to run the async method in the current thread.
        """
        try:
            # Always create a new event loop for thread safety
            # This handles the case where we're in a new thread without an event loop
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                logger.debug(f"Running chat_completion in sync mode with messages: {messages[:1]}...")
                result = new_loop.run_until_complete(self.chat_completion(messages, model, temperature, stream, format))
                logger.debug("Successfully completed chat_completion_sync")
                return result
            finally:
                new_loop.close()
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in chat_completion_sync: {error_msg}")
            
            # Provide more context in the error message
            if "timeout" in error_msg.lower():
                raise Exception(f"LM Studio request timed out. Reasoning models may require more time to generate responses: {error_msg}")
            elif "status" in error_msg.lower():
                raise Exception(f"LM Studio server error: {error_msg}")
            else:
                raise Exception(f"Error in chat completion: {error_msg}")

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
        Improved to better handle responses from reasoning models.
        """
        try:
            full_response = ""
            line_count = 0
            logger.debug("Starting to process streaming response")
            
            async for line in response.aiter_lines():
                line_count += 1
                if not line:
                    continue
                    
                # Handle standard SSE format
                if line.startswith('data: '):
                    json_str = line[6:]  # Remove 'data: ' prefix
                    if json_str.strip() == "[DONE]":
                        logger.debug("Received [DONE] marker in stream")
                        break
                        
                    try:
                        chunk = json.loads(json_str)
                        
                        # Handle different response formats
                        if 'choices' in chunk and chunk['choices']:
                            # Standard OpenAI-compatible format
                            choice = chunk['choices'][0]
                            
                            # Handle both delta format (streaming) and message format (non-streaming)
                            if 'delta' in choice:
                                content = choice['delta'].get('content', '')
                            elif 'message' in choice:
                                content = choice['message'].get('content', '')
                            else:
                                content = ''
                                
                            if content:
                                full_response += content
                                
                        # Handle reasoning model specific formats if needed
                        elif 'response' in chunk:
                            # Some models might use a simpler format
                            content = chunk.get('response', '')
                            if content:
                                full_response += content
                                
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON in streaming response: {e}, line: {json_str[:50]}...")
                        continue
                else:
                    # Some implementations might not use the 'data: ' prefix
                    try:
                        chunk = json.loads(line)
                        if 'content' in chunk:
                            full_response += chunk['content']
                    except json.JSONDecodeError:
                        # Not JSON, ignore
                        pass
                        
            logger.debug(f"Completed streaming response processing, received {line_count} lines")
            return full_response
            
        except Exception as e:
            logger.error(f"Error handling stream response: {e}")
            raise Exception(f"Error handling stream response: {str(e)}")