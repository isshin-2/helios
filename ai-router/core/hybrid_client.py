"""
HELIOS - Hybrid Thin-Client
Provides an optional WebSocket client for offloading reasoning to a remote larger model.
"""

import json
import logging
import asyncio
from typing import List, Dict, Union, AsyncGenerator

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

logger = logging.getLogger(__name__)

class HybridClient:
    """WebSocket client for optionally offloading reasoning to a remote server."""
    
    def __init__(self, remote_url: str = None):
        """
        Initialize the HybridClient.
        
        Args:
            remote_url (str, optional): The URL of the remote WebSocket server.
        """
        self.remote_url = remote_url
        self._ws = None
        self._connected = False
        self._reconnect_attempts = 0
        self._max_reconnects = 3

    async def connect(self) -> bool:
        """
        Connect to the remote WebSocket server.
        
        Returns:
            bool: True on success, False on failure.
        """
        if not HAS_WEBSOCKETS:
            logger.warning("websockets library not installed. Cannot connect.")
            return False

        if not self.remote_url:
            return False

        try:
            self._ws = await websockets.connect(self.remote_url)
            self._connected = True
            logger.info(f"Successfully connected to remote server at {self.remote_url}")
            self._reconnect_attempts = 0
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.remote_url}: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Cleanly close the WebSocket connection."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.error(f"Error while disconnecting: {e}")
            finally:
                self._ws = None
                self._connected = False

    async def chat(self, model: str, messages: List[Dict], tools: List[Dict] = None, stream: bool = True, **kwargs) -> Union[Dict, AsyncGenerator, None]:
        """
        Send a chat request to the remote server.
        
        Args:
            model (str): The model to use.
            messages (List[Dict]): The chat messages.
            tools (List[Dict], optional): Tools available for the model.
            stream (bool, optional): Whether to stream the response. Defaults to True.
            
        Returns:
            Union[Dict, AsyncGenerator, None]: The response, an async generator if streaming, or None on failure (caller falls back to local).
        """
        if not self.remote_url or not self._connected or not self._ws:
            return None

        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "stream": stream
        }

        try:
            await self._ws.send(json.dumps(payload))
            
            if stream:
                async def stream_generator():
                    try:
                        async for message in self._ws:
                            yield json.loads(message)
                    except Exception as e:
                        logger.warning(f"WebSocket stream error: {e}")
                        self._connected = False
                return stream_generator()
            else:
                response = await self._ws.recv()
                return json.loads(response)

        except Exception as e:
            logger.warning(f"WebSocket error during chat: {e}")
            self._connected = False
            return None

    async def is_available(self) -> bool:
        """
        Quick health check for the remote server.
        
        Returns:
            bool: True if available, False otherwise.
        """
        if not self.remote_url or not self._connected or not self._ws:
            return False

        try:
            async with asyncio.timeout(2.0):
                await self._ws.send(json.dumps({"type": "ping"}))
                response = await self._ws.recv()
                data = json.loads(response)
                return data.get("type") == "pong"
        except Exception:
            return False
