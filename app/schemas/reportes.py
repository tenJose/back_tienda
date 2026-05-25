from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel

# Gráficas Base
class ChartDataPoint(BaseModel):
    name: str
    value: Decimal

# Tablas Base
class MiniVenta(BaseModel):
    folio: str
    cliente: str
    cajero: str
    total: Decimal
    metodo_pago: str
    fecha: datetime
    estado: str

class MiniProductoBajo(BaseModel):
    producto: str
    existencia: Decimal
    stock_minimo: Decimal

class MiniCreditoVencido(BaseModel):
    cliente: str
    folio: Optional[str]
    saldo_pendiente: Decimal
    dias_vencido: int

class MiniClienteDeuda(BaseModel):
    cliente: str
    deuda_total: Decimal

# Reporte General
class ReporteGeneralResponse(BaseModel):
    ventas_periodo: Decimal
    ventas_hoy: Decimal
    numero_ventas: int
    ticket_promedio: Decimal
    ganancia_estimada: Decimal
    saldo_pendiente_creditos: Decimal
    creditos_vencidos: int
    productos_bajo_stock: int
    productos_agotados: int
    
    producto_mas_vendido: Optional[str]
    cliente_mayor_deuda: Optional[str]
    metodo_pago_mas_usado: Optional[str]
    dia_mas_ventas: Optional[str]
    
    chart_ventas_dia: List[ChartDataPoint]
    chart_metodos_pago: List[ChartDataPoint]
    chart_creditos_estado: List[ChartDataPoint]
    chart_productos_vendidos: List[ChartDataPoint]
    
    ultimas_ventas: List[MiniVenta]

# Reporte Ventas
class ReporteVentasResponse(BaseModel):
    total_vendido: Decimal
    numero_ventas: int
    ticket_promedio: Decimal
    ventas_canceladas: int
    
    chart_ventas_dia: List[ChartDataPoint]
    chart_metodos_pago: List[ChartDataPoint]
    chart_ventas_cajero: List[ChartDataPoint]
    
    ultimas_ventas: List[MiniVenta]

# Reporte Productos
class ReporteProductosResponse(BaseModel):
    productos_mas_vendidos: int
    productos_agotados: int
    productos_bajo_stock: int
    productos_sin_ventas: int
    
    chart_top_vendidos: List[ChartDataPoint]
    chart_top_ingreso: List[ChartDataPoint]
    chart_top_ganancia: List[ChartDataPoint]
    
    tabla_bajo_stock: List[MiniProductoBajo]
    tabla_agotados: List[MiniProductoBajo]
    
    class MiniProducto(BaseModel):
        producto: str
        existencia: Decimal
    tabla_sin_ventas: List[MiniProducto]

# Reporte Inventario
class ReporteInventarioResponse(BaseModel):
    inventario_actual: Decimal
    productos_agotados: int
    productos_bajo_stock: int
    valor_estimado_inventario: Decimal
    mermas_periodo: Decimal
    
    chart_inventario_categoria: List[ChartDataPoint]
    chart_productos_criticos: List[ChartDataPoint]
    
    class MiniInventario(BaseModel):
        producto: str
        existencia: Decimal
        stock_minimo: Decimal
        estado: str
        categoria: str
    tabla_inventario: List[MiniInventario]

# Reporte Creditos
class ReporteCreditosResponse(BaseModel):
    saldo_total_pendiente: Decimal
    creditos_pendientes: int
    creditos_parciales: int
    creditos_pagados: int
    creditos_vencidos: int
    abonos_recibidos_periodo: Decimal
    
    chart_creditos_estado: List[ChartDataPoint]
    chart_clientes_deuda: List[ChartDataPoint]
    chart_abonos_dia: List[ChartDataPoint]
    
    tabla_vencidos: List[MiniCreditoVencido]
    tabla_clientes_deuda: List[MiniClienteDeuda]
    
    class MiniCreditoProximo(BaseModel):
        cliente: str
        folio: Optional[str]
        saldo_pendiente: Decimal
        fecha_limite: date
    tabla_proximos_vencer: List[MiniCreditoProximo]

# Predicciones IA
class RecomendacionProducto(BaseModel):
    producto: str
    motivo: str
    accion_sugerida: str

class PrediccionesIAResponse(BaseModel):
    tendencia_ventas: str
    recomendaciones_comprar: List[RecomendacionProducto]
    productos_estancados: List[RecomendacionProducto]
