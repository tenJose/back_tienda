import os

def main():
    file_path = r"c:\Users\Jose Carlos\Documents\GitHub\tiendita_pos\back\app\services\product_service.py"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. list_products replacements
    old_list_select = """            Producto.es_granel,
            Producto.es_perecedero,
        )
        .select_from(Producto)
        .outerjoin(Departamento, Departamento.id == Producto.departamento_id)
        .outerjoin(Categoria, Categoria.id == Producto.categoria_id)
        .outerjoin(Marca, Marca.id == Producto.marca_id)
        .outerjoin(UnidadMedida, UnidadMedida.id == Producto.unidad_medida_id)
        .outerjoin(Inventario, Inventario.producto_id == Producto.id)
        .group_by(
            Producto.id,
            Departamento.nombre,
            Categoria.nombre,
            Marca.nombre,
            UnidadMedida.abreviatura,
        )"""

    new_list_select = """            Producto.es_granel,
            Producto.es_perecedero,
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
        )"""

    # 2. create_product replacements
    old_create_inst = """        imagen_url=payload.imagen_url,
        activo=payload.activo,
        created_by=user_id,
        updated_by=user_id,
    )"""

    new_create_inst = """        imagen_url=payload.imagen_url,
        activo=payload.activo,
        created_by=user_id,
        updated_by=user_id,
        proveedor_id=payload.proveedor_id,
        fecha_caducidad=payload.fecha_caducidad,
    )"""

    # 3. update_product replacements
    old_update_pop = '    data.pop("proveedor_id", None)'
    new_update_pop = '    # data.pop("proveedor_id", None)'

    # 4. product_detail select replacements
    old_detail_select = """            UnidadMedida.abreviatura.label("unidad"),
            func.coalesce(func.sum(Inventario.existencia), 0).label("stock_actual"),
        )
        .outerjoin(Categoria, Categoria.id == Producto.categoria_id)"""

    new_detail_select = """            UnidadMedida.abreviatura.label("unidad"),
            func.coalesce(func.sum(Inventario.existencia), 0).label("stock_actual"),
            Proveedor.nombre.label("proveedor_nombre"),
        )
        .outerjoin(Categoria, Categoria.id == Producto.categoria_id)"""

    old_detail_group = """        .outerjoin(Inventario, Inventario.producto_id == Producto.id)
        .where(Producto.id == product_id)
        .group_by(Producto.id, Categoria.nombre, Departamento.nombre, Marca.nombre, UnidadMedida.abreviatura)"""

    new_detail_group = """        .outerjoin(Proveedor, Proveedor.id == Producto.proveedor_id)
        .outerjoin(Inventario, Inventario.producto_id == Producto.id)
        .where(Producto.id == product_id)
        .group_by(Producto.id, Categoria.nombre, Departamento.nombre, Marca.nombre, UnidadMedida.abreviatura, Proveedor.nombre)"""

    old_detail_dict = """        maneja_lotes=product.maneja_lotes,
        imagen_url=product.imagen_url,
        historial_movimientos=["""

    new_detail_dict = """        maneja_lotes=product.maneja_lotes,
        imagen_url=product.imagen_url,
        proveedor_id=product.proveedor_id,
        proveedor_nombre=row["proveedor_nombre"],
        fecha_caducidad=product.fecha_caducidad,
        historial_movimientos=["""

    # Execute modifications
    modifications = [
        (old_list_select, new_list_select),
        (old_create_inst, new_create_inst),
        (old_update_pop, new_update_pop),
        (old_detail_select, new_detail_select),
        (old_detail_group, new_detail_group),
        (old_detail_dict, new_detail_dict),
    ]

    for old, new in modifications:
        if old in content:
            content = content.replace(old, new)
            print("Successfully replaced a block.")
        else:
            print(f"Warning: could not find block:\n{old[:100]}...")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Done editing product_service.py!")

if __name__ == "__main__":
    main()
