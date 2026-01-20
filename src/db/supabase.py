# src/db/supabase.py

from supabase import create_client
from src.config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_view(view_name: str, filters: dict = None) -> list:
    """Получить данные из view."""
    query = supabase.table(view_name).select("*")
    
    if filters:
        for column, value in filters.items():
            query = query.eq(column, value)
    
    response = query.execute()
    return response.data