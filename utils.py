import unicodedata
import re

def normalize_text(text: str) -> str:
    if not text:
        return ""

    # Lowercase
    text = text.lower()

    # Remove accents
    text = unicodedata.normalize("NFD", text)
    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    )

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


def split_message(text: str, max_length: int = 1500):
    """
    Splits text into chunks safe for WhatsApp.
    """
    chunks = []
    
    while len(text) > max_length:
        split_index = text.rfind("\n", 0, max_length)
        if split_index == -1:
            split_index = max_length
        
        chunks.append(text[:split_index])
        text = text[split_index:].strip()
    
    chunks.append(text)
    
    return chunks
