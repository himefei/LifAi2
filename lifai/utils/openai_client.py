"""
OpenAI Client for LifAi2

Provides integration with OpenAI's API for chat completions and vision capabilities.
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
import httpx
import json

from lifai.utils.logger_utils import get_module_logger

logger = get_module_logger(__name__)

class OpenAIClient:
    """OpenAI API client with vision support"""
    
    def __init__(self, api_key: str = None, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.supports_vision = True
        
        if not self.api_key:
            logger.warning("No OpenAI API key provided")
    
    async def fetch_models(self) -> List[str]:
        """Fetch available models"""
        if not self.api_key:
            return ["No API key configured"]
        
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/models", headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    models = [model["id"] for model in data.get("data", [])]
                    return models if models else ["No models found"]
                else:
                    logger.error(f"Failed to fetch models: {response.status_code}")
                    return ["Error fetching models"]
                    
        except Exception as e:
            logger.error(f"Error fetching OpenAI models: {e}")
            return ["Connection error"]
    
    def fetch_models_sync(self) -> List[str]:
        """Synchronous wrapper for fetch_models"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.fetch_models())
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in fetch_models_sync: {e}")
            return ["Error fetching models"]
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict:
        """Generate chat completion"""
        if not self.api_key:
            raise Exception("No OpenAI API key configured")
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }
            
            # Add any additional parameters
            data.update(kwargs)
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=120
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_msg = f"OpenAI API error: {response.status_code}"
                    if response.text:
                        error_msg += f" - {response.text}"
                    raise Exception(error_msg)
                    
        except Exception as e:
            logger.error(f"Error in OpenAI chat completion: {e}")
            raise
    
    def chat_completion_sync(
        self,
        model: str,
        messages: List[Dict],
        stream: bool = False,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict:
        """Synchronous wrapper for chat_completion"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.chat_completion(model, messages, stream, temperature, **kwargs)
                )
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in chat_completion_sync: {e}")
            raise