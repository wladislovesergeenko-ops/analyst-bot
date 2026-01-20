import sys

from src.db.supabase import supabase

# Тест подключения
response = supabase.table("wb_margin_daily").select("*").limit(1).execute()
print(response.data)