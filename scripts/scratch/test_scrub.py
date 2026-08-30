import re
import emoji

def clean_text_for_tts(text: str) -> str:
    \"\"\"Cleans up text for TTS reading.\"\"\"
    # 1. Remove <think>...</think> tags completely
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # 2. Replace code blocks with a spoken placeholder
    text = re.sub(r'```.*?```', ' [Code block provided] ', text, flags=re.DOTALL)
    
    # 3. Remove inline markdown characters
    text = re.sub(r'[*_#`~]', '', text)
    
    # 4. Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', ' [Link] ', text)
    
    # 5. Remove emojis
    text = emoji.replace_emoji(text, replace='')
    
    return text.strip()
