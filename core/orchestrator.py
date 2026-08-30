import sys
import asyncio
import json
import logging
import os
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from config import CONTEXT_SIZES, SYSTEM_PROMPTS, is_budget_mode_active
from router.classifier import classify_request
from router.rules import get_routing_decision
from db import get_db
from core.events import EventBus
from core.mcp_client import MCPManager

logger = logging.getLogger(__name__)

# Thread pool for non-blocking DB writes
_db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="db_writer")

# ─── Skills Cache ────────────────────────────────────────────────────────────
# Loaded once at import time so we never hit the filesystem during a request.
_skills_cache: Dict[str, str] = {}

def _load_skills_cache():
    skills_dir = "markdown_skills"
    if not os.path.exists(skills_dir):
        return
    for filename in os.listdir(skills_dir):
        if filename.endswith(".md"):
            keyword = filename[:-3].lower()
            with open(os.path.join(skills_dir, filename), "r", encoding="utf-8") as f:
                _skills_cache[keyword] = f.read()

_load_skills_cache()

def save_message(session_id: int, role: str, content: Any):
    """Save a message to the database (blocking, run in executor)."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Handle multimodal lists (e.g. vision array)
    if isinstance(content, list):
        content = json.dumps(content)
        
    cursor.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()

def inject_system_prompt(messages: List[Dict[str, Any]], category: str, rag_context: List[str] = None) -> List[Dict[str, Any]]:
    """Injects the appropriate system prompt, RAG context, and relevant Markdown Skills."""
    if not messages:
        return messages
        
    prompt = SYSTEM_PROMPTS.get(category, SYSTEM_PROMPTS["general"])
    
    # 1. RAG Context Injection
    if rag_context:
        context_str = "\n".join([f"- {c}" for c in rag_context])
        prompt += f"\n\nHere are some relevant facts you remember about the user:\n{context_str}\n"
        
    # 2. Markdown Skills Injection (from cache - zero filesystem I/O)
    raw_content = messages[-1].get("content", "")
    if isinstance(raw_content, list):
        raw_content = next((item.get("text", "") for item in raw_content if item.get("type") == "text"), str(raw_content))
    last_msg = raw_content.lower()
    for keyword, skill_content in _skills_cache.items():
        if keyword in last_msg:
            prompt += f"\n\n<skill name=\"{keyword}\">\n{skill_content}\n</skill>\n"

        
    if messages[0].get("role") == "system":
        messages[0]["content"] = prompt
        return messages
    
    return [{"role": "system", "content": prompt}] + messages

class ConversationOrchestrator:
    """
    Central orchestrator for HELIOS.
    Coordinates memory, classification, tool execution, and model generation.
    Publishes events to an EventBus instead of directly writing to a WebSocket.
    """
    def __init__(self, model_manager, tool_executor, memory_manager, permission_manager, tool_router=None):
        self.model_manager = model_manager
        self.tool_executor = tool_executor
        self.memory_manager = memory_manager
        self.permission_manager = permission_manager
        self.tool_router = tool_router
        self.cancellation_events = {}
        self.mcp_manager = MCPManager()
        # You would initialize actual MCP servers here, e.g., 
        # asyncio.create_task(self.mcp_manager.connect_server("sqlite", "python", ["-m", "mcp_sqlite"]))


    def cancel_current_request(self, session_id: int):
        if session_id in self.cancellation_events:
            self.cancellation_events[session_id].set()

    async def _handle_user_input(self, question: str, event_bus: EventBus) -> str:
        request_id = self.permission_manager.approval_manager.generate_request_id()
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.permission_manager.approval_manager.register_pending(request_id, future)
        
        await event_bus.publish("input_request", {
            "request_id": request_id,
            "question": question
        })
        
        try:
            # Wait a long time for the user to answer
            response = await asyncio.wait_for(future, timeout=300.0)
            return response.get("text", "")
        except asyncio.TimeoutError:
            return "User did not respond in time."
        except Exception as e:
            return f"Error waiting for input: {e}"

    async def _handle_tool_approval(self, user_id: int, operation: str, target: str, event_bus: EventBus, headless: bool = False) -> bool:
        """Handles requesting and waiting for user approval."""
        if self.permission_manager.approval_manager.has_session_approval(user_id, operation, target):
            return True
            
        if headless:
            await event_bus.publish("approval_request", {
                "request_id": "headless_denied",
                "operation": operation,
                "target": target
            })
            return False
            
        request_id = self.permission_manager.approval_manager.generate_request_id()
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.permission_manager.approval_manager.register_pending(request_id, future)
        
        await event_bus.publish("approval_request", {
            "request_id": request_id,
            "operation": operation,
            "target": target
        })
        
        try:
            approval = await asyncio.wait_for(future, timeout=60.0)
            if approval.get("approved"):
                scope = approval.get("scope", "once")
                self.permission_manager.approval_manager.grant_approval(
                    user_id, operation, target, scope
                )
                return True
            return False
        except asyncio.TimeoutError:
            return False

    async def process_request(self, session_id: int, user_id: int, messages: List[Dict[str, Any]], event_bus: EventBus, headless: bool = False):
        if not messages or not user_id or not session_id:
            return
            
        if session_id not in self.cancellation_events:
            self.cancellation_events[session_id] = asyncio.Event()
        self.cancellation_events[session_id].clear()

        # Extract text content (handle vision arrays)
        last_msg_raw = messages[-1]["content"]
        last_msg = last_msg_raw
        if isinstance(last_msg_raw, list):
            last_msg = next((item.get("text", "") for item in last_msg_raw if item.get("type") == "text"), str(last_msg_raw))
        
        # Save User Message to DB (non-blocking - runs in thread pool)
        # Note: We save the *raw* content here so the UI can render images if needed
        loop = asyncio.get_running_loop()
        loop.run_in_executor(_db_executor, save_message, session_id, "user", last_msg_raw)
        
        # Send initial loading status
        await event_bus.publish("status", "Analyzing your request...")
        
        # Extract facts in background (fire-and-forget) — disabled under memory pressure
        if not is_budget_mode_active():
            asyncio.create_task(self.memory_manager.extract_and_save_facts(user_id, last_msg))
        
        # ─── CONCURRENT PIPELINE ─────────────────────────────────────────
        from outer.classifier import RoutingEngine
        # Instantiate routing engine dynamically or pass down; for now instantiate locally
        routing_engine = RoutingEngine(semantic_cache_db=None) 
        
        rag_context, route_tuple = await asyncio.gather(
            self.memory_manager.search_memory(user_id, last_msg),
            routing_engine.route_request(last_msg_raw)
        )
        
        route_type, route_metadata = route_tuple
        
        # Construct compatibility 'route' dictionary for the rest of orchestrator
        route = {
            "route": route_type,
            "category": "general",
            "context_size": 4096,
            "model": route_metadata.get("model", route_metadata.get("model_chain", ["phi3:mini"])[0])
        }
        
        if route_type == "cloud":
            route["category"] = "cloud"
            
        await event_bus.publish("meta", {
            "route": route,
            "memory_injected": len(rag_context) > 0
        })
        
        messages = inject_system_prompt(messages, route.get("category", "general"), rag_context)
        
        MAX_TOOL_ITERATIONS = 8
        iteration = 0
        full_response = ""
        
        allowed_tools = []
        if self.tool_router:
            allowed_tools = self.tool_router.get_tool_schemas()
            
        mcp_tools = await self.mcp_manager.list_all_tools()
        if mcp_tools:
            allowed_tools.extend(mcp_tools)
            
        while iteration < MAX_TOOL_ITERATIONS:
            await event_bus.publish("status", "🧠 Generating response...")
            
            try:
                if route.get("route") == "cloud":
                    from models.gemini_client import GeminiClient
                    gemini = GeminiClient()
                    
                    async def adapted_gemini_stream():
                        try:
                            async for chunk in gemini.stream_chat(
                                messages=messages,
                                tools=allowed_tools if allowed_tools else None,
                                model=route.get("model", "gemini-2.5-flash")
                            ):
                                if chunk["type"] == "text":
                                    yield {"message": {"content": chunk["content"]}}
                                elif chunk["type"] == "tool_call":
                                    # Convert Gemini function call format to standard Ollama format
                                    yield {"message": {"tool_calls": [{
                                        "function": {
                                            "name": chunk["content"]["name"],
                                            "arguments": chunk["content"].get("args", {})
                                        }
                                    }]}}
                                elif chunk["type"] == "error":
                                    yield {"message": {"content": f"\n\n[System: {chunk['content']}]"}}
                        finally:
                            await gemini.close()
                            
                    stream = adapted_gemini_stream()
                else:
                    stream = await self.model_manager.execute_request(
                        target_model=route["model"],
                        messages=messages,
                        context_size=route["context_size"],
                        stream=True,
                        tools=allowed_tools if allowed_tools else None
                    )
                
                tool_calls = []
                content_accum = ""
                
                sys.stdout.write(f"\n\n--- LLM GENERATION START (Iteration {iteration}) ---\n")
                sys.stdout.flush()

                async for chunk in stream:
                    if self.cancellation_events[session_id].is_set():
                        await event_bus.publish("chunk", "\n\n[System: Generation stopped by user.]")
                        full_response += "\n\n[System: Generation stopped by user.]"
                        break
                    
                    if "message" in chunk:
                        msg = chunk["message"]
                        # Support for Ollama's native 'reasoning' field (e.g. DeepSeek-R1)
                        if "reasoning" in msg and msg["reasoning"]:
                            reasoning = msg["reasoning"]
                            content_accum += reasoning
                            full_response += reasoning
                            
                            try:
                                sys.stdout.write(reasoning)
                                sys.stdout.flush()
                            except UnicodeEncodeError:
                                sys.stdout.write(reasoning.encode('ascii', 'replace').decode('ascii'))
                                sys.stdout.flush()
                            
                            await event_bus.publish("chunk", reasoning)
                            
                        if "content" in msg and msg["content"]:
                            content = msg["content"]
                            content_accum += content
                            full_response += content
                            
                            # Stream to server terminal for monitoring
                            try:
                                sys.stdout.write(content)
                                sys.stdout.flush()
                            except UnicodeEncodeError:
                                sys.stdout.write(content.encode('ascii', 'replace').decode('ascii'))
                                sys.stdout.flush()
                            
                            await event_bus.publish("chunk", content)
                            
                        if "tool_calls" in msg and msg["tool_calls"]:
                            for tc in msg["tool_calls"]:
                                tool_calls.append(tc)
                sys.stdout.write("\n--- LLM GENERATION END ---\n")
                sys.stdout.flush()
                
                if self.cancellation_events[session_id].is_set():
                    break

                if not tool_calls:
                    await event_bus.publish("done", None)
                    break
                    
                # We have tool calls
                assistant_msg = {"role": "assistant", "content": content_accum, "tool_calls": tool_calls}
                messages.append(assistant_msg)
                
                for call in tool_calls:
                    function_name = call.get("function", {}).get("name")
                    arguments = call.get("function", {}).get("arguments", {})
                    
                    await event_bus.publish("status", f"🔧 Running tool {function_name}...")
                    
                    structured_result = {
                        "tool": function_name,
                        "status": "error",
                        "result": ""
                    }
                    
                    if "__" in function_name:
                        # MCP Tool Path - ALWAYS require approval for zero-trust
                        try:
                            server_name, _ = function_name.split("__", 1)
                            approved = await self._handle_tool_approval(user_id, "mcp_tool_execution", function_name, event_bus, headless)
                            
                            if approved:
                                res_text = await self.mcp_manager.call_tool(function_name, arguments)
                                structured_result["status"] = "success"
                                structured_result["result"] = res_text
                            else:
                                structured_result["status"] = "permission_denied"
                                structured_result["result"] = "User denied the operation."
                        except Exception as e:
                            logger.error(f"MCP Tool {function_name} failed: {e}")
                            structured_result["status"] = "error"
                            structured_result["result"] = str(e)
                    
                    elif not self.tool_router or function_name not in self.tool_router.tools:
                        structured_result["status"] = "unavailable"
                        structured_result["result"] = "Tool not found or not permitted."
                    else:
                        try:
                            tool = self.tool_router.tools[function_name]
                            # Pre-validate arguments
                            validated_args = tool.input_schema(**arguments).model_dump()
                            
                            # Execute
                            res_text, _ = await tool.execute(user_id=user_id, **validated_args)
                            
                            # Handle approval
                            if res_text.startswith("APPROVAL_REQUIRED::"):
                                parts = res_text.split("::", 2)
                                operation = parts[1] if len(parts) > 1 else "unknown"
                                target = parts[2] if len(parts) > 2 else "unknown"
                                
                                approved = await self._handle_tool_approval(user_id, operation, target, event_bus, headless)
                                
                                if approved:
                                    # Specific execution post-approval (like FileWriterTool's perform_write)
                                    if operation == "file_write" and function_name == "FileWriterTool":
                                        content_arg = validated_args.get("content", "")
                                        res_text, _ = await tool.perform_write(target, content_arg, user_id)
                                    else:
                                        # Re-run the tool execution since it's now approved
                                        res_text, _ = await tool.execute(user_id=user_id, **validated_args)
                                        
                                    structured_result["status"] = "success"
                                    structured_result["result"] = res_text
                                else:
                                    structured_result["status"] = "permission_denied"
                                    structured_result["result"] = "User denied the operation."
                            else:
                                structured_result["status"] = "success"
                                structured_result["result"] = res_text
                                
                        except Exception as e:
                            logger.error(f"Tool {function_name} failed: {e}")
                            if "validation" in str(e).lower() or "schema" in str(e).lower():
                                structured_result["status"] = "validation_error"
                            else:
                                structured_result["status"] = "error"
                            structured_result["result"] = str(e)
                            
                    # Append result to messages for the next LLM iteration
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(structured_result)
                    })
                    
                    # Ensure tool outputs are saved in the session history and displayed seamlessly
                    formatted_tool_output = f"\n\n[Tool Executed: {function_name}]\n{res_text}\n\n"
                    full_response += formatted_tool_output
                    await event_bus.publish("chunk", formatted_tool_output)
                    
            except Exception as e:
                import httpx
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                    fallback = config.MODEL_CONFIG.get("fallback")
                    if fallback and fallback != route["model"]:
                        logger.warning(f"Model {route['model']} not found. Retrying with fallback {fallback}.")
                        route["model"] = fallback
                        continue
                logger.error(f"Error executing request: {e}")
                import traceback
                tb_str = traceback.format_exc()
                logger.error(tb_str)
                full_response += f"\n\n[System Error: {str(e)}]"
                await event_bus.publish("chunk", f"\n\n[System Error: {str(e)}]")
                await event_bus.publish("done", None)
                break
                
            iteration += 1
            if iteration >= MAX_TOOL_ITERATIONS:
                warning = "\n\n[System Warning: Maximum tool iterations reached.]"
                full_response += warning
                await event_bus.publish("chunk", warning)
                await event_bus.publish("done", None)
                
        # Save Assistant Message to DB (non-blocking)
        if full_response:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(_db_executor, save_message, session_id, "assistant", full_response)
