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
    get_all_products,
    get_detailed_products,
    get_active_promotions,
    get_recent_conversation_history,
    get_pending_customer_message,
    clear_pending_customer_message
)
from orders import (
    handle_place_order_intent,
    handle_add_to_cart,
    handle_view_cart,
    handle_modify_cart,
    handle_confirm_order,
    handle_cancel_order,
    handle_cart_intent
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
    if customer and customer.get("timezone"):
        customer_timezone = customer["timezone"]
    else:
        customer_timezone = "America/Mexico_City"
    last_message_time = get_last_message_time(customer_id)

    logging.info("🟢 Known customer flow")

    # 🔹 Get conversation state
    state = get_conversation_state(customer_id)

    # 🔹 Get recent history (last 5 interactions)
    conversation_history = get_recent_conversation_history(customer_id)

    # ------------------------------------------------------
    # STEP 3A – Deliver Pending Customer Message (if any)
    # ------------------------------------------------------
    
    pending_message = get_pending_customer_message(customer_id)
    
    if pending_message:
        logging.info("📨 Delivering pending customer message")
    
        # Clear it immediately so it is only sent once
        clear_pending_customer_message(customer_id)
    
    # 🔹 Analyze intent with ChatGPT
    intent_data = analyze_intent(
        message_text=message["body"],
        context=state["context"] if state else None,
        history=conversation_history
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
    

    # ======================================================
    # 🧠 DETERMINISTIC ENGINE (Cart & Order Management)
    # ======================================================

    deterministic_intents = {
        "place_order": handle_cart_intent,
        "add_to_cart": handle_cart_intent,
        "view_cart": handle_view_cart,
        "modify_cart": handle_modify_cart,
        "confirm_order": handle_confirm_order,
        "cancel_order": handle_cancel_order,
    }

    if intent in deterministic_intents:

        handler = deterministic_intents[intent]

        # Some handlers require message_text, some don't
        if intent in ["add_to_cart", "modify_cart", "place_order"]:
            reply_text = handler(customer_id, message["body"])
        else:
            reply_text = handler(customer_id)

        if pending_message:
            reply_text = f"{pending_message}\n\n{reply_text}"
        
        # Update state
        upsert_conversation_state(
            customer_id=customer_id,
            current_flow=intent,
            current_step=None,
            context=intent_data.get("entities", {})
        )

        # Save outbound message
        save_message(
            customer_id=customer_id,
            direction="outbound",
            body=reply_text,
            intent=intent
        )

        # Send WhatsApp message
        try:
            twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_FROM,
                to=message["from_raw"],
                body=reply_text
            )
            logging.info("✅ Deterministic reply sent")

        except Exception as e:
            logging.error(f"❌ Error sending WhatsApp reply: {e}")

        return PlainTextResponse("", status_code=200)


    
    flow_config = get_ai_flow(intent)
    if not flow_config:
        system_reply = "No pude procesar tu solicitud."
    else:

        # Inject product catalog only if pricing related
        context_data = ""

        # ==============================
        # PRICING INTENT
        # ==============================
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

        # ==============================
        # PROMOTIONS INTENT
        # ==============================
        elif intent == "ask_promotions":
            promotions = get_active_promotions()

            context_data = json.dumps({
                "active_promotions": promotions
            })
    
        # ==============================
        # PRODUCT INFORMATION INTENT
        # ==============================
        elif intent == "product_info":
            detailed_products = get_detailed_products()
    
            context_data = json.dumps({
                "products": detailed_products
            })
    
        # ==============================
        # GENERATE RESPONSE
        # ==============================
    
        system_reply = generate_ai_response(
            base_system_prompt=flow_config["system_prompt"],
            user_message=message["body"],
            context_data=context_data,
            customer_timezone=customer_timezone,
            last_message_time=last_message_time,
            distributor_name=greeting_name
        )

    # 🔹 Compose final response (include greeting personalization)
    reply_text = system_reply 

    if pending_message:
        reply_text = f"{pending_message}\n\n{reply_text}"

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
