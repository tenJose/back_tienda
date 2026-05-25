from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import role_guard, get_current_user
from app.core.database import get_db
from app.services.product_service import list_products

router = APIRouter(prefix="/inventory", tags=["Inventario"])

CanViewInventory = Depends(role_guard({"dueno", "dueño", "administrador", "encargado", "ayudante"}))
CanManageInventory = Depends(role_guard({"dueno", "dueño", "administrador", "encargado"}))


class PurchaseDetailItem(BaseModel):
    producto_id: UUID
    cantidad: Decimal = Field(gt=0)
    costo_unitario: Decimal = Field(ge=0)
    descuento: Decimal = Field(default=Decimal("0"), ge=0)


class PurchaseEntryRequest(BaseModel):
    proveedor_id: UUID | None = None
    sucursal_id: UUID | None = None
    items: list[PurchaseDetailItem] = Field(min_length=1)
    notas: str | None = None


def _next_folio(db: Session, tipo: str, prefijo: str) -> str:
    db.execute(
        text(
            """
            INSERT INTO folios (id, tipo, prefijo, ultimo_numero, longitud)
            VALUES (gen_random_uuid(), :tipo, :prefijo, 0, 5)
            ON CONFLICT (tipo) DO NOTHING
            """
        ),
        {"tipo": tipo, "prefijo": prefijo},
    )
    row = db.execute(
        text(
            """
            UPDATE folios
            SET ultimo_numero = ultimo_numero + 1, updated_at = now()
            WHERE tipo = :tipo
            RETURNING prefijo, ultimo_numero, longitud
            """
        ),
        {"tipo": tipo},
    ).mappings().one()
    return f"{row['prefijo']}-{int(row['ultimo_numero']):0{int(row['longitud'])}d}"


@router.get("/alerts", dependencies=[CanViewInventory])
def get_low_stock_alerts(db: Session = Depends(get_db)):
    rows = list_products(
        db,
        q=None,
        departamento_id=None,
        categoria_id=None,
        activo=True,
        bajo_stock=True,
        granel=None,
        perecedero=None,
    )
    alerts = []
    for row in rows:
        stock = Decimal(row.stock)
        min_stock = Decimal(row.stock_minimo)
        urgency = "OUT" if stock <= 0 else "CRITICAL" if stock <= min_stock / 2 else "LOW"
        alerts.append(
            {
                "id": str(row.id),
                "producto_id": str(row.id),
                "producto_nombre": row.nombre,
                "categoria": row.categoria,
                "stock": str(stock),
                "stock_minimo": str(min_stock),
                "urgencia": urgency,
            }
        )
    return alerts


@router.get("/movements", dependencies=[CanViewInventory])
def get_movements(
    db: Session = Depends(get_db),
    producto_id: UUID | None = None,
    tipo_movimiento: str | None = None,
    q: str | None = None,
    limit: int = Query(default=150, ge=1, le=500),
):
    filters = ["1=1"]
    params: dict = {"limit": limit}
    if producto_id:
        filters.append("m.producto_id = CAST(:producto_id AS uuid)")
        params["producto_id"] = str(producto_id)
    if tipo_movimiento:
        filters.append("m.tipo_movimiento = :tipo_movimiento")
        params["tipo_movimiento"] = tipo_movimiento
    if q:
        filters.append("p.nombre ILIKE :q")
        params["q"] = f"%{q.strip()}%"

    where_clause = " AND ".join(filters)
    rows = db.execute(
        text(
            f"""
            SELECT m.id, m.producto_id, p.nombre AS producto_nombre, m.sucursal_id,
                   m.tipo_movimiento, m.cantidad, m.stock_anterior, m.stock_nuevo,
                   m.referencia_tipo, m.referencia_id, m.motivo,
                   COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), u.email, 'Usuario') AS usuario_nombre,
                   m.created_at
            FROM movimientos_inventario m
            JOIN productos p ON p.id = m.producto_id
            LEFT JOIN usuarios u ON u.id = m.usuario_id
            WHERE {where_clause}
            ORDER BY m.created_at DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


@router.get("/entries", dependencies=[CanViewInventory])
def get_entries(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT c.id, c.folio, c.proveedor_id, pr.nombre AS proveedor_nombre,
                   c.sucursal_id, c.usuario_id,
                   COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), u.email, 'Usuario') AS usuario_nombre,
                   c.subtotal, c.descuento, c.impuestos, c.total, c.estado, c.notas, c.created_at
            FROM compras c
            LEFT JOIN proveedores pr ON pr.id = c.proveedor_id
            LEFT JOIN usuarios u ON u.id = c.usuario_id
            ORDER BY c.created_at DESC
            LIMIT 100
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


@router.get("/entries/{entry_id}", dependencies=[CanViewInventory])
def get_entry_detail(entry_id: UUID, db: Session = Depends(get_db)):
    header = db.execute(
        text(
            """
            SELECT c.id, c.folio, c.proveedor_id, pr.nombre AS proveedor_nombre,
                   c.sucursal_id, c.usuario_id,
                   COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), u.email, 'Usuario') AS usuario_nombre,
                   c.subtotal, c.descuento, c.impuestos, c.total, c.estado, c.notas, c.created_at
            FROM compras c
            LEFT JOIN proveedores pr ON pr.id = c.proveedor_id
            LEFT JOIN usuarios u ON u.id = c.usuario_id
            WHERE c.id = :entry_id
            """
        ),
        {"entry_id": str(entry_id)},
    ).mappings().one_or_none()
    if not header:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrada no encontrada")

    items = db.execute(
        text(
            """
            SELECT cd.id, cd.producto_id, p.nombre AS producto_nombre, cd.cantidad,
                   cd.costo_unitario, cd.descuento, cd.subtotal
            FROM compra_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            WHERE cd.compra_id = :entry_id
            ORDER BY p.nombre
            """
        ),
        {"entry_id": str(entry_id)},
    ).mappings().all()
    return {**dict(header), "items": [dict(item) for item in items]}


@router.post("/entries", dependencies=[CanManageInventory])
def create_entry(payload: PurchaseEntryRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    product_ids = [str(item.producto_id) for item in payload.items]
    products = db.execute(
        text(
            """
            SELECT p.id, p.nombre, p.es_granel, p.costo,
                   COALESCE(i.existencia, 0) AS existencia, i.id AS inventario_id
            FROM productos p
            LEFT JOIN inventarios i ON i.producto_id = p.id
              AND ((CAST(:sucursal_id AS uuid) IS NULL AND i.sucursal_id IS NULL) OR i.sucursal_id = CAST(:sucursal_id AS uuid))
            WHERE p.id = ANY(CAST(:ids AS uuid[])) AND p.activo = true
            """
        ),
        {"ids": product_ids, "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None},
    ).mappings().all()
    by_id = {str(row["id"]): row for row in products}
    if len(by_id) != len(product_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hay productos inexistentes o inactivos")

    subtotal = Decimal("0")
    total_descuento = Decimal("0")
    detail_rows = []

    for item in payload.items:
        product = by_id[str(item.producto_id)]
        if item.cantidad != item.cantidad.to_integral_value() and not product["es_granel"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{product['nombre']} no permite cantidad decimal")
        
        line_total = item.costo_unitario * item.cantidad
        line_desc = item.descuento
        subtotal += line_total
        total_descuento += line_desc
        detail_rows.append((item, product, line_total - line_desc))

    total = subtotal - total_descuento
    folio = _next_folio(db, "compra", "COM")
    
    compra_res = db.execute(
        text(
            """
            INSERT INTO compras (folio, proveedor_id, sucursal_id, usuario_id, subtotal, descuento, impuestos, total, estado, notas)
            VALUES (:folio, :proveedor_id, :sucursal_id, :usuario_id, :subtotal, :descuento, 0, :total, 'completada', :notas)
            RETURNING id, created_at
            """
        ),
        {
            "folio": folio,
            "proveedor_id": str(payload.proveedor_id) if payload.proveedor_id else None,
            "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None,
            "usuario_id": user.get("id"),
            "subtotal": subtotal,
            "descuento": total_descuento,
            "total": total,
            "notas": payload.notas,
        },
    ).mappings().one()

    compra_id = compra_res["id"]

    for item, product, line_net in detail_rows:
        db.execute(
            text(
                """
                INSERT INTO compra_detalle (compra_id, producto_id, cantidad, costo_unitario, descuento, subtotal)
                VALUES (:compra_id, :producto_id, :cantidad, :costo_unitario, :descuento, :subtotal)
                """
            ),
            {
                "compra_id": str(compra_id),
                "producto_id": str(item.producto_id),
                "cantidad": item.cantidad,
                "costo_unitario": item.costo_unitario,
                "descuento": item.descuento,
                "subtotal": line_net,
            },
        )
        
        # update stock
        stock_anterior = Decimal(product["existencia"])
        stock_nuevo = stock_anterior + item.cantidad
        
        if product["inventario_id"] is None:
            # create inventory entry if not exists
            db.execute(
                text(
                    """
                    INSERT INTO inventarios (producto_id, sucursal_id, existencia, reservado)
                    VALUES (:producto_id, :sucursal_id, :existencia, 0)
                    """
                ),
                {"producto_id": str(item.producto_id), "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None, "existencia": stock_nuevo},
            )
        else:
            db.execute(
                text(
                    """
                    UPDATE inventarios SET existencia = :stock_nuevo, updated_at = now()
                    WHERE producto_id = :producto_id
                      AND ((CAST(:sucursal_id AS uuid) IS NULL AND sucursal_id IS NULL) OR sucursal_id = CAST(:sucursal_id AS uuid))
                    """
                ),
                {"producto_id": str(item.producto_id), "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None, "stock_nuevo": stock_nuevo},
            )

        # log movement
        db.execute(
            text(
                """
                INSERT INTO movimientos_inventario
                (producto_id, sucursal_id, tipo_movimiento, cantidad, stock_anterior, stock_nuevo, referencia_tipo, referencia_id, motivo, usuario_id)
                VALUES (:producto_id, :sucursal_id, 'entrada', :cantidad, :stock_anterior, :stock_nuevo, 'compra', :compra_id, :motivo, :usuario_id)
                """
            ),
            {
                "producto_id": str(item.producto_id),
                "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None,
                "cantidad": item.cantidad,
                "stock_anterior": stock_anterior,
                "stock_nuevo": stock_nuevo,
                "compra_id": str(compra_id),
                "motivo": payload.notas or "Entrada por compra",
                "usuario_id": user.get("id"),
            },
        )

        # update cost in product table if different
        if item.costo_unitario != Decimal(product["costo"]):
            db.execute(
                text(
                    """
                    UPDATE productos SET costo = :costo, updated_by = :usuario_id, updated_at = now()
                    WHERE id = :producto_id
                    """
                ),
                {"costo": item.costo_unitario, "usuario_id": user.get("id"), "producto_id": str(item.producto_id)},
            )
            # log price history
            db.execute(
                text(
                    """
                    INSERT INTO historial_precios
                    (producto_id, costo_anterior, costo_nuevo, precio_anterior, precio_nuevo, usuario_id, motivo)
                    VALUES (:producto_id, :costo_anterior, :costo_nuevo, NULL, NULL, :usuario_id, 'Actualizacion de costo por compra')
                    """
                ),
                {
                    "producto_id": str(item.producto_id),
                    "costo_anterior": product["costo"],
                    "costo_nuevo": item.costo_unitario,
                    "usuario_id": user.get("id"),
                },
            )

    db.commit()
    return {"id": compra_id, "folio": folio}
