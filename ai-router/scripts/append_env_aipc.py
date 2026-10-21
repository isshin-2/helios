import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.100.254', username='krithik', password='Krithik@2026', timeout=5)

sftp = ssh.open_sftp()
with sftp.file("D:/helios/ai-router/.env", "a") as f:
    f.write("\nGPT_SOVITS_ENABLED=true\nGPT_SOVITS_REF_AUDIO=D:/helios/voices/airi/reference.wav\nGPT_SOVITS_REF_TEXT=It's nice to meet you. Well, technically, we've already met, haven't we?\nGPT_SOVITS_API_URL=http://127.0.0.1:9880\n")

sftp.close()
ssh.close()
print("Updated .env via SFTP!")
