from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse

app = FastAPI()

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    print("🔥 WEBHOOK HIT 🔥")

    form = await request.form()
    print("FORM DATA:", dict(form))

    incoming_msg = form.get("Body")

    response = MessagingResponse()
    response.message(f"👋 Hola! Recibí tu mensaje: {incoming_msg}")

    return PlainTextResponse(
        str(response),
        media_type="application/xml"
    )
