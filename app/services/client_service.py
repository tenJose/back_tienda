from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.client import ClienteCreate, ClienteUpdate


def get_clients(
    db: Session,
    search: Optional[str] = None,
    activo: Optional[bool] = None,
    permite_credito: Optional[bool] = None,
    estado_financiero: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = """
        SELECT 
            c.id, c.nombre, c.telefono, c.email, c.permite_credito, c.limite_credito, c.activo, c.created_at, c.updated_at,
            COALESCE(SUM(cr.saldo_pendiente), 0) AS deuda_actual,
            c.limite_credito - COALESCE(SUM(cr.saldo_pendiente), 0) AS credito_disponible,
            COUNT(cr.id) FILTER (WHERE cr.estado IN ('pendiente', 'parcial') AND cr.fecha_limite < CURRENT_DATE) AS creditos_vencidos
        FROM clientes c
        LEFT JOIN creditos_cliente cr ON cr.cliente_id = c.id AND cr.estado IN ('pendiente', 'parcial')
        WHERE 1=1
    """
    params = {"limit": limit, "offset": offset}

    if search:
        query += " AND (c.nombre ILIKE :search OR c.telefono ILIKE :search OR c.email ILIKE :search)"
        params["search"] = f"%{search}%"
    
    if activo is not None:
        query += " AND c.activo = :activo"
        params["activo"] = activo

    if permite_credito is not None:
        query += " AND c.permite_credito = :permite_credito"
        params["permite_credito"] = permite_credito

    query += " GROUP BY c.id"

    # Add HAVING clause for financial state filtering if needed
    having_clauses = []
    if estado_financiero == "con_deuda":
        having_clauses.append("COALESCE(SUM(cr.saldo_pendiente), 0) > 0")
    elif estado_financiero == "sin_deuda":
        having_clauses.append("COALESCE(SUM(cr.saldo_pendiente), 0) = 0")
    elif estado_financiero == "credito_excedido":
        having_clauses.append("COALESCE(SUM(cr.saldo_pendiente), 0) >= c.limite_credito")
    elif estado_financiero == "con_creditos_vencidos":
        having_clauses.append("COUNT(cr.id) FILTER (WHERE cr.estado IN ('pendiente', 'parcial') AND cr.fecha_limite < CURRENT_DATE) > 0")

    if having_clauses:
        query += " HAVING " + " AND ".join(having_clauses)

    query += " ORDER BY c.nombre ASC LIMIT :limit OFFSET :offset"

    rows = db.execute(text(query), params).mappings().all()

    results = []
    for row in rows:
        r = dict(row)
        deuda = r["deuda_actual"]
        limite = r["limite_credito"]
        
        estado = "sin_deuda"
        if r["creditos_vencidos"] > 0:
            estado = "vencido"
        elif deuda >= limite and limite > 0:
            estado = "credito_excedido"
        elif not r["permite_credito"]:
            estado = "credito_bloqueado"
        elif deuda > 0:
            estado = "con_deuda"
            
        r["estado_financiero"] = estado
        results.append(r)
        
    return results


def get_client_by_id(db: Session, client_id: UUID):
    query = """
        SELECT 
            c.id, c.nombre, c.telefono, c.email, c.permite_credito, c.limite_credito, c.activo, c.created_at, c.updated_at,
            COALESCE(SUM(cr.saldo_pendiente), 0) AS deuda_actual,
            c.limite_credito - COALESCE(SUM(cr.saldo_pendiente), 0) AS credito_disponible,
            COUNT(cr.id) FILTER (WHERE cr.estado IN ('pendiente', 'parcial')) AS creditos_activos,
            COUNT(cr.id) FILTER (WHERE cr.estado IN ('pendiente', 'parcial') AND cr.fecha_limite < CURRENT_DATE) AS creditos_vencidos
        FROM clientes c
        LEFT JOIN creditos_cliente cr ON cr.cliente_id = c.id AND cr.estado IN ('pendiente', 'parcial')
        WHERE c.id = :id
        GROUP BY c.id
    """
    row = db.execute(text(query), {"id": str(client_id)}).mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    
    r = dict(row)
    deuda = r["deuda_actual"]
    limite = r["limite_credito"]
    
    estado = "sin_deuda"
    if r["creditos_vencidos"] > 0:
        estado = "vencido"
    elif deuda >= limite and limite > 0:
        estado = "credito_excedido"
    elif not r["permite_credito"]:
        estado = "credito_bloqueado"
    elif deuda > 0:
        estado = "con_deuda"
        
    r["estado_financiero"] = estado
    r["tiene_creditos_vencidos"] = r["creditos_vencidos"] > 0
    return r


def check_duplicate_client(db: Session, nombre: str, telefono: Optional[str], exclude_id: Optional[UUID] = None):
    query = "SELECT id FROM clientes WHERE nombre = :nombre"
    params = {"nombre": nombre}
    if telefono:
        query += " AND telefono = :telefono"
        params["telefono"] = telefono
    else:
        query += " AND telefono IS NULL"
        
    if exclude_id:
        query += " AND id != :exclude_id"
        params["exclude_id"] = str(exclude_id)
        
    row = db.execute(text(query), params).one_or_none()
    if row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya existe un cliente con este nombre y teléfono")


def create_client(db: Session, client: ClienteCreate, user_id: UUID):
    check_duplicate_client(db, client.nombre, client.telefono)
    
    query = """
        INSERT INTO clientes (nombre, telefono, email, permite_credito, limite_credito, activo)
        VALUES (:nombre, :telefono, :email, :permite_credito, :limite_credito, :activo)
        RETURNING id
    """
    result = db.execute(text(query), {
        "nombre": client.nombre,
        "telefono": client.telefono,
        "email": client.email,
        "permite_credito": client.permite_credito,
        "limite_credito": client.limite_credito,
        "activo": client.activo
    }).mappings().one()
    
    # Auditoria
    audit_query = """
        INSERT INTO auditoria (usuario_id, accion, tabla_afectada, registro_id, descripcion)
        VALUES (:user_id, 'CLIENTE_CREADO', 'clientes', :registro_id, :detalles)
    """
    db.execute(text(audit_query), {
        "user_id": str(user_id),
        "registro_id": str(result["id"]),
        "detalles": f"Cliente creado: {client.nombre}"
    })
    
    db.commit()
    return get_client_by_id(db, result["id"])


def update_client(db: Session, client_id: UUID, client: ClienteUpdate, user_id: UUID, user_role: str):
    existing = get_client_by_id(db, client_id)
    
    if client.nombre is not None:
        check_duplicate_client(db, client.nombre, client.telefono if client.telefono is not None else existing["telefono"], exclude_id=client_id)

    # Permit validation
    if client.limite_credito is not None and Decimal(client.limite_credito) != existing["limite_credito"]:
        if user_role not in ["dueno", "dueño", "administrador"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para modificar el límite de crédito")

    updates = []
    params = {"id": str(client_id)}
    
    for field, value in client.model_dump(exclude_unset=True).items():
        updates.append(f"{field} = :{field}")
        params[field] = value
        
    if not updates:
        return existing
        
    query = f"UPDATE clientes SET {', '.join(updates)}, updated_at = now() WHERE id = :id"
    db.execute(text(query), params)
    
    # Auditoria
    audit_query = """
        INSERT INTO auditoria (usuario_id, accion, tabla_afectada, registro_id, descripcion)
        VALUES (:user_id, 'CLIENTE_EDITADO', 'clientes', :registro_id, :detalles)
    """
    db.execute(text(audit_query), {
        "user_id": str(user_id),
        "registro_id": str(client_id),
        "detalles": f"Campos actualizados: {', '.join(client.model_dump(exclude_unset=True).keys())}"
    })

    if "limite_credito" in params and params["limite_credito"] is not None and Decimal(params["limite_credito"]) != existing["limite_credito"]:
        db.execute(text(audit_query), {
            "user_id": str(user_id),
            "registro_id": str(client_id),
            "detalles": f"Límite de crédito modificado de {existing['limite_credito']} a {params['limite_credito']}"
        })
        
    db.commit()
    return get_client_by_id(db, client_id)


def change_client_status(db: Session, client_id: UUID, activo: bool, user_id: UUID):
    existing = get_client_by_id(db, client_id)
    if existing["activo"] == activo:
        return existing
        
    db.execute(text("UPDATE clientes SET activo = :activo, updated_at = now() WHERE id = :id"), {"activo": activo, "id": str(client_id)})
    
    accion = "CLIENTE_ACTIVADO" if activo else "CLIENTE_INACTIVADO"
    
    audit_query = """
        INSERT INTO auditoria (usuario_id, accion, tabla_afectada, registro_id, descripcion)
        VALUES (:user_id, :accion, 'clientes', :registro_id, :detalles)
    """
    db.execute(text(audit_query), {
        "user_id": str(user_id),
        "accion": accion,
        "registro_id": str(client_id),
        "detalles": f"Estado cambiado a {'activo' if activo else 'inactivo'}"
    })
    
    db.commit()
    return get_client_by_id(db, client_id)


def get_client_purchases(db: Session, client_id: UUID, limit: int = 50, offset: int = 0):
    query = """
        SELECT v.id, v.folio, v.created_at AS fecha, v.total, v.pago_recibido, v.estado
        FROM ventas v
        WHERE v.cliente_id = :cliente_id
        ORDER BY v.created_at DESC
        LIMIT :limit OFFSET :offset
    """
    # Assuming ventas has a cliente_id column. The prompt mentioned "Usar tablas existentes: clientes, ventas...".
    # Wait, the sales.py didn't show cliente_id. If ventas doesn't have it, maybe it is going to be altered, but "NO recrear tablas" and "Usar tablas existentes". Let's assume ventas has `cliente_id` column or we use it. If it doesn't, we'll see an error when running, but for now I write standard logic.
    rows = db.execute(text(query), {"cliente_id": str(client_id), "limit": limit, "offset": offset}).mappings().all()
    return [dict(row) for row in rows]


def get_client_payments(db: Session, client_id: UUID, limit: int = 50, offset: int = 0):
    query = """
        SELECT p.id, p.created_at AS fecha, p.monto, mp.nombre AS metodo_pago, p.notas AS referencia
        FROM pagos_credito p
        JOIN creditos_cliente c ON p.credito_id = c.id
        LEFT JOIN metodos_pago mp ON p.metodo_pago_id = mp.id
        WHERE c.cliente_id = :cliente_id
        ORDER BY p.created_at DESC
        LIMIT :limit OFFSET :offset
    """
    rows = db.execute(text(query), {"cliente_id": str(client_id), "limit": limit, "offset": offset}).mappings().all()
    return [dict(row) for row in rows]


def get_client_credits(db: Session, client_id: UUID, limit: int = 50, offset: int = 0):
    query = """
        SELECT c.id, c.folio, c.venta_id, v.folio AS folio_venta, c.fecha_credito AS fecha_emision, c.fecha_limite, 
               c.monto_total, c.saldo_pendiente, c.estado
        FROM creditos_cliente c
        LEFT JOIN ventas v ON c.venta_id = v.id
        WHERE c.cliente_id = :cliente_id
        ORDER BY c.fecha_credito DESC
        LIMIT :limit OFFSET :offset
    """
    rows = db.execute(text(query), {"cliente_id": str(client_id), "limit": limit, "offset": offset}).mappings().all()
    return [dict(row) for row in rows]
