import subprocess
import threading
import queue
import time
import os
from pydantic import BaseModel, Field
from typing import Tuple
from tools.base import BaseTool

class REPLInput(BaseModel):
    code: str = Field(description="The python code to execute in the stateful REPL.")

class StatefulREPLTool(BaseTool):
    name: str = "stateful_repl"
    description: str = "Executes Python code in a persistent, stateful REPL (like OpenInterpreter). Variables and imports persist across calls."
    input_schema: type[BaseModel] = REPLInput

    def __init__(self, permission_manager=None):
        self.permission_manager = permission_manager
        self.process = None
        self.output_queue = queue.Queue()
        self._start_repl()

    def _start_repl(self):
        if self.process:
            self.process.kill()
        self.process = subprocess.Popen(
            ['python', '-i', '-q'], 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1,
            env=os.environ.copy()
        )
        def read_output():
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.output_queue.put(line)

        self.thread = threading.Thread(target=read_output, daemon=True)
        self.thread.start()
        time.sleep(0.5)
        while not self.output_queue.empty():
            self.output_queue.get()

    async def execute(self, user_id: int, code: str, **kwargs) -> Tuple[str, str]:
        if not self.process or self.process.poll() is not None:
            self._start_repl()

        marker = f"---REPL_MARKER_{time.time()}---"
        full_code = code.strip() + f"\nprint('{marker}')\n"
        
        try:
            self.process.stdin.write(full_code)
            self.process.stdin.flush()
        except Exception as e:
            self._start_repl()
            return (f"REPL Error: {str(e)}", self.name)

        output = ""
        start_time = time.time()
        
        while time.time() - start_time < 30:
            try:
                line = self.output_queue.get(timeout=0.1)
                if marker in line:
                    break
                output += line
            except queue.Empty:
                pass
                
        if not output.strip():
            output = "Code executed successfully (No output)."
            
        return (output.strip(), self.name)
