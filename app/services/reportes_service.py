import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text

def get_reporte_general(db: Session, start_date: datetime, end_date: datetime, sucursal_id: Optional[uuid.UUID] = None) -> dict:
    params = {"start_date": start_date, "end_date": end_date}
    sucursal_filter = ""
    if sucursal_id:
        params["sucursal_id"] = sucursal_id
        sucursal_filter = "AND sucursal_id = :sucursal_id"

    # KPIs Ventas Periodo y Número de Ventas
    res_ventas = db.execute(text(f"""
        SELECT COALESCE(SUM(total), 0) as total, COUNT(id) as count
        FROM ventas 
        WHERE estado = 'completada' AND created_at >= :start_date AND created_at <= :end_date
        {sucursal_filter}
    """), params).fetchone()
    
    ventas_periodo = res_ventas[0] if res_ventas else Decimal(0)
    numero_ventas = res_ventas[1] if res_ventas else 0
    ticket_promedio = ventas_periodo / numero_ventas if numero_ventas > 0 else Decimal(0)

    # Ventas Hoy
    today = datetime.combine(datetime.today(), datetime.min.time())
    res_hoy = db.execute(text(f"""
        SELECT COALESCE(SUM(total), 0)
        FROM ventas 
        WHERE estado = 'completada' AND created_at >= :today
        {sucursal_filter}
    """), {**params, "today": today}).fetchone()
    ventas_hoy = res_hoy[0] if res_hoy else Decimal(0)

    # Ganancia estimada (precio_unitario - costo_unitario) * cantidad
    res_ganancia = db.execute(text(f"""
        SELECT COALESCE(SUM((vd.precio_unitario - vd.costo_unitario) * vd.cantidad), 0)
        FROM venta_detalle vd
        JOIN ventas v ON v.id = vd.venta_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date
        {sucursal_filter.replace('sucursal_id', 'v.sucursal_id')}
    """), params).fetchone()
    ganancia_estimada = res_ganancia[0] if res_ganancia else Decimal(0)

    # Creditos
    res_creditos = db.execute(text(f"""
        SELECT COALESCE(SUM(saldo_pendiente), 0) as saldo,
               COUNT(CASE WHEN estado = 'vencido' THEN 1 END) as vencidos
        FROM creditos_cliente
        WHERE saldo_pendiente > 0
    """)).fetchone()
    saldo_pendiente_creditos = res_creditos[0] if res_creditos else Decimal(0)
    creditos_vencidos = res_creditos[1] if res_creditos else 0

    # Inventario
    inv_filter = ""
    if sucursal_id:
        inv_filter = "AND i.sucursal_id = :sucursal_id"
        
    res_inv = db.execute(text(f"""
        SELECT 
            COUNT(CASE WHEN i.existencia <= 0 THEN 1 END) as agotados,
            COUNT(CASE WHEN i.existencia > 0 AND i.existencia <= p.stock_minimo THEN 1 END) as bajos
        FROM inventarios i
        JOIN productos p ON p.id = i.producto_id
        WHERE p.activo = true {inv_filter}
    """), params).fetchone()
    productos_agotados = res_inv[0] if res_inv else 0
    productos_bajo_stock = res_inv[1] if res_inv else 0

    # Insights rápidos
    producto_mas_vendido = db.execute(text(f"""
        SELECT p.nombre
        FROM venta_detalle vd
        JOIN ventas v ON v.id = vd.venta_id
        JOIN productos p ON p.id = vd.producto_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date
        {sucursal_filter.replace('sucursal_id', 'v.sucursal_id')}
        GROUP BY p.nombre ORDER BY SUM(vd.cantidad) DESC LIMIT 1
    """), params).scalar()

    cliente_mayor_deuda = db.execute(text("""
        SELECT c.nombre
        FROM creditos_cliente cc
        JOIN clientes c ON c.id = cc.cliente_id
        WHERE cc.saldo_pendiente > 0
        GROUP BY c.nombre ORDER BY SUM(cc.saldo_pendiente) DESC LIMIT 1
    """)).scalar()

    metodo_pago_mas_usado = db.execute(text(f"""
        SELECT mp.nombre
        FROM ventas v
        JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date
        {sucursal_filter}
        GROUP BY mp.nombre ORDER BY COUNT(v.id) DESC LIMIT 1
    """), params).scalar()

    dia_mas_ventas = db.execute(text(f"""
        SELECT TO_CHAR(DATE(created_at), 'YYYY-MM-DD')
        FROM ventas
        WHERE estado = 'completada' AND created_at >= :start_date AND created_at <= :end_date
        {sucursal_filter}
        GROUP BY DATE(created_at) ORDER BY SUM(total) DESC LIMIT 1
    """), params).scalar()

    # Gráficas
    chart_ventas_dia = [{"name": str(r[0]), "value": r[1]} for r in db.execute(text(f"""
        SELECT TO_CHAR(DATE(created_at), 'YYYY-MM-DD') as name, SUM(total) as value
        FROM ventas WHERE estado = 'completada' AND created_at >= :start_date AND created_at <= :end_date {sucursal_filter}
        GROUP BY DATE(created_at) ORDER BY DATE(created_at)
    """), params).fetchall()]

    chart_metodos_pago = [{"name": r[0] or 'Efectivo', "value": r[1]} for r in db.execute(text(f"""
        SELECT mp.nombre as name, SUM(v.total) as value
        FROM ventas v
        LEFT JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        GROUP BY mp.nombre
    """), params).fetchall()]

    chart_creditos_estado = [{"name": r[0], "value": r[1]} for r in db.execute(text("""
        SELECT estado as name, SUM(saldo_pendiente) as value
        FROM creditos_cliente WHERE saldo_pendiente > 0 GROUP BY estado
    """)).fetchall()]

    chart_productos_vendidos = [{"name": r[0][:20], "value": r[1]} for r in db.execute(text(f"""
        SELECT p.nombre, SUM(vd.cantidad)
        FROM venta_detalle vd
        JOIN ventas v ON v.id = vd.venta_id
        JOIN productos p ON p.id = vd.producto_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter.replace('sucursal_id', 'v.sucursal_id')}
        GROUP BY p.nombre ORDER BY SUM(vd.cantidad) DESC LIMIT 5
    """), params).fetchall()]

    # Mini Tabla
    ultimas_ventas = [{"folio": r[0], "cliente": r[1] or 'Público General', "cajero": r[2] or 'Sistema', "total": r[3], "metodo_pago": r[4] or 'Efectivo', "fecha": r[5], "estado": r[6]} for r in db.execute(text(f"""
        SELECT v.folio, c.nombre, u.nombre, v.total, mp.nombre, v.created_at, v.estado
        FROM ventas v
        LEFT JOIN clientes c ON c.id = v.cliente_id
        LEFT JOIN usuarios u ON u.id = v.usuario_id
        LEFT JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
        WHERE v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        ORDER BY v.created_at DESC LIMIT 10
    """), params).fetchall()]

    return {
        "ventas_periodo": ventas_periodo,
        "ventas_hoy": ventas_hoy,
        "numero_ventas": numero_ventas,
        "ticket_promedio": ticket_promedio,
        "ganancia_estimada": ganancia_estimada,
        "saldo_pendiente_creditos": saldo_pendiente_creditos,
        "creditos_vencidos": creditos_vencidos,
        "productos_bajo_stock": productos_bajo_stock,
        "productos_agotados": productos_agotados,
        "producto_mas_vendido": producto_mas_vendido,
        "cliente_mayor_deuda": cliente_mayor_deuda,
        "metodo_pago_mas_usado": metodo_pago_mas_usado,
        "dia_mas_ventas": dia_mas_ventas,
        "chart_ventas_dia": chart_ventas_dia,
        "chart_metodos_pago": chart_metodos_pago,
        "chart_creditos_estado": chart_creditos_estado,
        "chart_productos_vendidos": chart_productos_vendidos,
        "ultimas_ventas": ultimas_ventas
    }

def get_reporte_ventas(db: Session, start_date: datetime, end_date: datetime, sucursal_id: Optional[uuid.UUID] = None) -> dict:
    params = {"start_date": start_date, "end_date": end_date}
    sucursal_filter = "AND sucursal_id = :sucursal_id" if sucursal_id else ""

    res_ventas = db.execute(text(f"""
        SELECT COALESCE(SUM(total), 0) as total, COUNT(id) as count
        FROM ventas 
        WHERE estado = 'completada' AND created_at >= :start_date AND created_at <= :end_date {sucursal_filter}
    """), params).fetchone()
    
    total_vendido = res_ventas[0] if res_ventas else Decimal(0)
    numero_ventas = res_ventas[1] if res_ventas else 0
    ticket_promedio = total_vendido / numero_ventas if numero_ventas > 0 else Decimal(0)

    ventas_canceladas = db.execute(text(f"""
        SELECT COUNT(id) FROM ventas 
        WHERE estado = 'cancelada' AND created_at >= :start_date AND created_at <= :end_date {sucursal_filter}
    """), params).scalar() or 0

    chart_ventas_dia = [{"name": str(r[0]), "value": r[1]} for r in db.execute(text(f"""
        SELECT TO_CHAR(DATE(created_at), 'YYYY-MM-DD') as name, SUM(total) as value
        FROM ventas WHERE estado = 'completada' AND created_at >= :start_date AND created_at <= :end_date {sucursal_filter}
        GROUP BY DATE(created_at) ORDER BY DATE(created_at)
    """), params).fetchall()]

    chart_metodos_pago = [{"name": r[0] or 'Efectivo', "value": r[1]} for r in db.execute(text(f"""
        SELECT mp.nombre as name, SUM(v.total) as value
        FROM ventas v LEFT JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        GROUP BY mp.nombre
    """), params).fetchall()]

    chart_ventas_cajero = [{"name": r[0] or 'Sistema', "value": r[1]} for r in db.execute(text(f"""
        SELECT u.nombre as name, SUM(v.total) as value
        FROM ventas v LEFT JOIN usuarios u ON u.id = v.usuario_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        GROUP BY u.nombre
    """), params).fetchall()]

    ultimas_ventas = [{"folio": r[0], "cliente": r[1] or 'Público General', "cajero": r[2] or 'Sistema', "total": r[3], "metodo_pago": r[4] or 'Efectivo', "fecha": r[5], "estado": r[6]} for r in db.execute(text(f"""
        SELECT v.folio, c.nombre, u.nombre, v.total, mp.nombre, v.created_at, v.estado
        FROM ventas v LEFT JOIN clientes c ON c.id = v.cliente_id LEFT JOIN usuarios u ON u.id = v.usuario_id LEFT JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
        WHERE v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        ORDER BY v.created_at DESC LIMIT 15
    """), params).fetchall()]

    return {
        "total_vendido": total_vendido,
        "numero_ventas": numero_ventas,
        "ticket_promedio": ticket_promedio,
        "ventas_canceladas": ventas_canceladas,
        "chart_ventas_dia": chart_ventas_dia,
        "chart_metodos_pago": chart_metodos_pago,
        "chart_ventas_cajero": chart_ventas_cajero,
        "ultimas_ventas": ultimas_ventas
    }

def get_reporte_productos(db: Session, start_date: datetime, end_date: datetime, sucursal_id: Optional[uuid.UUID] = None) -> dict:
    params = {"start_date": start_date, "end_date": end_date}
    sucursal_filter = "AND v.sucursal_id = :sucursal_id" if sucursal_id else ""
    inv_filter = "AND i.sucursal_id = :sucursal_id" if sucursal_id else ""

    productos_mas_vendidos_count = db.execute(text(f"""
        SELECT COUNT(DISTINCT vd.producto_id)
        FROM venta_detalle vd JOIN ventas v ON v.id = vd.venta_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
    """), params).scalar() or 0

    res_inv = db.execute(text(f"""
        SELECT 
            COUNT(CASE WHEN i.existencia <= 0 THEN 1 END),
            COUNT(CASE WHEN i.existencia > 0 AND i.existencia <= p.stock_minimo THEN 1 END)
        FROM inventarios i JOIN productos p ON p.id = i.producto_id WHERE p.activo = true {inv_filter}
    """), params).fetchone()
    productos_agotados = res_inv[0] if res_inv else 0
    productos_bajo_stock = res_inv[1] if res_inv else 0

    productos_sin_ventas = db.execute(text(f"""
        SELECT COUNT(DISTINCT i.producto_id)
        FROM inventarios i JOIN productos p ON p.id = i.producto_id
        WHERE i.existencia > 0 {inv_filter} AND i.producto_id NOT IN (
            SELECT vd.producto_id FROM venta_detalle vd JOIN ventas v ON v.id = vd.venta_id
            WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        )
    """), params).scalar() or 0

    chart_top_vendidos = [{"name": r[0][:20], "value": r[1]} for r in db.execute(text(f"""
        SELECT p.nombre, SUM(vd.cantidad)
        FROM venta_detalle vd JOIN ventas v ON v.id = vd.venta_id JOIN productos p ON p.id = vd.producto_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        GROUP BY p.nombre ORDER BY SUM(vd.cantidad) DESC LIMIT 10
    """), params).fetchall()]

    chart_top_ingreso = [{"name": r[0][:20], "value": r[1]} for r in db.execute(text(f"""
        SELECT p.nombre, SUM(vd.subtotal)
        FROM venta_detalle vd JOIN ventas v ON v.id = vd.venta_id JOIN productos p ON p.id = vd.producto_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        GROUP BY p.nombre ORDER BY SUM(vd.subtotal) DESC LIMIT 10
    """), params).fetchall()]

    chart_top_ganancia = [{"name": r[0][:20], "value": r[1]} for r in db.execute(text(f"""
        SELECT p.nombre, SUM((vd.precio_unitario - vd.costo_unitario) * vd.cantidad)
        FROM venta_detalle vd JOIN ventas v ON v.id = vd.venta_id JOIN productos p ON p.id = vd.producto_id
        WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        GROUP BY p.nombre ORDER BY SUM((vd.precio_unitario - vd.costo_unitario) * vd.cantidad) DESC LIMIT 10
    """), params).fetchall()]

    tabla_bajo_stock = [{"producto": r[0], "existencia": r[1], "stock_minimo": r[2]} for r in db.execute(text(f"""
        SELECT p.nombre, SUM(i.existencia), p.stock_minimo
        FROM inventarios i JOIN productos p ON p.id = i.producto_id
        WHERE p.activo = true AND i.existencia > 0 AND i.existencia <= p.stock_minimo {inv_filter}
        GROUP BY p.nombre, p.stock_minimo ORDER BY SUM(i.existencia) ASC LIMIT 10
    """), params).fetchall()]

    tabla_agotados = [{"producto": r[0], "existencia": r[1], "stock_minimo": r[2]} for r in db.execute(text(f"""
        SELECT p.nombre, SUM(i.existencia), p.stock_minimo
        FROM inventarios i JOIN productos p ON p.id = i.producto_id
        WHERE p.activo = true AND i.existencia <= 0 {inv_filter}
        GROUP BY p.nombre, p.stock_minimo ORDER BY SUM(i.existencia) ASC LIMIT 10
    """), params).fetchall()]

    tabla_sin_ventas = [{"producto": r[0], "existencia": r[1]} for r in db.execute(text(f"""
        SELECT p.nombre, SUM(i.existencia)
        FROM inventarios i JOIN productos p ON p.id = i.producto_id
        WHERE i.existencia > 0 {inv_filter} AND i.producto_id NOT IN (
            SELECT vd.producto_id FROM venta_detalle vd JOIN ventas v ON v.id = vd.venta_id
            WHERE v.estado = 'completada' AND v.created_at >= :start_date AND v.created_at <= :end_date {sucursal_filter}
        )
        GROUP BY p.nombre ORDER BY SUM(i.existencia) DESC LIMIT 10
    """), params).fetchall()]

    return {
        "productos_mas_vendidos": productos_mas_vendidos_count,
        "productos_agotados": productos_agotados,
        "productos_bajo_stock": productos_bajo_stock,
        "productos_sin_ventas": productos_sin_ventas,
        "chart_top_vendidos": chart_top_vendidos,
        "chart_top_ingreso": chart_top_ingreso,
        "chart_top_ganancia": chart_top_ganancia,
        "tabla_bajo_stock": tabla_bajo_stock,
        "tabla_agotados": tabla_agotados,
        "tabla_sin_ventas": tabla_sin_ventas
    }

def get_reporte_inventario(db: Session, start_date: datetime, end_date: datetime, sucursal_id: Optional[uuid.UUID] = None) -> dict:
    params = {"start_date": start_date, "end_date": end_date}
    inv_filter = "AND i.sucursal_id = :sucursal_id" if sucursal_id else ""

    res_inv = db.execute(text(f"""
        SELECT 
            SUM(i.existencia) as total_items,
            COUNT(CASE WHEN i.existencia <= 0 THEN 1 END) as agotados,
            COUNT(CASE WHEN i.existencia > 0 AND i.existencia <= p.stock_minimo THEN 1 END) as bajos,
            SUM(i.existencia * p.costo) as valor
        FROM inventarios i JOIN productos p ON p.id = i.producto_id WHERE p.activo = true {inv_filter}
    """), params).fetchone()
    
    inventario_actual = res_inv[0] if res_inv else Decimal(0)
    productos_agotados = res_inv[1] if res_inv else 0
    productos_bajo_stock = res_inv[2] if res_inv else 0
    valor_estimado_inventario = res_inv[3] if res_inv else Decimal(0)

    mermas_periodo = db.execute(text(f"""
        SELECT COALESCE(SUM(cantidad), 0)
        FROM mermas WHERE created_at >= :start_date AND created_at <= :end_date {inv_filter.replace('i.', '')}
    """), params).scalar() or Decimal(0)

    chart_inventario_categoria = [{"name": str(r[0] or 'Sin categoría'), "value": r[1]} for r in db.execute(text(f"""
        SELECT p.categoria_id, SUM(i.existencia)
        FROM inventarios i JOIN productos p ON p.id = i.producto_id
        WHERE p.activo = true {inv_filter}
        GROUP BY p.categoria_id
    """), params).fetchall()]
    
    # Reemplazar categoria_id con nombre en un sistema real (simplificado aquí por UUID string para demo)

    chart_productos_criticos = [{"name": r[0][:20], "value": r[1]} for r in db.execute(text(f"""
        SELECT p.nombre, SUM(i.existencia)
        FROM inventarios i JOIN productos p ON p.id = i.producto_id
        WHERE p.activo = true AND i.existencia <= p.stock_minimo {inv_filter}
        GROUP BY p.nombre ORDER BY SUM(i.existencia) ASC LIMIT 10
    """), params).fetchall()]

    tabla_inventario = [{"producto": r[0], "existencia": r[1], "stock_minimo": r[2], "estado": "agotado" if r[1]<=0 else ("bajo" if r[1]<=r[2] else "normal"), "categoria": str(r[3] or 'N/A')} for r in db.execute(text(f"""
        SELECT p.nombre, SUM(i.existencia), p.stock_minimo, p.categoria_id
        FROM inventarios i JOIN productos p ON p.id = i.producto_id
        WHERE p.activo = true {inv_filter}
        GROUP BY p.nombre, p.stock_minimo, p.categoria_id ORDER BY SUM(i.existencia) ASC LIMIT 15
    """), params).fetchall()]

    return {
        "inventario_actual": inventario_actual,
        "productos_agotados": productos_agotados,
        "productos_bajo_stock": productos_bajo_stock,
        "valor_estimado_inventario": valor_estimado_inventario,
        "mermas_periodo": mermas_periodo,
        "chart_inventario_categoria": chart_inventario_categoria,
        "chart_productos_criticos": chart_productos_criticos,
        "tabla_inventario": tabla_inventario
    }

def get_reporte_creditos(db: Session, start_date: datetime, end_date: datetime, sucursal_id: Optional[uuid.UUID] = None) -> dict:
    params = {"start_date": start_date, "end_date": end_date}
    
    res_cred = db.execute(text("""
        SELECT 
            SUM(saldo_pendiente) as saldo,
            COUNT(CASE WHEN estado = 'pendiente' THEN 1 END),
            COUNT(CASE WHEN estado = 'parcial' THEN 1 END),
            COUNT(CASE WHEN estado = 'pagado' THEN 1 END),
            COUNT(CASE WHEN estado = 'vencido' THEN 1 END)
        FROM creditos_cliente
    """)).fetchone()

    saldo_total_pendiente = res_cred[0] if res_cred else Decimal(0)
    creditos_pendientes = res_cred[1] if res_cred else 0
    creditos_parciales = res_cred[2] if res_cred else 0
    creditos_pagados = res_cred[3] if res_cred else 0
    creditos_vencidos = res_cred[4] if res_cred else 0

    abonos_recibidos_periodo = db.execute(text("""
        SELECT COALESCE(SUM(monto), 0)
        FROM pagos_credito WHERE created_at >= :start_date AND created_at <= :end_date
    """), params).scalar() or Decimal(0)

    chart_creditos_estado = [{"name": r[0], "value": r[1]} for r in db.execute(text("""
        SELECT estado as name, COUNT(id) as value
        FROM creditos_cliente GROUP BY estado
    """)).fetchall()]

    chart_clientes_deuda = [{"name": r[0], "value": r[1]} for r in db.execute(text("""
        SELECT c.nombre, SUM(cc.saldo_pendiente)
        FROM creditos_cliente cc JOIN clientes c ON c.id = cc.cliente_id
        WHERE cc.saldo_pendiente > 0
        GROUP BY c.nombre ORDER BY SUM(cc.saldo_pendiente) DESC LIMIT 10
    """)).fetchall()]

    chart_abonos_dia = [{"name": str(r[0]), "value": r[1]} for r in db.execute(text("""
        SELECT TO_CHAR(DATE(created_at), 'YYYY-MM-DD') as name, SUM(monto) as value
        FROM pagos_credito WHERE created_at >= :start_date AND created_at <= :end_date
        GROUP BY DATE(created_at) ORDER BY DATE(created_at)
    """), params).fetchall()]

    tabla_vencidos = [{"cliente": r[0], "folio": r[1], "saldo_pendiente": r[2], "dias_vencido": r[3] or 0} for r in db.execute(text("""
        SELECT c.nombre, cc.folio, cc.saldo_pendiente, EXTRACT(DAY FROM (NOW() - cc.fecha_limite))
        FROM creditos_cliente cc JOIN clientes c ON c.id = cc.cliente_id
        WHERE cc.estado = 'vencido' AND cc.saldo_pendiente > 0
        ORDER BY cc.fecha_limite ASC LIMIT 10
    """)).fetchall()]

    tabla_clientes_deuda = [{"cliente": r[0], "deuda_total": r[1]} for r in db.execute(text("""
        SELECT c.nombre, SUM(cc.saldo_pendiente)
        FROM creditos_cliente cc JOIN clientes c ON c.id = cc.cliente_id
        WHERE cc.saldo_pendiente > 0
        GROUP BY c.nombre ORDER BY SUM(cc.saldo_pendiente) DESC LIMIT 10
    """)).fetchall()]

    tabla_proximos_vencer = [{"cliente": r[0], "folio": r[1], "saldo_pendiente": r[2], "fecha_limite": r[3]} for r in db.execute(text("""
        SELECT c.nombre, cc.folio, cc.saldo_pendiente, cc.fecha_limite
        FROM creditos_cliente cc JOIN clientes c ON c.id = cc.cliente_id
        WHERE cc.saldo_pendiente > 0 AND cc.fecha_limite >= CURRENT_DATE AND cc.fecha_limite <= CURRENT_DATE + INTERVAL '7 days'
        ORDER BY cc.fecha_limite ASC LIMIT 10
    """)).fetchall()]

    return {
        "saldo_total_pendiente": saldo_total_pendiente,
        "creditos_pendientes": creditos_pendientes,
        "creditos_parciales": creditos_parciales,
        "creditos_pagados": creditos_pagados,
        "creditos_vencidos": creditos_vencidos,
        "abonos_recibidos_periodo": abonos_recibidos_periodo,
        "chart_creditos_estado": chart_creditos_estado,
        "chart_clientes_deuda": chart_clientes_deuda,
        "chart_abonos_dia": chart_abonos_dia,
        "tabla_vencidos": tabla_vencidos,
        "tabla_clientes_deuda": tabla_clientes_deuda,
        "tabla_proximos_vencer": tabla_proximos_vencer
    }
