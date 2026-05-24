import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import get_settings

def run_migration():
    settings = get_settings()
    print("Connecting to database...")
    engine = create_engine(settings.database_url)
    
    with engine.begin() as conn:
        print("Adding proveedor_id to productos...")
        conn.execute(text("""
            ALTER TABLE productos 
            ADD COLUMN IF NOT EXISTS proveedor_id UUID REFERENCES proveedores(id);
        """))
        
        print("Adding fecha_caducidad to productos...")
        conn.execute(text("""
            ALTER TABLE productos 
            ADD COLUMN IF NOT EXISTS fecha_caducidad DATE;
        """))
        
    print("Migration completed successfully!")

if __name__ == "__main__":
    run_migration()
