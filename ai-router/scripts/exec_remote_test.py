import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.100.254', username='krithik', password='Krithik@2026', timeout=5)

sftp = ssh.open_sftp()
sftp.put("c:/projects/HELIOS/ai-router/scripts/run_airi_test_remote.py", "D:/helios/ai-router/run_airi_test.py")
sftp.close()

stdin, stdout, stderr = ssh.exec_command("cd /d D:\\helios\\ai-router && venv\\Scripts\\python.exe run_airi_test.py")
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("=== REMOTE OUTPUT ===")
if out:
    print(out)
if err:
    print("=== REMOTE ERRORS ===")
    print(err)

ssh.close()
