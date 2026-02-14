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
