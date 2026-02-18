import logging
import json
from promotions import calculate_promotions
from ai import extract_order_products_with_gpt
from db import (
    get_all_products,
    get_product_by_sku
)


from db import (
    get_active_draft_order,
    create_draft_order,
    upsert_draft_line,
    get_draft_order_lines,
    update_draft_order_totals,
    convert_draft_to_order,
    get_product_by_sku
)




def handle_place_order_intent(customer_id, message_text):
    logging.info("🟢 handle_place_order_intent")

    # -------------------------------------------------
    # 1️⃣ Get or create draft
    # -------------------------------------------------
    draft = get_active_draft_order(customer_id)

    if not draft:
        draft = create_draft_order(customer_id)

    draft_order_id = draft["draft_order_id"]

    # -------------------------------------------------
    # 2️⃣ Confirmation shortcut
    # -------------------------------------------------
    if message_text.lower().strip() in ["confirmar", "finalizar", "si", "sí"]:
        order_id = 123  # replace with convert_draft_to_order
        return f"✅ Pedido confirmado.\nNúmero de pedido: {order_id}"

    # -------------------------------------------------
    # 3️⃣ Load product catalog
    # -------------------------------------------------
    products = get_all_products()

    product_catalog = [
        {
            "sku": p["sku"],
            "name": p["product"]
        }
        for p in products
    ]

    # -------------------------------------------------
    # 4️⃣ Extract products using GPT
    # -------------------------------------------------
    extraction = extract_order_products_with_gpt(
        message_text=message_text,
        product_catalog=product_catalog
    )

    logging.info("🛒 GPT Extraction Result:")
    logging.info(json.dumps(extraction, indent=2, ensure_ascii=False))

    items = extraction.get("items", [])
    ambiguous_items = extraction.get("ambiguous_items", [])

    # -------------------------------------------------
    # 5️⃣ Handle ambiguous products
    # -------------------------------------------------
    if ambiguous_items:
        reply = "Necesito un poco más de información 👇\n\n"

        for product in ambiguous_items:
            reply += f"Para *{product['requested_text']}* tengo estas opciones:\n"
            for option in product["possible_matches"]:
                reply += f"- {option['name']} ({option['sku']})\n"
            reply += "\n"

        reply += "¿Cuál prefieres?"

        return reply

    # -------------------------------------------------
    # 6️⃣ No valid items
    # -------------------------------------------------
    if not items:
        logging.warning("⚠️ No valid items extracted.")
        return (
            "No encontré productos válidos en tu mensaje.\n"
            "Puedes escribir por ejemplo:\n"
            "2 AVY-ARG-SHP-250"
        )

    # -------------------------------------------------
    # 7️⃣ Add items to draft
    # -------------------------------------------------
    for item in items:
        sku = item.get("sku")
        quantity = item.get("quantity", 1)

        product = get_product_by_sku(sku)
        if not product:
            logging.warning(f"⚠️ SKU not found in DB: {sku}")
            continue

        upsert_draft_line(
            draft_order_id=draft_order_id,
            sku=sku,
            quantity=quantity
        )

    totals = price_draft_order_simple(draft_order_id)

    return format_cart_summary(draft_order_id, totals)



def price_draft_order_simple(draft_order_id):

    lines = get_draft_order_lines(draft_order_id)

    subtotal = 0

    for line in lines:
        line_total = line["quantity"] * float(line["unit_price"])
        subtotal += line_total

    total = subtotal

    update_draft_order_totals(draft_order_id)

    return {
        "subtotal": round(subtotal, 2),
        "total": round(total, 2)
    }

def format_cart_summary(draft_order_id, totals):

    lines = get_draft_order_lines(draft_order_id)

    message = "🛒 Tu pedido actual:\n\n"

    for line in lines:
        line_total = line["quantity"] * float(line["unit_price"])

        message += (
            f"{line['quantity']}x {line['sku']}  "
            f"${line_total:.2f}\n"
        )

    message += "\n"
    message += f"Subtotal: ${totals['subtotal']:.2f}\n"
    message += f"Total: ${totals['total']:.2f}\n\n"
    message += "Escribe 'confirmar' para finalizar o agrega más productos."

    return message







