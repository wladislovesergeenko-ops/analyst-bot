from src.db.supabase import supabase

tables = [
    "wb_adv_fullstats_daily",
    "wb_adverts_nm_settings", 
    "wb_sales_funnel_products",
    "wb_unit_economics",
    # добавляй свои таблицы
]

for table_name in tables:
    try:
        response = supabase.table(table_name).select("*").limit(1).execute()
        if response.data:
            print(f"\n=== {table_name} ===")
            print(list(response.data[0].keys()))
    except Exception as e:
        print(f"\n=== {table_name} === ОШИБКА: {e}")