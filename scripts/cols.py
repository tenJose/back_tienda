import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
res = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='usuarios'")).fetchall()
for r in res:
    print(r[0])
db.close()
