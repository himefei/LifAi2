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
import time
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
                start_time = time.monotonic()
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
                logger.debug(f"LM Studio chat_completion raw non-stream response: {json.dumps(json_response, indent=2)}")

                # Ensure the response has 'choices' and the first choice has a 'message' object
                if 'choices' in json_response and len(json_response['choices']) > 0:
                    first_choice = json_response['choices'][0]
                    if 'message' in first_choice and isinstance(first_choice['message'], dict):
                        message_obj = first_choice['message']
                        # Ensure 'role' and 'content' are present in the message object
                        message_obj['role'] = message_obj.get('role', 'assistant')
                        message_obj['content'] = message_obj.get('content', '')

                        # Add the 'message' object at the top level for consistency with the Ollama client's adapted response
                        json_response['message'] = message_obj
                        
                        end_time = time.monotonic()
                        duration = end_time - start_time

                        if 'usage' in json_response and isinstance(json_response['usage'], dict):
                            usage = json_response['usage']
                            prompt_tokens = usage.get('prompt_tokens', 0)
                            completion_tokens = usage.get('completion_tokens', 0)
                            total_tokens = usage.get('total_tokens', 0)
                            
                            tokens_per_second = 0
                            if duration > 0 and completion_tokens > 0:
                                tokens_per_second = completion_tokens / duration
                            
                            logger.info(
                                f"LM Studio Completion Tokens: {completion_tokens}, Prompt Tokens: {prompt_tokens}, Total Tokens: {total_tokens}"
                            )
                            logger.info(f"LM Studio Generation Speed: {tokens_per_second:.2f} tokens/sec (Duration: {duration:.2f}s)")
                        else:
                            logger.warning("LM Studio response did not contain 'usage' information for token tracking.")

                        logger.debug(f"LM Studio chat_completion adapted response: {json.dumps(json_response, indent=2)}")
                        return json_response
                    else:
                        logger.error(f"LM Studio chat_completion response missing 'message' in first choice: {json.dumps(first_choice, indent=2)}")
                        raise Exception("Invalid LM Studio chat_completion response: 'message' missing in first choice.")
                else:
                    logger.error(f"LM Studio chat_completion response missing 'choices': {json.dumps(json_response, indent=2)}")
                    raise Exception("Invalid LM Studio chat_completion response: 'choices' missing or empty.")
                
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