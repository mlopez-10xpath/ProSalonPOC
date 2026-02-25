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
    remove_draft_line_quantity,
    delete_draft_line,
    get_products_by_ids,
    ger_active_promotions
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
        return (
            "No tienes un pedido activo actualmente\n."
            "Puedes escribir hacer pedido seguido \n"
            "del nombre del producto o el SKU.\n"
            "Ejemplo:\n"
            "hacer pedido 2 AVY-ARG-SHP-250\n"
            "o tambien algo como\n"
            "ordenar 2 Shampoo Ialurónico de 500 ml"
        )
        

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

    if not lines:
        return "🛒 Tu carrito está vacío."

    # ------------------------------------------------------
    # 🧠 1️⃣ Build enriched cart
    # ------------------------------------------------------
    cart_lines = get_cart_with_product_data(draft_order_id)

    # ------------------------------------------------------
    # 🧠 2️⃣ Load active promotions
    # ------------------------------------------------------
    promotions = get_active_promotions()  # you should already have this

    # ------------------------------------------------------
    # 🧠 3️⃣ Evaluate promotions
    # ------------------------------------------------------
    promotion_result = evaluate_promotions(cart_lines, promotions)

    total_discount = promotion_result.get("total_discount", 0.0)

    # ------------------------------------------------------
    # 🧮 4️⃣ Recalculate totals safely
    # ------------------------------------------------------
    subtotal = totals.get("subtotal", 0.0)
    final_total = subtotal - total_discount

    # Update totals dict (so nothing else breaks)
    totals["total_discount"] = total_discount
    totals["total"] = final_total
    totals["applied_promotions"] = promotion_result.get("applied", [])
    totals["upsell_suggestions"] = promotion_result.get("upsell", [])

    # ------------------------------------------------------
    # 🛒 5️⃣ Build message
    # ------------------------------------------------------
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
    message += f"Subtotal: ${subtotal:.2f}\n"

    # ------------------------------------------------------
    # 🎉 Promotions display
    # ------------------------------------------------------
    if totals["applied_promotions"]:
        message += "\n🎉 *Promociones aplicadas:*\n"
        for promo in totals["applied_promotions"]:
            message += f"• {promo['name']} (-${promo['discount']:.2f})\n"

        message += f"\nDescuento total: -${total_discount:.2f}\n"

    message += f"\n*Total: ${final_total:.2f}*\n"

    # ------------------------------------------------------
    # 💡 Upsell
    # ------------------------------------------------------
    if totals["upsell_suggestions"]:
        message += "\n💡 *Ofertas disponibles:*\n"
        for suggestion in totals["upsell_suggestions"]:
            message += f"• {suggestion['message']}\n"

    message += (
        "\nEscribe *confirmar* o *cancelar* para finalizar "
        "o agrega más productos."
    )

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

    cart_summary = format_cart_summary(draft_order_id, totals)

    return f"✅ Listo, ya se agregó a tu pedido.\n{cart_summary}"



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

    cart_summary = format_cart_summary(draft_order_id, totals)

    return f"✅ Listo, ya se modificó tu pedido.\n{cart_summary}"



def handle_cart_intent(customer_id: str, message_text: str):
    """
    Unified handler for:
    - place_order
    - add_to_cart
    """

    logging.info("🟢 handle_cart_intent")

    draft = get_active_draft_order(customer_id)

    # 🔹 Extract products from message
    products = get_all_products()
    product_catalog = [
        {"sku": p["sku"], "name": p["product"]}
        for p in products
    ]

    extraction = extract_order_products_with_gpt(
        message_text=message_text,
        product_catalog=product_catalog
    )

    items = extraction.get("items", [])

    has_products = len(items) > 0

    # =====================================================
    # SCENARIO 1: NO draft + NO products
    # =====================================================
    if not draft and not has_products:
        return (
            "No tienes un pedido activo actualmente.\n\n"
            "Puedes escribir algo como:\n"
            "hacer pedido 2 AVY-ARG-SHP-250\n"
            "o\n"
            "ordenar 2 Shampoo Ialurónico de 500 ml"
        )

    # =====================================================
    # SCENARIO 2: NO draft + YES products
    # =====================================================
    if not draft and has_products:

        draft = create_draft_order(customer_id)
        draft_order_id = draft["draft_order_id"]

        for item in items:
            upsert_draft_line(
                draft_order_id=draft_order_id,
                sku=item["sku"],
                quantity=item.get("quantity", 1)
            )

        update_draft_order_totals(draft_order_id)
        totals = price_draft_order_simple(draft_order_id)
        cart_summary = format_cart_summary(draft_order_id, totals)

        return f"✅ Listo, ya creé tu pedido.\n\n{cart_summary}"

    # =====================================================
    # SCENARIO 3: YES draft + NO products
    # =====================================================
    if draft and not has_products:
        return (
            "Ya tienes un pedido en proceso 🛒\n\n"
            "Puedes:\n"
            "- Agregar productos escribiendo el nombre o SKU\n"
            "- Ver tu pedido escribiendo 'ver pedido'\n"
            "- Confirmar con 'confirmar'\n"
            "- Cancelar con 'cancelar'"
        )

    # =====================================================
    # SCENARIO 4: YES draft + YES products
    # =====================================================
    if draft and has_products:

        draft_order_id = draft["draft_order_id"]

        for item in items:
            upsert_draft_line(
                draft_order_id=draft_order_id,
                sku=item["sku"],
                quantity=item.get("quantity", 1)
            )

        update_draft_order_totals(draft_order_id)
        totals = price_draft_order_simple(draft_order_id)
        cart_summary = format_cart_summary(draft_order_id, totals)

        return f"✅ Listo, ya se agregó a tu pedido.\n\n{cart_summary}"



# ==========================================================
# Get cart with product data
# ==========================================================

def get_cart_with_product_data(draft_order_id: str):
    """
    Returns enriched cart lines including product metadata
    needed for promotion evaluation.

    Output structure:
    [
        {
            "product_id": str,
            "sku": str,
            "name": str,
            "category_id": str,
            "line_id": str,
            "quantity": int,
            "unit_price": float,
            "line_subtotal": float
        }
    ]
    """

    # -----------------------------------------------------
    # 1️⃣ Fetch draft order lines
    # -----------------------------------------------------
    lines = get_draft_order_lines(draft_order_id)

    if not lines:
        return []

    # -----------------------------------------------------
    # 2️⃣ Fetch related product metadata in bulk
    # -----------------------------------------------------
    product_ids = list({line["product_id"] for line in lines})

    products = get_products_by_ids(product_ids)

    if not products:
        logging.warning(
            "No product metadata found for draft_order_id=%s",
            draft_order_id
        )
        return []

    product_map = {p["product_id"]: p for p in products}

    # -----------------------------------------------------
    # 3️⃣ Build enriched cart structure
    # -----------------------------------------------------
    enriched_cart = []

    for line in lines:
        product = product_map.get(line["product_id"])

        if not product:
            logging.warning(
                "Missing product metadata for product_id=%s",
                line["product_id"]
            )
            continue

        quantity = int(line["quantity"])
        unit_price = float(line["unit_price"])

        enriched_cart.append({
            "product_id": line["product_id"],
            "sku": line["sku"],
            "name": product.get("name"),
            "category_id": product.get("category_id"),
            "line_id": product.get("line_id"),
            "quantity": quantity,
            "unit_price": unit_price,
            "line_subtotal": quantity * unit_price
        })

    return enriched_cart




# ==========================================================
# Evaluate promotions
# ==========================================================

def evaluate_promotions(cart_lines: list, promotions: list):
    """
    Evaluates active promotions against enriched cart_lines.

    cart_lines structure:
    [
        {
            "product_id": str,
            "sku": str,
            "name": str,
            "category_id": str,
            "line_id": str,
            "quantity": int,
            "unit_price": float,
            "line_subtotal": float
        }
    ]

    Returns:
    {
        "applied": [ ... ],
        "upsell": [ ... ],
        "total_discount": float
    }
    """

    applied = []
    upsell = []
    total_discount = 0.0

    if not cart_lines:
        return {
            "applied": [],
            "upsell": [],
            "total_discount": 0.0
        }

    # Sort by priority (higher first)
    promotions_sorted = sorted(
        promotions,
        key=lambda x: x.get("priority_weight", 0),
        reverse=True
    )

    for promo in promotions_sorted:

        if not promo.get("is_active"):
            continue

        try:
            rules = json.loads(promo.get("rules", "{}"))
            reward = json.loads(promo.get("reward", "{}"))
        except Exception:
            continue  # skip malformed promotions safely

        promo_name = promo.get("name")

        # =====================================================
        # 1️⃣ CATEGORY OR LINE PERCENTAGE PROMOTIONS
        # =====================================================
        if rules.get("scope") in ["category", "line"]:

            scope_key = "category_id" if rules["scope"] == "category" else "line_id"
            eligible_ids = rules.get("category_ids") or rules.get("line_ids") or []

            matching_lines = [
                line for line in cart_lines
                if line.get(scope_key) in eligible_ids
            ]

            if matching_lines:

                subtotal = sum(line["line_subtotal"] for line in matching_lines)

                if reward.get("type") == "percentage":
                    discount = subtotal * (reward.get("value", 0) / 100)

                    # Optional discount cap
                    cap = promo.get("max_discount_cap")
                    if cap:
                        discount = min(discount, float(cap))

                    total_discount += discount

                    applied.append({
                        "promotion_id": promo.get("promotion_id"),
                        "name": promo_name,
                        "discount": round(discount, 2)
                    })

            else:
                # Basic upsell suggestion
                upsell.append({
                    "promotion_id": promo.get("promotion_id"),
                    "message": f"Agrega productos incluidos en '{promo_name}' y obtén {reward.get('value')}% de descuento."
                })

        # =====================================================
        # 2️⃣ BUY X GET Y (BROCHAS TYPE)
        # =====================================================
        if rules.get("scope") == "product_group":

            eligible_skus = rules.get("product_skus", [])
            buy_qty = rules.get("buy_quantity", 0)
            reward_qty = rules.get("reward_quantity", 0)

            matching_lines = [
                line for line in cart_lines
                if line["sku"] in eligible_skus
            ]

            total_qty = sum(line["quantity"] for line in matching_lines)

            if total_qty >= buy_qty + reward_qty and reward.get("type") == "percentage":

                # Apply discount to cheapest eligible items
                expanded_units = []

                for line in matching_lines:
                    for _ in range(line["quantity"]):
                        expanded_units.append(line["unit_price"])

                expanded_units.sort()  # cheapest first

                eligible_rewards = total_qty // (buy_qty + reward_qty)

                discount = 0.0
                for i in range(min(eligible_rewards * reward_qty, len(expanded_units))):
                    discount += expanded_units[i] * (reward.get("value", 0) / 100)

                total_discount += discount

                applied.append({
                    "promotion_id": promo.get("promotion_id"),
                    "name": promo_name,
                    "discount": round(discount, 2)
                })

            else:
                missing = buy_qty - total_qty
                if missing > 0:
                    upsell.append({
                        "promotion_id": promo.get("promotion_id"),
                        "message": f"Agrega {missing} producto(s) más para activar '{promo_name}'."
                    })
                elif total_qty >= buy_qty and total_qty < buy_qty + reward_qty:
                    upsell.append({
                        "promotion_id": promo.get("promotion_id"),
                        "message": f"Agrega {reward_qty} producto adicional para obtener el beneficio de '{promo_name}'."
                    })

        # =====================================================
        # 3️⃣ TRIGGER + REWARD (ARGÁN TYPE)
        # =====================================================
        if rules.get("trigger_products"):

            trigger_products = rules.get("trigger_products", [])
            reward_products = rules.get("reward_products", [])

            has_trigger = any(
                line["sku"] in trigger_products
                for line in cart_lines
            )

            reward_lines = [
                line for line in cart_lines
                if line["sku"] in reward_products
            ]

            if has_trigger and reward_lines and reward.get("type") == "percentage":

                discount = sum(
                    line["line_subtotal"] * (reward.get("value", 0) / 100)
                    for line in reward_lines
                )

                total_discount += discount

                applied.append({
                    "promotion_id": promo.get("promotion_id"),
                    "name": promo_name,
                    "discount": round(discount, 2)
                })

            elif has_trigger and not reward_lines:
                upsell.append({
                    "promotion_id": promo.get("promotion_id"),
                    "message": f"Agrega el producto complementario y obtén {reward.get('value')}% de descuento en '{promo_name}'."
                })

    return {
        "applied": applied,
        "upsell": upsell,
        "total_discount": round(total_discount, 2)
    }

