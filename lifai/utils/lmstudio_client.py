"""
LMStudioClient: Enhanced async Python client for LM Studio's latest API features.

This module provides comprehensive integration with LM Studio's native REST API and OpenAI-compatible
endpoints, featuring the latest capabilities including TTL support, enhanced model management,
structured outputs, and improved streaming responses.

Features:
    - Native LM Studio REST API support (/api/v0/* endpoints)
    - OpenAI-compatible endpoints for backward compatibility
    - TTL (Time-To-Live) support for automatic model unloading
    - Enhanced model management and information retrieval
    - Structured output support with JSON schemas
    - Improved streaming with better error handling
    - Comprehensive embeddings support
    - Async HTTP requests for non-blocking operations
"""

import httpx
import json
import logging
import asyncio
import time
from typing import List, Dict, Optional, Union, Any

logger = logging.getLogger(__name__)

class LMStudioClient:
    """Enhanced async client for LM Studio's native and OpenAI-compatible APIs."""
    def __init__(self, base_url="http://localhost:1234", use_native_api=True):
        """
        Initialize LM Studio client with support for both native and OpenAI-compatible APIs.
        
        Args:
            base_url: Base URL for LM Studio server (default: http://localhost:1234)
            use_native_api: Whether to use native REST API (/api/v0/) or OpenAI-compatible (/v1/)
        """
        self.base_url = base_url
        self.use_native_api = use_native_api
        self.native_base = f"{base_url}/api/v0"
        self.openai_base = f"{base_url}/v1"
        self.default_headers = {
            "Content-Type": "application/json"
        }
        logger.info(f"Initialized LMStudioClient with base_url={base_url}, native_api={use_native_api}")

    async def fetch_models(self) -> List[str]:
        """
        Asynchronously fetch available models using native LM Studio API or OpenAI-compatible endpoint.
        
        Returns:
            List of model names/IDs
        """
        try:
            async with httpx.AsyncClient() as client:
                if self.use_native_api:
                    # Use native LM Studio API for enhanced model information
                    response = await client.get(f"{self.native_base}/models", timeout=10)
                else:
                    # Use OpenAI-compatible endpoint for backward compatibility
                    response = await client.get(f"{self.openai_base}/models", timeout=10)
                
                response.raise_for_status()
                models_data = response.json()
                
                model_names = []
                if self.use_native_api:
                    # Native API may have different response structure
                    if isinstance(models_data, list):
                        model_names = [model.get('id', model.get('name', '')) for model in models_data if model]
                    elif 'data' in models_data:
                        model_names = [model.get('id', model.get('name', '')) for model in models_data.get('data', [])]
                else:
                    # OpenAI-compatible format
                    for model in models_data.get('data', []):
                        model_id = model.get('id', '')
                        if model_id:
                            model_names.append(model_id)
                
                # Filter out empty names
                model_names = [name for name in model_names if name.strip()]
                
                logger.info(f"Found {len(model_names)} models in LM Studio (native_api={self.use_native_api})")
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
                logger.debug(f"LM Studio generate_response raw result: {json.dumps(result, indent=2)}")
                if 'choices' in result and len(result['choices']) > 0:
                    choice = result['choices'][0]
                    if 'message' in choice and isinstance(choice['message'], dict) and 'content' in choice['message']:
                        # For generate_response, the original intent was to return just the content string.
                        # However, to align with the broader goal of consistent object structure for the *consuming code*
                        # that might be expecting a dict, we'll return a dict here too, but the primary value is the content.
                        # The calling code for generate_response might need adjustment if it strictly expects a string.
                        # For now, let's assume the consuming code (toolbar) is flexible or primarily uses chat_completion.
                        # This method is less critical than chat_completion for the toolbar's text replacement.
                        # Let's return the full message object for consistency, though it's a change from string.
                        # OR, if generate_response is *only* ever used to get a string, this change is problematic.
                        # Given the error context, let's assume the toolbar might be trying to access .message.content
                        # from what generate_response returns.
                        # To be safe and consistent with chat_completion, we'll make it return a dict.
                        message_obj = choice['message']
                        # Ensure role if not present, though LM Studio usually provides it.
                        message_obj['role'] = message_obj.get('role', 'assistant')
                        
                        # Return a dictionary that includes the 'message' object and 'choices'
                        # This makes it more like the chat_completion response.
                        # The original generate_response returned a string. This is a significant change.
                        # If direct string is needed, the caller of generate_response must adapt.
                        # For the sake of fixing the toolbar error, let's try to provide a consistent rich object.
                        # This method might not be the one causing the 'message' key error if toolbar uses chat_completion.
                        # Let's return the content string as originally designed for generate_response,
                        # and focus the structural change on chat_completion.
                        return choice['message']['content'].strip() # Reverting to original string return for this specific method
                    else:
                        logger.error(f"LM Studio generate_response missing 'message' or 'content' in choice: {json.dumps(choice, indent=2)}")
                        raise Exception("Invalid response structure from LM Studio in generate_response: 'message' or 'content' missing.")
                else:
                    raise Exception("No response content received from LM Studio in generate_response")
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
        temperature: Optional[float] = None,
        stream: bool = False,
        format: Optional[Union[str, Dict]] = None,
        ttl: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> Dict:
        """
        Enhanced chat completion with support for TTL, structured outputs, and both API endpoints.
        
        Args:
            messages: List of chat messages
            model: Model identifier
            temperature: Sampling temperature
            stream: Enable streaming responses
            format: Response format (legacy parameter)
            ttl: Time-to-live in seconds for automatic model unloading
            response_format: Structured output schema for JSON responses
        
        Returns:
            Chat completion response dictionary
        """
        try:
            # Choose API endpoint based on configuration
            if self.use_native_api:
                endpoint = f"{self.native_base}/chat/completions"
            else:
                endpoint = f"{self.openai_base}/chat/completions"
            
            # Build request data with enhanced features
            data = {
                "messages": messages,
                "stream": stream
            }
            
            # Add optional parameters
            if temperature is not None:
                data["temperature"] = temperature
            if model:
                data["model"] = model
            if ttl is not None:
                data["ttl"] = ttl
                
            # Handle response format (structured outputs)
            if response_format:
                data["response_format"] = response_format
            elif format:
                # Legacy format parameter support
                data["response_format"] = {"type": format} if isinstance(format, str) else format

            # Enhanced timeout for complex models and reasoning
            timeout = 120
            
            logger.debug(f"Sending enhanced chat completion request to LM Studio: {endpoint}")
            logger.debug(f"Request data: {json.dumps(data, indent=2)}")
            
            async with httpx.AsyncClient() as client:
                start_time = time.monotonic()
                response = await client.post(
                    endpoint,
                    headers=self.default_headers,
                    json=data,
                    timeout=timeout
                )
                
                response.raise_for_status()

                if stream:
                    return await self._handle_stream_response(response)
                    
                # Parse and enhance response
                json_response = response.json()
                
                # Ensure consistent response structure
                if 'choices' in json_response and len(json_response['choices']) > 0:
                    first_choice = json_response['choices'][0]
                    if 'message' in first_choice and isinstance(first_choice['message'], dict):
                        message_obj = first_choice['message']
                        message_obj['role'] = message_obj.get('role', 'assistant')
                        message_obj['content'] = message_obj.get('content', '')

                        # Add top-level message for consistent access
                        json_response['message'] = message_obj
                        
                        # Calculate performance metrics
                        end_time = time.monotonic()
                        duration = end_time - start_time

                        # Enhanced usage tracking
                        if 'usage' in json_response:
                            usage = json_response['usage']
                            prompt_tokens = usage.get('prompt_tokens', 0)
                            completion_tokens = usage.get('completion_tokens', 0)
                            total_tokens = usage.get('total_tokens', 0)
                            
                            tokens_per_second = completion_tokens / duration if duration > 0 and completion_tokens > 0 else 0
                            
                            logger.info(f"LM Studio Enhanced - Tokens: {completion_tokens}/{prompt_tokens}/{total_tokens} (completion/prompt/total)")
                            logger.info(f"LM Studio Performance: {tokens_per_second:.2f} tokens/sec, Duration: {duration:.2f}s")
                            
                            # Add performance metrics to response
                            json_response['performance'] = {
                                'tokens_per_second': tokens_per_second,
                                'duration_seconds': duration,
                                'time_to_first_token': json_response.get('stats', {}).get('time_to_first_token', 0)
                            }

                        return json_response
                    else:
                        raise Exception("Invalid response structure: missing 'message' in first choice")
                else:
                    raise Exception("Invalid response structure: missing or empty 'choices'")
                
        except httpx.RequestError as e:
            logger.error(f"HTTP request error in enhanced chat completion: {e}")
            raise Exception(f"LM Studio request failed: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"LM Studio error {e.response.status_code}: {e.response.text}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise Exception(f"Invalid JSON response: {str(e)}")
        except Exception as e:
            logger.error(f"Error in enhanced chat completion: {e}")
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
        Enhanced embeddings generation with support for both API endpoints.
        
        Args:
            input_text: Text or list of texts to embed
            model: Embedding model identifier
            
        Returns:
            Embeddings response with vectors and metadata
        """
        try:
            # Choose API endpoint
            if self.use_native_api:
                endpoint = f"{self.native_base}/embeddings"
            else:
                endpoint = f"{self.openai_base}/embeddings"
            
            # Prepare request data
            data = {
                "input": input_text if isinstance(input_text, list) else [input_text]
            }
            if model:
                data["model"] = model

            logger.debug(f"Generating embeddings via {endpoint}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint,
                    headers=self.default_headers,
                    json=data,
                    timeout=60  # Increased timeout for large batches
                )
                response.raise_for_status()
                
                embeddings_response = response.json()
                
                # Add metadata for enhanced tracking
                if 'usage' in embeddings_response:
                    logger.info(f"LM Studio Embeddings - Processed {len(data['input'])} inputs, "
                              f"Tokens: {embeddings_response['usage'].get('total_tokens', 'N/A')}")
                
                return embeddings_response
                
        except httpx.RequestError as e:
            logger.error(f"HTTP request error generating embeddings: {e}")
            raise Exception(f"LM Studio embeddings request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    async def get_model_info(self, model: str) -> Dict:
        """
        Get detailed information about a specific model.
        
        Args:
            model: Model identifier
            
        Returns:
            Model information including architecture, parameters, etc.
        """
        try:
            if self.use_native_api:
                endpoint = f"{self.native_base}/models/{model}"
            else:
                # OpenAI-compatible endpoint doesn't have individual model info
                endpoint = f"{self.openai_base}/models"
                
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, timeout=10)
                response.raise_for_status()
                
                if self.use_native_api:
                    return response.json()
                else:
                    # Filter from models list
                    models_data = response.json()
                    for model_data in models_data.get('data', []):
                        if model_data.get('id') == model:
                            return model_data
                    raise Exception(f"Model '{model}' not found")
                    
        except httpx.RequestError as e:
            logger.error(f"Error getting model info: {e}")
            raise Exception(f"Failed to get model info: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            raise

    async def list_loaded_models(self) -> List[Dict]:
        """
        List currently loaded models in memory.
        
        Returns:
            List of loaded model information
        """
        try:
            if self.use_native_api:
                # Use native API for enhanced loaded models info
                endpoint = f"{self.native_base}/models/loaded"
            else:
                # Fallback to general models endpoint
                endpoint = f"{self.openai_base}/models"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, timeout=10)
                response.raise_for_status()
                
                models_data = response.json()
                
                if isinstance(models_data, dict) and 'data' in models_data:
                    return models_data['data']
                elif isinstance(models_data, list):
                    return models_data
                else:
                    return []
                    
        except httpx.RequestError as e:
            logger.warning(f"Could not get loaded models info: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error getting loaded models: {e}")
            return []

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
                            logger.debug(f"LM Studio _handle_stream_response choice: {json.dumps(choice, indent=2)}")
                            
                            # Handle both delta format (streaming) and message format (non-streaming)
                            if 'delta' in choice and choice['delta'] is not None and 'content' in choice['delta']:
                                content = choice['delta'].get('content', '')
                            elif 'message' in choice and choice['message'] is not None and 'content' in choice['message']:
                                content = choice['message'].get('content', '')
                            else:
                                content = ''
                                logger.warning(f"LM Studio stream choice missing 'delta.content' or 'message.content': {json.dumps(choice, indent=2)}")
                                
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