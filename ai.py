import json
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are an intent classification engine for a distributor customer support assistant.

Your task:
- Identify the customer's intent
- Extract relevant entities
- Decide the next system action

Rules:
- Incomming messages most probably will be in Mexican Spanish
- Return ONLY valid JSON
- No explanations
- If unsure, intent = "unknown"

Possible intents:
- greeting
- place_order
- ask_prices
- ask_promotions
- track_order
- unknown

Entities:
- products: list of { sku, quantity }
- order_id: string or null

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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)}
        ]
    )

    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return {
            "intent": "unknown",
            "confidence": 0.0,
            "entities": {},
            "next_action": "fallback"
        }
