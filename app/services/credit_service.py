import math
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.credit import CreditoCreate, CreditoUpdate, AbonoCreate


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
    return f"{row['prefijo']}-{str(row['ultimo_numero']).zfill(row['longitud'])}"

def get_creditos(
    db: Session,
    search: Optional[str] = None,
    cliente_id: Optional[UUID] = None,
    estado: Optional[str] = None,
    vencido: Optional[bool] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    limit: int = 20,
    page: int = 1,
):
    offset = (page - 1) * limit

    base_query = """
        FROM creditos_cliente cr
        JOIN clientes c ON cr.cliente_id = c.id
        LEFT JOIN ventas v ON cr.venta_id = v.id
        WHERE 1=1
    """
    params = {}

    if search:
        base_query += " AND (c.nombre ILIKE :search OR c.telefono ILIKE :search OR v.folio ILIKE :search OR cr.notas ILIKE :search)"
        params["search"] = f"%{search}%"
    
    if cliente_id:
        base_query += " AND cr.cliente_id = :cliente_id"
        params["cliente_id"] = str(cliente_id)

    if estado:
        if estado == "vencido":
            base_query += " AND cr.fecha_limite < CURRENT_DATE AND cr.saldo_pendiente > 0"
        else:
            base_query += " AND cr.estado = :estado"
            params["estado"] = estado
            
    if vencido is True:
        base_query += " AND cr.fecha_limite < CURRENT_DATE AND cr.saldo_pendiente > 0"
    elif vencido is False:
        base_query += " AND (cr.fecha_limite >= CURRENT_DATE OR cr.fecha_limite IS NULL OR cr.saldo_pendiente = 0)"

    if fecha_desde:
        base_query += " AND cr.fecha_credito >= :fecha_desde"
        params["fecha_desde"] = fecha_desde

    if fecha_hasta:
        base_query += " AND cr.fecha_credito <= :fecha_hasta"
        params["fecha_hasta"] = fecha_hasta

    # Count total items
    count_query = f"SELECT COUNT(cr.id) {base_query}"
    total_items = db.execute(text(count_query), params).scalar()
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

    # Summary query
    summary_query = f"""
        SELECT 
            COUNT(cr.id) AS total_creditos,
            COUNT(cr.id) FILTER (WHERE cr.estado IN ('pendiente', 'parcial')) AS creditos_activos,
            COUNT(cr.id) FILTER (WHERE cr.estado = 'pendiente') AS pendientes,
            COUNT(cr.id) FILTER (WHERE cr.estado = 'parcial') AS parciales,
            COUNT(cr.id) FILTER (WHERE cr.estado = 'pagado') AS pagados,
            COUNT(cr.id) FILTER (WHERE cr.fecha_limite < CURRENT_DATE AND cr.saldo_pendiente > 0) AS vencidos,
            COALESCE(SUM(cr.saldo_pendiente), 0) AS saldo_pendiente_total,
            COALESCE(SUM(cr.monto_total - cr.saldo_pendiente), 0) AS monto_pagado_total
        {base_query}
    """
    summary_row = db.execute(text(summary_query), params).mappings().one()
    
    abonado_mes_query = """
        SELECT COALESCE(SUM(p.monto), 0) 
        FROM pagos_credito p
        WHERE date_trunc('month', p.created_at) = date_trunc('month', CURRENT_DATE)
    """
    if cliente_id:
        abonado_mes_query += " AND p.credito_id IN (SELECT id FROM creditos_cliente WHERE cliente_id = :cliente_id)"
    abonado_mes_actual = db.execute(text(abonado_mes_query), params).scalar()

    summary = dict(summary_row)
    summary["abonado_mes_actual"] = abonado_mes_actual

    # Main data query
    select_query = f"""
        SELECT 
            cr.id, cr.folio, cr.cliente_id, c.nombre AS cliente_nombre, c.telefono AS cliente_telefono,
            cr.venta_id, v.folio AS folio_venta,
            cr.monto_total, (cr.monto_total - cr.saldo_pendiente) AS monto_pagado, cr.saldo_pendiente,
            CASE WHEN cr.monto_total > 0 THEN ((cr.monto_total - cr.saldo_pendiente) / cr.monto_total) * 100 ELSE 0 END AS porcentaje_pagado,
            cr.estado,
            CASE 
                WHEN cr.saldo_pendiente = 0 THEN 'pagado'
                WHEN cr.fecha_limite < CURRENT_DATE AND cr.saldo_pendiente > 0 THEN 'vencido'
                ELSE cr.estado 
            END AS estado_visual,
            cr.fecha_credito, cr.fecha_limite,
            CASE 
                WHEN cr.fecha_limite < CURRENT_DATE AND cr.saldo_pendiente > 0 THEN (CURRENT_DATE - cr.fecha_limite)
                ELSE 0 
            END AS dias_atraso,
            cr.notas
        {base_query}
        ORDER BY cr.fecha_credito DESC
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    items_rows = db.execute(text(select_query), params).mappings().all()

    return {
        "items": [dict(row) for row in items_rows],
        "total": total_items,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "summary": summary
    }


def get_credito_by_id(db: Session, credito_id: UUID):
    query = """
        SELECT 
            cr.id, cr.folio, cr.cliente_id, c.nombre AS cliente_nombre, c.telefono AS cliente_telefono,
            cr.venta_id, v.folio AS folio_venta,
            cr.monto_total, (cr.monto_total - cr.saldo_pendiente) AS monto_pagado, cr.saldo_pendiente,
            CASE WHEN cr.monto_total > 0 THEN ((cr.monto_total - cr.saldo_pendiente) / cr.monto_total) * 100 ELSE 0 END AS porcentaje_pagado,
            cr.estado,
            CASE 
                WHEN cr.saldo_pendiente = 0 THEN 'pagado'
                WHEN cr.fecha_limite < CURRENT_DATE AND cr.saldo_pendiente > 0 THEN 'vencido'
                ELSE cr.estado 
            END AS estado_visual,
            cr.fecha_credito, cr.fecha_limite,
            CASE 
                WHEN cr.fecha_limite < CURRENT_DATE AND cr.saldo_pendiente > 0 THEN (CURRENT_DATE - cr.fecha_limite)
                ELSE 0 
            END AS dias_atraso,
            cr.notas
        FROM creditos_cliente cr
        JOIN clientes c ON cr.cliente_id = c.id
        LEFT JOIN ventas v ON cr.venta_id = v.id
        WHERE cr.id = :id
    """
    row = db.execute(text(query), {"id": str(credito_id)}).mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crédito no encontrado")
    return dict(row)


def create_credito(db: Session, payload: CreditoCreate, user_id: UUID, user_role: str):
    # Validar cliente
    cliente = db.execute(
        text("SELECT id, activo, permite_credito, limite_credito FROM clientes WHERE id = :id"),
        {"id": str(payload.cliente_id)}
    ).mappings().one_or_none()

    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    if not cliente["activo"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cliente está inactivo")
    if not cliente["permite_credito"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El cliente no permite crédito")

    # Validar límite de crédito si no es administrador
    if user_role not in ["dueno", "dueño", "administrador"]:
        deuda_actual = db.execute(
            text("SELECT COALESCE(SUM(saldo_pendiente), 0) FROM creditos_cliente WHERE cliente_id = :id AND estado IN ('pendiente', 'parcial')"),
            {"id": str(payload.cliente_id)}
        ).scalar()
        if (deuda_actual + payload.monto_total) > cliente["limite_credito"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El monto excede el límite de crédito del cliente")

    folio = _next_folio(db, "credito", "CRE")

    # Crear crédito
    query = """
        INSERT INTO creditos_cliente (id, folio, cliente_id, venta_id, monto_total, saldo_pendiente, estado, fecha_credito, fecha_limite, notas)
        VALUES (gen_random_uuid(), :folio, :cliente_id, :venta_id, :monto_total, :saldo_pendiente, 'pendiente', CURRENT_TIMESTAMP, :fecha_limite, :notas)
        RETURNING id
    """
    res = db.execute(text(query), {
        "folio": folio,
        "cliente_id": str(payload.cliente_id),
        "venta_id": str(payload.venta_id) if payload.venta_id else None,
        "monto_total": payload.monto_total,
        "saldo_pendiente": payload.monto_total,
        "fecha_limite": payload.fecha_limite,
        "notas": payload.notas
    }).mappings().one()

    # Auditoria
    db.execute(text("""
        INSERT INTO auditoria (id, usuario_id, accion, tabla_afectada, registro_id, descripcion, created_at)
        VALUES (gen_random_uuid(), :usuario_id, 'CREDITO_CREADO', 'creditos_cliente', :registro_id, :descripcion, CURRENT_TIMESTAMP)
    """), {
        "usuario_id": str(user_id),
        "registro_id": str(res["id"]),
        "descripcion": f"Crédito creado por un monto de ${payload.monto_total}"
    })
    db.commit()
    return get_credito_by_id(db, res["id"])


def update_credito(db: Session, credito_id: UUID, payload: CreditoUpdate, user_id: UUID):
    credito = get_credito_by_id(db, credito_id)
    updates = []
    params = {"id": str(credito_id)}

    if payload.fecha_limite is not None:
        updates.append("fecha_limite = :fecha_limite")
        params["fecha_limite"] = payload.fecha_limite
    if payload.notas is not None:
        updates.append("notas = :notas")
        params["notas"] = payload.notas

    if not updates:
        return credito

    query = f"UPDATE creditos_cliente SET {', '.join(updates)} WHERE id = :id"
    db.execute(text(query), params)

    db.execute(text("""
        INSERT INTO auditoria (id, usuario_id, accion, tabla_afectada, registro_id, descripcion, created_at)
        VALUES (gen_random_uuid(), :usuario_id, 'CREDITO_EDITADO', 'creditos_cliente', :registro_id, :descripcion, CURRENT_TIMESTAMP)
    """), {
        "usuario_id": str(user_id),
        "registro_id": str(credito_id),
        "descripcion": "Datos del crédito actualizados"
    })
    db.commit()
    return get_credito_by_id(db, credito_id)


def registrar_abono(db: Session, credito_id: UUID, payload: AbonoCreate, user_id: UUID):
    # Lock for update
    credito = db.execute(
        text("SELECT id, monto_total, saldo_pendiente, estado FROM creditos_cliente WHERE id = :id FOR UPDATE"),
        {"id": str(credito_id)}
    ).mappings().one_or_none()

    if not credito:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crédito no encontrado")
    
    if credito["saldo_pendiente"] == 0 or credito["estado"] == "pagado":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El crédito ya está pagado en su totalidad")
    
    if payload.monto > credito["saldo_pendiente"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El abono excede el saldo pendiente")

    nuevo_saldo = credito["saldo_pendiente"] - payload.monto
    nuevo_estado = "pagado" if nuevo_saldo == 0 else "parcial"

    # Insertar pago
    pago_res = db.execute(text("""
        INSERT INTO pagos_credito (id, credito_id, usuario_id, monto, metodo_pago_id, notas, created_at)
        VALUES (gen_random_uuid(), :credito_id, :usuario_id, :monto, :metodo_pago_id, :notas, CURRENT_TIMESTAMP)
        RETURNING id
    """), {
        "credito_id": str(credito_id),
        "usuario_id": str(user_id),
        "monto": payload.monto,
        "metodo_pago_id": str(payload.metodo_pago_id) if payload.metodo_pago_id else None,
        "notas": payload.notas
    }).mappings().one()

    # Actualizar credito
    db.execute(text("UPDATE creditos_cliente SET saldo_pendiente = :saldo, estado = :estado WHERE id = :id"), {
        "saldo": nuevo_saldo,
        "estado": nuevo_estado,
        "id": str(credito_id)
    })

    # Auditoria de pago
    db.execute(text("""
        INSERT INTO auditoria (id, usuario_id, accion, tabla_afectada, registro_id, descripcion, created_at)
        VALUES (gen_random_uuid(), :usuario_id, 'ABONO_CREDITO_REGISTRADO', 'pagos_credito', :registro_id, :descripcion, CURRENT_TIMESTAMP)
    """), {
        "usuario_id": str(user_id),
        "registro_id": str(pago_res["id"]),
        "descripcion": f"Abono de ${payload.monto} registrado para crédito {str(credito_id)}"
    })

    if nuevo_estado == "pagado" and credito["estado"] != "pagado":
        db.execute(text("""
            INSERT INTO auditoria (id, usuario_id, accion, tabla_afectada, registro_id, descripcion, created_at)
            VALUES (gen_random_uuid(), :usuario_id, 'CREDITO_PAGADO', 'creditos_cliente', :registro_id, 'Crédito liquidado en su totalidad', CURRENT_TIMESTAMP)
        """), {
            "usuario_id": str(user_id),
            "registro_id": str(credito_id)
        })

    db.commit()
    return get_credito_by_id(db, credito_id)


def get_historial_pagos(db: Session, credito_id: UUID):
    query = """
        SELECT p.id, p.credito_id, p.usuario_id, 
               COALESCE(u.nombre || ' ' || u.apellido, u.email, 'Cajero') AS usuario_nombre,
               p.monto, mp.nombre AS metodo_pago,
               NULL AS referencia, p.notas, p.created_at
        FROM pagos_credito p
        LEFT JOIN usuarios u ON p.usuario_id = u.id
        LEFT JOIN metodos_pago mp ON p.metodo_pago_id = mp.id
        WHERE p.credito_id = :credito_id
        ORDER BY p.created_at DESC
    """
    rows = db.execute(text(query), {"credito_id": str(credito_id)}).mappings().all()
    return [dict(r) for r in rows]
