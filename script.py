import re
with open('Documents/ai-router/config.py', 'r') as f: data=f.read()
data = re.sub(r'OLLAMA_HOST = .+', 'OLLAMA_HOST = "http://127.0.0.1:11434"', data)
with open('Documents/ai-router/config.py', 'w') as f: f.write(data)
print('Updated OLLAMA_HOST')
