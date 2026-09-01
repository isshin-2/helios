import json
import httpx
import logging
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
import config

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Async client for Google's Gemini API via HTTPX.
    Uses SSE for low-latency streaming to stay within the 8GB RAM budget without
    pulling in heavy external SDKs.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0),
            headers={"Content-Type": "application/json"}
        )

    async def close(self):
        """Gracefully close the HTTP client to prevent resource leaks."""
        await self._client.aclose()

    def _format_tools(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Translates tools into Gemini's function calling schema.
        Handles both internal OpenAI-style tools and MCP tools.
        """
        function_declarations = []
        for t in mcp_tools:
            if "type" in t and t["type"] == "function" and "function" in t:
                # Built-in tool in OpenAI format
                func = t["function"]
                func_decl = {
                    "name": func.get("name"),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {"type": "object", "properties": {}})
                }
            else:
                # MCP tool format
                func_decl = {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}})
                }
            
            # Gemini is strict about parameters being an object
            if "type" not in func_decl["parameters"]:
                func_decl["parameters"]["type"] = "object"
                
            function_declarations.append(func_decl)
            
        if not function_declarations:
            return []
            
        return [{"functionDeclarations": function_declarations}]

    def _format_messages(self, messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str]:
        """
        Converts generic message format (role, content) to Gemini's format.
        Extracts the system prompt to be passed separately.
        """
        gemini_messages = []
        system_prompt = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt += msg.get("content", "") + "\n\n"
                continue
                
            role = "user" if msg["role"] in ("user", "tool") else "model"
            content = msg.get("content", "")
            
            parts = []
            if isinstance(content, str):
                parts.append({"text": content})
            elif isinstance(content, list):
                # Handle multimodal arrays
                for item in content:
                    if item.get("type") == "text":
                        parts.append({"text": item.get("text", "")})
                    elif item.get("type") == "image_url":
                        img_url = item.get("image_url", {}).get("url", "")
                        if img_url.startswith("data:image/"):
                            header, b64_data = img_url.split(",", 1)
                            mime = header.split(";")[0].replace("data:", "")
                            parts.append({
                                "inlineData": {
                                    "mimeType": mime,
                                    "data": b64_data
                                }
                            })
            
            # Prevent consecutive messages with the same role by merging them
            if gemini_messages and gemini_messages[-1]["role"] == role:
                gemini_messages[-1]["parts"].extend(parts)
            else:
                gemini_messages.append({
                    "role": role,
                    "parts": parts
                })
                
        return gemini_messages, system_prompt.strip()

    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        system_prompt: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = "gemini-3.6-flash"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams responses from Gemini via SSE.
        """
        gemini_messages, extracted_system = self._format_messages(messages)
        
        if extracted_system:
            system_prompt = (system_prompt + "\n\n" + extracted_system).strip()
            
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": 0.2
            }
        }
        
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }
            
        if tools:
            formatted_tools = self._format_tools(tools)
            if formatted_tools:
                payload["tools"] = formatted_tools

        url = f"{self.base_url}/{model}:streamGenerateContent?alt=sse&key={self.api_key}"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self._client.stream("POST", url, json=payload) as response:
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            await response.aread()
                            logger.warning(f"Gemini API 429 Rate Limit. Retrying in {2 ** attempt} seconds...")
                            await asyncio.sleep(2 ** attempt)
                            continue
                    
                    if response.status_code != 200:
                        await response.aread()
                        logger.error(f"Gemini API Error {response.status_code}: {response.text}")
                        if response.status_code == 429:
                            yield {"type": "error", "content": "Gemini API 429 Rate Limit Exceeded. You are sending requests too quickly. Please wait 60 seconds before trying again."}
                        else:
                            yield {"type": "error", "content": f"Cloud LLM Error: {response.status_code}"}
                        return
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            logger.info(f"Gemini raw stream line: {line}")
                            try:
                                data = json.loads(line[6:])
                                if "candidates" in data and len(data["candidates"]) > 0:
                                    candidate = data["candidates"][0]
                                    if "content" in candidate and "parts" in candidate["content"]:
                                        for part in candidate["content"]["parts"]:
                                            if "text" in part:
                                                yield {"type": "text", "content": part["text"]}
                                            if "functionCall" in part:
                                                yield {"type": "tool_call", "content": part["functionCall"]}
                                    else:
                                        logger.warning(f"Gemini returned candidate without content parts: {candidate}")
                            except json.JSONDecodeError:
                                continue
                    return # Exit the function successfully
            except httpx.TimeoutException as e:
                logger.error(f"Gemini API Timeout: {e}")
                yield {"type": "error", "content": "Cloud API connection timed out."}
                return

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        system_prompt: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = "gemini-3.6-flash",
        stream: bool = False,
        **kwargs
    ) -> Any:
        """
        Non-streaming or streaming wrapper for Gemini.
        """
        if stream:
            return self.stream_chat(messages, system_prompt, tools, model)
            
        gemini_messages, extracted_system = self._format_messages(messages)
        
        if extracted_system:
            system_prompt = (system_prompt + "\n\n" + extracted_system).strip()
            
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": 0.2
            }
        }
        
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }
            
        if tools:
            formatted_tools = self._format_tools(tools)
            if formatted_tools:
                payload["tools"] = formatted_tools

        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self._client.post(url, json=payload)
                
                if response.status_code == 429 and attempt < max_retries - 1:
                    logger.warning(f"Gemini API 429 Rate Limit. Retrying in {2 ** attempt} seconds...")
                    await asyncio.sleep(2 ** attempt)
                    continue
                    
                if response.status_code == 429:
                    return {"role": "assistant", "content": "Gemini API 429 Rate Limit Exceeded. You are sending requests too quickly. Please wait 60 seconds before trying again."}
                response.raise_for_status()
                data = response.json()
                
                # Translate Gemini's format to our standard format
                message_obj = {"role": "assistant", "content": ""}
                
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                message_obj["content"] += part["text"]
                            if "functionCall" in part:
                                if "tool_calls" not in message_obj:
                                    message_obj["tool_calls"] = []
                                fc = part["functionCall"]
                                message_obj["tool_calls"].append({
                                    "type": "function",
                                    "function": {
                                        "name": fc["name"],
                                        "arguments": json.dumps(fc.get("args", {}))
                                    }
                                })
                                
                return {"message": message_obj}
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 429:
                    logger.error(f"Gemini API Error: {e.response.text}")
                    raise
                if attempt == max_retries - 1:
                    logger.error(f"Gemini API Error (Max Retries Reached): {e.response.text}")
                    raise
            except Exception as e:
                logger.error(f"Gemini Error: {e}")
                raise
