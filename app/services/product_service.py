from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.models.catalogs import Categoria, Departamento, Marca, Proveedor, Subcategoria, UnidadMedida
from app.models.inventory import HistorialPrecios, Inventario, MovimientoInventario
from app.models.products import Producto
from app.schemas.product import (
    InventoryAdjustRequest,
    ProductCreate,
    ProductCreateResponse,
    ProductDetail,
    ProductListItem,
    ProductUpdate,
)


def _next_internal_code(db: Session, categoria_id: UUID | None) -> str:
    prefijo = "PRO"
    if categoria_id:
        categoria = db.get(Categoria, categoria_id)
        if categoria and categoria.prefijo_codigo:
            prefijo = categoria.prefijo_codigo.upper()

    # Bloquea la fila de folios para evitar colisiones de codigo interno.
    result = db.execute(
        text(
            """
            INSERT INTO folios (id, tipo, prefijo, ultimo_numero, longitud)
            VALUES (gen_random_uuid(), 'producto', :prefijo, 0, 4)
            ON CONFLICT (tipo) DO UPDATE SET prefijo = EXCLUDED.prefijo
            RETURNING id
            """
        ),
        {"prefijo": prefijo},
    )
    result.scalar_one_or_none()

    row = db.execute(
        text(
            """
            UPDATE folios
            SET ultimo_numero = ultimo_numero + 1,
                prefijo = :prefijo,
                updated_at = now()
            WHERE tipo = 'producto'
            RETURNING ultimo_numero, longitud, prefijo
            """
        ),
        {"prefijo": prefijo},
    ).mappings().one()

    return f"{row['prefijo']}-{int(row['ultimo_numero']):0{int(row['longitud'])}d}"


def list_products(
    db: Session,
    q: str | None,
    departamento_id: UUID | None,
    categoria_id: UUID | None,
    activo: bool | None,
    bajo_stock: bool,
    granel: bool | None,
    perecedero: bool | None,
) -> list[ProductListItem]:
    stock_expr = func.coalesce(func.sum(Inventario.existencia), 0)

    query = (
        select(
            Producto.id,
            Producto.codigo_interno,
            Producto.codigo_barras,
            Producto.nombre,
            Departamento.nombre.label("departamento"),
            Categoria.nombre.label("categoria"),
            Marca.nombre.label("marca"),
            UnidadMedida.abreviatura.label("unidad"),
            Producto.tipo_venta,
            Producto.costo,
            Producto.precio_venta,
            stock_expr.label("stock"),
            Producto.stock_minimo,
            Producto.activo,
            Producto.es_granel,
            Producto.es_perecedero,
            Producto.imagen_url,
            Producto.proveedor_id,
            Proveedor.nombre.label("proveedor_nombre"),
            Producto.fecha_caducidad,
        )
        .select_from(Producto)
        .outerjoin(Departamento, Departamento.id == Producto.departamento_id)
        .outerjoin(Categoria, Categoria.id == Producto.categoria_id)
        .outerjoin(Marca, Marca.id == Producto.marca_id)
        .outerjoin(UnidadMedida, UnidadMedida.id == Producto.unidad_medida_id)
        .outerjoin(Proveedor, Proveedor.id == Producto.proveedor_id)
        .outerjoin(Inventario, Inventario.producto_id == Producto.id)
        .group_by(
            Producto.id,
            Departamento.nombre,
            Categoria.nombre,
            Marca.nombre,
            UnidadMedida.abreviatura,
            Proveedor.nombre,
        )
        .order_by(Producto.nombre.asc())
    )

    filters = []
    if q:
        like_value = f"%{q.strip()}%"
        filters.append(
            or_(
                Producto.nombre.ilike(like_value),
                Producto.codigo_interno.ilike(like_value),
                Producto.codigo_barras.ilike(like_value),
                Categoria.nombre.ilike(like_value),
                Marca.nombre.ilike(like_value),
            )
        )
    if departamento_id:
        filters.append(Producto.departamento_id == departamento_id)
    if categoria_id:
        filters.append(Producto.categoria_id == categoria_id)
    if activo is not None:
        filters.append(Producto.activo == activo)
    if granel is not None:
        filters.append(Producto.es_granel == granel)
    if perecedero is not None:
        filters.append(Producto.es_perecedero == perecedero)

    if filters:
        query = query.where(and_(*filters))

    if bajo_stock:
        query = query.having(stock_expr <= Producto.stock_minimo)

    rows = db.execute(query).mappings().all()
    return [ProductListItem.model_validate(dict(row)) for row in rows]


def create_product(db: Session, payload: ProductCreate, user_id: UUID | None, can_sell_below_cost: bool = False) -> ProductCreateResponse:
    if payload.precio_venta < payload.costo and not can_sell_below_cost:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El precio de venta no puede ser menor al costo")
    codigo_interno = _next_internal_code(db, payload.categoria_id)

    product = Producto(
        codigo_interno=codigo_interno,
        codigo_barras=payload.codigo_barras,
        nombre=payload.nombre,
        descripcion=payload.descripcion,
        departamento_id=payload.departamento_id,
        categoria_id=payload.categoria_id,
        subcategoria_id=payload.subcategoria_id,
        marca_id=payload.marca_id,
        unidad_medida_id=payload.unidad_medida_id,
        tipo_venta=payload.tipo_venta,
        costo=payload.costo,
        precio_venta=payload.precio_venta,
        precio_mayoreo=payload.precio_mayoreo,
        stock_minimo=payload.stock_minimo,
        stock_maximo=payload.stock_maximo,
        es_granel=payload.es_granel,
        es_producto_gancho=payload.es_producto_gancho,
        es_producto_utilidad=payload.es_producto_utilidad,
        es_perecedero=payload.es_perecedero,
        maneja_caducidad=payload.maneja_caducidad,
        maneja_lotes=payload.maneja_lotes,
        imagen_url=payload.imagen_url,
        activo=payload.activo,
        created_by=user_id,
        updated_by=user_id,
        proveedor_id=payload.proveedor_id,
        fecha_caducidad=payload.fecha_caducidad,
    )
    db.add(product)
    db.flush()

    inv = Inventario(
        producto_id=product.id,
        sucursal_id=payload.sucursal_id,
        existencia=payload.stock_inicial,
        reservado=Decimal("0"),
    )
    db.add(inv)

    mov = MovimientoInventario(
        producto_id=product.id,
        sucursal_id=payload.sucursal_id,
        tipo_movimiento="entrada_inicial",
        cantidad=payload.stock_inicial,
        stock_anterior=Decimal("0"),
        stock_nuevo=payload.stock_inicial,
        motivo="Carga inicial de producto",
        usuario_id=user_id,
    )
    db.add(mov)
    db.commit()
    db.refresh(product)

    return ProductCreateResponse(id=product.id, codigo_interno=product.codigo_interno, created_at=product.created_at)


def update_product(db: Session, product_id: UUID, payload: ProductUpdate, user_id: UUID | None, can_change_prices: bool, can_sell_below_cost: bool = False) -> Producto:
    product = db.get(Producto, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    data = payload.model_dump(exclude_unset=True)
    if not can_change_prices and ("precio_venta" in data or "costo" in data):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu rol no puede cambiar costos/precios")
    # data.pop("proveedor_id", None)

    previous_costo = product.costo
    previous_precio = product.precio_venta

    for key, value in data.items():
        setattr(product, key, value)

    if product.precio_venta < product.costo and not can_sell_below_cost:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El precio de venta no puede ser menor al costo")
    product.updated_by = user_id

    if "precio_venta" in data or "costo" in data:
        history = HistorialPrecios(
            producto_id=product.id,
            precio_anterior=previous_precio,
            precio_nuevo=product.precio_venta,
            costo_anterior=previous_costo,
            costo_nuevo=product.costo,
            usuario_id=user_id,
            motivo="Actualizacion desde formulario de edicion",
        )
        db.add(history)

    db.commit()
    db.refresh(product)
    return product


def update_status(db: Session, product_id: UUID, activo: bool, user_id: UUID | None) -> Producto:
    product = db.get(Producto, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    previous = {"activo": product.activo}
    product.activo = activo
    product.updated_by = user_id
    db.execute(
        text(
            """
            INSERT INTO auditoria (usuario_id, accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos, descripcion)
            VALUES (:usuario_id, :accion, 'productos', :registro_id, CAST(:anteriores AS jsonb), CAST(:nuevos AS jsonb), :descripcion)
            """
        ),
        {
            "usuario_id": str(user_id) if user_id else None,
            "accion": "activar_producto" if activo else "inactivar_producto",
            "registro_id": str(product_id),
            "anteriores": f'{{"activo": {str(previous["activo"]).lower()}}}',
            "nuevos": f'{{"activo": {str(activo).lower()}}}',
            "descripcion": f"Producto {product.nombre} {'activado' if activo else 'inactivado'}",
        },
    )
    db.commit()
    db.refresh(product)
    return product


def adjust_inventory(db: Session, product_id: UUID, payload: InventoryAdjustRequest, user_id: UUID | None) -> dict:
    product = db.get(Producto, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    query = select(Inventario).where(Inventario.producto_id == product_id)
    if payload.sucursal_id is None:
        query = query.where(Inventario.sucursal_id.is_(None))
    else:
        query = query.where(Inventario.sucursal_id == payload.sucursal_id)
    inventory = db.execute(query).scalar_one_or_none()

    if not inventory:
        inventory = Inventario(producto_id=product_id, sucursal_id=payload.sucursal_id, existencia=Decimal("0"), reservado=Decimal("0"))
        db.add(inventory)
        db.flush()

    stock_anterior = inventory.existencia
    if payload.tipo_movimiento in {"salida", "merma"}:
        signed_quantity = -payload.cantidad
    elif payload.tipo_movimiento == "correccion":
        signed_quantity = payload.cantidad - stock_anterior
    else:
        signed_quantity = payload.cantidad
    stock_nuevo = stock_anterior + signed_quantity
    if stock_nuevo < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El ajuste deja stock negativo")

    inventory.existencia = stock_nuevo
    movement = MovimientoInventario(
        producto_id=product_id,
        sucursal_id=payload.sucursal_id,
        tipo_movimiento=payload.tipo_movimiento,
        cantidad=signed_quantity,
        stock_anterior=stock_anterior,
        stock_nuevo=stock_nuevo,
        motivo=payload.motivo,
        usuario_id=user_id,
    )
    db.add(movement)
    if payload.tipo_movimiento == "merma":
        db.execute(
            text(
                """
                INSERT INTO mermas (producto_id, sucursal_id, cantidad, motivo, descripcion, usuario_id)
                VALUES (:producto_id, :sucursal_id, :cantidad, :motivo, :descripcion, :usuario_id)
                """
            ),
            {
                "producto_id": str(product_id),
                "sucursal_id": str(payload.sucursal_id) if payload.sucursal_id else None,
                "cantidad": str(payload.cantidad),
                "motivo": payload.motivo,
                "descripcion": "Merma registrada desde ajuste de inventario",
                "usuario_id": str(user_id) if user_id else None,
            },
        )
    db.commit()

    return {
        "producto_id": str(product_id),
        "stock_anterior": str(stock_anterior),
        "stock_nuevo": str(stock_nuevo),
    }


def product_detail(db: Session, product_id: UUID) -> ProductDetail:
    row = db.execute(
        select(
            Producto,
            Categoria.nombre.label("categoria"),
            Departamento.nombre.label("departamento"),
            Marca.nombre.label("marca"),
            UnidadMedida.abreviatura.label("unidad"),
            func.coalesce(func.sum(Inventario.existencia), 0).label("stock_actual"),
            Proveedor.nombre.label("proveedor_nombre"),
        )
        .outerjoin(Categoria, Categoria.id == Producto.categoria_id)
        .outerjoin(Departamento, Departamento.id == Producto.departamento_id)
        .outerjoin(Marca, Marca.id == Producto.marca_id)
        .outerjoin(UnidadMedida, UnidadMedida.id == Producto.unidad_medida_id)
        .outerjoin(Proveedor, Proveedor.id == Producto.proveedor_id)
        .outerjoin(Inventario, Inventario.producto_id == Producto.id)
        .where(Producto.id == product_id)
        .group_by(Producto.id, Categoria.nombre, Departamento.nombre, Marca.nombre, UnidadMedida.abreviatura, Proveedor.nombre)
    ).mappings().one_or_none()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    product = row["Producto"]

    movs = db.execute(
        select(MovimientoInventario)
        .where(MovimientoInventario.producto_id == product_id)
        .order_by(MovimientoInventario.created_at.desc())
        .limit(20)
    ).scalars().all()

    prices = db.execute(
        select(HistorialPrecios)
        .where(HistorialPrecios.producto_id == product_id)
        .order_by(HistorialPrecios.created_at.desc())
        .limit(20)
    ).scalars().all()

    compras = db.execute(
        text(
            """
            SELECT c.folio, cd.cantidad, cd.costo_unitario, c.created_at
            FROM compra_detalle cd
            JOIN compras c ON c.id = cd.compra_id
            WHERE cd.producto_id = :product_id
            ORDER BY c.created_at DESC
            LIMIT 10
            """
        ),
        {"product_id": str(product_id)},
    ).mappings().all()

    ventas = db.execute(
        text(
            """
            SELECT v.folio, vd.cantidad, vd.precio_unitario, v.created_at
            FROM venta_detalle vd
            JOIN ventas v ON v.id = vd.venta_id
            WHERE vd.producto_id = :product_id
            ORDER BY v.created_at DESC
            LIMIT 10
            """
        ),
        {"product_id": str(product_id)},
    ).mappings().all()

    margen = Decimal("0")
    if product.costo and product.costo > 0:
        margen = ((product.precio_venta - product.costo) / product.costo) * Decimal("100")

    return ProductDetail(
        id=product.id,
        codigo_interno=product.codigo_interno,
        codigo_barras=product.codigo_barras,
        nombre=product.nombre,
        descripcion=product.descripcion,
        categoria=row["categoria"],
        departamento=row["departamento"],
        marca=row["marca"],
        unidad=row["unidad"],
        tipo_venta=product.tipo_venta,
        costo=product.costo,
        precio_venta=product.precio_venta,
        precio_mayoreo=product.precio_mayoreo,
        margen=margen,
        stock_actual=row["stock_actual"],
        stock_minimo=product.stock_minimo,
        stock_maximo=product.stock_maximo,
        activo=product.activo,
        departamento_id=product.departamento_id,
        categoria_id=product.categoria_id,
        subcategoria_id=product.subcategoria_id,
        marca_id=product.marca_id,
        unidad_medida_id=product.unidad_medida_id,
        es_granel=product.es_granel,
        es_producto_gancho=product.es_producto_gancho,
        es_producto_utilidad=product.es_producto_utilidad,
        es_perecedero=product.es_perecedero,
        maneja_caducidad=product.maneja_caducidad,
        maneja_lotes=product.maneja_lotes,
        imagen_url=product.imagen_url,
        proveedor_id=product.proveedor_id,
        proveedor_nombre=row["proveedor_nombre"],
        fecha_caducidad=product.fecha_caducidad,
        historial_movimientos=[
            {
                "fecha": m.created_at,
                "tipo": m.tipo_movimiento,
                "cantidad": m.cantidad,
                "stock_anterior": m.stock_anterior,
                "stock_nuevo": m.stock_nuevo,
                "motivo": m.motivo,
            }
            for m in movs
        ],
        historial_precios=[
            {
                "fecha": p.created_at,
                "precio_anterior": p.precio_anterior,
                "precio_nuevo": p.precio_nuevo,
                "costo_anterior": p.costo_anterior,
                "costo_nuevo": p.costo_nuevo,
                "motivo": p.motivo,
            }
            for p in prices
        ],
        ultimas_ventas=[dict(v) for v in ventas],
        ultimas_compras=[dict(c) for c in compras],
    )


def list_catalog_options(db: Session, model, only_active: bool = True):
    query = select(model.id, model.nombre).order_by(model.nombre.asc())
    if only_active:
        if hasattr(model, "activo"):
            query = query.where(model.activo.is_(True))
        elif hasattr(model, "activa"):
            query = query.where(model.activa.is_(True))
    return db.execute(query).mappings().all()


def list_categories(db: Session, departamento_id: UUID | None):
    query = select(Categoria.id, Categoria.nombre).order_by(Categoria.nombre.asc())
    if departamento_id:
        query = query.where(Categoria.departamento_id == departamento_id)
    query = query.where(Categoria.activa.is_(True))
    return db.execute(query).mappings().all()


def list_subcategories(db: Session, categoria_id: UUID | None):
    query = select(Subcategoria.id, Subcategoria.nombre).where(Subcategoria.activa.is_(True)).order_by(Subcategoria.nombre.asc())
    if categoria_id:
        query = query.where(Subcategoria.categoria_id == categoria_id)
    return db.execute(query).mappings().all()


def get_product_by_barcode(db: Session, codigo: str) -> ProductListItem | None:
    codigo = codigo.strip()
    if not codigo:
        return None
    rows = list_products(db, q=codigo, departamento_id=None, categoria_id=None, activo=True, bajo_stock=False, granel=None, perecedero=None)
    exact = next((row for row in rows if row.codigo_barras == codigo or row.codigo_interno == codigo), None)
    return exact


def delete_product(db: Session, product_id: UUID, user_id: UUID | None) -> Producto:
    product = db.get(Producto, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    sales_count = db.execute(
        text("SELECT COUNT(*) FROM venta_detalle WHERE producto_id = :product_id"),
        {"product_id": str(product_id)},
    ).scalar_one()
    if sales_count and int(sales_count) > 0:
        return update_status(db, product_id, False, user_id)

    db.execute(text("DELETE FROM movimientos_inventario WHERE producto_id = :product_id"), {"product_id": str(product_id)})
    db.execute(text("DELETE FROM inventarios WHERE producto_id = :product_id"), {"product_id": str(product_id)})
    db.execute(text("DELETE FROM historial_precios WHERE producto_id = :product_id"), {"product_id": str(product_id)})
    db.delete(product)
    db.commit()
    return product
