import json
import os
from openai import OpenAI
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Tuple
import logging

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are an intent classification engine for a distributor customer support assistant.

Your task:
- Identify the customer's intent
- Extract relevant entities
- Decide the next system action

You will receive a JSON object with:
- message: the current user message
- context: internal state if available
- recent_conversation: last conversation turns (user and assistant)
Use recent_conversation to determine intent more accurately.

Rules:
- Incomming messages could probably be in Mexican Spanish
- If the user is asking about the CURRENT draft order, use view_cart.
- If the user is asking about shipping or delivery status, use track_order.
- If unsure between add_to_cart and modify_cart:
    - If product not yet mentioned in conversation → add_to_cart
    - If referring to existing cart item → modify_cart
- Return ONLY valid JSON
- No explanations
- If unsure, intent = "unknown"

Possible intents:
--------------------------------------
INTENT DEFINITIONS
--------------------------------------

CART (Draft Order — before confirmation):

- add_to_cart:
  User wants to add products to their current draft order.
  Examples:
  - "agrega shampoo platino"
  - "quiero 2 geles"
  - "añade el de 500 ml"

- view_cart:
  User is asking what products are currently in their draft order.
  Examples:
  - "qué tengo en mi pedido"
  - "muéstrame mi carrito"
  - "cuál es mi pedido actual"
  - "ver pedido"

- modify_cart:
  User wants to remove or change quantities in their draft order.
  Examples:
  - "quita el shampoo"
  - "cambia a 3 el de 500"
  - "elimina el platino"

- confirm_order:
  User wants to finalize and confirm the draft order.
  Examples:
  - "confirmar"
  - "finalizar pedido"
  - "sí, confírmalo"

- cancel_order:
  User wants to cancel the current draft order.
  Examples:
  - "cancelar"
  - "cancel"
  - "anular pedido"

POST-CHECKOUT:

- track_order:
  User is asking about the status of an already confirmed order.
  Examples:
  - "dónde está mi pedido"
  - "ya lo enviaron?"
  - "estatus de mi orden"

GENERAL:

- ask_prices:
  User is asking about product prices.
  Examples:
  - "cuánto cuesta el de 500"
  - "precio del shampoo platino"

- ask_promotions:
  User is asking about discounts or promotions.
  Examples:
  - "tienen promociones?"
  - "hay ofertas?"

- product_info:
  User wants details about a product.
  Examples:
  - "para qué sirve el shampoo ialurónico"
  - "qué ingredientes tiene"

- greeting:
  Greetings or small talk.
  Examples:
  - "hola"
  - "buenos días"

- unknown:
  Anything that does not clearly match the above.

--------------------------------------

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
# ==========================================================
# GPT -  Analyze Intent
# ==========================================================
def analyze_intent(
    message_text: str,
    context: dict | None = None,
    history: list | None = None
) -> dict:

    payload = {
        "message": message_text,
        "context": context or {},
        "recent_conversation": history or []
    }

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False)
            }
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

# ==========================================================
# GPT - Generate AI Response
# ==========================================================
def generate_ai_response(
    base_system_prompt: str,
    user_message: str,
    context_data: str,
    customer_timezone: str,
    last_message_time=None,
    distributor_name: str | None = None
):
    """
    Sends full reasoning task to GPT with dynamic greeting intelligence.
    """

    greeting_type, time_of_day = build_greeting_context(last_message_time,
                                                       customer_timezone)

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

# ==========================================================
# GPT - Build Greeting Context
# ==========================================================
def build_greeting_context(
    last_message_time: Optional[datetime],
    customer_timezone: str
) -> Tuple[str, str]:
    """
    Determines:
    - greeting_type: first_ever_message | reconnection | new_day | continuation
    - time_of_day: morning | afternoon | evening
    """

    # --------------------------------------------------
    # 1️⃣ Get customer local time
    # --------------------------------------------------
    now_utc = datetime.now(timezone.utc)
    local_now = now_utc.astimezone(ZoneInfo(customer_timezone))

    # --------------------------------------------------
    # 2️⃣ Determine greeting type
    # --------------------------------------------------
    if not last_message_time:
        greeting_type = "first_ever_message"
    else:
        # Convert last message time to customer's timezone
        last_local = last_message_time.astimezone(
            ZoneInfo(customer_timezone)
        )

        time_diff = local_now - last_local

        if time_diff > timedelta(days=4):
            greeting_type = "reconnection"
        elif last_local.date() != local_now.date():
            greeting_type = "new_day"
        else:
            greeting_type = "continuation"

    # --------------------------------------------------
    # 3️⃣ Determine time of day
    # --------------------------------------------------
    local_hour = local_now.hour

    if 5 <= local_hour < 12:
        time_of_day = "morning"
    elif 12 <= local_hour < 19:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"

    return greeting_type, time_of_day



def extract_order_products_with_gpt(message_text: str, product_catalog: list):
    """
    Uses GPT to extract products from message.
    Supports:
    - Multiple products
    - Misspellings
    - Ambiguous matches
    """

    system_prompt = f"""
You are a product extraction and SKU matching assistant.

Your job:
- Extract ALL products mentioned in the message.
- Match each product ONLY to valid SKUs from the provided catalog.
- Handle misspellings and informal language.
- Support multiple products in one message.
- Detect ambiguous products (multiple presentations).
- NEVER invent SKUs.

You MUST respond in valid JSON only.
No explanations.
No extra text.

-------------------------
AVAILABLE PRODUCTS:
{json.dumps(product_catalog, ensure_ascii=False)}
-------------------------

Rules:

1. Default quantity to 1 if not specified.
2. Interpret numbers written as words (uno, dos, etc).
3. Only use SKUs from the provided list.
4. If a product clearly matches ONE SKU → add to "items".
5. If multiple SKUs could match → add to "ambiguous_items".
6. If no product matches → ignore it.

Response format:

{{
  "needs_clarification": boolean,
  "items": [
    {{
      "sku": "VALID_SKU",
      "quantity": number
    }}
  ],
  "ambiguous_items": [
    {{
      "requested_text": "original phrase",
      "possible_matches": [
        {{
          "sku": "VALID_SKU",
          "name": "Product Name"
        }}
      ]
    }}
  ]
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_text}
            ]
        )

        content = response.choices[0].message.content.strip()

        logging.info("🤖 Raw GPT extraction response:")
        logging.info(content)

        return json.loads(content)

    except Exception as e:
        logging.error(f"❌ GPT extraction error: {e}")
        return {
            "needs_clarification": False,
            "items": [],
            "ambiguous_items": []
        }
