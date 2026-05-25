-- Seed minimal reference data into Supabase so local and Android see the same catalogs.
-- Execute in Supabase SQL Editor after backup.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Departments
INSERT INTO public.departamentos (id, nombre, activo)
SELECT gen_random_uuid(), v.nombre, true
FROM (VALUES
  ('General'),
  ('Abarrotes'),
  ('Bebidas'),
  ('Limpieza')
) AS v(nombre)
WHERE NOT EXISTS (
  SELECT 1 FROM public.departamentos d WHERE d.nombre = v.nombre
);

-- Brands
INSERT INTO public.marcas (id, nombre, activa)
SELECT gen_random_uuid(), v.nombre, true
FROM (VALUES
  ('Genérica')
) AS v(nombre)
WHERE NOT EXISTS (
  SELECT 1 FROM public.marcas m WHERE m.nombre = v.nombre
);

-- Units
INSERT INTO public.unidades_medida (id, nombre, abreviatura, activa)
SELECT gen_random_uuid(), v.nombre, v.abreviatura, true
FROM (VALUES
  ('Pieza', 'pz'),
  ('Kilogramo', 'kg'),
  ('Litro', 'lt')
) AS v(nombre, abreviatura)
WHERE NOT EXISTS (
  SELECT 1 FROM public.unidades_medida u WHERE u.nombre = v.nombre
);

-- Suppliers
INSERT INTO public.proveedores (id, nombre, activo)
SELECT gen_random_uuid(), v.nombre, true
FROM (VALUES
  ('Sin proveedor')
) AS v(nombre)
WHERE NOT EXISTS (
  SELECT 1 FROM public.proveedores p WHERE p.nombre = v.nombre
);

-- Example categories
INSERT INTO public.categorias (id, nombre, prefijo_codigo, activa)
SELECT gen_random_uuid(), v.nombre, v.prefijo_codigo, true
FROM (VALUES
  ('Varios', 'VAR')
) AS v(nombre, prefijo_codigo)
WHERE NOT EXISTS (
  SELECT 1 FROM public.categorias c WHERE c.nombre = v.nombre
);

-- Ensure product defaults
ALTER TABLE IF EXISTS public.productos ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE IF EXISTS public.inventarios ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE IF EXISTS public.movimientos_inventario ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE IF EXISTS public.historial_precios ALTER COLUMN id SET DEFAULT gen_random_uuid();
