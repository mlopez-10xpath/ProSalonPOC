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
