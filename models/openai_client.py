import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
import httpx
from config import OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        if not self.api_key:
            logger.warning(f"API key is missing for {base_url}. API calls will fail.")

    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                # Extract text strings if it's an array
                text_parts = [p["text"] for p in content if p.get("type") == "text"]
                content = "\n".join(text_parts)
            formatted.append({"role": role, "content": content})
        return formatted

    def _format_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        formatted_tools = []
        for t in tools:
            # Assumes the tool is already in standard format
            if "type" in t and "function" in t:
                formatted_tools.append(t)
            else:
                formatted_tools.append({
                    "type": "function",
                    "function": t
                })
        return formatted_tools

    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = "meta-llama/llama-3.1-8b-instruct"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.api_key:
            yield {"type": "error", "content": f"API key not configured for {self.base_url}"}
            return

        formatted_messages = self._format_messages(messages)
        formatted_tools = self._format_tools(tools)

        payload = {
            "model": model,
            "messages": formatted_messages,
            "stream": True,
            "temperature": 0.2
        }
        if formatted_tools:
            payload["tools"] = formatted_tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "HELIOS",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                for attempt in range(3):
                    req = client.build_request(
                        "POST", 
                        self.base_url, 
                        json=payload, 
                        headers=headers
                    )
                    response = await client.send(req, stream=True)
                    
                    if response.status_code == 429:
                        await response.aread()
                        logger.warning(f"API 429 Rate Limit. Retrying in {2 ** attempt} seconds...")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    
                    if response.status_code != 200:
                        err_text = await response.aread()
                        logger.error(f"API Error {response.status_code}: {err_text}")
                        yield {"type": "error", "content": f"API Error: {response.status_code} - {err_text}"}
                        return
                    
                    current_tool_call = None
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if line.startswith("data: "):
                            if line == "data: [DONE]":
                                break
                            try:
                                data = json.loads(line[6:])
                                choices = data.get("choices", [])
                                if not choices:
                                    continue
                                delta = choices[0].get("delta", {})
                                
                                if "content" in delta and delta["content"]:
                                    yield {"type": "text", "content": delta["content"]}
                                    
                                if "tool_calls" in delta:
                                    tc_list = delta["tool_calls"]
                                    for tc in tc_list:
                                        if tc.get("id"):
                                            # New tool call
                                            if current_tool_call:
                                                # Yield the completed one
                                                try:
                                                    args_dict = json.loads(current_tool_call["args"])
                                                except:
                                                    args_dict = {}
                                                yield {"type": "tool_call", "content": {"name": current_tool_call["name"], "args": args_dict}}
                                            current_tool_call = {"name": tc["function"]["name"], "args": tc["function"].get("arguments", "")}
                                        else:
                                            # Append arguments
                                            if current_tool_call and "function" in tc and "arguments" in tc["function"]:
                                                current_tool_call["args"] += tc["function"]["arguments"]
                            except json.JSONDecodeError:
                                continue
                    
                    # Flush the final tool call if exists
                    if current_tool_call:
                        try:
                            args_dict = json.loads(current_tool_call["args"])
                        except:
                            args_dict = {}
                        yield {"type": "tool_call", "content": {"name": current_tool_call["name"], "args": args_dict}}
                    
                    return
            except httpx.TimeoutException as e:
                logger.error(f"API Timeout: {e}")
                yield {"type": "error", "content": f"API Request Error: {e}"}
                return
            except Exception as e:
                logger.error(f"API Exception: {e}")
                yield {"type": "error", "content": str(e)}
                return

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = "meta-llama/llama-3.1-8b-instruct:free",
        stream: bool = False,
        **kwargs
    ) -> Any:
        if stream:
            return self.stream_chat(messages, tools, model)
        return None
