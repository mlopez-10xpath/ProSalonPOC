from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import logging
import os
from twilio.rest import Client

# ------------------
# App & logging
# ------------------
app = FastAPI()
logging.basicConfig(level=logging.INFO)

# ------------------
# Twilio client
# ------------------
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = os.environ["TWILIO_WHATSAPP_FROM"]  # e.g. whatsapp:+14155238886

twilio_client = Client(
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN
)

# ------------------
# Webhook
# ------------------
@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()

    message = {
        "from_phone": form.get("WaId"),              # e.g. 5213314179343
        "from_raw": form.get("From"),                # e.g. whatsapp:+5213314179343
        "profile_name": form.get("ProfileName"),     # WhatsApp profile name
        "body": form.get("Body", "").strip(),        # message text
        "message_sid": form.get("MessageSid"),
    }

    logging.info(f"📩 INCOMING MESSAGE: {message}")

    # ------------------
    # TEMP response logic (Step 2 complete)
    # ------------------
    reply_text = f"Hola {message['profile_name']} 👋\nRecibí tu mensaje: \"{message['body']}\""

    try:
        twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=message["from_raw"],   # MUST include whatsapp:
            body=reply_text
        )
        logging.info("✅ WhatsApp reply sent")

    except Exception as e:
        logging.error(f"❌ Error sending WhatsApp reply: {e}")

    # ------------------
    # ACK fast (CRITICAL for Twilio)
    # ------------------
    return PlainTextResponse("OK", status_code=200)
