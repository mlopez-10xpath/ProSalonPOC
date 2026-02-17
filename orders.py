from promotions import calculate_promotions


def price_draft_order(draft_order_id: str):

    draft_order = load_draft_order(draft_order_id)
    draft_lines = load_draft_order_lines(draft_order_id)
    promotions = load_active_promotions()

    order_dict = build_order_dict(draft_order, draft_lines)

    discounts = calculate_promotions(order_dict, promotions)

    apply_discounts_to_lines(draft_lines, discounts)

    totals = recalculate_totals(draft_lines)

    update_draft_lines(draft_lines)
    update_draft_order_totals(draft_order_id, totals)

    return totals



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
