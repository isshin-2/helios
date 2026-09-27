import os
import subprocess
import signal
import time
from typing import Optional, Dict

def launch_isolated_process(cmd: list[str], env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None) -> subprocess.Popen:
    """
    Launches a process in a new process group to allow complete tree termination.
    Hides platform-specific logic.
    """
    kwargs = {}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs['start_new_session'] = True

    return subprocess.Popen(
        cmd,
        env=env,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs
    )

def kill_process_tree(proc: subprocess.Popen):
    """
    Terminates a process and all its children across platforms.
    """
    if proc.poll() is not None:
        return  # Already exited

    if os.name == 'nt':
        # On Windows, taskkill /T terminates the tree
        try:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass
    else:
        # On POSIX, kill the process group
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            # Process or group might have already exited or we lack permissions
            try:
                proc.kill()
            except OSError:
                pass
                
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        pass
