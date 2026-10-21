import os
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.100.254', username='krithik', password='Krithik@2026', timeout=5)

sftp = ssh.open_sftp()
sftp.put("c:/projects/HELIOS/ai-router/core/audio/tts/kokoro.py", "D:/helios/ai-router/core/audio/tts/kokoro.py")
sftp.close()
ssh.close()
print("Updated kokoro.py on AI PC!")
