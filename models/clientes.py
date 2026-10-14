import pandas as pd


def normalizar_codigo(serie):
    return (
        serie.fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\.0$", "", regex=True)
    )


def construir_tabla_clientes(df_clientes):
    """
    Acepta:
    - SQL/analytics: codigo_logistico, codigo_cliente, nombre, entrega, preparacion
    - Maestro Clientes versionado:
      codigo_logistico, Codigo_Cliente, Cliente, tipo, Entrega, Preparacion2
    - contrato interno ya normalizado.
    """
    tabla = df_clientes.copy()

    if tabla is None or tabla.empty:
        return pd.DataFrame(columns=[
            "CodigoSucursal", "ClienteCodigo", "ClienteDescripcion",
            "TipoCliente", "FrecuenciaEntrega", "FrecuenciaPreparacion",
        ])

    tabla.columns = tabla.columns.astype(str).str.strip()

    if {
        "CodigoSucursal", "ClienteCodigo", "ClienteDescripcion",
        "FrecuenciaEntrega", "FrecuenciaPreparacion",
    }.issubset(tabla.columns):
        if "TipoCliente" not in tabla.columns:
            tabla["TipoCliente"] = ""

    elif {
        "codigo_logistico", "codigo_cliente", "nombre",
        "entrega", "preparacion",
    }.issubset(tabla.columns):
        tabla = tabla.rename(columns={
            "codigo_logistico": "CodigoSucursal",
            "codigo_cliente": "ClienteCodigo",
            "nombre": "ClienteDescripcion",
            "entrega": "FrecuenciaEntrega",
            "preparacion": "FrecuenciaPreparacion",
        })
        tabla["TipoCliente"] = ""

    elif {
        "codigo_logistico", "Codigo_Cliente", "Cliente",
        "Entrega", "Preparacion2",
    }.issubset(tabla.columns):
        tabla = tabla.rename(columns={
            "codigo_logistico": "CodigoSucursal",
            "Codigo_Cliente": "ClienteCodigo",
            "Cliente": "ClienteDescripcion",
            "Entrega": "FrecuenciaEntrega",
            "Preparacion2": "FrecuenciaPreparacion",
        })
        if "tipo" in tabla.columns:
            tabla = tabla.rename(columns={"tipo": "TipoCliente"})
        else:
            tabla["TipoCliente"] = ""

    else:
        raise ValueError(
            "Maestro Clientes no coincide con los contratos soportados. "
            f"Columnas recibidas: {list(tabla.columns)}"
        )

    for c in ["CodigoSucursal", "ClienteCodigo"]:
        tabla[c] = normalizar_codigo(tabla[c])

    for c in [
        "ClienteDescripcion", "TipoCliente",
        "FrecuenciaEntrega", "FrecuenciaPreparacion",
    ]:
        if c not in tabla.columns:
            tabla[c] = ""
        tabla[c] = tabla[c].fillna("").astype(str).str.strip()

    tabla["TipoCliente"] = tabla["TipoCliente"].str.upper()
    tabla["FrecuenciaEntrega"] = tabla["FrecuenciaEntrega"].str.upper()
    tabla["FrecuenciaPreparacion"] = tabla["FrecuenciaPreparacion"].str.upper()

    tabla = tabla.loc[tabla["CodigoSucursal"].ne("")].copy()
    tabla = (
        tabla.sort_values(["CodigoSucursal", "ClienteDescripcion"])
        .drop_duplicates("CodigoSucursal", keep="first")
        .reset_index(drop=True)
    )

    return tabla[[
        "CodigoSucursal", "ClienteCodigo", "ClienteDescripcion",
        "TipoCliente", "FrecuenciaEntrega", "FrecuenciaPreparacion",
    ]].copy()
