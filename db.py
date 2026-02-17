import logging
import os
from supabase import create_client
from datetime import datetime, timezone, timedelta, date
from typing import List, Dict


# ==========================================================
# Supabase
# Database for 
# ==========================================================
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(url, key)


# ==========================================================
# SupaBase – Customer lookup 
# ==========================================================

def find_customer_by_phone(phone: str) -> dict | None:
    """
    Find a customer by phone number.
    Returns customer dict or None if not found.
    """
    logging.info(f"Supabase '{phone}' lookup ")
    response = (
        supabase
        .table("customers")
        .select("*")
        .eq("phone", phone)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]

# ==========================================================
# SupaBase – Save Message in database log
# ==========================================================

def save_message(customer_id: str, direction: str, body: str, intent: str | None = None):
    try:
        response = supabase.table("messages").insert({
            "customer_id": customer_id,
            "direction": direction,
            "body": body,
            "intent": intent
        }).execute()

        return response.data

    except Exception as e:
        logging.exception("Error saving message")
        return None


# ==========================================================
# SupaBase – get Conversation State Stored in the Conversation Log 
# ==========================================================
def get_conversation_state(customer_id: str):
    try:
        response = (
            supabase
            .table("conversation_state")
            .select("*")
            .eq("customer_id", customer_id)
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0]

        return None

    except Exception as e:
        logging.exception("Error fetching conversation state")
        return None


# ==========================================================
# SupaBase – Insert Conversation State
# ==========================================================
def upsert_conversation_state(
    customer_id: str,
    current_flow: str | None = None,
    current_step: str | None = None,
    context: dict | None = None
):
    try:
        response = (
            supabase
            .table("conversation_state")
            .upsert({
                "customer_id": customer_id,
                "current_flow": current_flow,
                "current_step": current_step,
                "context": context or {},
            })
            .execute()
        )

        return response.data

    except Exception as e:
        logging.exception("Error updating conversation state")
        return None


# ==========================================================
# SupaBase – Lookup Product by SKU or Name
# ==========================================================

def get_product_by_name_or_sku(search_term: str):
    response = (
        supabase
        .table("products")
        .select("*")
        .or_(f"product.ilike.%{search_term}%,sku.ilike.%{search_term}%")
        .limit(100)
        .execute()
    )

    return response.data[0] if response.data else None

# ==========================================================
# SupaBase – Strict SKU Lookup
# ==========================================================

def get_product_by_sku(sku: str):
    response = (
        supabase
        .table("products")
        .select("*")
        .eq("sku", sku)
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None




# ==========================================================
# SupaBase – Fetch All Products (for intelligent matching)
# ==========================================================
def get_all_products(limit: int = 500):
    """
    Fetch a batch of products for fuzzy matching.
    Increase limit if your catalog grows.
    """
    try:
        response = (
            supabase
            .table("products")
            .select("*")
            .limit(limit)
            .execute()
        )

        return response.data or []

    except Exception:
        logging.exception("Error fetching products")
        return []

# ==========================================================
# Fetch AI Flow Configuration
# ==========================================================
def get_ai_flow(intent: str):
    try:
        response = (
            supabase
            .table("ai_flows")
            .select("*")
            .eq("intent", intent)
            .eq("active", True)
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0]

        return None

    except Exception:
        logging.exception("Error fetching AI flow config")
        return None
        
# ==========================================================
# Get last message time for a customer
# ==========================================================
from datetime import datetime

def get_last_message_time(customer_id: str):
    response = (
        supabase
        .table("messages")
        .select("created_at")
        .eq("customer_id", customer_id)
        .eq("direction", "inbound")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if response.data and len(response.data) > 0:
        created_at_str = response.data[0]["created_at"]

        return datetime.fromisoformat(
            created_at_str.replace("Z", "+00:00")
        )

    return None

# ==========================================================
# Get active promotions
# ==========================================================
def get_active_promotions() -> List[Dict]:
    today = date.today().isoformat()

    response = (
        supabase
        .table("promotions")
        .select("*")
        .eq("is_active", True)
        .or_(f"start_date.is.null,start_date.lte.{today}")
        .or_(f"end_date.is.null,end_date.gte.{today}")
        .execute()
    )

    if response.data and len(response.data) > 0:
        return response.data

    return []
# ==========================================================
# Get detail product info
# ==========================================================
def get_detailed_products():
    products = get_all_products()

    return [
        {
            "name": p["product"],
            "sku": p.get("sku"),
            "line": p.get("line"),
            "category": p.get("category"),
            "description": p.get("description"),
            "size": p.get("size"),
            "price": p.get("price")
        }
        for p in products
    ]

# ==========================================================
# Draft Order Management
# ==========================================================
def get_active_draft_order(customer_id: str):
    response = (
        supabase.table("draft_orders")
        .select("*")
        .eq("customer_id", customer_id)
        .eq("status", "open")
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]
    return None


def create_draft_order(customer_id: str, currency: str = "USD"):
    response = (
        supabase.table("draft_orders")
        .insert({
            "customer_id": customer_id,
            "status": "open",
            "subtotal": 0,
            "discount_total": 0,
            "final_total": 0,
            "currency": currency
        })
        .execute()
    )

    return response.data[0]

def get_draft_order_lines(draft_order_id: str):
    response = (
        supabase.table("draft_order_lines")
        .select("*")
        .eq("draft_order_id", draft_order_id)
        .execute()
    )

    return response.data or []


from datetime import datetime

def upsert_draft_line(draft_order_id: str, sku: str, quantity: int):
    # 1️⃣ Get product info
    product_resp = (
        supabase.table("products")
        .select("product_id, sku, price")
        .eq("sku", sku)
        .limit(1)
        .execute()
    )

    if not product_resp.data:
        raise Exception(f"Product with SKU {sku} not found")

    product = product_resp.data[0]
    unit_price = float(product["price"])
    line_subtotal = unit_price * quantity

    # 2️⃣ Check if line exists
    line_resp = (
        supabase.table("draft_order_lines")
        .select("*")
        .eq("draft_order_id", draft_order_id)
        .eq("sku", sku)
        .limit(1)
        .execute()
    )

    now = datetime.utcnow().isoformat()

    if line_resp.data:
        # Update existing line
        existing_line = line_resp.data[0]
        new_quantity = existing_line["quantity"] + quantity
        new_subtotal = unit_price * new_quantity

        update_resp = (
            supabase.table("draft_order_lines")
            .update({
                "quantity": new_quantity,
                "line_subtotal": new_subtotal,
                "final_line_total": new_subtotal,
                "updated_at": now
            })
            .eq("draft_order_line_id", existing_line["draft_order_line_id"])
            .execute()
        )

        return update_resp.data[0]

    else:
        # Insert new line
        insert_resp = (
            supabase.table("draft_order_lines")
            .insert({
                "draft_order_id": draft_order_id,
                "product_id": product["product_id"],
                "sku": sku,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_subtotal": line_subtotal,
                "applied_promotion_id": None,
                "discount_amount": 0,
                "final_line_total": line_subtotal,
                "created_at": now,
                "updated_at": now
            })
            .execute()
        )

        return insert_resp.data[0]


def update_draft_order_totals(draft_order_id: str):
    lines = get_draft_order_lines(draft_order_id)

    subtotal = sum(float(line["line_subtotal"]) for line in lines)
    discount_total = sum(float(line["discount_amount"]) for line in lines)
    final_total = sum(float(line["final_line_total"]) for line in lines)

    response = (
        supabase.table("draft_orders")
        .update({
            "subtotal": subtotal,
            "discount_total": discount_total,
            "final_total": final_total,
            "updated_at": datetime.utcnow().isoformat()
        })
        .eq("draft_order_id", draft_order_id)
        .execute()
    )

    return response.data[0]


def convert_draft_to_order(draft_order_id: str):
    # Get draft
    draft_resp = (
        supabase.table("draft_orders")
        .select("*")
        .eq("draft_order_id", draft_order_id)
        .single()
        .execute()
    )

    draft = draft_resp.data

    # Create order header
    order_resp = (
        supabase.table("orders")
        .insert({
            "customer_id": draft["customer_id"],
            "subtotal": draft["subtotal"],
            "discount_total": draft["discount_total"],
            "final_total": draft["final_total"],
            "currency": draft["currency"],
            "status": "confirmed"
        })
        .execute()
    )

    order = order_resp.data[0]

    # Get draft lines
    lines = get_draft_order_lines(draft_order_id)

    # Insert order lines
    for line in lines:
        supabase.table("order_lines").insert({
            "order_id": order["order_id"],
            "product_id": line["product_id"],
            "sku": line["sku"],
            "quantity": line["quantity"],
            "unit_price": line["unit_price"],
            "discount_amount": line["discount_amount"],
            "final_line_total": line["final_line_total"]
        }).execute()

    # Close draft
    supabase.table("draft_orders").update({
        "status": "converted",
        "updated_at": datetime.utcnow().isoformat()
    }).eq("draft_order_id", draft_order_id).execute()

    return order
