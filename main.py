from fastapi import FastAPI, Request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = FastAPI()

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    print("🔥 WEBHOOK HIT 🔥")

    form = await request.form()
    print("FORM DATA:", dict(form))

    incoming_msg = form.get("Body", "")

    twiml = MessagingResponse()
    twiml.message(f"👋 Hola Manuel, recibí: {incoming_msg}")

    return Response(
        content=str(twiml),
        media_type="application/xml"
    )
