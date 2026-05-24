import sys
import os
sys.path.append(r'c:\Users\Jose Carlos\Documents\GitHub\tiendita_pos\back')

from sqlalchemy import create_engine, inspect
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)
inspector = inspect(engine)

for table in ["lotes_producto", "compras", "proveedores", "negocio_configuracion"]:
    print(f"\nColumns in {table}:")
    for col in inspector.get_columns(table):
        print(f"  {col['name']}: {col['type']}")
