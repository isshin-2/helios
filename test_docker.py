import os
from sandbox.manager import SandboxManager

def test_docker_sandbox():
    print("Testing SandboxManager with Docker...")
    # Ensure Docker is enabled
    manager = SandboxManager(use_docker=True)
    
    print("Creating sandbox container...")
    sandbox_id = manager.create_sandbox()
    
    if not sandbox_id:
        print("FAIL: Could not create sandbox.")
        return
        
    print(f"Sandbox created: {sandbox_id}")
    
    print("Executing command inside sandbox: 'echo hello from docker'")
    exit_code, stdout, stderr = manager.execute(sandbox_id, "echo hello from docker")
    
    print(f"Exit Code: {exit_code}")
    print(f"STDOUT: {stdout.strip()}")
    print(f"STDERR: {stderr.strip()}")
    
    print("Executing command to check OS: 'uname -a'")
    exit_code2, stdout2, stderr2 = manager.execute(sandbox_id, "uname -a")
    print(f"Exit Code: {exit_code2}")
    print(f"STDOUT: {stdout2.strip()}")
    
    print("Executing command to check user: 'whoami'")
    exit_code3, stdout3, stderr3 = manager.execute(sandbox_id, "whoami")
    print(f"Exit Code: {exit_code3}")
    print(f"STDOUT: {stdout3.strip()}")
    
    print("Destroying sandbox...")
    manager.destroy_sandbox(sandbox_id)
    print("Done.")

if __name__ == "__main__":
    test_docker_sandbox()
