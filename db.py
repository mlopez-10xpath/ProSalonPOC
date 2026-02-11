import logging
import os


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





def get_product_by_name_or_sku(search_term: str):
    response = (
        supabase
        .table("product")
        .select("*")
        .or_(f"name.ilike.%{search_term}%,sku.ilike.%{search_term}%")
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None
