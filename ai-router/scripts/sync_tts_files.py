import os
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.100.254', username='krithik', password='Krithik@2026', timeout=5)

sftp = ssh.open_sftp()

files_to_sync = [
    ("c:/projects/HELIOS/ai-router/config/voice_profiles.yaml", "D:/helios/ai-router/config/voice_profiles.yaml"),
    ("c:/projects/HELIOS/ai-router/config/pronunciation.yaml", "D:/helios/ai-router/config/pronunciation.yaml"),
    ("c:/projects/HELIOS/ai-router/config/resources.yaml", "D:/helios/ai-router/config/resources.yaml"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/gpt_sovits.py", "D:/helios/ai-router/core/audio/tts/gpt_sovits.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/manager.py", "D:/helios/ai-router/core/audio/tts/manager.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/base.py", "D:/helios/ai-router/core/audio/tts/base.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/resource_policy.py", "D:/helios/ai-router/core/audio/tts/resource_policy.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/speech_planner.py", "D:/helios/ai-router/core/audio/tts/speech_planner.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/text_normalizer.py", "D:/helios/ai-router/core/audio/tts/text_normalizer.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/prosody.py", "D:/helios/ai-router/core/audio/tts/prosody.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/pronunciation.py", "D:/helios/ai-router/core/audio/tts/pronunciation.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/audio_processor.py", "D:/helios/ai-router/core/audio/tts/audio_processor.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/tts/__init__.py", "D:/helios/ai-router/core/audio/tts/__init__.py"),
    ("c:/projects/HELIOS/ai-router/core/audio/voice_manager.py", "D:/helios/ai-router/core/audio/voice_manager.py"),
    ("c:/projects/HELIOS/ai-router/config.py", "D:/helios/ai-router/config.py"),
]

for local, remote in files_to_sync:
    if os.path.exists(local):
        print(f"Uploading {os.path.basename(local)} -> {remote}")
        sftp.put(local, remote)

sftp.close()
ssh.close()
print("All TTS modules & configs successfully synced to AI PC!")
