
from db import get_product_by_name_or_sku

def handle_intent(intent_data: dict, state: dict | None) -> str:
    intent = intent_data["intent"]
    entities = intent_data.get("entities", {})

    if intent == "greeting":
        return "Hi! 👋 How can I help you today?"

    if intent == "ask_prices":
        
        product_name = entities.get("product_name")

        if not product_name:
            return "Claro 😊 ¿De qué producto necesitas el precio?"

        product = get_product_by_name(product_name)

        if not product:
            return (
                f"No encontré el producto '{product_name}'. "
                "¿Podrías confirmar el nombre?"
            )

        price = product.get("price")

        return (
            f"El precio de *{product['name']}* es "
            f"${price}."
        )
    if intent == "ask_promotions":
        return "We currently have promotions on selected products. Which category are you interested in?"

    if intent == "place_order":
        products = entities.get("products", [])

        if not products:
            return "I can help with that. What products and quantities would you like to order?"

        return "Got it! Let me confirm availability and place your order."

    if intent == "track_order":
        order_id = entities.get("order_id")

        if not order_id:
            return "Sure. Can you share the order number you want to track?"

        return f"Checking the status of order {order_id} for you now."

    return "Sorry, I didn’t quite get that. Could you please clarify?"
