from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, role_guard
from app.core.database import get_db
from app.schemas.client import (
    ClienteCreate,
    ClienteDetailResponse,
    ClienteListResponse,
    ClienteStatusUpdate,
    ClienteUpdate,
    CompraHistorialResponse,
    CreditoActivoResponse,
    PagoHistorialResponse,
)
from app.services import client_service

router = APIRouter(prefix="/clientes", tags=["Clientes"])

CanRead = Depends(role_guard({"dueno", "dueño", "administrador", "encargado", "cajero"}))
CanWrite = Depends(role_guard({"dueno", "dueño", "administrador", "encargado"}))
# Note: Admin/Owner specific validations are inside the service (e.g. for limite_credito)

@router.get("", response_model=List[ClienteListResponse], dependencies=[CanRead])
def list_clients(
    search: Optional[str] = None,
    activo: Optional[bool] = None,
    permite_credito: Optional[bool] = None,
    estado_financiero: Optional[str] = Query(None, description="sin_deuda, con_deuda, credito_excedido, con_creditos_vencidos"),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    return client_service.get_clients(db, search, activo, permite_credito, estado_financiero, limit, offset)


@router.get("/{client_id}", response_model=ClienteDetailResponse, dependencies=[CanRead])
def get_client(client_id: UUID, db: Session = Depends(get_db)):
    return client_service.get_client_by_id(db, client_id)


@router.post("", response_model=ClienteDetailResponse, status_code=status.HTTP_201_CREATED, dependencies=[CanWrite])
def create_client(
    payload: ClienteCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    return client_service.create_client(db, payload, user["id"])


@router.put("/{client_id}", response_model=ClienteDetailResponse, dependencies=[CanWrite])
def update_client(
    client_id: UUID,
    payload: ClienteUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    return client_service.update_client(db, client_id, payload, user["id"], user.get("rol", "encargado"))


@router.patch("/{client_id}/estado", response_model=ClienteDetailResponse, dependencies=[CanWrite])
def change_client_status(
    client_id: UUID,
    payload: ClienteStatusUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    return client_service.change_client_status(db, client_id, payload.activo, user["id"])


@router.get("/{client_id}/resumen", response_model=ClienteDetailResponse, dependencies=[CanRead])
def get_client_resume(client_id: UUID, db: Session = Depends(get_db)):
    return client_service.get_client_by_id(db, client_id)


@router.get("/{client_id}/historial-compras", response_model=List[CompraHistorialResponse], dependencies=[CanRead])
def get_client_purchases(
    client_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    return client_service.get_client_purchases(db, client_id, limit, offset)


@router.get("/{client_id}/historial-pagos", response_model=List[PagoHistorialResponse], dependencies=[CanRead])
def get_client_payments(
    client_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    return client_service.get_client_payments(db, client_id, limit, offset)


@router.get("/{client_id}/creditos", response_model=List[CreditoActivoResponse], dependencies=[CanRead])
def get_client_credits(
    client_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    return client_service.get_client_credits(db, client_id, limit, offset)
