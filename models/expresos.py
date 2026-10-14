import pandas as pd


def normalizar_codigo(serie):
    return (
        serie.fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\.0$", "", regex=True)
    )


def construir_tabla_expresos(df_expresos):
    """
    Acepta:
    - raw/Data Expresos: cod_expre, nombre, direccion, localidad,
      agrupador, zona_agrupador
    - analytics: codigo_expreso, nombre, direccion, localidad,
      agrupador, zona_agrupador
    - contrato interno ya normalizado.
    """
    tabla = df_expresos.copy()

    columnas_finales = [
        "CodigoExpreso", "Expreso", "DireccionExpreso",
        "LocalidadExpreso", "AgrupadorExpreso", "ZonaAgrupadorExpreso",
    ]

    if tabla is None or tabla.empty:
        return pd.DataFrame(columns=columnas_finales)

    tabla.columns = tabla.columns.astype(str).str.strip()

    if set(columnas_finales).issubset(tabla.columns):
        pass
    elif {
        "codigo_expreso", "nombre", "direccion", "localidad",
        "agrupador", "zona_agrupador",
    }.issubset(tabla.columns):
        tabla = tabla.rename(columns={
            "codigo_expreso": "CodigoExpreso",
            "nombre": "Expreso",
            "direccion": "DireccionExpreso",
            "localidad": "LocalidadExpreso",
            "agrupador": "AgrupadorExpreso",
            "zona_agrupador": "ZonaAgrupadorExpreso",
        })
    elif {
        "cod_expre", "nombre", "direccion", "localidad",
        "agrupador", "zona_agrupador",
    }.issubset(tabla.columns):
        tabla = tabla.rename(columns={
            "cod_expre": "CodigoExpreso",
            "nombre": "Expreso",
            "direccion": "DireccionExpreso",
            "localidad": "LocalidadExpreso",
            "agrupador": "AgrupadorExpreso",
            "zona_agrupador": "ZonaAgrupadorExpreso",
        })
    else:
        raise ValueError(
            "Datos Expresos no coincide con los contratos soportados. "
            f"Columnas recibidas: {list(tabla.columns)}"
        )

    tabla["CodigoExpreso"] = normalizar_codigo(tabla["CodigoExpreso"])

    for c in columnas_finales[1:]:
        tabla[c] = tabla[c].fillna("").astype(str).str.strip()

    tabla = tabla.loc[tabla["CodigoExpreso"].ne("")].copy()
    tabla = (
        tabla.sort_values(["CodigoExpreso", "Expreso"])
        .drop_duplicates("CodigoExpreso", keep="first")
        .reset_index(drop=True)
    )

    return tabla[columnas_finales].copy()
