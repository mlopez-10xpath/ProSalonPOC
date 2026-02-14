import json
import os
from openai import OpenAI
from datetime import datetime, timezone, timedelta

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are an intent classification engine for a distributor customer support assistant.

Your task:
- Identify the customer's intent
- Extract relevant entities
- Decide the next system action

Rules:
- Incomming messages could probably be in Mexican Spanish
- Return ONLY valid JSON
- No explanations
- If unsure, intent = "unknown"

Possible intents:
- greeting
- place_order
- ask_prices
- ask_promotions
- track_order
- product_info
- unknown

Entities:
- product_name: string or null
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


def generate_ai_response(
    base_system_prompt: str,
    user_message: str,
    context_data: str,
    last_message_time=None,
    distributor_name: str | None = None
):
    """
    Sends full reasoning task to GPT with dynamic greeting intelligence.
    """

    greeting_type, time_of_day = build_greeting_context(last_message_time)

    greeting_context = f"""
Greeting rules:
- greeting_type: {greeting_type}
- time_of_day: {time_of_day}
- distributor_name: {distributor_name}

Instructions:
- If greeting_type is "first_ever_message", greet warmly.
- If "new_day", greet briefly.
- If "reconnection", greet warmly and acknowledge time gap.
- If "continuation", DO NOT greet.
- Use appropriate Spanish greeting:
    - morning → Buenos días
    - afternoon → Buenas tardes
    - evening → Buenas noches
- Keep greeting short and natural.
- Never greet twice in same day continuation.
"""

    full_system_prompt = "\n\n".join([
        base_system_prompt,
        greeting_context
    ])

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": full_system_prompt},
            {"role": "system", "content": f"Relevant data:\n{context_data}"},
            {"role": "user", "content": user_message}
        ]
    )

    return response.choices[0].message.content


def build_greeting_context(last_message_time):
    now = datetime.now(timezone.utc)

    # Determine greeting type
    if not last_message_time:
        greeting_type = "first_ever_message"
    else:
        time_diff = now - last_message_time

        if time_diff > timedelta(days=4):
            greeting_type = "reconnection"
        elif last_message_time.date() != now.date():
            greeting_type = "new_day"
        else:
            greeting_type = "continuation"

    # Determine time of day
    local_hour = now.hour

    if 5 <= local_hour < 12:
        time_of_day = "morning"
    elif 12 <= local_hour < 19:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"

    return greeting_type, time_of_day

