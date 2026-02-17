import logging
from promotions import calculate_promotions

from db import (
    get_active_draft_order,
    create_draft_order,
    upsert_draft_line,
    get_draft_order_lines,
    update_draft_order_totals,
    convert_draft_to_order,
    get_product_by_sku
)


def handle_place_order_intent(customer_id, message_text, intent_data):
    logging.info("🟢 handle place_order intent")
    draft = get_active_draft_order(customer_id)

    if not draft:
        draft = create_draft_order(customer_id)

    draft_order_id = draft["draft_order_id"]

    # Extract items from GPT entities
    items = intent_data.get("entities", {}).get("products", [])

    if not items:
        logging.warning("⚠️ No items extracted from GPT.")
    else:
        logging.info("🛒 %s item(s) extracted", len(items))
        logging.info(json.dumps(items, indent=2, ensure_ascii=False))
    
    # If user confirms
    if message_text.lower() in ["confirmar", "finalizar", "si", "sí"]:
        # order_id = convert_draft_to_order(draft_order_id)
        order_id = 123
        return f"✅ Pedido confirmado.\nNúmero de pedido: {order_id}"

    # Add items
    if items:
        for item in items:
            sku = item.get("sku")
            quantity = item.get("quantity", 1)

            product = get_product_by_sku(sku)
            if not product:
                continue

            upsert_draft_line(
                draft_order_id=draft_order_id,
                sku=sku,
                quantity=quantity,
                unit_price=product["price"]
            )

        totals = price_draft_order_simple(draft_order_id)

        return format_cart_summary(draft_order_id, totals)

    return "¿Qué productos deseas agregar? Puedes escribir por ejemplo:\n2 AVY-ARG-SHP-250"


def price_draft_order_simple(draft_order_id):

    lines = get_draft_order_lines(draft_order_id)

    subtotal = 0

    for line in lines:
        line_total = line["quantity"] * float(line["unit_price"])
        subtotal += line_total

    total = subtotal

    update_draft_order_totals(
        draft_order_id=draft_order_id,
        subtotal=subtotal,
        total=total
    )

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







