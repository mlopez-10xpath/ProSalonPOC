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

    draft = get_active_draft_order(customer_id)

    if not draft:
        draft = create_draft_order(customer_id)

    draft_order_id = draft["draft_order_id"]

    # Extract items from GPT entities
    items = intent_data.get("entities", {}).get("items", [])

    # If user confirms
    if message_text.lower() in ["confirmar", "finalizar", "si", "sí"]:
        order_id = convert_draft_to_order(draft_order_id)
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


def price_draft_order(conn, draft_order_id: str):

    try:
        conn.autocommit = False

        draft_order = load_draft_order(conn, draft_order_id)
        draft_lines = load_draft_order_lines(conn, draft_order_id)
        promotions = load_active_promotions(conn)

        order_dict = build_order_dict(draft_order, draft_lines)

        discounts = calculate_promotions(order_dict, promotions)

        apply_discounts_to_lines(draft_lines, discounts)

        totals = recalculate_totals(draft_lines)

        update_draft_lines(conn, draft_lines)
        update_draft_order_totals(conn, draft_order_id, totals)

        conn.commit()

        return totals

    except Exception as e:
        conn.rollback()
        raise e




def build_order_dict(draft_order, draft_lines):

    return {
        "draft_order_id": draft_order["draft_order_id"],
        "lines": [
            {
                "line_id": line["draft_order_line_id"],
                "sku": line["sku"],
                "product_id": line["product_id"],
                "category_id": line["category_id"],
                "line_id_ref": line["line_id_ref"],
                "quantity": line["quantity"],
                "unit_price": float(line["unit_price"]),
            }
            for line in draft_lines
        ]
    }


def apply_discounts_to_lines(draft_lines, discounts):

    for line in draft_lines:

        discount_data = discounts.get(line["draft_order_line_id"])

        if discount_data:
            line["discount_amount"] = discount_data["discount_amount"]
            line["applied_promotion_id"] = discount_data["promotion_id"]
        else:
            line["discount_amount"] = 0
            line["applied_promotion_id"] = None


def recalculate_totals(draft_lines):

    subtotal = 0
    discount_total = 0

    for line in draft_lines:

        line_subtotal = line["quantity"] * float(line["unit_price"])
        discount = float(line.get("discount_amount", 0))

        line["line_subtotal"] = round(line_subtotal, 2)
        line["final_line_total"] = round(line_subtotal - discount, 2)

        subtotal += line_subtotal
        discount_total += discount

    final_total = subtotal - discount_total

    return {
        "subtotal": round(subtotal, 2),
        "discount_total": round(discount_total, 2),
        "final_total": round(final_total, 2)
    }




def update_draft_lines(conn, draft_lines):

    with conn.cursor() as cur:

        for line in draft_lines:
            cur.execute("""
                UPDATE draft_order_lines
                SET
                    discount_amount = %s,
                    applied_promotion_id = %s,
                    line_subtotal = %s,
                    final_line_total = %s,
                    updated_at = NOW()
                WHERE draft_order_line_id = %s
            """, (
                line["discount_amount"],
                line["applied_promotion_id"],
                line["line_subtotal"],
                line["final_line_total"],
                line["draft_order_line_id"]
            ))



def update_draft_order_totals(conn, draft_order_id, totals):

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE draft_orders
            SET
                subtotal = %s,
                discount_total = %s,
                final_total = %s,
                status = 'priced',
                updated_at = NOW()
            WHERE draft_order_id = %s
        """, (
            totals["subtotal"],
            totals["discount_total"],
            totals["final_total"],
            draft_order_id
        ))



