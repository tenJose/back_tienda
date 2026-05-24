import sys
import os
sys.path.append(r'c:\Users\Jose Carlos\Documents\GitHub\tiendita_pos\back')

from sqlalchemy import create_engine, text
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)

with engine.connect() as conn:
    res = conn.execute(text("SELECT * FROM metodos_pago"))
    for row in res:
        print(row)
