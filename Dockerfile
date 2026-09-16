FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    git \
    curl \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV DOCKER_ENV=1
ENV HOST=0.0.0.0
ENV PORT=8000

# Expose the API port
EXPOSE 8000

# Start the HELIOS FastAPI server
CMD ["python", "main.py"]
