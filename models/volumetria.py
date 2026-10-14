import pandas as pd


def normalizar_codigo(serie):
    return (
        serie.fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\.0$", "", regex=True)
    )


def construir_tabla_volumetria(df_volumetria):
    """
    Acepta Maestro Volumetria versionado y contratos SQL/internos.
    """
    columnas_finales = [
        "CodigoArticulo", "ArticuloDescripcion", "Familia",
        "AltoMM", "AnchoMM", "ProfundoMM", "PesoKg",
        "UnidadVenta", "VolumenM3", "VolumenUnidadVentaM3",
    ]

    tabla = df_volumetria.copy()

    if tabla is None or tabla.empty:
        return pd.DataFrame(columns=columnas_finales)

    tabla.columns = tabla.columns.astype(str).str.strip()

    # Archivo versionado actual
    if {
        "Codigo", "Descripcion", "Alto", "Ancho",
        "Profundo", "UnidadVenta", "Kg", "Familia",
    }.issubset(tabla.columns):
        tabla = tabla.rename(columns={
            "Codigo": "CodigoArticulo",
            "Descripcion": "ArticuloDescripcion",
            "Alto": "AltoMM",
            "Ancho": "AnchoMM",
            "Profundo": "ProfundoMM",
            "Kg": "PesoKg",
        })

    # SQL / core / analytics
    elif {
        "codigo_articulo", "descripcion", "alto_mm", "ancho_mm",
        "profundo_mm", "peso_kg",
    }.issubset(tabla.columns):
        tabla = tabla.rename(columns={
            "codigo_articulo": "CodigoArticulo",
            "descripcion": "ArticuloDescripcion",
            "alto_mm": "AltoMM",
            "ancho_mm": "AnchoMM",
            "profundo_mm": "ProfundoMM",
            "peso_kg": "PesoKg",
            "unidad_venta": "UnidadVenta",
            "familia": "Familia",
            "volumen_m3": "VolumenM3",
        })

    # Contrato interno
    elif {
        "CodigoArticulo", "AltoMM", "AnchoMM",
        "ProfundoMM", "PesoKg",
    }.issubset(tabla.columns):
        pass

    else:
        raise ValueError(
            "Maestro Volumetria no coincide con los contratos soportados. "
            f"Columnas recibidas: {list(tabla.columns)}"
        )

    if "ArticuloDescripcion" not in tabla.columns:
        tabla["ArticuloDescripcion"] = ""
    if "Familia" not in tabla.columns:
        tabla["Familia"] = ""
    if "UnidadVenta" not in tabla.columns:
        tabla["UnidadVenta"] = 1

    tabla["CodigoArticulo"] = normalizar_codigo(tabla["CodigoArticulo"])
    tabla["ArticuloDescripcion"] = (
        tabla["ArticuloDescripcion"].fillna("").astype(str).str.strip()
    )
    tabla["Familia"] = tabla["Familia"].fillna("").astype(str).str.strip()

    for c in ["AltoMM", "AnchoMM", "ProfundoMM", "PesoKg"]:
        tabla[c] = pd.to_numeric(tabla[c], errors="coerce").fillna(0)

    tabla["UnidadVenta"] = (
        pd.to_numeric(tabla["UnidadVenta"], errors="coerce")
        .fillna(1)
    )
    tabla.loc[tabla["UnidadVenta"] <= 0, "UnidadVenta"] = 1
    tabla["UnidadVenta"] = tabla["UnidadVenta"].astype(int)

    calculado = (
        tabla["AltoMM"] * tabla["AnchoMM"] * tabla["ProfundoMM"]
    ) / 1_000_000_000

    if "VolumenM3" in tabla.columns:
        existente = pd.to_numeric(tabla["VolumenM3"], errors="coerce")
        tabla["VolumenM3"] = existente.where(existente.notna() & (existente > 0), calculado)
    else:
        tabla["VolumenM3"] = calculado

    tabla["VolumenUnidadVentaM3"] = tabla["VolumenM3"] * tabla["UnidadVenta"]

    tabla["VolumenM3"] = tabla["VolumenM3"].round(6)
    tabla["VolumenUnidadVentaM3"] = tabla["VolumenUnidadVentaM3"].round(6)
    tabla["PesoKg"] = tabla["PesoKg"].round(3)

    tabla = tabla.loc[tabla["CodigoArticulo"].ne("")].copy()
    tabla = (
        tabla.sort_values(["CodigoArticulo", "ArticuloDescripcion"])
        .drop_duplicates("CodigoArticulo", keep="first")
        .reset_index(drop=True)
    )

    return tabla[columnas_finales].copy()
