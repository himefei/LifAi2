"""
OllamaClient: Enhanced async Python client for Ollama's latest API features.

This module provides comprehensive integration with Ollama's latest API capabilities including
the new embedding endpoints, enhanced streaming, better error handling, and support for
advanced model management features. Updated for optimal inference speed and latest Context7 findings.

Features:
    - Latest Ollama API endpoints including new /api/embed (migrated from deprecated /api/embeddings)
    - Enhanced streaming responses with better chunk handling and native thinking support
    - Comprehensive model management (list loaded, version info, detailed metrics)
    - Batch embedding support for multiple inputs with improved performance tracking
    - Advanced error handling with contextual messages and better recovery
    - Support for advanced model options, keep_alive, and thinking models
    - Async HTTP requests optimized for inference speed
    - Enhanced performance metrics and monitoring
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
        # Note: Connection test will be performed when first method is called

    async def test_connection(self) -> bool:
        """Enhanced connection test with version information and performance metrics."""
        try:
            async with httpx.AsyncClient() as client:
                start_time = time.monotonic()
                
                # Test basic connection and get version info
                version_response = await client.get(f"{self.api_base}/version", timeout=5)
                
                if version_response.status_code == 200:
                    version_info = version_response.json()
                    connection_time = time.monotonic() - start_time
                    logger.info(f"Successfully connected to Ollama server version: {version_info}")
                    logger.info(f"Connection established in {connection_time:.3f}s")
                    return True
                else:
                    # Fallback to tags endpoint for older versions
                    tags_response = await client.get(f"{self.api_base}/tags", timeout=5)
                    if tags_response.status_code == 200:
                        connection_time = time.monotonic() - start_time
                        logger.info(f"Successfully connected to Ollama server (legacy version) in {connection_time:.3f}s")
                        return True
                    else:
                        logger.error(f"Failed to connect to Ollama server. Status codes: version={version_response.status_code}, tags={tags_response.status_code}")
                        return False
        except httpx.TimeoutException:
            logger.error("Connection to Ollama server timed out. Check if server is running and responsive.")
            return False
        except httpx.ConnectError:
            logger.error("Could not connect to Ollama server. Ensure it's running on the correct port.")
            return False
        except httpx.RequestError as e:
            logger.error(f"Network error connecting to Ollama server: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error testing connection: {str(e)}")
            return False

    async def fetch_models(self) -> List[str]:
        """Enhanced model fetching with comprehensive metadata and performance tracking."""
        try:
            logger.debug("Fetching available models from Ollama")
            start_time = time.monotonic()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base}/tags", timeout=10)
                
                if response.status_code == 200:
                    models_data = response.json()
                    models = []
                    total_size = 0
                    
                    for model in models_data.get('models', []):
                        model_name = model.get('name', '')
                        if model_name:
                            models.append(model_name)
                            # Log additional model info if available
                            size = model.get('size', 0)
                            total_size += size
                            modified = model.get('modified_at', '')
                            digest = model.get('digest', '')[:12] + '...' if model.get('digest') else 'N/A'
                            
                            # Enhanced model details logging
                            details = model.get('details', {})
                            family = details.get('family', 'unknown')
                            param_size = details.get('parameter_size', 'unknown')
                            quant_level = details.get('quantization_level', 'unknown')
                            
                            logger.debug(f"Model: {model_name} | Family: {family} | Params: {param_size} | "
                                       f"Quant: {quant_level} | Size: {size:,} bytes | Digest: {digest}")
                    
                    fetch_time = time.monotonic() - start_time
                    logger.info(f"Successfully fetched {len(models)} models from Ollama in {fetch_time:.3f}s")
                    logger.info(f"Total models storage: {total_size:,} bytes ({total_size / (1024**3):.2f} GB)")
                    return models
                else:
                    logger.error(f"Failed to fetch models. Status code: {response.status_code}, Response: {response.text}")
                    return []
        except httpx.TimeoutException:
            logger.error("Timeout fetching models from Ollama server. Server may be overloaded.")
            return []
        except httpx.ConnectError:
            logger.error("Could not connect to Ollama server. Is it running?")
            return []
        except httpx.RequestError as e:
            logger.error(f"Network error fetching models: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching models: {str(e)}")
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
        temperature: Optional[float] = None,
        think: Optional[bool] = None
    ) -> str:
        """Asynchronously generate a response from the model with enhanced features."""
        try:
            url = f"{self.base_url}/api/generate"
            data = {
                "model": model,
                "prompt": prompt,
                "stream": stream
            }
            # Add native thinking support for reasoning models
            if think is not None:
                data["think"] = think
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
        temperature: Optional[float] = None,
        think: Optional[bool] = None
    ) -> Dict:
        """Asynchronously generate a chat completion using the new chat API."""
        try:
            url = f"{self.base_url}/api/chat"
            data = {
                "model": model,
                "messages": messages,
                "stream": stream
            }
            # Add native thinking support for reasoning models
            if think is not None:
                data["think"] = think
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

                    # Handle native thinking tokens if present
                    thinking_content = ollama_message_obj.get('thinking', '')
                    if thinking_content:
                        logger.debug(f"Native thinking tokens extracted: {len(thinking_content)} chars")
                        # Store thinking separately for optional access
                        ollama_message_obj['thinking'] = thinking_content

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
                    
                    # Add thinking to top-level response if present
                    if thinking_content:
                        adapted_response['thinking'] = thinking_content
                    
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
        Asynchronously handle streaming responses from the API with native thinking support.
        """
        try:
            full_response = ""
            full_thinking = ""
            async for line in response.aiter_lines():
                if line:
                    try:
                        json_response = json.loads(line)
                        logger.debug(f"Ollama stream raw line content: {json_response}")
                        content_piece = ""
                        thinking_piece = ""
                        
                        # Check for /api/chat structure with native thinking support
                        if "message" in json_response and isinstance(json_response.get("message"), dict):
                            message = json_response["message"]
                            content_piece = message.get("content", "")
                            thinking_piece = message.get("thinking", "")
                        # Check for /api/generate structure
                        elif "response" in json_response:
                            content_piece = json_response["response"]
                            thinking_piece = json_response.get("thinking", "")
                        
                        if content_piece:
                            full_response += content_piece
                        if thinking_piece:
                            full_thinking += thinking_piece
                        
                        # If the stream is supposed to yield structured chunks (OpenAI-like)
                        # this part would need to construct and yield those instead of concatenating.
                        # For now, it matches the previous behavior of returning a single string.

                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON in Ollama streaming response: {e}, line: {line[:100]}...")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing Ollama stream line: {e}, line: {line[:100]}...")
                        continue
            
            # Log thinking extraction if present
            if full_thinking:
                logger.debug(f"Native thinking tokens extracted from stream: {len(full_thinking)} chars")
            
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
        Enhanced embeddings generation using the latest /api/embed endpoint with optimal performance.
        
        Args:
            model: Model name for embedding generation
            input_text: Text or list of texts to embed
            options: Additional model parameters
            truncate: Whether to truncate input to fit context length (default: True)
            keep_alive: How long to keep model loaded after request (default: 5m)
            
        Returns:
            Embeddings response with vectors and enhanced performance metadata
        """
        try:
            # Use the latest /api/embed endpoint (replacing deprecated /api/embeddings)
            url = f"{self.api_base}/embed"
            
            # Support both single string and list of strings with optimal batching
            if isinstance(input_text, str):
                input_data = input_text
                batch_size = 1
            else:
                input_data = input_text
                batch_size = len(input_text)
            
            data = {
                "model": model,
                "input": input_data,
                "truncate": truncate,
                "keep_alive": keep_alive
            }
            
            if options:
                data["options"] = options

            logger.debug(f"Generating embeddings using /api/embed for {batch_size} input(s) with model: {model}")
            
            async with httpx.AsyncClient() as client:
                start_time = time.monotonic()
                response = await client.post(url, json=data, timeout=120)  # Increased timeout for large batches
                
                if response.status_code == 200:
                    embeddings_response = response.json()
                    
                    # Enhanced performance metrics logging
                    end_time = time.monotonic()
                    request_duration = end_time - start_time
                    
                    # Extract detailed metrics from response
                    total_duration = embeddings_response.get('total_duration', 0)
                    load_duration = embeddings_response.get('load_duration', 0)
                    prompt_eval_count = embeddings_response.get('prompt_eval_count', 0)
                    
                    # Calculate processing rates
                    total_duration_s = total_duration / 1e9 if total_duration > 0 else request_duration
                    load_duration_s = load_duration / 1e9 if load_duration > 0 else 0
                    
                    # Log comprehensive metrics
                    logger.info(f"Ollama Embeddings Success:")
                    logger.info(f"  Model: {model} | Batch Size: {batch_size} | Tokens: {prompt_eval_count}")
                    logger.info(f"  Request Duration: {request_duration:.3f}s | Total Duration: {total_duration_s:.3f}s")
                    logger.info(f"  Load Duration: {load_duration_s:.3f}s")
                    
                    if prompt_eval_count > 0 and total_duration_s > 0:
                        tokens_per_second = prompt_eval_count / total_duration_s
                        logger.info(f"  Processing Rate: {tokens_per_second:.2f} tokens/second")
                    
                    # Validate embeddings structure
                    embeddings = embeddings_response.get('embeddings', [])
                    if embeddings:
                        if isinstance(embeddings[0], list):
                            embedding_dim = len(embeddings[0])
                            logger.debug(f"  Embedding Dimensions: {embedding_dim}")
                        logger.debug(f"  Generated {len(embeddings)} embedding vector(s)")
                    
                    return embeddings_response
                else:
                    error_msg = f"Embeddings generation failed with status {response.status_code}"
                    if response.text:
                        error_msg += f": {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
        except httpx.TimeoutException:
            error_msg = f"Embeddings request timed out after {120}s. Consider reducing batch size or using shorter inputs."
            logger.error(error_msg)
            raise Exception(error_msg)
        except httpx.ConnectError:
            error_msg = "Could not connect to Ollama server for embeddings. Ensure server is running."
            logger.error(error_msg)
            raise Exception(error_msg)
        except httpx.RequestError as e:
            error_msg = f"Network error during embeddings generation: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error generating embeddings: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

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
        temperature: Optional[float] = None,
        think: Optional[bool] = None
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
                        temperature=temperature,
                        think=think
                    )
                )
            finally:
                new_loop.close()
        except Exception as e:
            logger.error(f"Error in chat_completion_sync: {e}")
            # Propagate the exception or return a specific error structure
            raise Exception(f"Synchronous chat completion failed: {str(e)}")