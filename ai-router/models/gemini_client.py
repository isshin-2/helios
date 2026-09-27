import json
import logging
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
import config
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Async client for Google's Gemini API via the official google-genai SDK.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.client = genai.Client(api_key=self.api_key)

    async def close(self):
        """No-op for the SDK"""
        pass

    def _format_tools(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Translates tools into Gemini's function calling schema.
        Handles both internal OpenAI-style tools and MCP tools.
        """
        def clean_schema(schema: Any) -> Any:
            if isinstance(schema, dict):
                schema.pop("additionalProperties", None)
                if "type" in schema and isinstance(schema["type"], list):
                    types = [t for t in schema["type"] if t != "null"]
                    schema["type"] = types[0] if types else "string"
                if "items" in schema and isinstance(schema["items"], list):
                    if len(schema["items"]) > 0:
                        schema["items"] = schema["items"][0]
                    else:
                        schema["items"] = {"type": "string"}
                for key, value in list(schema.items()):
                    schema[key] = clean_schema(value)
                return schema
            elif isinstance(schema, list):
                return [clean_schema(item) for item in schema]
            return schema

        function_declarations = []
        for t in mcp_tools:
            if "type" in t and t["type"] == "function" and "function" in t:
                func = t["function"]
                func_decl = {
                    "name": func.get("name"),
                    "description": func.get("description", ""),
                    "parameters": clean_schema(func.get("parameters", {"type": "object", "properties": {}}))
                }
            else:
                func_decl = {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": clean_schema(t.get("inputSchema", {"type": "object", "properties": {}}))
                }
            
            if "type" not in func_decl["parameters"]:
                func_decl["parameters"]["type"] = "object"
                
            function_declarations.append(func_decl)
            
        if not function_declarations:
            return None
            
        return [{"function_declarations": function_declarations}]

    def _format_messages(self, messages: List[Dict[str, Any]]):
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
                for item in content:
                    if item.get("type") == "text":
                        parts.append({"text": item.get("text", "")})
                    elif item.get("type") == "image_url":
                        img_url = item.get("image_url", {}).get("url", "")
                        if img_url.startswith("data:image/"):
                            header, b64_data = img_url.split(",", 1)
                            mime = header.split(";")[0].replace("data:", "")
                            # google-genai SDK handles inline data like this
                            # we can pass it as a dict
                            parts.append({
                                "inline_data": {
                                    "mime_type": mime,
                                    "data": b64_data
                                }
                            })
            
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
        
        gemini_messages, extracted_system = self._format_messages(messages)
        
        if extracted_system:
            system_prompt = (system_prompt + "\n\n" + extracted_system).strip()
            
        generation_config = {
            "temperature": 0.2
        }
        if system_prompt:
            generation_config["system_instruction"] = system_prompt
        if tools:
            formatted_tools = self._format_tools(tools)
            if formatted_tools:
                generation_config["tools"] = formatted_tools

        try:
            # Note: client.aio.models.generate_content_stream for async
            response = await self.client.aio.models.generate_content_stream(
                model=model,
                contents=gemini_messages,
                config=generation_config
            )
            
            async for chunk in response:
                if chunk.text:
                    yield {"type": "text", "content": chunk.text}
                
                # Check for function calls
                if chunk.function_calls:
                    for fc in chunk.function_calls:
                        yield {
                            "type": "tool_call",
                            "content": {
                                "name": fc.name,
                                "arguments": fc.args
                            }
                        }
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            yield {"type": "error", "content": f"Cloud API Error: {str(e)}"}

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        system_prompt: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = "gemini-3.6-flash",
        stream: bool = False,
        **kwargs
    ) -> Any:
        
        if stream:
            return self.stream_chat(messages, system_prompt, tools, model)
            
        gemini_messages, extracted_system = self._format_messages(messages)
        
        if extracted_system:
            system_prompt = (system_prompt + "\n\n" + extracted_system).strip()
            
        generation_config = {
            "temperature": 0.2
        }
        if system_prompt:
            generation_config["system_instruction"] = system_prompt
        if tools:
            formatted_tools = self._format_tools(tools)
            if formatted_tools:
                generation_config["tools"] = formatted_tools

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=gemini_messages,
                config=generation_config
            )
            
            if response.text:
                return {"type": "text", "content": response.text}
                
            if response.function_calls:
                # Return the first tool call
                fc = response.function_calls[0]
                return {
                    "type": "tool_call",
                    "content": {
                        "name": fc.name,
                        "arguments": fc.args
                    }
                }
                
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            raise RuntimeError(f"Cloud API Error: {str(e)}")
