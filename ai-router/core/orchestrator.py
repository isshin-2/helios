import sys
def safe_print(text):
    import sys
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(text.encode('utf-8'))
        else:
            sys.stdout.write(text)
        sys.stdout.flush()
    except Exception:
        pass




import asyncio
import json
import logging
import os
import re
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from config import CONTEXT_SIZES, SYSTEM_PROMPTS, is_budget_mode_active
from router.classifier import classify_request
from router.rules import get_routing_decision
from db import get_db
from core.events import EventBus, global_bus
import core.task_manager as tm
from core.verification import verification_manager
from core.agent_manager import agent_manager
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

    async def start(self):
        import os
        import asyncio
        if os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"):
            npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
            asyncio.create_task(self.mcp_manager.connect_server(
                "google_workspace",
                npx_cmd,
                ["-y", "@aaronsb/google-workspace-mcp"]
            ))


    def cancel_current_request(self, session_id: int):
        global_bus.cancel_session(session_id)
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

    async def _handle_tool_approval(self, user_id: int, operation: str, target: str, event_bus: EventBus, headless: bool = False, agent_mode: bool = False) -> bool:
        """Handles requesting and waiting for user approval."""
        if self.permission_manager.approval_manager.has_session_approval(user_id, operation, target):
            return True
            
        # Hard block permanently protected applications/credentials
        if hasattr(self.permission_manager, "is_protected_computer_target") and self.permission_manager.is_protected_computer_target(target):
            await event_bus.publish("approval_request", {
                "request_id": "blocked_protected",
                "operation": operation,
                "target": target,
                "reason": "Target is a protected credential/system application."
            })
            return False

        # Agent mode may bypass approval ONLY for explicitly safe capabilities
        if agent_mode:
            if hasattr(self.permission_manager, "is_safe_for_agent_mode") and self.permission_manager.is_safe_for_agent_mode(operation, target):
                return True
            # Dangerous computer actions and high-risk operations remain protected and continue to approval check!
            
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

    async def process_request(self, session_id: int, user_id: int, messages: List[Dict[str, Any]], event_bus: EventBus, headless: bool = False, agent_mode: bool = False):
        if not messages or not user_id or not session_id:
            return
            
        if session_id not in self.cancellation_events:
            self.cancellation_events[session_id] = asyncio.Event()
        self.cancellation_events[session_id].clear()

        # Extract text content (handle vision arrays)
        task = tm.task_manager.create_task(str(session_id), str(messages[-1].get('content', '')), user_id)
        task.transition(tm.TaskState.RUNNING)

        last_msg_raw = messages[-1]["content"]
        last_msg = last_msg_raw
        if isinstance(last_msg_raw, list):
            last_msg = next((item.get("text", "") for item in last_msg_raw if item.get("type") == "text"), str(last_msg_raw))
        
        # Save User Message to DB (non-blocking - runs in thread pool)
        # Note: We save the *raw* content here so the UI can render images if needed
        loop = asyncio.get_running_loop()
        loop.run_in_executor(_db_executor, save_message, session_id, "user", last_msg_raw)
        
        # Attach CharacterManager to the request EventBus if character addon is enabled
        try:
            from core.character_manager import character_manager
            if character_manager.enabled:
                character_manager.attach_event_bus(event_bus)
        except Exception:
            pass

        # Send initial loading status
        await event_bus.publish("status", "Analyzing your request...")
        
        _mem_keywords = ("remember", "my name", "i am", "i like", "prefer", "fact", "earlier", "previous", "who am i", "what did i")
        _action_keywords = (
            "notepad", "mouse", "cursor", "click", "screenshot", "screen",
            "display", "open app", "open the app", "open ", "launch ", "type ",
            "press ", "scroll", "hotkey", "test", "run ", "execute", "take a screenshot",
            "calc", "calculator", "math", "app"
        )
        has_action_request = any(kw in str(last_msg).lower() for kw in _action_keywords)
        _greeting_patterns = {"hi", "hello", "hey", "yo", "sup", "what's up", "whats up", "howdy", "good morning", "good evening", "good afternoon"}
        clean_msg = re.sub(r'[^\w\s]', '', str(last_msg).lower().strip())
        is_greeting_text = clean_msg in _greeting_patterns or (
            len(str(last_msg).strip()) < 30 and any(clean_msg.startswith(w) for w in ["hi ", "hello ", "hey ", "yo ", "sup "])
        )
        is_short_greeting = is_greeting_text and not has_action_request and not agent_mode and not any(k in str(last_msg).lower() for k in _mem_keywords)

        if not is_budget_mode_active() and not is_short_greeting:
            asyncio.create_task(self.memory_manager.extract_and_save_facts(user_id, last_msg))
        
        # ─── CONCURRENT PIPELINE ─────────────────────────────────────────
        from outer.classifier import RoutingEngine
        # Instantiate routing engine dynamically or pass down; for now instantiate locally
        routing_engine = RoutingEngine(semantic_cache_db=None) 
        
        if is_short_greeting:
            rag_context = []
            route_tuple = await routing_engine.route_request(last_msg_raw, agent_mode=agent_mode)
        else:
            rag_context, route_tuple = await asyncio.gather(
                self.memory_manager.search_memory(user_id, last_msg),
                routing_engine.route_request(last_msg_raw, agent_mode=agent_mode)
            )
        
        route_type, route_metadata = route_tuple

        agent = agent_manager.get_agent(
            route_type,
            provider=getattr(self.model_manager, "provider", None),
            permission_manager=self.permission_manager,
            event_bus=event_bus
        )
        if agent:
            result = await agent.execute(
                last_msg,
                context={
                    "user_id": user_id,
                    "session_id": session_id,
                    "task_id": str(getattr(task, "id", f"task_{session_id}"))
                }
            )
            content_str = result.summary if hasattr(result, "summary") else str(result)
            await event_bus.publish("message", {"role": "assistant", "content": content_str})
            await event_bus.publish("chunk", content_str)
            await event_bus.publish("done", None)
            self.memory_manager.save_to_memory(user_id, content_str, "assistant")
            return

          
        
        # Construct compatibility 'route' dictionary for the rest of orchestrator
        detected_category = route_metadata.get("category", "general")
        if agent_mode or has_action_request:
            detected_category = "agent"
        elif route_type == "cloud":
            detected_category = "cloud"

        default_agent_model = "hermes3:8b"
        chosen_model = route_metadata.get("model", default_agent_model if detected_category == "agent" else "llama3.2:3b")
        if detected_category == "agent" and chosen_model == "llama3.2:3b":
            chosen_model = default_agent_model
            
        route = {
            "route": route_type,
            "category": detected_category,
            "context_size": 1024 if is_short_greeting else route_metadata.get("context_size", 8192 if detected_category == "agent" else 4096),
            "model": "llama3.2:3b" if is_short_greeting else chosen_model
        }
            
        await event_bus.publish("meta", {
            "route": route,
            "memory_injected": len(rag_context) > 0
        })
        
        if is_short_greeting and route.get("category") == "general" and not rag_context:
            fast_sys = (
                "You are Airi, a sharp, friendly, embodied AI engineering companion in a real-time 3D Techwear VRM avatar body. "
                "Start every reply with `[BODY: move=<stay|walk_to_user|step_back|circle_user|return_center>, "
                "pose=<wave|nod|peace|cheer|shrug|bow|confident|smug_pose|dance_shikano|backflip|think_pose|talk_explain|cyber_salute|superhero_landing|martial_arts_guard|double_biceps_flex|facepalm|zen_meditation|point_forward|rock_on_pose>, "
                "emotion=<neutral|happy|amused|curious|excited|concerned|serious>]` followed by a concise, natural 1-2 sentence reply in character."
            )
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = fast_sys
            else:
                messages = [{"role": "system", "content": fast_sys}] + messages
        else:
            messages = inject_system_prompt(messages, route.get("category", "general"), rag_context)
        
        MAX_TOOL_ITERATIONS = 3
        iteration = 0
        full_response = ""
        
        allowed_tools = []
        needs_tools = (
            agent_mode
            or route.get("category") in ("agent", "tool_use", "system", "coding")
            or has_action_request
        )
        if needs_tools:
            if self.tool_router:
                all_schemas = self.tool_router.get_tool_schemas()
                if route.get("category") in ("agent", "system") or has_action_request:
                    os_tool_names = {
                        "computer_control", "screen_vision", "terminal", "TerminalTool",
                        "stateful_shell", "StatefulShellTool", "file_reader", "FileReaderTool",
                        "file_writer", "FileWriterTool", "directory_lister", "DirectoryListerTool",
                        "ask_user", "AskUserTool", "git_ops", "process_monitor", "http_client",
                        "env_secrets", "reverse_engineer"
                    }
                    q_lower = str(last_msg).lower()
                    if any(w in q_lower for w in ["search", "web", "google", "lookup", "browse"]):
                        os_tool_names.update(["web_search", "browser_tool"])
                    if any(w in q_lower for w in ["github", "issue", "repo", "git"]):
                        os_tool_names.update(["github_create_issue", "github_list_issues", "repo_map", "git_ops"])
                    if any(w in q_lower for w in ["reverse", "decompile", "binary", "assembly", "disassemble", "rea", "pe", "elf"]):
                        os_tool_names.update(["reverse_engineer"])
                    if any(w in q_lower for w in ["process", "port", "kill", "cpu", "ram", "task"]):
                        os_tool_names.update(["process_monitor"])
                    if any(w in q_lower for w in ["http", "api", "curl", "request", "webhook", "fetch"]):
                        os_tool_names.update(["http_client"])
                    if any(w in q_lower for w in ["env", "secret", "token", "variable", "key"]):
                        os_tool_names.update(["env_secrets"])
                    if any(w in q_lower for w in ["printer", "bambu", "3d", "octoprint", "print"]):
                        os_tool_names.update(["bambu_printer_status", "bambu_printer_stop", "octoprint_control", "octoprint_status"])
                    if any(w in q_lower for w in ["drive", "cloud"]):
                        os_tool_names.update(["google_drive_list_files", "google_drive_read_file"])
                    allowed_tools = [s for s in all_schemas if s.get("function", {}).get("name") in os_tool_names]
                else:
                    allowed_tools = all_schemas
                
            mcp_tools = await self.mcp_manager.list_all_tools()
            if mcp_tools:
                allowed_tools.extend(mcp_tools)

        
        # Track whether screen_vision has been called (for vision enforcement)
        vision_used = False
            
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
                
                safe_print(f"\n\n--- LLM GENERATION START (Iteration {iteration}) ---\n")

                async for chunk in stream:
                    if self.cancellation_events[session_id].is_set() or global_bus.get_token(session_id).is_cancelled:
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
                                safe_print(reasoning)
                            except UnicodeEncodeError:
                                safe_print(reasoning.encode('ascii', 'replace').decode('ascii'))
                            
                            await event_bus.publish("thought", reasoning)
                            await event_bus.publish("chunk", reasoning)
                            
                        if "content" in msg and msg["content"]:
                            content = msg["content"]
                            content_accum += content
                            full_response += content
                            
                            # Stream to server terminal for monitoring
                            try:
                                safe_print(content)
                            except UnicodeEncodeError:
                                safe_print(content.encode('ascii', 'replace').decode('ascii'))
                            
                            await event_bus.publish("chunk", content)
                            
                            # ── STREAM-INTERRUPT: break as soon as a complete ```json ... ``` block lands ──
                            import re as _re
                            if _re.search(r'```json\s*\{.*?\}\s*```', content_accum, _re.DOTALL):
                                safe_print("\n[STREAM-INTERRUPT] Complete JSON tool block detected – stopping generation early.\n")
                                break
                            
                        if "tool_calls" in msg and msg["tool_calls"]:
                            for tc in msg["tool_calls"]:
                                tool_calls.append(tc)
                safe_print("\n--- LLM GENERATION END ---\n")
                
                if self.cancellation_events[session_id].is_set() or global_bus.get_token(session_id).is_cancelled:
                    break

                # ── TRUNCATE: strip everything after the JSON block so hallucinated text never enters history ──
                json_block_match = re.search(r'(```json\s*\{.*?\}\s*```)', content_accum, re.DOTALL)
                if json_block_match and not tool_calls:
                    # Keep only the JSON block itself in the assistant message
                    content_accum = json_block_match.group(1)
                    # Also strip hallucinated text from full_response so it is neither saved to history nor spoken by TTS
                    full_response = ""
                elif not tool_calls and any(tag in content_accum for tag in ("<tool_call>", "```")):
                    full_response = ""
                
                if not tool_calls:
                    # Fallback for models outputting JSON blocks or tool tags instead of native tool calls
                    json_blocks = []
                    # 1. Standard markdown code blocks: ```json ... ``` or ``` ... ```
                    for m in re.finditer(r'```(?:json)?\s*(\{.*?\})\s*```', content_accum, re.DOTALL):
                        json_blocks.append(m.group(1))
                    # 2. <tool_call> tags
                    for m in re.finditer(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', content_accum, re.DOTALL):
                        json_blocks.append(m.group(1))
                    # 3. json\n{...}\n[/json]
                    for m in re.finditer(r'json\s*(\{.*?\})\s*\[/json\]', content_accum, re.DOTALL):
                        json_blocks.append(m.group(1))
                    # 4. Balanced braces fallback
                    if not json_blocks:
                        for m in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content_accum, re.DOTALL):
                            json_blocks.append(m.group(0))

                    for block in json_blocks:
                        try:
                            parsed = json.loads(block)
                            if isinstance(parsed, dict):
                                func_name = parsed.get("function", parsed.get("name"))
                                args = parsed.get("arguments", parsed.get("parameters", {}))
                                if not func_name and "action" in parsed:
                                    func_name = "computer_control"
                                    args = parsed
                                if func_name:
                                    if func_name in ["move", "click", "double_click", "right_click", "type", "press", "hotkey", "scroll", "open_app"]:
                                        args["action"] = func_name
                                        func_name = "computer_control"
                                    # Validate and filter empty degenerate tool calls
                                    if func_name == "computer_control":
                                        action = str(args.get("action", "")).strip()
                                        if not action:
                                            continue
                                        if action in ("launch_application", "open_app") and not str(args.get("app_name", "")).strip():
                                            continue
                                        if action in ("type", "write") and not str(args.get("text", "")).strip():
                                            continue
                                        if action in ("press", "hotkey") and not args.get("keys") and not args.get("key"):
                                            continue
                                    tool_calls.append({
                                        "function": {
                                            "name": func_name,
                                            "arguments": args
                                        }
                                    })
                        except Exception:
                            pass
                            
                if not tool_calls:
                    await event_bus.publish("done", None)
                    break
                
                # ── VISION ENFORCEMENT: force screen_vision before spatial computer_control ──
                # Spatial actions strictly require pixel coordinates on screen
                SPATIAL_ACTIONS = {"click", "double_click", "right_click", "move", "click_element"}
                enforced_tool_calls = []
                for call in tool_calls:
                    fn = call.get("function", {}).get("name", "")
                    fn_args = call.get("function", {}).get("arguments", {})
                    action = fn_args.get("action", "")
                    if not action and (fn_args.get("app_name") or fn_args.get("app")):
                        action = "launch_application"
                        fn_args["action"] = action
                    
                    if fn == "computer_control" and action in SPATIAL_ACTIONS and not vision_used:
                        safe_print("[VISION ENFORCEMENT] Blocked spatial computer_control – injecting screen_vision first.\n")
                        enforced_tool_calls.append({
                            "function": {
                                "name": "screen_vision",
                                "arguments": {"query": f"Locate elements on screen needed to: {action}. Provide exact pixel coordinates."}
                            }
                        })
                    enforced_tool_calls.append(call)
                tool_calls = enforced_tool_calls
                    
                # We have tool calls
                assistant_msg = {"role": "assistant", "content": content_accum, "tool_calls": tool_calls}
                messages.append(assistant_msg)
                
                needs_input_break = False
                for call in tool_calls:
                    function_name = call.get("function", {}).get("name")
                    arguments = call.get("function", {}).get("arguments", {})
                    
                    await event_bus.publish("tool_start", {"tool": function_name})
                    await event_bus.publish("status", f"[System] Running tool {function_name}...")
                    
                    # Track screen_vision usage for enforcement
                    if function_name == "screen_vision":
                        vision_used = True
                    
                    structured_result = {
                        "tool": function_name,
                        "status": "error",
                        "result": ""
                    }
                    
                    if "__" in function_name:
                        # MCP Tool Path - ALWAYS require approval for zero-trust
                        try:
                            server_name, _ = function_name.split("__", 1)
                            approved = await self._handle_tool_approval(user_id, "mcp_tool_execution", function_name, event_bus, headless, agent_mode)
                            
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
                                
                                approved = await self._handle_tool_approval(user_id, operation, target, event_bus, headless, agent_mode)
                                
                                if approved:
                                    # Specific execution post-approval (like FileWriterTool's perform_write)
                                    if operation == "file_write" and function_name in ("FileWriterTool", "file_writer"):
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
                            
                    res_text_safe = str(structured_result.get("result", ""))
                    
                    # Phase 6 & 7: Verification & Bounded Recovery
                    is_verified, reject_reason = verification_manager.verify_tool_result(function_name, structured_result)
                    if not is_verified:
                        await event_bus.publish("tool_error", {"tool": function_name, "error": reject_reason})
                        if not verification_manager.record_failure(str(session_id)):
                            # Limit exceeded
                            task.transition(tm.TaskState.FAILED, "Max recovery attempts exceeded")
                            warning = f"\n\n[System Error: Agent exceeded maximum recovery attempts. Last error: {reject_reason}]"
                            full_response += warning
                            await event_bus.publish("chunk", warning)
                            await event_bus.publish("done", None)
                            break
                        else:
                            # Remind LLM to fix it
                            structured_result["result"] = f"[{reject_reason}] " + res_text_safe
                    else:
                        verification_manager.record_success(str(session_id))
                        await event_bus.publish("tool_complete", {"tool": function_name})

                    
                    if res_text_safe.startswith("INPUT_REQUIRED::"):
                        raw_question = res_text_safe.replace("INPUT_REQUIRED::", "").strip()
                        options = None
                        
                        opts_match = re.search(r'\[OPTIONS:(.*?)\]', raw_question)
                        if opts_match:
                            options = opts_match.group(1).split('|')
                            raw_question = raw_question.replace(opts_match.group(0), "").strip()
                            
                        # Send an actual input_request event to trigger the modal
                        await event_bus.publish("input_request", {"question": raw_question, "options": options, "session_id": session_id})
                        
                        messages.append({
                            "role": "user",
                            "content": f"SYSTEM/TOOL RESULT from '{function_name}':\n{json.dumps(structured_result)}\n\nIMPORTANT INSTRUCTION: You have requested user input. STOP GENERATING NOW and wait for the user to respond."
                        })
                        
                        # Break out of the orchestration loop to yield to the user
                        await event_bus.publish("done", None)
                        needs_input_break = True
                        break
                    
                    # Small models (3B) often fail to understand "role": "tool" and break character.
                    # Appending as "role": "user" with guidance allows continued tool execution OR completion.
                    messages.append({
                        "role": "user",
                        "content": f"SYSTEM/TOOL RESULT from '{function_name}':\n{json.dumps(structured_result)}\n\nIMPORTANT INSTRUCTION: If additional steps are required, continue using tools (output ONLY a ```json tool call block). If the requested goal is already completely accomplished, conclude the task by outputting a concise conversational summary to the user (without any further tool calls)."
                    })
                    
                    # Ensure tool outputs are saved in the session history and displayed seamlessly
                    formatted_tool_output = f"\n\n[Tool Executed: {function_name}]\n{res_text_safe}\n\n"
                    full_response += formatted_tool_output
                    await event_bus.publish("chunk", formatted_tool_output)
                    
            except Exception as e:
                import httpx
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                    model_cfg = config.MODEL_CONFIG.get(route["model"], {})
                    fallback = model_cfg.get("fallback") or model_cfg.get("cloud_fallback")
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
                
            if needs_input_break:
                break
                
            iteration += 1
            if iteration >= MAX_TOOL_ITERATIONS:
                warning = "\n\n[System Warning: Maximum tool iterations reached.]"
                full_response += warning
                await event_bus.publish("chunk", warning)
                await event_bus.publish("done", None)
                
        if task.state == tm.TaskState.RUNNING:
            task.transition(tm.TaskState.COMPLETED, "Loop finished")

        # Save Assistant Message to DB (non-blocking)
        if full_response:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(_db_executor, save_message, session_id, "assistant", full_response)
            
            # Extract facts from the AI's final response (this naturally catches tool summaries!)
            if not is_budget_mode_active() and not is_short_greeting:
                asyncio.create_task(self.memory_manager.extract_and_save_facts(user_id, full_response))
