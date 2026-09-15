import os
import json
import logging
from typing import AsyncGenerator, Dict, Any, List
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class LocalAIProvider:
    def __init__(self, base_url="http://localhost:8080/v1", api_key="sk-localai"):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: List[Dict[str, Any]] = None,
        stream: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }
            if tools:
                kwargs["tools"] = tools

            response = await self.client.chat.completions.create(**kwargs)

            if stream:
                async for chunk in response:
                    # Map OpenAI format to HELIOS internal format
                    content = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta.content else ""
                    tool_calls = chunk.choices[0].delta.tool_calls if chunk.choices and chunk.choices[0].delta.tool_calls else None
                    
                    yield_data = {}
                    if content:
                        yield_data["message"] = {"content": content}
                    if tool_calls:
                        # Reconstruct tool call object
                        formatted_calls = []
                        for tc in tool_calls:
                            formatted_calls.append({
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": json.loads(tc.function.arguments) if tc.function.arguments else {}
                                }
                            })
                        yield_data["message"] = {"tool_calls": formatted_calls}
                    
                    if yield_data:
                        yield yield_data
            else:
                yield {"message": {"content": response.choices[0].message.content}}

        except Exception as e:
            logger.error(f"LocalAI Error: {str(e)}")
            raise e
