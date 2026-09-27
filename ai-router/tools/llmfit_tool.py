import asyncio
import json
import logging
from pydantic import BaseModel, Field
from tools.base import BaseTool
import subprocess

logger = logging.getLogger(__name__)

class LLMFitInput(BaseModel):
    command: str = Field(..., description="The llmfit command to run (e.g. 'system', 'recommend', 'search <query>', 'info <model>', 'fit', 'plan <model>')")
    limit: int = Field(5, description="Maximum number of results to return (for recommend, search, fit)")

class LLMFitTool(BaseTool):
    """
    Tool to run llmfit, a utility for right-sizing LLM models to the system's hardware.
    It can detect system hardware, recommend models that fit, and show requirements for specific models.
    """
    
    @property
    def name(self) -> str:
        return "llmfit"

    @property
    def description(self) -> str:
        return "Right-size LLMs for this hardware. Use 'system' to detect specs, 'recommend' for top picks, 'search <query>' to find models, 'info <model>' for details, or 'fit' for all compatible models."

    @property
    def input_schema(self) -> type[BaseModel]:
        return LLMFitInput

    async def execute(self, user_id: int, **kwargs) -> tuple[str, str]:
        command_str = kwargs.get("command", "system")
        limit = kwargs.get("limit", 5)
        
        args = [".\\llmfit_bin\\llmfit-v1.1.15-x86_64-pc-windows-msvc\\llmfit.exe"]
        
        # Split command to handle arguments like "search llama"
        cmd_parts = command_str.split()
        args.extend(cmd_parts)
        
        # Add flags
        args.append("--json")
        if cmd_parts[0] in ["recommend", "search", "fit"]:
            args.extend(["--limit", str(limit)])
            
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip() or stdout.decode().strip()
                return f"Error running llmfit: {error_msg}", self.name
                
            try:
                # Parse JSON to format it nicely
                data = json.loads(stdout.decode())
                
                # Truncate large results if it's a list (like recommendations)
                if isinstance(data, dict) and "recommendations" in data:
                    recs = data["recommendations"]
                    if isinstance(recs, list) and len(recs) > limit:
                        data["recommendations"] = recs[:limit]
                        
                return json.dumps(data, indent=2), self.name
            except json.JSONDecodeError:
                return stdout.decode().strip(), self.name
                
        except FileNotFoundError:
            return "llmfit executable not found. Make sure it is installed in the llmfit_bin directory.", self.name
        except Exception as e:
            logger.error(f"llmfit tool error: {e}")
            return f"Failed to execute llmfit: {str(e)}", self.name
