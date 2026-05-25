import sys
import os

# Append the current directory so app can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from sqlalchemy import text

def run_seed():
    db = SessionLocal()
    try:
        with open('seed_catalogos.sql', 'r', encoding='utf-8') as f:
            sql = f.read()
            
        print("Executing seed_catalogos.sql...")
        db.execute(text(sql))
        db.commit()
        print("Seed executed successfully!")
        
    except Exception as e:
        print(f"Error executing seed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    run_seed()
