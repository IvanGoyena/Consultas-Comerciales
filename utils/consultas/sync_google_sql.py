from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text

from database import engine
from utils.google_sheets import leer_hoja


# ==========================================================
# CONFIGURACIÓN
# ==========================================================
# La web Comercial escribe en Google Sheets.
# El host replica esas gestiones en PostgreSQL.
#
# IMPORTANTE:
# Si Logística ya modificó un registro desde el host y quedó marcado
# como HOST_LOCAL, este sincronizador NO lo pisa con una versión vieja
# de Google Sheets.
PROTEGER_CAMBIOS_HOST_LOCAL = True


# ==========================================================
# NORMALIZACIÓN
# ==========================================================

def _limpiar(valor: Any) -> str:
    if valor is None:
        return ""

    if isinstance(valor, float) and pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.lower() in {"nan", "none", "<na>", "nat", "null"}:
        return ""

    if texto.endswith(".0") and texto[:-2].replace("-", "").isdigit():
        texto = texto[:-2]

    return texto


def _pedido(valor: Any) -> str:
    texto = _limpiar(valor)
    return texto.split("-")[0].strip() if texto else ""


def _fecha(valor: Any) -> datetime | None:
    texto = _limpiar(valor)

    if not texto:
        return None

    fecha = pd.to_datetime(
        texto,
        errors="coerce",
        dayfirst=True,
    )

    if pd.isna(fecha):
        return None

    if isinstance(fecha, pd.Timestamp):
        return fecha.to_pydatetime()

    return fecha


def _fecha_dia(valor: Any) -> date | None:
    dt = _fecha(valor)
    return dt.date() if dt is not None else None


def _numero(valor: Any) -> Decimal | None:
    texto = _limpiar(valor)

    if not texto:
        return None

    try:
        return Decimal(texto.replace(",", "."))
    except Exception:
        return None


def _json_safe(valor: Any) -> Any:
    if valor is None:
        return None

    if isinstance(valor, (datetime, date)):
        return valor.isoformat()

    if isinstance(valor, Decimal):
        return str(valor)

    if isinstance(valor, pd.Timestamp):
        return valor.isoformat()

    if isinstance(valor, float) and pd.isna(valor):
        return None

    return valor


def _hash_payload(payload: dict[str, Any]) -> str:
    canonico = {
        clave: _json_safe(valor)
        for clave, valor in sorted(payload.items())
    }

    texto_json = json.dumps(
        canonico,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        texto_json.encode("utf-8")
    ).hexdigest()


# ==========================================================
# FUENTES ACTIVAS
# ==========================================================

@dataclass(frozen=True)
class Fuente:
    nombre_hoja: str
    tabla_sql: str
    pk_sql: str
    pk_google: str
    mapping: dict[str, tuple[str, Callable[[Any], Any]]]


FUENTES: tuple[Fuente, ...] = (
    Fuente(
        nombre_hoja="Solicitudes",
        tabla_sql="commercial.solicitud",
        pk_sql="solicitud_id",
        pk_google="SolicitudID",
        mapping={
            "solicitud_id": ("SolicitudID", _limpiar),
            "pedido": ("Pedido", _pedido),
            "cliente": ("Cliente", _limpiar),
            "tipo_solicitud": ("TipoSolicitud", _limpiar),
            "prioridad": ("Prioridad", _limpiar),
            "descripcion": ("Descripcion", _limpiar),
            "fecha_habilitacion": ("FechaHabilitacion", _fecha_dia),
            "usuario_solicitante": ("UsuarioSolicitante", _limpiar),
            "fecha_solicitud": ("FechaSolicitud", _fecha),
            "estado_solicitud": ("EstadoSolicitud", _limpiar),
            "responsable": ("Responsable", _limpiar),
            "respuesta": ("Respuesta", _limpiar),
            "fecha_resolucion": ("FechaResolucion", _fecha),
        },
    ),
    Fuente(
        nombre_hoja="Reclamos",
        tabla_sql="commercial.reclamo",
        pk_sql="reclamo_id",
        pk_google="ReclamoID",
        mapping={
            "reclamo_id": ("ReclamoID", _limpiar),
            "pedido": ("Pedido", _pedido),
            "remito": ("Remito", _limpiar),
            "cliente": ("Cliente", _limpiar),
            "fecha_reclamo": ("FechaReclamo", _fecha),
            "tipo_reclamo": ("TipoReclamo", _limpiar),
            "descripcion": ("Descripcion", _limpiar),
            "responsable": ("Responsable", _limpiar),
            "estado_reclamo": ("EstadoReclamo", _limpiar),
            "resolucion": ("Resolucion", _limpiar),
            "usuario_creador": ("UsuarioCreador", _limpiar),
            "fecha_creacion": ("FechaCreacion", _fecha),
            "fecha_cierre": ("FechaCierre", _fecha),
        },
    ),
    Fuente(
        nombre_hoja="ReclamosDetalle",
        tabla_sql="commercial.reclamo_detalle",
        pk_sql="reclamo_detalle_id",
        pk_google="ReclamoDetalleID",
        mapping={
            "reclamo_detalle_id": ("ReclamoDetalleID", _limpiar),
            "reclamo_id": ("ReclamoID", _limpiar),
            "codigo_articulo": ("CodigoArticulo", _limpiar),
            "descripcion_articulo": ("DescripcionArticulo", _limpiar),
            "cantidad": ("Cantidad", _numero),
            "observacion": ("Observacion", _limpiar),
        },
    ),
    Fuente(
        nombre_hoja="CancelacionesEntrega",
        tabla_sql="commercial.cancelacion_entrega",
        pk_sql="cancelacion_entrega_id",
        pk_google="CancelacionEntregaID",
        mapping={
            "cancelacion_entrega_id": ("CancelacionEntregaID", _limpiar),
            "remito": ("Remito", _limpiar),
            "cliente": ("Cliente", _limpiar),
            "motivo": ("Motivo", _limpiar),
            "observacion": ("Observacion", _limpiar),
            "usuario_solicitante": ("UsuarioSolicitante", _limpiar),
            "fecha_solicitud": ("FechaSolicitud", _fecha),
            "estado_cancelacion": ("EstadoCancelacion", _limpiar),
            "telefono_destino": ("TelefonoDestino", _limpiar),
            "estado_whatsapp": ("EstadoWhatsApp", _limpiar),
            "fecha_envio_whatsapp": ("FechaEnvioWhatsApp", _fecha),
            "responsable_confirmacion": ("ResponsableConfirmacion", _limpiar),
            "fecha_confirmacion": ("FechaConfirmacion", _fecha),
            "observacion_confirmacion": ("ObservacionConfirmacion", _limpiar),
            "numero_ir": ("NumeroIR", _limpiar),
            "fecha_ir": ("FechaIR", _fecha),
            "estado_reingreso": ("EstadoReingreso", _limpiar),
            "fecha_reingreso": ("FechaReingreso", _fecha),
            "fecha_cierre": ("FechaCierre", _fecha),
            "responsable_gestion": ("ResponsableGestion", _limpiar),
            "fecha_inicio_gestion": ("FechaInicioGestion", _fecha),
            "resultado_operativo": ("ResultadoOperativo", _limpiar),
            "responsable_ir": ("ResponsableIR", _limpiar),
            "observacion_ir": ("ObservacionIR", _limpiar),
            "responsable_reingreso": ("ResponsableReingreso", _limpiar),
            "observacion_reingreso": ("ObservacionReingreso", _limpiar),
            "resultado_final": ("ResultadoFinal", _limpiar),
            "ultima_actualizacion": ("UltimaActualizacion", _fecha),
        },
    ),
)


# ==========================================================
# VALIDACIÓN SQL
# ==========================================================

def validar_estructura_sql() -> None:
    """
    Comprueba que las tablas destino existan antes de sincronizar.
    """
    faltantes = []

    with engine.connect() as conn:
        for fuente in FUENTES:
            existe = conn.execute(
                text("SELECT to_regclass(:tabla)"),
                {"tabla": fuente.tabla_sql},
            ).scalar()

            if not existe:
                faltantes.append(fuente.tabla_sql)

    if faltantes:
        raise RuntimeError(
            "Faltan tablas SQL requeridas: "
            + ", ".join(faltantes)
        )


# ==========================================================
# LECTURA / UPSERT
# ==========================================================

def _leer_google(fuente: Fuente) -> pd.DataFrame:
    """
    LEE GOOGLE DIRECTAMENTE.

    No usa leer_gestion_consultas.py porque en el host ese módulo
    lee PostgreSQL. Para sincronizar Google -> SQL necesitamos evitar
    ese circuito y consultar Sheets de forma explícita.
    """
    tabla = leer_hoja(fuente.nombre_hoja)

    if tabla is None:
        return pd.DataFrame()

    return tabla.copy()


def _leer_existentes(
    conn,
    fuente: Fuente,
) -> dict[str, dict[str, str]]:
    filas = conn.execute(
        text(
            f"""
            SELECT
                {fuente.pk_sql}::TEXT AS pk,
                COALESCE(source_hash, '') AS source_hash,
                COALESCE(source_system, '') AS source_system
            FROM {fuente.tabla_sql}
            """
        )
    ).mappings().all()

    return {
        _limpiar(fila["pk"]): {
            "source_hash": _limpiar(fila["source_hash"]),
            "source_system": _limpiar(
                fila["source_system"]
            ).upper(),
        }
        for fila in filas
        if _limpiar(fila["pk"])
    }


def _upsert(
    conn,
    fuente: Fuente,
    payload: dict[str, Any],
    source_hash: str,
) -> None:
    columnas = list(payload.keys())

    nombres_insert = columnas + [
        "source_system",
        "source_sheet",
        "source_hash",
        "synced_at",
        "updated_at",
    ]

    valores_insert = [
        f":{columna}"
        for columna in columnas
    ] + [
        "'GOOGLE_SHEETS'",
        ":source_sheet",
        ":source_hash",
        "NOW()",
        "NOW()",
    ]

    actualizaciones = [
        f"{columna} = EXCLUDED.{columna}"
        for columna in columnas
        if columna != fuente.pk_sql
    ] + [
        "source_system = 'GOOGLE_SHEETS'",
        "source_sheet = EXCLUDED.source_sheet",
        "source_hash = EXCLUDED.source_hash",
        "synced_at = NOW()",
        "updated_at = NOW()",
    ]

    consulta = text(
        f"""
        INSERT INTO {fuente.tabla_sql} (
            {", ".join(nombres_insert)}
        )
        VALUES (
            {", ".join(valores_insert)}
        )
        ON CONFLICT ({fuente.pk_sql})
        DO UPDATE SET
            {", ".join(actualizaciones)}
        """
    )

    parametros = dict(payload)
    parametros["source_sheet"] = fuente.nombre_hoja
    parametros["source_hash"] = source_hash

    conn.execute(consulta, parametros)


def sincronizar_fuente(
    fuente: Fuente,
) -> dict[str, Any]:
    google = _leer_google(fuente)

    resumen = {
        "Fuente": fuente.nombre_hoja,
        "Leidas": int(len(google)),
        "Insertadas": 0,
        "Actualizadas": 0,
        "SinCambios": 0,
        "ProtegidasHost": 0,
        "SinID": 0,
        "Errores": 0,
        "Estado": "OK",
        "Mensaje": "",
    }

    if google.empty:
        return resumen

    if fuente.pk_google not in google.columns:
        raise RuntimeError(
            f"La hoja {fuente.nombre_hoja} no contiene "
            f"la columna ID {fuente.pk_google}."
        )

    with engine.begin() as conn:
        existentes = _leer_existentes(
            conn,
            fuente,
        )

        for _, fila in google.iterrows():
            pk = _limpiar(
                fila.get(
                    fuente.pk_google,
                    "",
                )
            )

            if not pk:
                resumen["SinID"] += 1
                continue

            payload: dict[str, Any] = {}

            for (
                columna_sql,
                (
                    columna_google,
                    transformador,
                ),
            ) in fuente.mapping.items():

                valor = (
                    fila.get(columna_google, "")
                    if columna_google in google.columns
                    else ""
                )

                payload[columna_sql] = (
                    transformador(valor)
                )

            payload[fuente.pk_sql] = pk

            nuevo_hash = _hash_payload(payload)
            anterior = existentes.get(pk)

            if (
                PROTEGER_CAMBIOS_HOST_LOCAL
                and anterior
                and anterior["source_system"] == "HOST_LOCAL"
            ):
                resumen["ProtegidasHost"] += 1
                continue

            if (
                anterior
                and anterior["source_hash"] == nuevo_hash
            ):
                resumen["SinCambios"] += 1
                continue

            _upsert(
                conn,
                fuente,
                payload,
                nuevo_hash,
            )

            if anterior is None:
                resumen["Insertadas"] += 1
            else:
                resumen["Actualizadas"] += 1

    return resumen


def sincronizar_todo() -> pd.DataFrame:
    validar_estructura_sql()

    resultados: list[dict[str, Any]] = []

    for fuente in FUENTES:
        try:
            resultados.append(
                sincronizar_fuente(fuente)
            )

        except Exception as error:
            resultados.append({
                "Fuente": fuente.nombre_hoja,
                "Leidas": 0,
                "Insertadas": 0,
                "Actualizadas": 0,
                "SinCambios": 0,
                "ProtegidasHost": 0,
                "SinID": 0,
                "Errores": 1,
                "Estado": "ERROR",
                "Mensaje": (
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
            })

    return pd.DataFrame(resultados)


def obtener_resumen_sql() -> pd.DataFrame:
    filas = []

    with engine.connect() as conn:
        for fuente in FUENTES:
            cantidad = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM {fuente.tabla_sql}
                    """
                )
            ).scalar_one()

            ultimo_sync = conn.execute(
                text(
                    f"""
                    SELECT MAX(synced_at)
                    FROM {fuente.tabla_sql}
                    WHERE source_system = 'GOOGLE_SHEETS'
                    """
                )
            ).scalar_one()

            filas.append({
                "Fuente": fuente.nombre_hoja,
                "FilasSQL": int(cantidad),
                "UltimoSyncGoogle": ultimo_sync,
            })

    return pd.DataFrame(filas)


if __name__ == "__main__":
    resultado = sincronizar_todo()
    print(resultado.to_string(index=False))
