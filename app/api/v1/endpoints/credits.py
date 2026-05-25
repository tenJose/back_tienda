from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, role_guard
from app.core.database import get_db
from app.schemas.credit import (
    AbonoCreate,
    CreditoCreate,
    CreditoDetalleResponse,
    CreditoPaginatedResponse,
    CreditoResponse,
    CreditoStatusUpdate,
    CreditoUpdate,
    HistorialPagoResponse,
)
from app.services import credit_service

router = APIRouter(prefix="/creditos", tags=["Creditos"])

CanRead = Depends(role_guard({"dueno", "dueño", "administrador", "encargado", "cajero"}))
CanWrite = Depends(role_guard({"dueno", "dueño", "administrador", "encargado"}))
CanPay = Depends(role_guard({"dueno", "dueño", "administrador", "encargado", "cajero"}))


@router.get("", response_model=CreditoPaginatedResponse, dependencies=[CanRead])
def list_creditos(
    search: Optional[str] = None,
    cliente_id: Optional[UUID] = None,
    estado: Optional[str] = None,
    vencido: Optional[bool] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    limit: int = 20,
    page: int = 1,
    db: Session = Depends(get_db)
):
    return credit_service.get_creditos(
        db, search, cliente_id, estado, vencido, fecha_desde, fecha_hasta, limit, page
    )


@router.post("", response_model=CreditoResponse, status_code=status.HTTP_201_CREATED, dependencies=[CanWrite])
def create_credito(
    payload: CreditoCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    return credit_service.create_credito(db, payload, user["id"], user.get("rol_nombre", "encargado"))


@router.get("/{credito_id}", response_model=CreditoDetalleResponse, dependencies=[CanRead])
def get_credito(credito_id: UUID, db: Session = Depends(get_db)):
    credito = credit_service.get_credito_by_id(db, credito_id)
    pagos = credit_service.get_historial_pagos(db, credito_id)
    return {**credito, "pagos": pagos}


@router.put("/{credito_id}", response_model=CreditoResponse, dependencies=[CanWrite])
def update_credito(
    credito_id: UUID,
    payload: CreditoUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    return credit_service.update_credito(db, credito_id, payload, user["id"])


@router.post("/{credito_id}/abonos", response_model=CreditoResponse, dependencies=[CanPay])
def registrar_abono(
    credito_id: UUID,
    payload: AbonoCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    return credit_service.registrar_abono(db, credito_id, payload, user["id"])


@router.get("/{credito_id}/pagos", response_model=List[HistorialPagoResponse], dependencies=[CanRead])
def get_pagos(credito_id: UUID, db: Session = Depends(get_db)):
    return credit_service.get_historial_pagos(db, credito_id)
