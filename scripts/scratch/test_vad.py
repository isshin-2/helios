import pyaudio
import numpy as np
import torch
import time

pa = pyaudio.PyAudio()
stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=512)

model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False, onnx=False, trust_repo=True)

print("Listening for 5 seconds... Please speak clearly into the microphone.")
start = time.time()
while time.time() - start < 5:
    data = stream.read(512, exception_on_overflow=False)
    audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    tensor = torch.from_numpy(audio_np)
    prob = model(tensor, 16000).item()
    if prob > 0.5:
        print(f"Speech detected! Prob: {prob:.2f}")

stream.stop_stream()
stream.close()
pa.terminate()
