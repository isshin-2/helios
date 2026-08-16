import asyncio
import logging
import os
from typing import List, Dict, Any

from config import CONTEXT_SIZES, SYSTEM_PROMPTS
from router.classifier import classify_request
from router.rules import get_routing_decision
from db import get_db
from core.events import EventBus

logger = logging.getLogger(__name__)

def save_message(session_id: int, role: str, content: str):
    conn = get_db()
    cursor = conn.cursor()
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
        
    # 2. Markdown Skills Injection
    last_msg = messages[-1].get("content", "").lower()
    skills_dir = "markdown_skills"
    if os.path.exists(skills_dir):
        for filename in os.listdir(skills_dir):
            if filename.endswith(".md"):
                keyword = filename[:-3].lower()
                if keyword in last_msg:
                    with open(os.path.join(skills_dir, filename), "r", encoding="utf-8") as f:
                        skill_content = f.read()
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

    async def process_request(self, session_id: int, user_id: int, messages: List[Dict[str, Any]], event_bus: EventBus):
        if not messages or not user_id or not session_id:
            return

        last_msg = messages[-1]["content"]
        
        # Save User Message to DB
        save_message(session_id, "user", last_msg)
        
        # Send initial loading status
        await event_bus.publish("status", "Analyzing your request...")
        
        # Extract facts in background
        asyncio.create_task(self.memory_manager.extract_and_save_facts(user_id, last_msg))
        
        # Retrieve RAG Memory
        rag_context = await self.memory_manager.search_memory(user_id, last_msg)
        
        # Classify & Route
        await event_bus.publish("status", "Routing to the best model...")
        classification = classify_request(messages)
        route = get_routing_decision(classification)
        
        await event_bus.publish("meta", {
            "route": route,
            "memory_injected": len(rag_context) > 0
        })
        
        # Execute
        full_response = ""
        if route["route"] == "tool":
            skill_name = route.get("skill")
            
            # Send contextual status based on skill type
            status_map = {
                "FileReaderSkill": "📁 Reading file...",
                "DirectoryListerSkill": "📂 Listing directory...",
                "FileWriterSkill": "✏️ Preparing file write...",
                "TerminalSkill": "⚙️ Preparing command...",
                "SystemSkill": "🔧 Checking system...",
                "InternetSkill": "🌐 Searching the web...",
                "ComposioSkill": "🔗 Connecting integration...",
            }
            await event_bus.publish("status", "🔐 Checking permissions...")
            await event_bus.publish("status", status_map.get(skill_name, "Executing tool..."))
            
            # Phase 3 Transition: Check if the new tool router can handle it, otherwise fallback to legacy skill executor
            # Since tools are migrated in Phase 4/5, tool_router will likely skip for now.
            result = None
            tool_name = "unknown"
            if self.tool_router and skill_name in self.tool_router.tools:
                result, tool_name = await self.tool_router.execute(skill_name, user_id=user_id, task=last_msg)
            else:
                result, tool_name = await self.tool_executor.execute(
                    last_msg, force_skill=skill_name, user_id=user_id
                )
            
    async def _handle_tool_approval(self, user_id: int, operation: str, target: str, event_bus: EventBus) -> bool:
        """Handles requesting and waiting for user approval."""
        if self.permission_manager.approval_manager.has_session_approval(user_id, operation, target):
            return True
            
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

    async def process_request(self, session_id: int, user_id: int, messages: List[Dict[str, Any]], event_bus: EventBus):
        if not messages or not user_id or not session_id:
            return

        last_msg = messages[-1]["content"]
        
        # Save User Message to DB
        save_message(session_id, "user", last_msg)
        
        # Send initial loading status
        await event_bus.publish("status", "Analyzing your request...")
        
        # Extract facts in background
        asyncio.create_task(self.memory_manager.extract_and_save_facts(user_id, last_msg))
        
        # Retrieve RAG Memory
        rag_context = await self.memory_manager.search_memory(user_id, last_msg)
        
        # Classify & Route
        await event_bus.publish("status", "Routing to the best model...")
        classification = classify_request(messages)
        route = get_routing_decision(classification)
        
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
            
        while iteration < MAX_TOOL_ITERATIONS:
            await event_bus.publish("status", "🧠 Generating response...")
            
            try:
                stream = await self.model_manager.execute_request(
                    target_model=route["model"],
                    messages=messages,
                    context_size=route["context_size"],
                    stream=True,
                    tools=allowed_tools if allowed_tools else None
                )
                
                tool_calls = []
                content_accum = ""
                
                async for chunk in stream:
                    if "message" in chunk:
                        msg = chunk["message"]
                        if "content" in msg and msg["content"]:
                            content = msg["content"]
                            content_accum += content
                            full_response += content
                            await event_bus.publish("chunk", content)
                            
                        if "tool_calls" in msg and msg["tool_calls"]:
                            for tc in msg["tool_calls"]:
                                tool_calls.append(tc)
                
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
                    
                    if not self.tool_router or function_name not in self.tool_router.tools:
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
                                
                                approved = await self._handle_tool_approval(user_id, operation, target, event_bus)
                                
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
                    import json
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(structured_result)
                    })
                    
            except Exception as e:
                logger.error(f"Error executing request: {e}")
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
                
        # Save Assistant Message to DB
        if full_response:
            save_message(session_id, "assistant", full_response)
