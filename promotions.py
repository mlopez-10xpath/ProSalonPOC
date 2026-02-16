from typing import Dict, List


def calculate_promotions(order: dict, promotions: List[dict]) -> Dict[str, dict]:
    """
    Returns:
    {
        line_id: {
            "promotion_id": str,
            "discount_amount": float
        }
    }
    """

    best_discounts = {}

    for promo in promotions:
        promo_result = _evaluate_promotion(order, promo)

        for line_id, result in promo_result.items():

            current_best = best_discounts.get(line_id)

            if not current_best:
                best_discounts[line_id] = result
            else:
                if result["discount_amount"] > current_best["discount_amount"]:
                    best_discounts[line_id] = result

    return best_discounts


# ===============================
# Promotion Dispatcher
# ===============================

def _evaluate_promotion(order: dict, promo: dict) -> Dict[str, dict]:

    promo_type = promo["promotion_type"]

    if promo_type == "percentage":
        return _evaluate_percentage(order, promo)

    if promo_type == "buy_x_get_y":
        return _evaluate_buy_x_get_y(order, promo)

    if promo_type == "bundle":
        return _evaluate_bundle(order, promo)

    return {}

def _evaluate_percentage(order: dict, promo: dict) -> Dict[str, dict]:

    rules = promo["rules"]
    reward = promo["reward"]
    percent = reward["value"]

    discounts = {}

    for line in order["lines"]:

        if not _line_matches_scope(line, rules):
            continue

        subtotal = line["quantity"] * line["unit_price"]
        discount = round(subtotal * percent / 100, 2)

        if discount <= 0:
            continue

        discounts[line["line_id"]] = {
            "promotion_id": promo["promotion_id"],
            "discount_amount": discount
        }

    return discounts

def _line_matches_scope(line: dict, rules: dict) -> bool:

    scope = rules.get("scope")

    if scope == "line":
        return line["line_id_ref"] in rules.get("line_ids", [])

    if scope == "category":
        return line["category_id"] in rules.get("category_ids", [])

    if scope == "product":
        return line["sku"] in rules.get("product_skus", [])

    return False

def _evaluate_buy_x_get_y(order: dict, promo: dict) -> Dict[str, dict]:

    rules = promo["rules"]
    reward = promo["reward"]

    buy_qty = rules["buy_quantity"]
    reward_qty = rules["reward_quantity"]
    percent = reward["value"]

    eligible_units = []

    for line in order["lines"]:
        if line["sku"] in rules["product_skus"]:
            for _ in range(line["quantity"]):
                eligible_units.append({
                    "line_id": line["line_id"],
                    "unit_price": line["unit_price"]
                })

    total_required = buy_qty + reward_qty
    total_units = len(eligible_units)

    if total_units < total_required:
        return {}

    times_applicable = total_units // total_required
    total_reward_units = times_applicable * reward_qty

    eligible_units.sort(key=lambda x: x["unit_price"])

    discounted_units = eligible_units[:total_reward_units]

    discounts = {}

    for unit in discounted_units:
        discount_amount = round(unit["unit_price"] * percent / 100, 2)

        if unit["line_id"] not in discounts:
            discounts[unit["line_id"]] = {
                "promotion_id": promo["promotion_id"],
                "discount_amount": 0
            }

        discounts[unit["line_id"]]["discount_amount"] += discount_amount

    return discounts

def _evaluate_bundle(order: dict, promo: dict) -> Dict[str, dict]:

    rules = promo["rules"]
    reward = promo["reward"]
    percent = reward["value"]

    trigger_skus = rules["trigger_products"]
    reward_skus = rules["reward_products"]

    has_trigger = any(
        line["sku"] in trigger_skus
        for line in order["lines"]
    )

    if not has_trigger:
        return {}

    discounts = {}

    for line in order["lines"]:
        if line["sku"] in reward_skus:

            subtotal = line["quantity"] * line["unit_price"]
            discount = round(subtotal * percent / 100, 2)

            if discount <= 0:
                continue

            discounts[line["line_id"]] = {
                "promotion_id": promo["promotion_id"],
                "discount_amount": discount
            }

    return discounts
