from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=180)
    departamento_id: UUID | None = None
    categoria_id: UUID | None = None
    subcategoria_id: UUID | None = None
    marca_id: UUID | None = None
    unidad_medida_id: UUID | None = None
    tipo_venta: str = Field(default="pieza", max_length=50)
    codigo_barras: str | None = Field(default=None, max_length=100)

    costo: Decimal = Field(default=Decimal("0"), ge=0)
    precio_venta: Decimal = Field(default=Decimal("0"), ge=0)
    precio_mayoreo: Decimal | None = Field(default=None, ge=0)

    stock_minimo: Decimal = Field(default=Decimal("0"), ge=0)
    stock_maximo: Decimal | None = Field(default=None, ge=0)

    es_granel: bool = False
    es_producto_gancho: bool = False
    es_producto_utilidad: bool = False
    es_perecedero: bool = False
    maneja_caducidad: bool = False
    maneja_lotes: bool = False
    fecha_caducidad: date | None = None

    activo: bool = True
    descripcion: str | None = None
    imagen_url: str | None = None
    proveedor_id: UUID | None = None


class ProductCreate(ProductBase):
    stock_inicial: Decimal = Field(default=Decimal("0"), ge=0)
    sucursal_id: UUID | None = None


class ProductUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=180)
    codigo_barras: str | None = Field(default=None, max_length=100)
    departamento_id: UUID | None = None
    categoria_id: UUID | None = None
    subcategoria_id: UUID | None = None
    marca_id: UUID | None = None
    unidad_medida_id: UUID | None = None
    tipo_venta: str | None = Field(default=None, max_length=50)
    precio_venta: Decimal | None = Field(default=None, ge=0)
    precio_mayoreo: Decimal | None = Field(default=None, ge=0)
    costo: Decimal | None = Field(default=None, ge=0)
    stock_minimo: Decimal | None = Field(default=None, ge=0)
    stock_maximo: Decimal | None = Field(default=None, ge=0)
    proveedor_id: UUID | None = None
    fecha_caducidad: date | None = None
    activo: bool | None = None
    descripcion: str | None = None
    imagen_url: str | None = None
    es_granel: bool | None = None
    es_producto_gancho: bool | None = None
    es_producto_utilidad: bool | None = None
    es_perecedero: bool | None = None
    maneja_caducidad: bool | None = None
    maneja_lotes: bool | None = None


class ProductStatusUpdate(BaseModel):
    activo: bool


class InventoryAdjustRequest(BaseModel):
    sucursal_id: UUID | None = None
    cantidad: Decimal = Field(gt=0)
    motivo: str = Field(min_length=3, max_length=300)
    tipo_movimiento: str = Field(default="ajuste", max_length=50)


class ProductListItem(BaseModel):
    id: UUID
    codigo_interno: str
    codigo_barras: str | None
    nombre: str
    departamento: str | None
    categoria: str | None
    marca: str | None
    unidad: str | None
    tipo_venta: str
    costo: Decimal
    precio_venta: Decimal
    stock: Decimal
    stock_minimo: Decimal
    activo: bool
    es_granel: bool
    es_perecedero: bool
    imagen_url: str | None = None
    proveedor_id: UUID | None = None
    proveedor_nombre: str | None = None
    fecha_caducidad: date | None = None


class ProductDetail(BaseModel):
    id: UUID
    codigo_interno: str
    codigo_barras: str | None
    nombre: str
    descripcion: str | None
    categoria: str | None
    departamento: str | None
    marca: str | None
    unidad: str | None
    tipo_venta: str
    costo: Decimal
    precio_venta: Decimal
    precio_mayoreo: Decimal | None = None
    margen: Decimal
    stock_actual: Decimal
    stock_minimo: Decimal
    stock_maximo: Decimal | None = None
    activo: bool
    departamento_id: UUID | None = None
    categoria_id: UUID | None = None
    subcategoria_id: UUID | None = None
    marca_id: UUID | None = None
    unidad_medida_id: UUID | None = None
    es_granel: bool = False
    es_producto_gancho: bool = False
    es_producto_utilidad: bool = False
    es_perecedero: bool = False
    maneja_caducidad: bool = False
    maneja_lotes: bool = False
    imagen_url: str | None = None
    proveedor_id: UUID | None = None
    proveedor_nombre: str | None = None
    fecha_caducidad: date | None = None
    historial_movimientos: list[dict]
    historial_precios: list[dict]
    ultimas_ventas: list[dict]
    ultimas_compras: list[dict]


class ProductCreateResponse(BaseModel):
    id: UUID
    codigo_interno: str
    created_at: datetime
