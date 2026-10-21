import os
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.100.254', username='krithik', password='Krithik@2026', timeout=5)

sftp = ssh.open_sftp()

# Ensure directories exist on AI PC
dirs = [
    "D:/helios/voices",
    "D:/helios/voices/airi"
]

for d in dirs:
    try:
        sftp.mkdir(d)
        print("Created:", d)
    except Exception as e:
        print("Dir exists or error:", d, e)

local_voice_dir = "c:/projects/HELIOS/voices/airi"
for f in os.listdir(local_voice_dir):
    local_path = os.path.join(local_voice_dir, f)
    remote_path = f"D:/helios/voices/airi/{f}"
    print(f"Uploading {local_path} -> {remote_path}...")
    sftp.put(local_path, remote_path)
    print(f"Uploaded {f} ({os.path.getsize(local_path)} bytes)")

sftp.close()
ssh.close()
print("Voice assets synchronized to AI PC!")
