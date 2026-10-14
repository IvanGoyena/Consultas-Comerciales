import pandas as pd


# ==========================================================
# NORMALIZACIÓN DE CÓDIGOS
# ==========================================================

def normalizar_codigo(serie):
    return (
        serie
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\.0$", "", regex=True)
    )


# ==========================================================
# MAESTRO DE CLIENTES
# ==========================================================

def construir_tabla_clientes(df_clientes):
    """
    Construye la tabla satélite de clientes a partir de
    analytics.vw_maestro_clientes.

    Fuente canónica:
        core.cliente
            -> analytics.vw_maestro_clientes
            -> models.clientes

    TipoCliente se conserva temporalmente vacío sólo como columna de
    compatibilidad para no romper consumidores existentes. Ya no se obtiene
    ni se inventa desde el maestro.
    """

    tabla = df_clientes.copy()

    # ------------------------------------------------------
    # NORMALIZAR NOMBRES DE COLUMNAS
    # ------------------------------------------------------
    tabla.columns = (
        tabla.columns
        .astype(str)
        .str.strip()
    )

    # ------------------------------------------------------
    # CONTRATO SQL
    # ------------------------------------------------------
    columnas_requeridas = [
        "codigo_logistico",
        "codigo_cliente",
        "nombre",
        "entrega",
        "preparacion",
    ]

    columnas_faltantes = [
        columna
        for columna in columnas_requeridas
        if columna not in tabla.columns
    ]

    if columnas_faltantes:
        raise ValueError(
            "Faltan columnas en analytics.vw_maestro_clientes: "
            f"{columnas_faltantes}"
        )

    # ------------------------------------------------------
    # RENOMBRAR AL CONTRATO INTERNO DEL MÓDULO
    # ------------------------------------------------------
    tabla = tabla.rename(
        columns={
            "codigo_logistico": "CodigoSucursal",
            "codigo_cliente": "ClienteCodigo",
            "nombre": "ClienteDescripcion",
            "entrega": "FrecuenciaEntrega",
            "preparacion": "FrecuenciaPreparacion",
        }
    )

    # ------------------------------------------------------
    # NORMALIZAR CLAVES
    # ------------------------------------------------------
    tabla["CodigoSucursal"] = normalizar_codigo(
        tabla["CodigoSucursal"]
    )

    tabla["ClienteCodigo"] = normalizar_codigo(
        tabla["ClienteCodigo"]
    )

    # ------------------------------------------------------
    # LIMPIEZA DE TEXTOS
    # ------------------------------------------------------
    columnas_texto = [
        "ClienteDescripcion",
        "FrecuenciaEntrega",
        "FrecuenciaPreparacion",
    ]

    for columna in columnas_texto:
        tabla[columna] = (
            tabla[columna]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    tabla["FrecuenciaEntrega"] = (
        tabla["FrecuenciaEntrega"]
        .str.upper()
    )

    tabla["FrecuenciaPreparacion"] = (
        tabla["FrecuenciaPreparacion"]
        .str.upper()
    )

    # ------------------------------------------------------
    # COMPATIBILIDAD TEMPORAL
    # ------------------------------------------------------
    # core.cliente no tiene un tipo_cliente operativo y el módulo no debe
    # inventarlo. Se conserva la columna vacía para evitar romper código
    # legado que todavía pudiera referenciarla.
    tabla["TipoCliente"] = ""

    # ------------------------------------------------------
    # ELIMINAR REGISTROS SIN CLAVE
    # ------------------------------------------------------
    tabla = tabla[
        tabla["CodigoSucursal"] != ""
    ].copy()

    # ------------------------------------------------------
    # EVITAR DUPLICADOS
    # Una fila por código logístico / sucursal
    # ------------------------------------------------------
    tabla = (
        tabla
        .sort_values(
            [
                "CodigoSucursal",
                "ClienteDescripcion",
            ]
        )
        .drop_duplicates(
            subset=["CodigoSucursal"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    # ------------------------------------------------------
    # TABLA SATÉLITE FINAL
    # ------------------------------------------------------
    columnas_finales = [
        "CodigoSucursal",
        "ClienteCodigo",
        "ClienteDescripcion",
        "TipoCliente",
        "FrecuenciaEntrega",
        "FrecuenciaPreparacion",
    ]

    return tabla[columnas_finales].copy()
