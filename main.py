from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    print("🔥 WEBHOOK HIT 🔥")

    form = await request.form()
    print("FORM DATA:", dict(form))

    response = MessagingResponse()
    response.message("Webhook received")

    return str(response)

