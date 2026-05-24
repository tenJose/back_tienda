from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.catalogs import Categoria, Departamento, Marca, Proveedor, UnidadMedida
from app.schemas.catalog import OptionItem
from app.services.product_service import list_catalog_options, list_categories, list_subcategories

router = APIRouter(prefix="/catalogs", tags=["Catalogos"])


@router.get("/departamentos", response_model=list[OptionItem])
def departamentos(db: Session = Depends(get_db)):
    rows = list_catalog_options(db, Departamento)
    return [OptionItem.model_validate(r) for r in rows]


@router.get("/categorias", response_model=list[OptionItem])
def categorias(departamento_id: UUID | None = None, db: Session = Depends(get_db)):
    rows = list_categories(db, departamento_id)
    return [OptionItem.model_validate(r) for r in rows]


@router.get("/subcategorias", response_model=list[OptionItem])
def subcategorias(categoria_id: UUID | None = None, db: Session = Depends(get_db)):
    rows = list_subcategories(db, categoria_id)
    return [OptionItem.model_validate(r) for r in rows]


@router.get("/marcas", response_model=list[OptionItem])
def marcas(db: Session = Depends(get_db)):
    rows = list_catalog_options(db, Marca)
    return [OptionItem.model_validate(r) for r in rows]


@router.get("/unidades", response_model=list[OptionItem])
def unidades(db: Session = Depends(get_db)):
    rows = list_catalog_options(db, UnidadMedida)
    return [OptionItem.model_validate(r) for r in rows]


@router.get("/proveedores", response_model=list[OptionItem])
def proveedores(db: Session = Depends(get_db)):
    rows = list_catalog_options(db, Proveedor)
    return [OptionItem.model_validate(r) for r in rows]


@router.get("/metodos-pago")
def metodos_pago(db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT id, nombre FROM metodos_pago WHERE activo = true ORDER BY nombre")).mappings().all()
    return [{"id": str(row["id"]), "nombre": row["nombre"]} for row in rows]
