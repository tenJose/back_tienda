from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CreditoCreate(BaseModel):
    cliente_id: UUID
    venta_id: Optional[UUID] = None
    monto_total: Decimal = Field(gt=0, decimal_places=2)
    fecha_limite: Optional[date] = None
    notas: Optional[str] = None


class CreditoUpdate(BaseModel):
    fecha_limite: Optional[date] = None
    notas: Optional[str] = None


class CreditoStatusUpdate(BaseModel):
    estado: str


class AbonoCreate(BaseModel):
    monto: Decimal = Field(gt=0, decimal_places=2)
    metodo_pago_id: Optional[UUID] = None
    notas: Optional[str] = None


class CreditoResponse(BaseModel):
    id: UUID
    folio: Optional[str] = None
    cliente_id: UUID
    cliente_nombre: str
    cliente_telefono: Optional[str] = None
    venta_id: Optional[UUID] = None
    folio_venta: Optional[str] = None
    monto_total: Decimal
    monto_pagado: Decimal
    saldo_pendiente: Decimal
    porcentaje_pagado: Decimal
    estado: str
    estado_visual: str
    fecha_credito: datetime
    fecha_limite: Optional[date] = None
    dias_atraso: int
    notas: Optional[str] = None


class CreditoSummaryResponse(BaseModel):
    total_creditos: int
    creditos_activos: int
    pendientes: int
    parciales: int
    pagados: int
    vencidos: int
    saldo_pendiente_total: Decimal
    monto_pagado_total: Decimal
    abonado_mes_actual: Decimal


class CreditoPaginatedResponse(BaseModel):
    items: List[CreditoResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    summary: CreditoSummaryResponse


class HistorialPagoResponse(BaseModel):
    id: UUID
    credito_id: UUID
    usuario_id: Optional[UUID] = None
    usuario_nombre: Optional[str] = None
    monto: Decimal
    metodo_pago: Optional[str] = None
    referencia: Optional[str] = None
    notas: Optional[str] = None
    created_at: datetime


class CreditoDetalleResponse(CreditoResponse):
    pagos: List[HistorialPagoResponse] = []
