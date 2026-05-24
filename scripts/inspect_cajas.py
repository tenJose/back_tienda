import sys
import os
sys.path.append(r'c:\Users\Jose Carlos\Documents\GitHub\tiendita_pos\back')

from sqlalchemy import create_engine, text
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    print("Columns in cajas:")
    try:
        for col in conn.execute(text("SELECT * FROM cajas LIMIT 0")).keys():
            print("  ", col)
    except Exception as e:
        print("  Error:", e)

    print("\nColumns in cortes_caja:")
    try:
        for col in conn.execute(text("SELECT * FROM cortes_caja LIMIT 0")).keys():
            print("  ", col)
    except Exception as e:
        print("  Error:", e)

    print("\nSample ventas rows:")
    try:
        res = conn.execute(text("SELECT id, folio, total, estado, created_at FROM ventas LIMIT 5"))
        for row in res:
            print("  ", row)
    except Exception as e:
        print("  Error:", e)
