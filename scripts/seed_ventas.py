import sys
import os
import uuid
from datetime import datetime, timedelta
import random
from decimal import Decimal
from sqlalchemy import text

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal

def seed_sales():
    db = SessionLocal()
    
    productos = db.execute(text("SELECT id, precio_venta, costo FROM productos WHERE activo = true")).fetchall()
    if not productos:
        print("No hay productos. Ejecuta primero los scripts de seed de productos.")
        db.close()
        return

    usuario = db.execute(text("SELECT id FROM usuarios LIMIT 1")).fetchone()
    if not usuario:
        print("No hay usuarios.")
        db.close()
        return

    sucursal = db.execute(text("SELECT id FROM sucursales LIMIT 1")).fetchone()
    sucursal_id = sucursal[0] if sucursal else None
        
    metodos_pago = db.execute(text("SELECT id FROM metodos_pago")).fetchall()
    if not metodos_pago:
        print("No hay métodos de pago.")
        db.close()
        return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=40)
    
    print("Generando ventas...")
    current_date = start_date
    count_ventas = 0
    while current_date <= end_date:
        num_sales = random.randint(3, 12)
        for _ in range(num_sales):
            hora = random.randint(8, 20)
            minuto = random.randint(0, 59)
            fecha_venta = current_date.replace(hour=hora, minute=minuto)
            
            venta_id = uuid.uuid4()
            metodo_id = random.choice(metodos_pago)[0]
            
            num_items = random.randint(1, 4)
            productos_venta = random.sample(productos, num_items)
            
            total_venta = Decimal(0)
            detalles = []
            for prod in productos_venta:
                cantidad = Decimal(random.randint(1, 3))
                precio = prod[1] or Decimal(10)
                costo = prod[2] or Decimal(5)
                subtotal = precio * cantidad
                total_venta += subtotal
                
                detalles.append({
                    "id": uuid.uuid4(),
                    "venta_id": venta_id,
                    "producto_id": prod[0],
                    "cantidad": cantidad,
                    "precio_unitario": precio,
                    "costo_unitario": costo,
                    "subtotal": subtotal
                })
            
            db.execute(text("""
                INSERT INTO ventas (id, folio, usuario_id, sucursal_id, metodo_pago_id, total, pago_recibido, cambio, estado, created_at)
                VALUES (:id, :folio, :usuario_id, :sucursal_id, :metodo_pago_id, :total, :pago_recibido, :cambio, :estado, :created_at)
            """), {
                "id": venta_id,
                "folio": f"V-{fecha_venta.strftime('%Y%m%d')}-{random.randint(1000,9999)}",
                "usuario_id": usuario[0],
                "sucursal_id": sucursal_id,
                "metodo_pago_id": metodo_id,
                "total": total_venta,
                "pago_recibido": total_venta,
                "cambio": Decimal(0),
                "estado": 'completada',
                "created_at": fecha_venta
            })
            
            for d in detalles:
                db.execute(text("""
                    INSERT INTO venta_detalle (id, venta_id, producto_id, cantidad, precio_unitario, costo_unitario, subtotal)
                    VALUES (:id, :venta_id, :producto_id, :cantidad, :precio_unitario, :costo_unitario, :subtotal)
                """), d)
                
            count_ventas += 1
            
        current_date += timedelta(days=1)
        
    db.commit()
    print(f"Se crearon {count_ventas} ventas en la base de datos.")
    db.close()

if __name__ == "__main__":
    seed_sales()
