import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    codigo_interno: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    codigo_barras: Mapped[str | None] = mapped_column(String(100), unique=True)

    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text())

    departamento_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departamentos.id"))
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categorias.id"))
    subcategoria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subcategorias.id"))
    marca_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("marcas.id"))
    unidad_medida_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("unidades_medida.id"))
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("proveedores.id"))

    tipo_venta: Mapped[str] = mapped_column(String(50), default="pieza")

    costo: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    precio_venta: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    precio_mayoreo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    stock_minimo: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    stock_maximo: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))

    es_granel: Mapped[bool] = mapped_column(Boolean, default=False)
    es_producto_gancho: Mapped[bool] = mapped_column(Boolean, default=False)
    es_producto_utilidad: Mapped[bool] = mapped_column(Boolean, default=False)
    es_perecedero: Mapped[bool] = mapped_column(Boolean, default=False)
    maneja_caducidad: Mapped[bool] = mapped_column(Boolean, default=False)
    maneja_lotes: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_caducidad: Mapped[date | None] = mapped_column(Date)

    imagen_url: Mapped[str | None] = mapped_column(Text())

    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
