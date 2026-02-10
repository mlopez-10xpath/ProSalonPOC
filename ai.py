import json
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INTENT_SYSTEM_PROMPT = """
You are an intent classification engine for a WhatsApp customer support assistant.

Your job:
- Identify the user's intent
- Extract relevant entities
- Decide the next logical action

Rules:
- Messages most probably will be in Mexican Spanish
- Return ONLY valid JSON
- Do NOT include explanations
- If unsure, use intent = "unknown"

Possible intents:
- greeting
- create_order
- ask_prices
- track_order
- unknown

JSON format:
{
  "intent": string,
  "confidence": number between 0 and 1,
  "entities": object,
  "next_action": string
}
"""

def analyze_intent(message_text: str, context: dict | None = None) -> dict:
    payload = {
        "message": message_text,
        "context": context or {}
    }

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)}
        ]
    )

    content = response.choices[0].message.content

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "intent": "unknown",
            "confidence": 0.0,
            "entities": {},
            "next_action": "fallback"
        }
