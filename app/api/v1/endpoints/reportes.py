import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.schemas.reportes import (
    ReporteGeneralResponse,
    ReporteVentasResponse,
    ReporteProductosResponse,
    ReporteInventarioResponse,
    ReporteCreditosResponse,
    PrediccionesIAResponse
)
from app.services import reportes_service
from app.services.ai_service import get_predictions

router = APIRouter()

def validate_dates(fecha_inicio: datetime, fecha_fin: datetime):
    if fecha_inicio > fecha_fin:
        raise HTTPException(status_code=400, detail="La fecha de inicio no puede ser mayor a la fecha de fin")

@router.get("/general", response_model=ReporteGeneralResponse)
def get_reporte_general(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    sucursal_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    validate_dates(fecha_inicio, fecha_fin)
    return reportes_service.get_reporte_general(db, fecha_inicio, fecha_fin, sucursal_id)

@router.get("/ventas", response_model=ReporteVentasResponse)
def get_reporte_ventas(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    sucursal_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    validate_dates(fecha_inicio, fecha_fin)
    return reportes_service.get_reporte_ventas(db, fecha_inicio, fecha_fin, sucursal_id)

@router.get("/productos", response_model=ReporteProductosResponse)
def get_reporte_productos(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    sucursal_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    validate_dates(fecha_inicio, fecha_fin)
    return reportes_service.get_reporte_productos(db, fecha_inicio, fecha_fin, sucursal_id)

@router.get("/inventario", response_model=ReporteInventarioResponse)
def get_reporte_inventario(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    sucursal_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    validate_dates(fecha_inicio, fecha_fin)
    return reportes_service.get_reporte_inventario(db, fecha_inicio, fecha_fin, sucursal_id)

@router.get("/creditos", response_model=ReporteCreditosResponse)
def get_reporte_creditos(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    sucursal_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    validate_dates(fecha_inicio, fecha_fin)
    return reportes_service.get_reporte_creditos(db, fecha_inicio, fecha_fin, sucursal_id)

@router.get("/predicciones", response_model=PrediccionesIAResponse)
def get_predicciones_ia(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    sucursal_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    validate_dates(fecha_inicio, fecha_fin)
    
    # Recopilar datos clave para la IA (usamos las mismas funciones optimizadas)
    res_general = reportes_service.get_reporte_general(db, fecha_inicio, fecha_fin, sucursal_id)
    res_productos = reportes_service.get_reporte_productos(db, fecha_inicio, fecha_fin, sucursal_id)
    
    ai_data = {
        "ventas_totales_periodo": res_general.get("ventas_periodo"),
        "numero_ventas": res_general.get("numero_ventas"),
        "ticket_promedio": res_general.get("ticket_promedio"),
        "top_productos_vendidos": [{"nombre": p["name"], "cantidad": p["value"]} for p in res_productos.get("chart_top_vendidos", [])],
        "productos_sin_ventas_con_stock": [{"nombre": p["producto"], "stock_actual": p["existencia"]} for p in res_productos.get("tabla_sin_ventas", [])],
        "productos_agotados": [{"nombre": p["producto"], "stock_minimo": p["stock_minimo"]} for p in res_productos.get("tabla_agotados", [])]
    }
    
    predicciones = get_predictions(ai_data)
    return predicciones
