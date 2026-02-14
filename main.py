# ==========================================================
# External Libraries
# ==========================================================
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from twilio.rest import Client
from supabase import create_client
from datetime import datetime, timezone, timedelta
# ==========================================================
# Libraries
# ==========================================================
import logging
import os
import json
# ==========================================================
# User defined functions
# ==========================================================
from ai import ( 
    analyze_intent,
    generate_ai_response
)
from flows import handle_intent
from db import (
    find_customer_by_phone,
    get_conversation_state,
    get_last_message_time,
    upsert_conversation_state,
    save_message,
    get_ai_flow, 
    get_all_products
)

# ==========================================================
# App & logging
# ==========================================================
app = FastAPI()
logging.basicConfig(level=logging.INFO)

# ==========================================================
# Twilio configuration
# (Fail fast if something critical is missing)
# ==========================================================
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = os.environ["TWILIO_WHATSAPP_FROM"]  # whatsapp:+14155238886

twilio_client = Client(
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN
)




# ==========================================================
# WhatsApp Webhook
# ==========================================================
@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """
    Main Twilio WhatsApp webhook.
    - Receives incoming messages
    - Looks up customer in Airtable
    - Sends exactly ONE outbound WhatsApp message
    - Returns fast 200 OK (no TwiML)
    """

    form = await request.form()

    # Normalize incoming data from Twilio
    message = {
        "from_phone": form.get("WaId"),              # e.g. 5213314179343
        "from_raw": form.get("From"),                # e.g. whatsapp:+5213314179343
        "profile_name": form.get("ProfileName"),     # WhatsApp profile name
        "body": form.get("Body", "").strip(),        # Message text
        "message_sid": form.get("MessageSid"),
    }

    logging.info(f"📩 INCOMING MESSAGE: {message}")

    # ------------------------------------------------------
    # STEP 1 – Customer Lookup
    # ------------------------------------------------------
    customer = None
    if message["from_phone"]:
        customer = find_customer_by_phone(message["from_phone"])

    # ------------------------------------------------------
    # STEP 2 – Unknown customer flow
    # ------------------------------------------------------
    if not customer:
        reply_text = (
            "Hola 👋\n"
            "Gracias por escribirnos.\n\n"
            "Aún no te tenemos registrado. "
            "En un momento alguien del equipo te contactará."
        )

        logging.info("🔵 Unknown customer flow")

        # Send reply immediately
        try:
            twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_FROM,
                to=message["from_raw"],
                body=reply_text
            )
        except Exception as e:
            logging.error(f"❌ Error sending WhatsApp reply: {e}")

        return PlainTextResponse("", status_code=200)

    # ------------------------------------------------------
    # STEP 3 – Known customer flow
    # ------------------------------------------------------

    customer_id = customer["customer_id"]  # Make sure your customers table has this
    greeting_name = customer.get("greeting") or message["profile_name"]

    logging.info("🟢 Known customer flow")

    # 🔹 Get conversation state
    state = get_conversation_state(customer_id)
    now = datetime.now(timezone.utc)
    last_message_time = get_last_message_time(conversation_id)

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

    local_hour = now.hour  # adjust if you use timezone offset
    if 5 <= local_hour < 12:
        time_of_day = "morning"
    elif 12 <= local_hour < 19:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"

    system_context = f"""
    You are a helpful assistant for distributors.
    
    Greeting rules:
    - greeting_type: {greeting_type}
    - time_of_day: {time_of_day}
    
    Instructions:
    - If greeting_type is "first_ever_message", greet warmly.
    - If "new_day", greet briefly.
    - If "reconnection", greet warmly and acknowledge time gap.
    - If "continuation", DO NOT greet.
    - Use appropriate Spanish greeting based on time_of_day:
        - morning → "Buenos días"
        - afternoon → "Buenas tardes"
        - evening → "Buenas noches"
    - Keep greetings short and natural.
    - Never repeat greeting inside same day continuation.
    """

    
    # 🔹 Analyze intent with ChatGPT
    intent_data = analyze_intent(
        message_text=message["body"],
        context=state["context"] if state else None
    )
    
    logging.info(f"🤖 Intent detected: {intent_data}")

    # 🔹 Save inbound message
    save_message(
        customer_id=customer_id,
        direction="inbound",
        body=message["body"],
        intent=intent_data.get("intent")
    )

    # 🔹 Handle intent (business logic)
    intent = intent_data.get("intent")        
    flow_config = get_ai_flow(intent)
    
    if not flow_config:
        system_reply = "No pude procesar tu solicitud."
    else:

        # Inject product catalog only if pricing related
        context_data = ""    
        if intent == "ask_prices":
            products = get_all_products()
            # Send compact product catalog
            context_data = json.dumps([
                {
                    "name": p["product"],
                    "sku": p.get("sku"),
                    "price": p["price"]
                }
                for p in products
            ])
    
        system_reply = generate_ai_response(
            system_prompt=flow_config["system_prompt"],
            user_message=message["body"],
            context_data=context_data
        )


    # 🔹 Compose final response (include greeting personalization)
    reply_text = system_reply 

    # 🔹 Update conversation state
    upsert_conversation_state(
        customer_id=customer_id,
        current_flow=intent_data.get("intent"),
        current_step=intent_data.get("next_action"),
        context=intent_data.get("entities", {})
    )

    # 🔹 Save outbound message
    save_message(
        customer_id=customer_id,
        direction="outbound",
        body=reply_text,
        intent=intent_data.get("intent")
    )

    # ------------------------------------------------------
    # Send WhatsApp response (ONLY ONCE)
    # ------------------------------------------------------
    try:
        twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=message["from_raw"],   # must include whatsapp:
            body=reply_text
        )
        logging.info("✅ WhatsApp reply sent")

    except Exception as e:
        logging.error(f"❌ Error sending WhatsApp reply: {e}")

    # ------------------------------------------------------
    # ACK Twilio FAST (prevents retries + ghost messages)
    # ------------------------------------------------------
    return PlainTextResponse("", status_code=200)
