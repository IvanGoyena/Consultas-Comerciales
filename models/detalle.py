import pandas as pd


# ==========================================================
# TABLA DETALLE PEDIDOS
# ==========================================================

def construir_tabla_detalle(

    df_detalle,
    df_articulos,
    df_volumetria=None,  # Maestro separado usado en Cloud/versionados.

):

    # ------------------------------------------------------
    # COPIA
    # ------------------------------------------------------

    tabla = df_detalle.copy()


    # ------------------------------------------------------
    # RENOMBRAR COLUMNAS
    # ------------------------------------------------------

    tabla = tabla.rename(

        columns={

            "nro_com": "Pedido",

            "cod_art": "ArticuloCodigo",

            "can_art": "Cantidad",

            "can_reserv": "CantidadReservada"

        }

    )

    # ------------------------------------------------------
    # TIPOS DE DATOS
    # ------------------------------------------------------

    tabla["Pedido"] = (

        tabla["Pedido"]

        .fillna("")

        .astype(str)

    )


    tabla["ArticuloCodigo"] = (
        tabla["ArticuloCodigo"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\.0$", "", regex=True)
    )

    tabla["Cantidad"] = (

        pd.to_numeric(

            tabla["Cantidad"],

            errors="coerce"

        )

        .fillna(0)

        .astype(int)

    )

    # ------------------------------------------------------
    # CANTIDAD RESERVADA / TRANSMITIDA AL WMS
    # ------------------------------------------------------

    if "CantidadReservada" not in tabla.columns:
        tabla["CantidadReservada"] = 0

    tabla["CantidadReservada"] = (
        pd.to_numeric(
            tabla["CantidadReservada"],
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
    )

    # ------------------------------------------------------
    # MAESTRO ARTICULOS
    # ------------------------------------------------------

    articulos = df_articulos.copy()

    # ------------------------------------------------------
    # COLUMNAS REQUERIDAS DEL MAESTRO ARTÍCULOS
    # ------------------------------------------------------
    # Las dimensiones NO son obligatorias acá: en Cloud viven en
    # Maestro Volumetria y se completan más abajo.
    columnas_requeridas = [
        "COD_ART",
        "DESCRIP",
    ]

    faltantes = [
        c
        for c in columnas_requeridas
        if c not in articulos.columns
    ]

    if faltantes:
        raise ValueError(
            f"Faltan columnas base en Maestro Articulos: {faltantes}"
        )

    # Metadatos opcionales: mantener contrato aunque el maestro cambie.
    for columna in [
        "Rubro", "Marca", "Terminacion", "Tipo", "Origen", "Gama",
        "Familia", "Familia_2", "Sector", "Sectorizacion",
    ]:
        if columna not in articulos.columns:
            articulos[columna] = ""

    # ------------------------------------------------------
    # COMPLETAR VOLUMETRÍA DESDE MAESTRO VOLUMETRÍA
    # ------------------------------------------------------
    articulos.columns = articulos.columns.astype(str).str.strip()

    articulos["COD_ART"] = (
        articulos["COD_ART"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\.0$", "", regex=True)
    )

    columnas_vol = [
        "AltoMM", "AnchoMM", "ProfundoMM", "PesoKg", "VolumenM3",
    ]

    if df_volumetria is not None and not df_volumetria.empty:
        from models.volumetria import construir_tabla_volumetria

        vol = construir_tabla_volumetria(df_volumetria.copy())
        vol = vol[
            ["CodigoArticulo", *columnas_vol]
        ].rename(columns={"CodigoArticulo": "COD_ART"})
        vol = vol.drop_duplicates("COD_ART", keep="first")

        articulos = articulos.merge(
            vol,
            on="COD_ART",
            how="left",
            suffixes=("", "_VOL"),
            validate="many_to_one",
        )

        for columna in columnas_vol:
            respaldo = f"{columna}_VOL"
            if respaldo in articulos.columns:
                if columna not in articulos.columns:
                    articulos[columna] = articulos[respaldo]
                else:
                    base_num = pd.to_numeric(articulos[columna], errors="coerce")
                    vol_num = pd.to_numeric(articulos[respaldo], errors="coerce")
                    articulos[columna] = base_num.where(
                        base_num.notna() & (base_num > 0),
                        vol_num,
                    )
                articulos = articulos.drop(columns=[respaldo])

    for columna in columnas_vol:
        if columna not in articulos.columns:
            articulos[columna] = 0

    # ------------------------------------------------------
    # TIPOS DE DATOS
    # ------------------------------------------------------

    articulos["COD_ART"] = (
        articulos["COD_ART"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"\.0$", "", regex=True)
    )

    # ------------------------------------------------------
    # MERGE
    # ------------------------------------------------------

    tabla = tabla.merge(

        articulos,

        left_on="ArticuloCodigo",

        right_on="COD_ART",

        how="left"

    )

    # ------------------------------------------------------
    # RENOMBRAR COLUMNAS
    # ------------------------------------------------------

    tabla = tabla.rename(

        columns={

            "DESCRIP": "ArticuloDescripcion",

            "Familia_2": "Familia2"

        }

    )


    # ------------------------------------------------------
    # FORMATOS DE VOLUMETRÍA
    # ------------------------------------------------------

    columnas_volumetria = [
        "AltoMM",
        "AnchoMM",
        "ProfundoMM",
        "PesoKg",
        "VolumenM3",
    ]

    for columna in columnas_volumetria:

        tabla[columna] = (
            pd.to_numeric(
                tabla[columna],
                errors="coerce"
            )
            .fillna(0)
        )

    # ------------------------------------------------------
    # VOLUMEN TOTAL POR LÍNEA
    # ------------------------------------------------------

    # Para pedidos activos en DIGIP (PENDIENTE / PREPARACION),
    # la reserva ERP representa la cantidad efectivamente transmitida al WMS.
    # No usar can_art: incluye también el pendiente todavía no transmitido.
    tabla["VolumenLineaM3"] = (
        tabla["CantidadReservada"]
        * tabla["VolumenM3"]
    )

    tabla["VolumenM3"] = (
        tabla["VolumenM3"]
        .round(6)
    )

    tabla["VolumenLineaM3"] = (
        tabla["VolumenLineaM3"]
        .round(4)
    )


    # ------------------------------------------------------
    # ELIMINAR COLUMNAS AUXILIARES
    # ------------------------------------------------------

    tabla = tabla.drop(

        columns=[

            "COD_ART",
            "COD_RUB",
            "COD_MAR"

        ],

        errors="ignore"

    )

    # ------------------------------------------------------
    # ORDENAR COLUMNAS
    # ------------------------------------------------------

    tabla = tabla[
        [
            "Pedido",
            "ArticuloCodigo",
            "ArticuloDescripcion",
            "Cantidad",
            "CantidadReservada",
            "Familia",
            "Familia2",
            "Marca",
            "Tipo",
            "Origen",
            "Gama",
            "Rubro",
            "Sector",
            "Sectorizacion",
            "Terminacion",
            "AltoMM",
            "AnchoMM",
            "ProfundoMM",
            "PesoKg",
            "VolumenM3",
            "VolumenLineaM3",
        ]
    ].copy()


    # ------------------------------------------------------
    # ORDENAR REGISTROS
    # ------------------------------------------------------

    tabla = tabla.sort_values(

        [

            "Pedido",

            "Familia",

            "ArticuloDescripcion"

        ]

    ).reset_index(

        drop=True

    )


    return tabla    

# ==========================================================
# RESUMEN PEDIDOS
# ==========================================================

def construir_resumen_pedidos(

    tabla_detalle

):

    # ------------------------------------------------------
    # COPIA
    # ------------------------------------------------------

    resumen = tabla_detalle.copy()

    # ------------------------------------------------------
    # TOTAL UNIDADES
    # ------------------------------------------------------

    resumen = (
        resumen
        .groupby(
            "Pedido",
            as_index=False
        )
        .agg(
            TotalUnidades=(
                "Cantidad",
                "sum"
            ),
            TotalSKUs=(
                "ArticuloCodigo",
                "nunique"
            ),
            TotalM3=(
                "VolumenLineaM3",
                "sum"
            )
        )
    )

    resumen["TotalM3"] = (
        resumen["TotalM3"]
        .fillna(0)
        .round(3)
    )

# ------------------------------------------------------
# UNIDADES POR SECTORIZACION
# ------------------------------------------------------

    familias = (
    tabla_detalle
    .groupby(
        [
            "Pedido",
            "Sectorizacion"
        ],
        as_index=False
    )
    .agg(
        Unidades=(
            "Cantidad",
            "sum"
        )
    )
)

    familias = familias.rename(
    columns={
        "Sectorizacion": "Familia"
    }
)

    # ------------------------------------------------------
    # TEXTO FAMILIAS
    # ------------------------------------------------------

    familias["Detalle"] = (

        familias["Familia"]

        +

        " ("

        +

        familias["Unidades"]

        .astype(int)

        .astype(str)

        +

        ")"

    )

    detalle_familias = (

        familias

        .groupby(

            "Pedido"

        )["Detalle"]

        .apply(

            " | ".join

        )

        .reset_index(

            name="DetalleFamilias"

        )

    )

    # ------------------------------------------------------
    # FAMILIAS EN COLUMNAS
    # ------------------------------------------------------

    familias_pivot = (

        familias

        .pivot(

            index="Pedido",

            columns="Familia",

            values="Unidades"

        )

        .fillna(0)

        .astype(int)

        .reset_index()

    )

    familias_pivot.columns.name = None

    # ------------------------------------------------------
    # MERGE RESUMEN
    # ------------------------------------------------------

    resumen = resumen.merge(

        detalle_familias,

        on="Pedido",

        how="left"

    )

    resumen = resumen.merge(

        familias_pivot,

        on="Pedido",

        how="left"

    )

    resumen = resumen.fillna(0)

    return resumen

