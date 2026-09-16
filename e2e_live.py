import asyncio
import os
import shutil
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import config
from core.supervisor import Supervisor
from core.state_machine import TaskState
from core.task_contract import TaskContract
from agents.base import BaseAgent, AgentResult, AgentStatus

class LivePlanner(BaseAgent):
    def __init__(self, provider):
        super().__init__()
        self.provider = provider
    @property
    def agent_type(self) -> str: return "planner"
    async def execute(self, objective: str, context=None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        return self._make_result(AgentStatus.SUCCESS, "Plan created", detail="Step 1: Fix bug in tmp_live_test/src/calculator.py\nStep 2: Run tests", started_at=started_at)

class LiveCoder(BaseAgent):
    def __init__(self, provider):
        super().__init__()
        self.provider = provider
        self.attempts = 0
    @property
    def agent_type(self) -> str: return "coder"
    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        self.attempts += 1
        started_at = datetime.now(timezone.utc)
        
        calc_path = os.path.join("tmp_live_test", "src", "calculator.py")
        with open(calc_path, "r") as f:
            code = f.read()

        err_context = context.get("verification_error", "") if context else ""
        
        prompt = f"""
You are a Python coder. Your objective is: {objective}
Here is the current code:
```python
{code}
```
"""
        if err_context:
            prompt += f"\nPrevious verification failed with error:\n{err_context}\nFix it!\n"
        prompt += "Return ONLY the completely rewritten valid python code. Do not include markdown blocks or any other text."
        
        print(f"-> Sending prompt to LLM (Attempt {self.attempts})...")
        import httpx
        import config
        headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}
        payload = {"model": "qwen/qwen3.8-27b", "messages": [{"role": "user", "content": prompt}]}
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
        
        if content.startswith("```"):
            lines = content.split("\n")
            if len(lines) > 2:
                content = "\n".join(lines[1:-1])
                
        with open(calc_path, "w") as f:
            f.write(content)
            
        print(f"-> Gemini wrote:\n{content}")
        return self._make_result(AgentStatus.SUCCESS, "Wrote code", detail="Applied LLM patch", started_at=started_at)

class LiveTester(BaseAgent):
    @property
    def agent_type(self) -> str: return "tester"
    async def execute(self, objective: str, context=None) -> AgentResult:
        import subprocess
        print("-> Running pytest...")
        # Run pytest on the tmp folder
        res = subprocess.run([r".\venv\Scripts\pytest.exe", r"tmp_live_test\tests\test_calculator.py"], capture_output=True, text=True)
        if res.returncode == 0:
            return self._make_result(AgentStatus.SUCCESS, "Tests passed", detail=res.stdout, started_at=datetime.now(timezone.utc))
        else:
            return self._make_result(AgentStatus.FAILURE, "Tests failed", error=res.stdout, started_at=datetime.now(timezone.utc))

class LiveReviewer(BaseAgent):
    @property
    def agent_type(self) -> str: return "reviewer"
    async def execute(self, objective: str, context=None) -> AgentResult:
        return self._make_result(AgentStatus.SUCCESS, "Review complete", started_at=datetime.now(timezone.utc))

async def run_live_e2e():
    print("=== LIVE E2E TEST (Gemini) ===")
    
    # Needs db initialized
    import db
    db.init_db()

    successes = 0
    for i in range(10):
        print(f"\n=== RELIABILITY RUN {i+1}/10 ===")
        # Create temporary bug project
        if os.path.exists("tmp_live_test"):
            shutil.rmtree("tmp_live_test")
        os.makedirs("tmp_live_test/src", exist_ok=True)
        os.makedirs("tmp_live_test/tests", exist_ok=True)
        
        # Inject intentional bug
        with open("tmp_live_test/src/calculator.py", "w") as f:
            f.write("def add(a, b):\n    return a - b\n")
            
        with open("tmp_live_test/tests/test_calculator.py", "w") as f:
            f.write("import sys\nimport os\nsys.path.insert(0, os.path.abspath('tmp_live_test/src'))\nfrom calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")

        planner = LivePlanner(None)
        coder = LiveCoder(None)
        tester = LiveTester()
        reviewer = LiveReviewer()

        objective = "Fix the bug in the add function inside tmp_live_test/src/calculator.py."
        contract = TaskContract(objective=objective)
        supervisor = Supervisor()
        supervisor.start(contract)
        
        while not supervisor.is_done:
            state = supervisor.state
            result = None
            context = {}
            if state == TaskState.ANALYZE:
                result = AgentResult(agent_id="analyzer-mock", agent_type="analyzer", status=AgentStatus.SUCCESS, summary="Analysis complete.", started_at=datetime.now(timezone.utc))
            elif state == TaskState.PLAN:
                result = await planner.execute(objective, context)
            elif state == TaskState.EXECUTE or state == TaskState.REPAIR:
                result = await coder.execute(objective, context)
            elif state == TaskState.VERIFY:
                result = await tester.execute(objective, context)
            elif state == TaskState.FINALIZE:
                result = await reviewer.execute(objective, context)
            elif state == TaskState.WAITING_APPROVAL:
                supervisor.approve()
                continue
            
            if result:
                decision = supervisor.evaluate(result)
                supervisor.apply(decision)

        final_summary = supervisor.finalize_task()
        if final_summary.get("success"):
            successes += 1
            print(f"Run {i+1} PASSED.")
        else:
            print(f"Run {i+1} FAILED.")
            
    print(f"\n--- Reliability Test Completed: {successes}/10 Successes ---")

if __name__ == "__main__":
    asyncio.run(run_live_e2e())
