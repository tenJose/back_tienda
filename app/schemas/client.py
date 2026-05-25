from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


class ClienteBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    telefono: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    permite_credito: bool = False
    limite_credito: Decimal = Field(default=Decimal("0"), ge=0)
    activo: bool = True


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=150)
    telefono: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    permite_credito: Optional[bool] = None
    limite_credito: Optional[Decimal] = Field(None, ge=0)


class ClienteStatusUpdate(BaseModel):
    activo: bool


class ClienteListResponse(ClienteBase):
    id: UUID
    deuda_actual: Decimal = Decimal("0")
    credito_disponible: Decimal = Decimal("0")
    estado_financiero: str = "sin_deuda"
    created_at: datetime
    updated_at: datetime


class ClienteDetailResponse(ClienteListResponse):
    creditos_activos: int = 0
    tiene_creditos_vencidos: bool = False


class CompraHistorialResponse(BaseModel):
    id: UUID
    folio: str
    fecha: datetime
    total: Decimal
    pago_recibido: Decimal
    estado: str


class PagoHistorialResponse(BaseModel):
    id: UUID
    fecha: datetime
    monto: Decimal
    metodo_pago: Optional[str] = "Efectivo"
    referencia: Optional[str] = None

class CreditoActivoResponse(BaseModel):
    id: UUID
    folio: Optional[str] = None
    venta_id: Optional[UUID] = None
    folio_venta: Optional[str] = None
    fecha_emision: datetime
    fecha_limite: Optional[datetime]
    monto_total: Decimal
    saldo_pendiente: Decimal
    estado: str
