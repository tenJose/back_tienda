import ast
import json
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import role_guard, get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/sales", tags=["Ventas"])
CanSell = Depends(role_guard({"dueno", "dueño", "administrador", "encargado", "cajero"}))


class SaleItem(BaseModel):
    producto_id: UUID
    cantidad: Decimal = Field(gt=0)


class SaleRequest(BaseModel):
    items: list[SaleItem] = Field(min_length=1)
    metodo_pago_id: UUID | None = None
    pago_recibido: Decimal = Field(ge=0)
    sucursal_id: UUID | None = None


def _payment_method_name(db: Session, metodo_pago_id: UUID | None) -> str:
    if not metodo_pago_id:
        return "Efectivo"
    row = db.execute(
        text("SELECT nombre FROM metodos_pago WHERE id = :id"),
        {"id": str(metodo_pago_id)},
    ).mappings().one_or_none()
    return row["nombre"] if row else "Otro"


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


@router.get("")
def list_sales(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT v.id, v.folio, v.created_at, v.total, v.pago_recibido, v.cambio, v.estado,
                   COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), u.email, 'Cajero') AS cajero,
                   mp.nombre AS metodo_pago
            FROM ventas v
            LEFT JOIN usuarios u ON u.id = v.usuario_id
            LEFT JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
            ORDER BY v.created_at DESC
            LIMIT 200
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


@router.post("", dependencies=[CanSell])
def create_sale(payload: SaleRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    product_ids = [str(item.producto_id) for item in payload.items]
    products = db.execute(
        text(
            """
            SELECT p.id, p.nombre, p.precio_venta, p.costo, p.es_granel,
                   COALESCE(i.existencia, 0) AS existencia, i.id AS inventario_id
            FROM productos p
            LEFT JOIN inventarios i ON i.producto_id = p.id
              AND ((:sucursal_id IS NULL AND i.sucursal_id IS NULL) OR i.sucursal_id = CAST(:sucursal_id AS uuid))
            WHERE p.id = ANY(CAST(:ids AS uuid[])) AND p.activo = true
            """
        ),
        {"ids": product_ids, "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None},
    ).mappings().all()
    by_id = {str(row["id"]): row for row in products}
    if len(by_id) != len(product_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hay productos inexistentes o inactivos")

    subtotal = Decimal("0")
    detail_rows = []
    for item in payload.items:
        product = by_id[str(item.producto_id)]
        if item.cantidad != item.cantidad.to_integral_value() and not product["es_granel"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{product['nombre']} no permite cantidad decimal")
        if Decimal(product["existencia"]) < item.cantidad:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Stock insuficiente para {product['nombre']}")
        line_total = Decimal(product["precio_venta"]) * item.cantidad
        subtotal += line_total
        detail_rows.append((item, product, line_total))

    pago_recibido = payload.pago_recibido
    cambio = pago_recibido - subtotal
    if payload.metodo_pago_id is None:
        if pago_recibido < subtotal:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pago recibido insuficiente")
    else:
        pago_recibido = subtotal
        cambio = Decimal("0")

    folio = _next_folio(db, "venta", "VTA")
    ticket_folio = _next_folio(db, "ticket", "TCK")
    venta_id = db.execute(
        text(
            """
            INSERT INTO ventas (folio, usuario_id, sucursal_id, subtotal, total, metodo_pago_id, pago_recibido, cambio)
            VALUES (:folio, :usuario_id, :sucursal_id, :subtotal, :total, :metodo_pago_id, :pago_recibido, :cambio)
            RETURNING id, created_at
            """
        ),
        {
            "folio": folio,
            "usuario_id": user.get("id"),
            "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None,
            "subtotal": subtotal,
            "total": subtotal,
            "metodo_pago_id": str(payload.metodo_pago_id) if payload.metodo_pago_id else None,
            "pago_recibido": pago_recibido,
            "cambio": cambio,
        },
    ).mappings().one()

    for item, product, line_total in detail_rows:
        db.execute(
            text(
                """
                INSERT INTO venta_detalle (venta_id, producto_id, cantidad, precio_unitario, costo_unitario, subtotal)
                VALUES (:venta_id, :producto_id, :cantidad, :precio_unitario, :costo_unitario, :subtotal)
                """
            ),
            {
                "venta_id": str(venta_id["id"]),
                "producto_id": str(item.producto_id),
                "cantidad": item.cantidad,
                "precio_unitario": product["precio_venta"],
                "costo_unitario": product["costo"],
                "subtotal": line_total,
            },
        )
        stock_anterior = Decimal(product["existencia"])
        stock_nuevo = stock_anterior - item.cantidad
        db.execute(
            text(
                """
                UPDATE inventarios SET existencia = :stock_nuevo, updated_at = now()
                WHERE producto_id = :producto_id
                  AND ((:sucursal_id IS NULL AND sucursal_id IS NULL) OR sucursal_id = CAST(:sucursal_id AS uuid))
                """
            ),
            {"producto_id": str(item.producto_id), "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None, "stock_nuevo": stock_nuevo},
        )
        db.execute(
            text(
                """
                INSERT INTO movimientos_inventario
                (producto_id, sucursal_id, tipo_movimiento, cantidad, stock_anterior, stock_nuevo, referencia_tipo, referencia_id, motivo, usuario_id)
                VALUES (:producto_id, :sucursal_id, 'venta', :cantidad, :stock_anterior, :stock_nuevo, 'venta', :venta_id, 'Venta POS', :usuario_id)
                """
            ),
            {
                "producto_id": str(item.producto_id),
                "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None,
                "cantidad": -item.cantidad,
                "stock_anterior": stock_anterior,
                "stock_nuevo": stock_nuevo,
                "venta_id": str(venta_id["id"]),
                "usuario_id": user.get("id"),
            },
        )

    config = db.execute(text("SELECT nombre_negocio, mensaje_ticket FROM negocio_configuracion ORDER BY created_at LIMIT 1")).mappings().one_or_none()
    ticket = {
        "negocio": config["nombre_negocio"] if config else "Negocio",
        "folio": folio,
        "folio_ticket": ticket_folio,
        "fecha": str(venta_id["created_at"]),
        "cajero": user.get("nombre") or user.get("email") or "Cajero",
        "productos": [{"nombre": p["nombre"], "cantidad": str(i.cantidad), "precio_unitario": str(p["precio_venta"]), "subtotal": str(t)} for i, p, t in detail_rows],
        "subtotal": str(subtotal),
        "total": str(subtotal),
        "pago_recibido": str(pago_recibido),
        "cambio": str(cambio),
        "metodo_pago": _payment_method_name(db, payload.metodo_pago_id),
        "mensaje": config["mensaje_ticket"] if config else "Gracias por su compra",
    }
    db.execute(
        text("INSERT INTO tickets (venta_id, folio_ticket, contenido) VALUES (:venta_id, :folio_ticket, :contenido)"),
        {"venta_id": str(venta_id["id"]), "folio_ticket": ticket_folio, "contenido": str(ticket)},
    )
    db.commit()
    return {"id": venta_id["id"], "folio": folio, "ticket": ticket}


class CashOpenRequest(BaseModel):
    monto_inicial: Decimal = Field(ge=0)
    sucursal_id: UUID | None = None


class CashCloseRequest(BaseModel):
    efectivo_contado: Decimal = Field(ge=0)
    tarjeta: Decimal | None = None
    transferencia: Decimal | None = None


@router.get("/cortes-caja/active")
def get_active_cash_cut(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    row = db.execute(
        text(
            "SELECT * FROM cortes_caja WHERE usuario_id = :usuario_id AND estado = 'abierta' ORDER BY created_at DESC LIMIT 1"
        ),
        {"usuario_id": user.get("id")},
    ).mappings().one_or_none()
    return dict(row) if row else None


@router.post("/cortes-caja/apertura", dependencies=[CanSell])
def open_cash_cut(payload: CashOpenRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    res = db.execute(
        text(
            "INSERT INTO cortes_caja (usuario_id, sucursal_id, monto_inicial, estado) VALUES (:usuario_id, :sucursal_id, :monto_inicial, 'abierta') RETURNING id, created_at"
        ),
        {"usuario_id": user.get("id"), "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None, "monto_inicial": payload.monto_inicial},
    ).mappings().one()
    db.commit()
    return {"id": res["id"], "created_at": res["created_at"]}


@router.post("/cortes-caja/cierre", dependencies=[CanSell])
def close_cash_cut(payload: CashCloseRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    corte = db.execute(
        text("SELECT id, created_at FROM cortes_caja WHERE usuario_id = :usuario_id AND estado = 'abierta' ORDER BY created_at DESC LIMIT 1"),
        {"usuario_id": user.get("id")},
    ).mappings().one_or_none()
    if not corte:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay corte de caja abierto")

    totals = db.execute(
        text(
            "SELECT COALESCE(SUM(total),0) AS total_ventas, COALESCE(SUM(CASE WHEN metodo_pago_id IS NULL THEN total ELSE 0 END),0) AS total_efectivo FROM ventas WHERE usuario_id = :usuario_id AND created_at >= :since AND estado = 'completada'"
        ),
        {"usuario_id": user.get("id"), "since": corte["created_at"]},
    ).mappings().one()

    db.execute(
        text("UPDATE cortes_caja SET monto_cierre = :monto_cierre, estado = 'cerrada', closed_at = now() WHERE id = :id"),
        {"monto_cierre": payload.efectivo_contado, "id": str(corte["id"])},
    )
    db.commit()

    return {
        "id": corte["id"],
        "total_ventas": str(totals["total_ventas"]),
        "total_efectivo": str(totals["total_efectivo"]),
        "monto_cierre": str(payload.efectivo_contado),
    }


@router.get("/{sale_id}", dependencies=[CanSell])
def get_sale_detail(sale_id: UUID, db: Session = Depends(get_db)):
    sale = db.execute(
        text(
            """
            SELECT v.id, v.folio, v.created_at, v.subtotal, v.total, v.pago_recibido, v.cambio, v.estado,
                   COALESCE(u.nombre || ' ' || COALESCE(u.apellido, ''), u.email, 'Cajero') AS cajero,
                   mp.nombre AS metodo_pago
            FROM ventas v
            LEFT JOIN usuarios u ON u.id = v.usuario_id
            LEFT JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
            WHERE v.id = :id
            """
        ),
        {"id": str(sale_id)},
    ).mappings().one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")

    items = db.execute(
        text(
            """
            SELECT vd.id, vd.producto_id, p.nombre AS producto_nombre, vd.cantidad,
                   vd.precio_unitario, vd.subtotal
            FROM venta_detalle vd
            JOIN productos p ON p.id = vd.producto_id
            WHERE vd.venta_id = :venta_id
            ORDER BY p.nombre
            """
        ),
        {"venta_id": str(sale_id)},
    ).mappings().all()
    return {**dict(sale), "items": [dict(item) for item in items]}


@router.get("/{sale_id}/ticket", dependencies=[CanSell])
def get_sale_ticket(sale_id: UUID, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT folio_ticket, contenido FROM tickets WHERE venta_id = :venta_id ORDER BY created_at DESC LIMIT 1"),
        {"venta_id": str(sale_id)},
    ).mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    contenido = row["contenido"]
    if isinstance(contenido, str):
        try:
            ticket = json.loads(contenido)
        except json.JSONDecodeError:
            try:
                ticket = ast.literal_eval(contenido)
            except (SyntaxError, ValueError):
                ticket = {"mensaje": contenido}
    else:
        ticket = contenido
    return {"folio_ticket": row["folio_ticket"], "ticket": ticket}


@router.post("/{sale_id}/cancel", dependencies=[CanSell])
def cancel_sale(sale_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # verify sale exists and not already canceled
    sale = db.execute(text("SELECT id, estado FROM ventas WHERE id = :id"), {"id": str(sale_id)}).mappings().one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
    if sale["estado"] == 'cancelada':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Venta ya cancelada")

    # retrieve sale details
    detalles = db.execute(text("SELECT producto_id, cantidad FROM venta_detalle WHERE venta_id = :id"), {"id": str(sale_id)}).mappings().all()
    for d in detalles:
        producto_id = str(d["producto_id"])
        cantidad = Decimal(d["cantidad"])
        # restore stock
        db.execute(
            text(
                """
                UPDATE inventarios SET existencia = COALESCE(existencia, 0) + :cantidad, updated_at = now()
                WHERE producto_id = :producto_id
                """
            ),
            {"producto_id": producto_id, "cantidad": cantidad},
        )
        # log movement
        db.execute(
            text(
                """
                INSERT INTO movimientos_inventario
                (producto_id, sucursal_id, tipo_movimiento, cantidad, stock_anterior, stock_nuevo, referencia_tipo, referencia_id, motivo, usuario_id)
                VALUES (:producto_id, NULL, 'entrada', :cantidad, NULL, NULL, 'venta_cancelada', :venta_id, 'Cancelacion de venta', :usuario_id)
                """
            ),
            {"producto_id": producto_id, "cantidad": cantidad, "venta_id": str(sale_id), "usuario_id": user.get("id")},
        )

    db.execute(text("UPDATE ventas SET estado = 'cancelada', updated_at = now() WHERE id = :id"), {"id": str(sale_id)})
    db.commit()
    return {"ok": True}
