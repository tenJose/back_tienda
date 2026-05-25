from sqlalchemy import create_engine, inspect
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)
inspector = inspect(engine)

def print_table(name):
    print(f"TABLE: {name}")
    try:
        columns = inspector.get_columns(name)
        for col in columns:
            print(f"  {col['name']}: {col['type']} (Nullable: {col['nullable']})")
    except Exception as e:
        print(f"  Error: {e}")

print_table('creditos_cliente')
print_table('pagos_credito')
print_table('ventas')
print_table('auditoria')
