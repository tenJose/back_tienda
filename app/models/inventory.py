import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Inventario(Base):
    __tablename__ = "inventarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sucursales.id"))
    existencia: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    reservado: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sucursales.id"))
    tipo_movimiento: Mapped[str] = mapped_column(String(50), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    stock_anterior: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    stock_nuevo: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    referencia_tipo: Mapped[str | None] = mapped_column(String(50))
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    motivo: Mapped[str | None] = mapped_column(Text())
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class HistorialPrecios(Base):
    __tablename__ = "historial_precios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    precio_anterior: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    precio_nuevo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    costo_anterior: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    costo_nuevo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    motivo: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
