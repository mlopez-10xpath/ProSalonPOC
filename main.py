from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()

    message = {
        "from_phone": form.get("WaId"),  # clean phone, no whatsapp:
        "from_raw": form.get("From"),
        "profile_name": form.get("ProfileName"),
        "body": form.get("Body", "").strip(),
        "message_sid": form.get("MessageSid"),
    }

    logging.info(f"📩 INCOMING MESSAGE: {message}")

    # ACK fast (important!)
    return PlainTextResponse("OK", status_code=200)
