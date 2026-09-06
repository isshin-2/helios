FROM python:3.11-slim

WORKDIR /app

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copy only the necessary server files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ core/
COPY providers/ providers/
COPY tools/ tools/
COPY router/ router/
COPY security/ security/
COPY config.py .
COPY db.py .
COPY main.py .
COPY prompts/ prompts/

EXPOSE 8000 8001 11434

# Start Ollama in background, pull the model, then start HELIOS
CMD ollama serve & sleep 5 && ollama pull qwen2.5-coder:7b && python -m uvicorn main:app --host 0.0.0.0 --port 8000
