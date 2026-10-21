import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.100.254', username='krithik', password='Krithik@2026', timeout=5)

sftp = ssh.open_sftp()
test_file = "c:/projects/HELIOS/ai-router/tests/test_tts_pipeline.py"
sftp.put(test_file, "D:/helios/ai-router/tests/test_tts_pipeline.py")
sftp.close()

stdin, stdout, stderr = ssh.exec_command("cd /d D:\\helios\\ai-router && venv\\Scripts\\python.exe -m pytest tests/test_tts_pipeline.py -v")
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print("=== REMOTE TTS PIPELINE PYTEST OUTPUT ===")
if out:
    print(out)
if err:
    print("=== REMOTE TTS PIPELINE PYTEST ERRORS ===")
    print(err)

ssh.close()
