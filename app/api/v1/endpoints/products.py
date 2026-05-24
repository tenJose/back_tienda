from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import CanManageProducts, CanViewProducts, get_current_user
from app.core.database import get_db
from app.schemas.product import (
    InventoryAdjustRequest,
    ProductCreate,
    ProductCreateResponse,
    ProductDetail,
    ProductListItem,
    ProductStatusUpdate,
    ProductUpdate,
)
from app.services.product_service import (
    adjust_inventory,
    create_product,
    delete_product,
    get_product_by_barcode,
    list_products,
    product_detail,
    update_product,
    update_status,
)

router = APIRouter(prefix="/products", tags=["Productos"])


@router.get("", response_model=list[ProductListItem], dependencies=[CanViewProducts])
def get_products(
    q: str | None = Query(default=None, description="Busca por nombre, codigo interno, barras, categoria o marca"),
    departamento_id: UUID | None = None,
    categoria_id: UUID | None = None,
    activo: bool | None = None,
    bajo_stock: bool = False,
    granel: bool | None = None,
    perecedero: bool | None = None,
    db: Session = Depends(get_db),
):
    return list_products(
        db,
        q=q,
        departamento_id=departamento_id,
        categoria_id=categoria_id,
        activo=activo,
        bajo_stock=bajo_stock,
        granel=granel,
        perecedero=perecedero,
    )


@router.post("", response_model=ProductCreateResponse, dependencies=[CanManageProducts])
def post_product(payload: ProductCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    permisos = set(user.get("permisos") or [])
    return create_product(
        db,
        payload,
        user_id=user.get("id"),
        can_sell_below_cost="productos.vender_bajo_costo" in permisos,
    )


@router.put("/{product_id}", dependencies=[CanManageProducts])
def put_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    role = user.get("rol")
    permisos = set(user.get("permisos") or [])
    can_change_prices = role in {"dueno", "dueño", "administrador"} or "productos.cambiar_precio" in permisos
    product = update_product(
        db,
        product_id,
        payload,
        user_id=user.get("id"),
        can_change_prices=can_change_prices,
        can_sell_below_cost="productos.vender_bajo_costo" in permisos,
    )
    return {"id": product.id, "nombre": product.nombre, "activo": product.activo}


@router.patch("/{product_id}/status", dependencies=[CanManageProducts])
def patch_status(product_id: UUID, payload: ProductStatusUpdate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    product = update_status(db, product_id, payload.activo, user_id=user.get("id"))
    return {"id": product.id, "activo": product.activo}


@router.post("/{product_id}/adjust-inventory", dependencies=[CanManageProducts])
def post_adjust_inventory(product_id: UUID, payload: InventoryAdjustRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return adjust_inventory(db, product_id, payload, user_id=user.get("id"))


@router.get("/barcode/{codigo}", response_model=ProductListItem, dependencies=[CanViewProducts])
def get_product_barcode(codigo: str, db: Session = Depends(get_db)):
    product = get_product_by_barcode(db, codigo)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return product


@router.delete("/{product_id}", dependencies=[CanManageProducts])
def delete_product_endpoint(product_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    product = delete_product(db, product_id, user_id=user.get("id"))
    return {"id": str(product.id), "deleted": True}


@router.get("/{product_id}", response_model=ProductDetail, dependencies=[CanViewProducts])
def get_product_detail(product_id: UUID, db: Session = Depends(get_db)):
    return product_detail(db, product_id)
