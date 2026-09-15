import httpx
from config import GROQ_API_KEY

resp = httpx.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {GROQ_API_KEY}"})
for model in resp.json().get("data", []):
    print(model["id"])
