import logging
import os
from supabase import create_client

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

