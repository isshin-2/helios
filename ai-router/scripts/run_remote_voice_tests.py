import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.100.254', username='krithik', password='Krithik@2026', timeout=5)

sftp = ssh.open_sftp()
sftp.put('c:/projects/HELIOS/ai-router/scripts/setup_voice.py', 'D:/helios/ai-router/scripts/setup_voice.py')
sftp.put('c:/projects/HELIOS/scripts/verify_voice.py', 'D:/helios/scripts/verify_voice.py')
sftp.close()

stdin, stdout, stderr = ssh.exec_command('cd /d D:\\helios\\ai-router && venv\\Scripts\\python.exe -c "from scripts.setup_voice import test_voice_output; test_voice_output()"')
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')

print('=== REMOTE AI PC VOICE OUTPUT TEST ===')
if out:
    print(out.strip())
if err:
    print('ERR:', err.strip())

stdin, stdout, stderr = ssh.exec_command('cd /d D:\\helios && venv\\Scripts\\python.exe scripts/verify_voice.py --test')
out2 = stdout.read().decode('utf-8', errors='ignore')
err2 = stderr.read().decode('utf-8', errors='ignore')

print('=== REMOTE AI PC VOICE BIOMETRICS TEST ===')
if out2:
    print(out2.strip())
if err2:
    print('ERR:', err2.strip())

ssh.close()
