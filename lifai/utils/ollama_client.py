"""
OllamaClient: Enhanced async Python client for Ollama's latest API features.

This module provides comprehensive integration with Ollama's latest API capabilities including
the new embedding endpoints, enhanced streaming, better error handling, and support for
advanced model management features.

Features:
    - Latest Ollama API endpoints including new /api/embed
    - Enhanced streaming responses with better chunk handling
    - Comprehensive model management (list loaded, version info)
    - Batch embedding support for multiple inputs
    - Improved error handling and logging
    - Support for advanced model options and keep_alive
    - Async HTTP requests for optimal performance
"""

from typing import Optional, List, Dict, Union, Any
import httpx
import logging
from lifai.utils.logger_utils import get_module_logger
import json
import base64
import asyncio
import time

logger = get_module_logger(__name__)

class OllamaClient:
    """Enhanced async client for Ollama's latest API features."""
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        logger.info(f"Initializing enhanced OllamaClient with base URL: {base_url}")
        # Test connection on init
        asyncio.create_task(self.test_connection())

    async def test_connection(self) -> bool:
        """Enhanced connection test with version information."""
        try:
            async with httpx.AsyncClient() as client:
                # Test basic connection and get version info
                version_response = await client.get(f"{self.api_base}/version", timeout=5)
                if version_response.status_code == 200:
                    version_info = version_response.json()
                    logger.info(f"Successfully connected to Ollama server version: {version_info}")
                    return True
                else:
                    # Fallback to tags endpoint for older versions
                    tags_response = await client.get(f"{self.api_base}/tags", timeout=5)
                    if tags_response.status_code == 200:
                        logger.info("Successfully connected to Ollama server (legacy version)")
                        return True
                    else:
                        logger.error(f"Failed to connect to Ollama server. Status code: {tags_response.status_code}")
                        return False
        except httpx.RequestError:
            logger.error("Could not connect to Ollama server. Is it running?")
            return False
        except Exception as e:
            logger.error(f"Error testing connection: {str(e)}")
            return False

    async def fetch_models(self) -> List[str]:
        """Enhanced model fetching with additional metadata."""
        try:
            logger.debug("Fetching available models from Ollama")
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base}/tags", timeout=10)
                if response.status_code == 200:
                    models_data = response.json()
                    models = []
                    
                    for model in models_data.get('models', []):
                        model_name = model.get('name', '')
                        if model_name:
                            models.append(model_name)
                            # Log additional model info if available
                            size = model.get('size', 0)
                            modified = model.get('modified_at', '')
                            logger.debug(f"Model: {model_name}, Size: {size}, Modified: {modified}")
                    
                    logger.info(f"Successfully fetched {len(models)} models from Ollama")
                    return models
                else:
                    logger.error(f"Failed to fetch models. Status code: {response.status_code}")
                    return []
        except httpx.RequestError:
            logger.error("Could not connect to Ollama server. Is it running?")
            return []
        except Exception as e:
            logger.error(f"Error fetching models: {str(e)}")
            return []

    async def list_loaded_models(self) -> List[Dict]:
        """List currently loaded models in memory using /api/ps endpoint."""
        try:
            logger.debug("Fetching loaded models from Ollama")
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base}/ps", timeout=5)
                if response.status_code == 200:
                    loaded_data = response.json()
                    models = loaded_data.get('models', [])
                    logger.info(f"Found {len(models)} loaded models in memory")
                    return models
                else:
                    logger.warning(f"Failed to fetch loaded models. Status code: {response.status_code}")
                    return []
        except httpx.RequestError:
            logger.warning("Could not get loaded models info from Ollama")
            return []
        except Exception as e:
            logger.warning(f"Error fetching loaded models: {str(e)}")
            return []
            
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
        model: str,
        prompt: str,
        stream: bool = False,
        format: Optional[Union[str, Dict]] = None,
        options: Optional[Dict] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Asynchronously generate a response from the model with enhanced features."""
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

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=120)
                if response.status_code == 200:
                    if stream:
                        return await self._handle_stream_response(response)
                    return response.json()["response"]
                else:
                    error_msg = f"Request failed with status {response.status_code}"
                    if response.text:
                        error_msg += f": {response.text}"
                    raise Exception(error_msg)
        except httpx.TimeoutException:
            raise Exception("Request timed out. The server took too long to respond.")
        except Exception as e:
            raise Exception(f"Error generating response: {str(e)}")

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict],
        stream: bool = False,
        format: Optional[Union[str, Dict]] = None,
        options: Optional[Dict] = None,
        temperature: Optional[float] = None
    ) -> Dict:
        """Asynchronously generate a chat completion using the new chat API."""
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

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=120)
                if response.status_code == 200:
                    if stream:
                        # For streaming, _handle_stream_response should ideally yield OpenAI-like chunks
                        # or the calling code needs to be adapted.
                        # For now, it returns a concatenated string.
                        # If the calling code for stream expects dicts, this needs further change.
                        return await self._handle_stream_response(response) # This returns a string currently

                    raw_ollama_response = response.json()
                    logger.debug(f"Ollama chat_completion raw non-stream response: {json.dumps(raw_ollama_response, indent=2)}")

                    # Extract and ensure the core message object is well-formed
                    ollama_message_obj = raw_ollama_response.get("message", {"role": "assistant", "content": ""})
                    if not isinstance(ollama_message_obj, dict):
                        logger.warning(f"Ollama raw response 'message' field was not a dict: {ollama_message_obj}. Wrapping it.")
                        ollama_message_obj = {"role": "assistant", "content": str(ollama_message_obj)}
                    else:
                        # Ensure 'content' and 'role' keys exist, providing defaults if necessary
                        ollama_message_obj['content'] = ollama_message_obj.get('content', '')
                        ollama_message_obj['role'] = ollama_message_obj.get('role', 'assistant')

                    # Adapt to a structure that's both OpenAI-like and provides direct message access
                    adapted_response = {
                        "choices": [{
                            "index": 0,
                            "message": ollama_message_obj,  # OpenAI-style path
                            "finish_reason": "stop" if raw_ollama_response.get("done") else "length"
                        }],
                        "message": ollama_message_obj,  # Direct access path, similar to Ollama's native response
                        "model": raw_ollama_response.get("model", model),
                        # Potentially add other fields like id, object, created, usage if needed by consumer
                        # "id": f"chatcmpl-ollama-{raw_ollama_response.get('created_at', '')}",
                        # "object": "chat.completion",
                        # "created": int(time.time()), # Placeholder
                        "usage": {
                            "prompt_tokens": raw_ollama_response.get("prompt_eval_count", 0),
                            "completion_tokens": raw_ollama_response.get("eval_count", 0),
                            "total_tokens": raw_ollama_response.get("prompt_eval_count", 0) + raw_ollama_response.get("eval_count", 0)
                        }
                    }
                    
                    # Log token usage and speed
                    prompt_tokens = raw_ollama_response.get("prompt_eval_count", 0)
                    completion_tokens = raw_ollama_response.get("eval_count", 0)
                    total_tokens = prompt_tokens + completion_tokens
                    eval_duration_ns = raw_ollama_response.get("eval_duration", 0) # Duration for completion tokens
                    
                    tokens_per_second = 0
                    if eval_duration_ns > 0 and completion_tokens > 0:
                        eval_duration_s = eval_duration_ns / 1.0e9  # Convert nanoseconds to seconds
                        tokens_per_second = completion_tokens / eval_duration_s
                        logger.info(
                            f"Ollama Completion Tokens: {completion_tokens}, Prompt Tokens: {prompt_tokens}, Total Tokens: {total_tokens}"
                        )
                        logger.info(f"Ollama Generation Speed: {tokens_per_second:.2f} tokens/sec (Duration: {eval_duration_s:.2f}s)")
                    elif completion_tokens > 0 : # If duration is zero but tokens were generated
                         logger.info(
                            f"Ollama Completion Tokens: {completion_tokens}, Prompt Tokens: {prompt_tokens}, Total Tokens: {total_tokens}"
                        )
                         logger.info(f"Ollama Generation Speed: N/A (eval_duration not available or zero)")
                    else:
                        logger.info(f"Ollama: No completion tokens generated or eval_duration not available.")

                    logger.debug(f"Ollama chat_completion adapted response: {json.dumps(adapted_response, indent=2)}")
                    return adapted_response
                else:
                    error_msg = f"Chat completion failed with status {response.status_code}"
                    if response.text:
                        error_msg += f": {response.text}"
                    raise Exception(error_msg)
        except Exception as e:
            raise Exception(f"Error in chat completion: {str(e)}")

    async def _handle_stream_response(self, response: httpx.Response) -> str:
        """
        Asynchronously handle streaming responses from the API.
        """
        try:
            full_response = ""
            async for line in response.aiter_lines():
                if line:
                    try:
                        json_response = json.loads(line)
                        logger.debug(f"Ollama stream raw line content: {json_response}")
                        content_piece = ""
                        # Check for /api/chat structure
                        if "message" in json_response and isinstance(json_response.get("message"), dict) and "content" in json_response["message"]:
                            content_piece = json_response["message"]["content"]
                        # Check for /api/generate structure
                        elif "response" in json_response:
                            content_piece = json_response["response"]
                        
                        if content_piece:
                            full_response += content_piece
                        
                        # If the stream is supposed to yield structured chunks (OpenAI-like)
                        # this part would need to construct and yield those instead of concatenating.
                        # For now, it matches the previous behavior of returning a single string.

                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON in Ollama streaming response: {e}, line: {line[:100]}...")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing Ollama stream line: {e}, line: {line[:100]}...")
                        continue
            return full_response
        except Exception as e:
            raise Exception(f"Error handling stream response: {str(e)}")

    async def generate_embeddings(
        self,
        model: str,
        input_text: Union[str, List[str]],
        options: Optional[Dict] = None,
        truncate: bool = True,
        keep_alive: str = "5m"
    ) -> Dict:
        """
        Enhanced embeddings generation using the latest /api/embed endpoint.
        
        Args:
            model: Model name for embedding generation
            input_text: Text or list of texts to embed
            options: Additional model parameters
            truncate: Whether to truncate input to fit context length
            keep_alive: How long to keep model loaded after request
            
        Returns:
            Embeddings response with vectors and metadata
        """
        try:
            # Use the latest /api/embed endpoint
            url = f"{self.api_base}/embed"
            
            # Support both single string and list of strings
            if isinstance(input_text, str):
                input_data = input_text
            else:
                input_data = input_text
            
            data = {
                "model": model,
                "input": input_data,
                "truncate": truncate,
                "keep_alive": keep_alive
            }
            
            if options:
                data["options"] = options

            logger.debug(f"Generating embeddings for {len(input_data) if isinstance(input_data, list) else 1} inputs")
            
            async with httpx.AsyncClient() as client:
                start_time = time.monotonic()
                response = await client.post(url, json=data, timeout=60)
                
                if response.status_code == 200:
                    embeddings_response = response.json()
                    
                    # Log performance metrics
                    end_time = time.monotonic()
                    duration = end_time - start_time
                    
                    # Extract metrics from response
                    total_duration = embeddings_response.get('total_duration', 0)
                    load_duration = embeddings_response.get('load_duration', 0)
                    prompt_eval_count = embeddings_response.get('prompt_eval_count', 0)
                    
                    logger.info(f"Ollama Embeddings - Model: {model}, Inputs: {len(input_data) if isinstance(input_data, list) else 1}")
                    logger.info(f"Ollama Embeddings Performance - Duration: {duration:.2f}s, "
                              f"Tokens: {prompt_eval_count}, Load time: {load_duration/1e9:.2f}s")
                    
                    return embeddings_response
                else:
                    error_msg = f"Embeddings generation failed with status {response.status_code}"
                    if response.text:
                        error_msg += f": {response.text}"
                    raise Exception(error_msg)
                    
        except httpx.TimeoutException:
            raise Exception("Embeddings request timed out. Try reducing input size or increasing timeout.")
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise Exception(f"Error generating embeddings: {str(e)}")

    async def get_model_info(self, model: str) -> Dict:
        """
        Get detailed information about a specific model.
        
        Args:
            model: Model name
            
        Returns:
            Model information including size, parameters, etc.
        """
        try:
            # Get model info from the tags endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base}/tags", timeout=10)
                if response.status_code == 200:
                    models_data = response.json()
                    for model_data in models_data.get('models', []):
                        if model_data.get('name') == model:
                            return model_data
                    raise Exception(f"Model '{model}' not found")
                else:
                    raise Exception(f"Failed to get model info: {response.status_code}")
        except Exception as e:
            logger.error(f"Error getting model info: {str(e)}")
            raise

    async def pull_model(self, model: str, stream: bool = False) -> Dict:
        """
        Pull/download a model from the Ollama registry.
        
        Args:
            model: Model name to pull
            stream: Whether to stream download progress
            
        Returns:
            Pull response or final status
        """
        try:
            url = f"{self.api_base}/pull"
            data = {
                "model": model,
                "stream": stream
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, timeout=300)  # Long timeout for downloads
                
                if response.status_code == 200:
                    if stream:
                        # Handle streaming progress updates
                        progress_info = []
                        async for line in response.aiter_lines():
                            if line:
                                try:
                                    progress = json.loads(line)
                                    progress_info.append(progress)
                                    logger.info(f"Pull progress: {progress.get('status', 'Unknown')}")
                                except json.JSONDecodeError:
                                    continue
                        return {"status": "completed", "progress": progress_info}
                    else:
                        return response.json()
                else:
                    raise Exception(f"Pull failed with status {response.status_code}: {response.text}")
                    
        except Exception as e:
            logger.error(f"Error pulling model: {str(e)}")
            raise

    def chat_completion_sync(
        self,
        model: str,
        messages: List[Dict],
        stream: bool = False,
        format: Optional[Union[str, Dict]] = None,
        options: Optional[Dict] = None,
        temperature: Optional[float] = None
    ) -> Dict:
        """
        Synchronous wrapper for chat_completion.
        Uses asyncio to run the async method in the current thread.
        """
        try:
            # Always create a new event loop for thread safety
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(
                    self.chat_completion(
                        model=model,
                        messages=messages,
                        stream=stream,
                        format=format,
                        options=options,
                        temperature=temperature
                    )
                )
            finally:
                new_loop.close()
        except Exception as e:
            logger.error(f"Error in chat_completion_sync: {e}")
            # Propagate the exception or return a specific error structure
            raise Exception(f"Synchronous chat completion failed: {str(e)}")