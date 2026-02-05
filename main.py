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
    form = await request.form()
    
    incoming_msg = form.get("Body")
    from_number = form.get("From")

    print("Message:", incoming_msg)
    print("From:", from_number)

    response = MessagingResponse()
    response.message(f"👋 Hola! Recibí tu mensaje: {incoming_msg}")

    return str(response)
