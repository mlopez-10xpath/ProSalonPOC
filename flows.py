from db import get_all_products
from utils import normalize_text
from difflib import SequenceMatcher

# ==========================================================
# Fuzzy similarity helper
# ==========================================================
def similarity(a: str, b: str) -> float:
    """
    Returns similarity score between 0 and 1.
    """
    return SequenceMatcher(None, a, b).ratio()


def handle_intent(intent_data: dict, state: dict | None) -> str:
    intent = intent_data["intent"]
    entities = intent_data.get("entities", {})

    if intent == "greeting":
        return "Hi! 👋 How can I help you today?"

    if intent == "ask_prices":

        product_name = entities.get("product_name")

        if not product_name:
            return "Claro 😊 ¿De qué producto necesitas el precio?"

        # ------------------------------------------------------
        # STEP 1 – Normalize user input
        # ------------------------------------------------------
        normalized_input = normalize_text(product_name)

        # ------------------------------------------------------
        # STEP 2 – Fetch product catalog
        # ------------------------------------------------------
        products = get_all_products()

        matches = []

        # ------------------------------------------------------
        # STEP 3 – Intelligent matching
        # - Accent insensitive
        # - Partial match
        # - Fuzzy match
        # ------------------------------------------------------
        for product in products:

            db_name = product.get("product", "")
            normalized_db_name = normalize_text(db_name)

            # Direct containment match
            if normalized_input in normalized_db_name:
                matches.append(product)
                continue

            # Fuzzy similarity match
            score = similarity(normalized_input, normalized_db_name)

            if score > 0.75:  # You can tune this threshold
                matches.append(product)

        # ------------------------------------------------------
        # STEP 4 – No matches
        # ------------------------------------------------------
        if not matches:
            return (
                f"No encontré el producto '{product_name}'. "
                "¿Podrías confirmar el nombre?"
            )

        # ------------------------------------------------------
        # STEP 5 – Single match
        # ------------------------------------------------------
        if len(matches) == 1:
            product = matches[0]

            return (
                f"El precio de *{product['product']}* es "
                f"${product['price']} MXN 💰\n\n"
                "¿Te gustaría agregarlo a tu pedido?"
            )

        # ------------------------------------------------------
        # STEP 6 – Multiple presentations
        # Example:
        # Shampoo Avyna 250ml
        # Shampoo Avyna 500ml
        # Shampoo Avyna 1L
        # ------------------------------------------------------
        response_lines = ["Encontré varias presentaciones:\n"]

        for product in matches:
            response_lines.append(
                f"• *{product['product']}* — ${product['price']} MXN"
            )

        response_lines.append("\n¿Cuál presentación te interesa?")

        return "\n".join(response_lines)

        
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
