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
    get_product_by_sku,
    cancel_draft_order,
    remove_draft_line_quantity
)

def detect_cart_operation(message_text: str) -> tuple[str, bool]:
    """
    Returns:
    - operation: "add" or "remove"
    - remove_all: True if user clearly wants all quantity removed
    """

    text = message_text.lower()

    remove_keywords = [
        "quita",
        "quitar",
        "elimina",
        "eliminar",
        "borra",
        "remueve",
        "saca",
    ]

    remove_all_keywords = [
        "todos",
        "todas",
        "todo el",
        "todo los",
    ]

    is_remove = any(word in text for word in remove_keywords)
    is_remove_all = any(word in text for word in remove_all_keywords)

    if is_remove:
        return "remove", is_remove_all

    return "add", False


def is_cart_query(message_text: str) -> bool:
    message_text = message_text.lower()

    triggers = [
        "que tengo",
        "qué tengo",
        "mi pedido",
        "ver pedido",
        "ver mi pedido",
        "mostrar pedido",
        "carrito",
        "pedido actual"
    ]

    return any(t in message_text for t in triggers)



def handle_place_order_intent(customer_id, message_text):
    """
    Called when user says something like:
    'quiero hacer un pedido'
    """

    logging.info("🟢 handle_place_order_intent")

    draft = get_active_draft_order(customer_id)

    if draft:
        return (
            "Ya tienes un pedido en proceso 🛒\n\n"
            "Puedes:\n"
            "- Agregar productos escribiendo el nombre o SKU\n"
            "- Ver tu pedido escribiendo 'ver pedido'\n"
            "- Confirmar con 'confirmar'\n"
            "- Cancelar con 'cancelar'"
        )

    create_draft_order(customer_id)

    return (
        "Perfecto 👍 Empecemos tu pedido.\n\n"
        "Puedes escribir el nombre del producto o el SKU.\n"
        "Ejemplo:\n"
        "2 AVY-ARG-SHP-250\n"
        "o tambien algo como\n"
        "2 Shampoo Ialurónico de 500 ml"
    )



# ==========================================================
# View Cart
# ==========================================================
def handle_view_cart(customer_id):
    logging.info("🟢 handle_view_cart")

    draft = get_active_draft_order(customer_id)

    if not draft:
        return "No tienes un pedido activo."

    draft_order_id = draft["draft_order_id"]

    totals = price_draft_order_simple(draft_order_id)

    return format_cart_summary(draft_order_id, totals)

# ==========================================================
# Price Draft Order Simple
# ==========================================================
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

# ==========================================================
# Cart Summary 
# ==========================================================
def format_cart_summary(draft_order_id, totals):

    lines = get_draft_order_lines(draft_order_id)

    message = "🛒 *Tu pedido actual:*\n\n"

    for line in lines:
        sku = line["sku"]
        quantity = line["quantity"]
        unit_price = float(line["unit_price"])
        line_total = quantity * unit_price

        product = get_product_by_sku(sku)
        product_name = product["product"] if product else sku

        message += (
            f"{quantity}x *{product_name}*\n"
            f"   ${unit_price:.2f} c/u  |  Total: ${line_total:.2f}\n\n"
        )

    message += "-----------------------------\n"
    message += f"Subtotal: ${totals['subtotal']:.2f}\n"
    message += f"Total: ${totals['total']:.2f}\n\n"
    message += "Escribe *confirmar* para finalizar o agrega más productos."

    return message

# ==========================================================
# Confirm Order --- NEEDS COMPLETITION
# ==========================================================
def handle_confirm_order(customer_id):
    logging.info("🟢 handle_confirm_order")

    draft = get_active_draft_order(customer_id)

    if not draft:
        return "No tienes un pedido activo para confirmar."

    draft_order_id = draft["draft_order_id"]

    # order_id = convert_draft_to_order(draft_order_id)
    order_id = 123

    return (
        f"✅ Pedido confirmado.\n"
        f"Número de pedido: {order_id}"
    )

# ==========================================================
# Draft Order Cancelation
# ==========================================================
def handle_cancel_order(customer_id):
    logging.info("🟢 handle_cancel_order")

    draft = get_active_draft_order(customer_id)

    if not draft:
        return "No tienes un pedido activo."

    cancelled = cancel_draft_order(draft["draft_order_id"])

    if not cancelled:
        return "Hubo un problema cancelando el pedido."

    return "🛑 Tu pedido fue cancelado."

# ==========================================================
# Add to Daft Order 
# ==========================================================
def handle_add_to_cart(customer_id, message_text):
    logging.info("🟢 handle_add_to_cart")

    draft = get_active_draft_order(customer_id)

    if not draft:
        draft = create_draft_order(customer_id)

    draft_order_id = draft["draft_order_id"]

    # Load product catalog
    products = get_all_products()

    product_catalog = [
        {
            "sku": p["sku"],
            "name": p["product"]
        }
        for p in products
    ]

    # GPT extraction
    extraction = extract_order_products_with_gpt(
        message_text=message_text,
        product_catalog=product_catalog
    )

    logging.info("🛒 GPT Extraction Result:")
    logging.info(json.dumps(extraction, indent=2, ensure_ascii=False))

    items = extraction.get("items", [])
    ambiguous_items = extraction.get("ambiguous_items", [])

    # Handle ambiguous
    if ambiguous_items:
        reply = "Necesito un poco más de información 👇\n\n"

        for product in ambiguous_items:
            reply += f"Para *{product['requested_text']}* tengo estas opciones:\n"
            for option in product["possible_matches"]:
                reply += f"- {option['name']} ({option['sku']})\n"
            reply += "\n"

        reply += "¿Cuál prefieres?"

        return reply

    if not items:
        return (
            "No encontré productos válidos en tu mensaje.\n"
            "Ejemplo:\n"
            "2 AVY-ARG-SHP-250"
        )

    # Add items
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


# ==========================================================
# Modify Draft Order
# ==========================================================
def handle_modify_cart(customer_id: str, message_text: str):
    logging.info("🟢 handle_modify_cart")

    draft = get_active_draft_order(customer_id)
    if not draft:
        return "No tienes un pedido activo."

    draft_order_id = draft["draft_order_id"]

    operation, remove_all_flag = detect_cart_operation(message_text)

    # Load products for GPT matching
    products = get_all_products()

    product_catalog = [
        {
            "sku": p["sku"],
            "name": p["product"]
        }
        for p in products
    ]

    extraction = extract_order_products_with_gpt(
        message_text=message_text,
        product_catalog=product_catalog
    )

    items = extraction.get("items", [])

    if not items:
        return "No encontré productos válidos para modificar."

    for item in items:
        sku = item.get("sku")
        quantity = item.get("quantity")

        if operation == "remove":
    
            # 🔥 If remove-all language OR no quantity detected → remove full line
            if remove_all_flag or not quantity:
                delete_draft_line(
                    draft_order_id=draft_order_id,
                    sku=sku
                )
            else:
                remove_draft_line_quantity(
                    draft_order_id=draft_order_id,
                    sku=sku,
                    quantity=quantity
                )
    
        else:
            upsert_draft_line(
                draft_order_id=draft_order_id,
                sku=sku,
                quantity=quantity or 1
            )


    update_draft_order_totals(draft_order_id)

    totals = price_draft_order_simple(draft_order_id)

    return format_cart_summary(draft_order_id, totals)
