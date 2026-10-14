import pandas as pd
import re


def normalizar_codigo(serie):
    return (
        serie.fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\.0$", "", regex=True)
    )


def _canon(nombre: str) -> str:
    """
    Canoniza encabezados para aceptar diferencias de mayúsculas,
    espacios, guiones y underscores.
    """
    texto = str(nombre).strip().lower()
    texto = (
        texto.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ñ", "n")
    )
    return re.sub(r"[^a-z0-9]+", "", texto)


def construir_tabla_expresos(df_expresos):
    """
    Acepta:
    - SQL/analytics:
      codigo_expreso, nombre, direccion, localidad, agrupador, zona_agrupador
    - Raw/versionado real:
      Cod_Expre, Nombre, Direccion, Localidad, Agrupador, Zona Agrupador
    - Otras variantes equivalentes de mayúsculas/espacios.
    - Contrato interno ya normalizado.
    """
    columnas_finales = [
        "CodigoExpreso",
        "Expreso",
        "DireccionExpreso",
        "LocalidadExpreso",
        "AgrupadorExpreso",
        "ZonaAgrupadorExpreso",
    ]

    if df_expresos is None or df_expresos.empty:
        return pd.DataFrame(columns=columnas_finales)

    tabla = df_expresos.copy()
    tabla.columns = tabla.columns.astype(str).str.strip()

    mapa = {_canon(c): c for c in tabla.columns}

    def buscar(*aliases):
        for alias in aliases:
            key = _canon(alias)
            if key in mapa:
                return mapa[key]
        return None

    # Si ya viene con contrato interno, no renombrar.
    if set(columnas_finales).issubset(tabla.columns):
        pass
    else:
        origen_codigo = buscar(
            "codigo_expreso",
            "cod_expre",
            "CodigoExpreso",
            "Cod_Expre",
        )
        origen_nombre = buscar(
            "nombre",
            "expreso",
            "Nombre",
        )
        origen_direccion = buscar(
            "direccion",
            "Direccion",
        )
        origen_localidad = buscar(
            "localidad",
            "Localidad",
        )
        origen_agrupador = buscar(
            "agrupador",
            "Agrupador",
        )
        origen_zona = buscar(
            "zona_agrupador",
            "zona agrupador",
            "Zona Agrupador",
            "ZonaAgrupador",
        )

        faltantes = [
            nombre
            for nombre, valor in {
                "codigo_expreso": origen_codigo,
                "nombre": origen_nombre,
                "direccion": origen_direccion,
                "localidad": origen_localidad,
                "agrupador": origen_agrupador,
                "zona_agrupador": origen_zona,
            }.items()
            if valor is None
        ]

        if faltantes:
            raise ValueError(
                "Datos Expresos no coincide con los contratos soportados. "
                f"Faltan campos equivalentes a: {faltantes}. "
                f"Columnas recibidas: {list(tabla.columns)}"
            )

        tabla = tabla.rename(columns={
            origen_codigo: "CodigoExpreso",
            origen_nombre: "Expreso",
            origen_direccion: "DireccionExpreso",
            origen_localidad: "LocalidadExpreso",
            origen_agrupador: "AgrupadorExpreso",
            origen_zona: "ZonaAgrupadorExpreso",
        })

    tabla["CodigoExpreso"] = normalizar_codigo(
        tabla["CodigoExpreso"]
    )

    for c in columnas_finales[1:]:
        if c not in tabla.columns:
            tabla[c] = ""
        tabla[c] = (
            tabla[c]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    tabla = tabla.loc[
        tabla["CodigoExpreso"].ne("")
    ].copy()

    tabla = (
        tabla
        .sort_values(["CodigoExpreso", "Expreso"])
        .drop_duplicates("CodigoExpreso", keep="first")
        .reset_index(drop=True)
    )

    return tabla[columnas_finales].copy()
