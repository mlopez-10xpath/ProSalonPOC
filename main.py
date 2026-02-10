from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import logging
import os
from twilio.rest import Client
from pyairtable import Table
from supabase import create_client

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
# Supabase
# Database for 
# ==========================================================
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(url, key)


# ==========================================================
# SupaBase – Customer lookup 
# ==========================================================

def find_customer_by_phone(phone: str) -> dict | None:
    """
    Find a customer by phone number.
    Returns customer dict or None if not found.
    """
    logging.info(f"Supabase '{phone}' lookup ")
    response = (
        supabase
        .table("customers")
        .select("*")
        .eq("phone", phone)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


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
    # STEP 6 – Customer-aware logic
    # ------------------------------------------------------
    customer = None
    if message["from_phone"]:
        customer = find_customer_by_phone(message["from_phone"])

    # Decide response based on customer existence
    if customer:
        # Known customer
        customer_name = customer.get("greeting", message["profile_name"])

        reply_text = (
            f"Hola {customer_name} 👋\n"
            f"Gracias por escribirnos.\n\n"
            f"Recibimos tu mensaje:\n"
            f"“{message['body']}”"
        )

        logging.info("🟢 Known customer flow")

    else:
        # Unknown customer
        reply_text = (
            "Hola 👋\n"
            "Gracias por escribirnos.\n\n"
            "Aún no te tenemos registrado. "
            "En un momento alguien del equipo te contactará."
        )

        logging.info("🔵 Unknown customer flow")

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
