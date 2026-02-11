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
