from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from config import ES_STREAMLIT_CLOUD

# Cloud continúa trabajando directamente contra Google Sheets.
# En el host, PostgreSQL es la fuente primaria y cada alta/actualización
# se replica inmediatamente a Google Sheets para mantener visible el avance
# en la versión que todavía consume Comercial.
from utils.consultas.persistencia_google import (
    agregar_registro as agregar_registro_google,
    actualizar_registro as actualizar_registro_google,
    asegurar_hoja as asegurar_hoja_google,
)

if ES_STREAMLIT_CLOUD:
    from utils.consultas.persistencia_google import (
        agregar_registro,
        actualizar_registro,
        leer_hoja,
        asegurar_hoja,
    )
else:
    from utils.consultas.persistencia_sql import (
        agregar_registro,
        actualizar_registro,
        leer_hoja,
        asegurar_hoja,
    )

ZONA_HORARIA = ZoneInfo("America/Argentina/Buenos_Aires")
ESTADOS_CERRADOS = {"FINALIZADA", "CANCELADA"}


def ahora() -> str:
    return datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d %H:%M:%S")


def limpiar(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def generar_id() -> str:
    return f"CAN-ENT-{datetime.now(ZONA_HORARIA):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:5].upper()}"


def separar_remitos(valor: Any) -> list[str]:
    partes = re.split(r"[\n,;]+", limpiar(valor))
    salida=[]
    for item in partes:
        item=item.strip()
        if item and item not in salida:
            salida.append(item)
    if not salida:
        raise ValueError("Ingresá al menos un remito.")
    return salida


def normalizar_remitos(valor: Any) -> str:
    return "\n".join(separar_remitos(valor))


def actualizar(cancelacion_id: Any, cambios: dict[str, Any]) -> dict[str, Any]:
    cid = limpiar(cancelacion_id)
    if not cid:
        raise ValueError("El ID de la gestión es obligatorio.")

    cambios = {**cambios, "UltimaActualizacion": ahora()}

    # Escritura primaria:
    # - Cloud -> Google Sheets
    # - Host  -> PostgreSQL
    actualizar_registro(
        "CancelacionesEntrega",
        "CancelacionEntregaID",
        cid,
        cambios,
    )

    # En host replicamos el mismo avance a Google Sheets.
    if not ES_STREAMLIT_CLOUD:
        try:
            actualizar_registro_google(
                "CancelacionesEntrega",
                "CancelacionEntregaID",
                cid,
                cambios,
            )
        except Exception as error:
            raise RuntimeError(
                "La gestión quedó actualizada en PostgreSQL, pero no se pudo "
                "replicar a Google Sheets. "
                f"Detalle: {error}"
            ) from error

    return {"ok": True, "id": cid}


def guardar_cancelacion_entrega(
    remito: Any,
    cliente: str,
    motivo: str,
    observacion: str,
    usuario_solicitante: str,
) -> dict[str, Any]:
    asegurar_hoja("CancelacionesEntrega")
    remitos=normalizar_remitos(remito)
    tabla=leer_hoja("CancelacionesEntrega")
    nuevos=set(separar_remitos(remitos))
    if tabla is not None and not tabla.empty and "Remito" in tabla.columns:
        for _,fila in tabla.iterrows():
            estado=limpiar(fila.get("EstadoCancelacion","")).upper()
            if estado in ESTADOS_CERRADOS:
                continue
            repetidos=nuevos.intersection(set(separar_remitos(fila.get("Remito",""))))
            if repetidos:
                return {"ok": True,"duplicado": True,
                        "id": limpiar(fila.get("CancelacionEntregaID","")),
                        "mensaje": "Ya existe una cancelación activa para: "+", ".join(sorted(repetidos))}
    fecha=ahora()
    registro={
        "CancelacionEntregaID": generar_id(), "Remito": remitos, "Cliente": limpiar(cliente),
        "Motivo": limpiar(motivo), "Observacion": limpiar(observacion),
        "UsuarioSolicitante": limpiar(usuario_solicitante), "FechaSolicitud": fecha,
        "EstadoCancelacion": "Pendiente de gestión",
        "ResponsableConfirmacion": "", "FechaConfirmacion": "", "ObservacionConfirmacion": "",
        "NumeroIR": "", "FechaIR": "", "EstadoReingreso": "Pendiente",
        "FechaReingreso": "", "FechaCierre": "", "ResponsableGestion": "",
        "FechaInicioGestion": "", "ResultadoOperativo": "", "ResponsableIR": "",
        "ObservacionIR": "", "ResponsableReingreso": "", "ObservacionReingreso": "",
        "ResultadoFinal": "", "UltimaActualizacion": fecha,
    }
    agregar_registro("CancelacionesEntrega", registro)

    if not ES_STREAMLIT_CLOUD:
        try:
            asegurar_hoja_google("CancelacionesEntrega")
            agregar_registro_google("CancelacionesEntrega", registro)
        except Exception as error:
            raise RuntimeError(
                "La gestión quedó creada en PostgreSQL, pero no se pudo "
                "replicar a Google Sheets. "
                f"Detalle: {error}"
            ) from error

    return {
        "ok": True,
        "duplicado": False,
        "id": registro["CancelacionEntregaID"],
        "registro": registro,
    }



def guardar_devolucion_directa(
    remito: Any,
    cliente: str,
    motivo: str,
    numero_pedido: str,
    numero_pallet: str,
    observacion: str,
    usuario_solicitante: str,
) -> dict[str, Any]:
    """
    Alta iniciada por Logística para mercadería que llega como devolución directa.

    No pasa por el paso de detener la entrega: queda lista para registrar IR.
    Se persiste en PostgreSQL + Google Sheets cuando corre en el host.
    """
    asegurar_hoja("CancelacionesEntrega")
    remitos = normalizar_remitos(remito)
    tabla = leer_hoja("CancelacionesEntrega")
    nuevos = set(separar_remitos(remitos))

    if tabla is not None and not tabla.empty and "Remito" in tabla.columns:
        for _, fila in tabla.iterrows():
            estado = limpiar(fila.get("EstadoCancelacion", "")).upper()
            if estado in ESTADOS_CERRADOS:
                continue
            repetidos = nuevos.intersection(
                set(separar_remitos(fila.get("Remito", "")))
            )
            if repetidos:
                return {
                    "ok": True,
                    "duplicado": True,
                    "id": limpiar(fila.get("CancelacionEntregaID", "")),
                    "mensaje": (
                        "Ya existe una gestión activa para: "
                        + ", ".join(sorted(repetidos))
                    ),
                }

    fecha = ahora()
    usuario = limpiar(usuario_solicitante)
    observacion_limpia = limpiar(observacion)
    numero_pedido_limpio = limpiar(numero_pedido)
    numero_pallet_limpio = limpiar(numero_pallet)

    if not numero_pedido_limpio:
        raise ValueError("El número de pedido es obligatorio.")

    partes_observacion = ["Devolución directa recibida por Logística."]
    partes_observacion.append(f"Pedido: {numero_pedido_limpio}.")
    if numero_pallet_limpio:
        partes_observacion.append(f"Pallet: {numero_pallet_limpio}.")
    if observacion_limpia:
        partes_observacion.append(observacion_limpia)

    observacion_final = " ".join(partes_observacion)

    registro = {
        "CancelacionEntregaID": generar_id(),
        "Remito": remitos,
        "Cliente": limpiar(cliente),
        "Motivo": limpiar(motivo),
        "Observacion": observacion_final,
        "UsuarioSolicitante": usuario,
        "FechaSolicitud": fecha,
        "EstadoCancelacion": "Devolución recibida",
        "ResponsableConfirmacion": usuario,
        "FechaConfirmacion": fecha,
        "ObservacionConfirmacion": "Alta directa desde Gestiones Operativas.",
        "NumeroIR": "",
        "FechaIR": "",
        "EstadoReingreso": "Pendiente",
        "FechaReingreso": "",
        "FechaCierre": "",
        "ResponsableGestion": usuario,
        "FechaInicioGestion": fecha,
        "ResultadoOperativo": "Devolución directa",
        "ResponsableIR": "",
        "ObservacionIR": "",
        "ResponsableReingreso": "",
        "ObservacionReingreso": "",
        "ResultadoFinal": "",
        "UltimaActualizacion": fecha,
    }

    agregar_registro("CancelacionesEntrega", registro)

    if not ES_STREAMLIT_CLOUD:
        try:
            asegurar_hoja_google("CancelacionesEntrega")
            agregar_registro_google("CancelacionesEntrega", registro)
        except Exception as error:
            raise RuntimeError(
                "La devolución quedó creada en PostgreSQL, pero no se pudo "
                "replicar a Google Sheets. "
                f"Detalle: {error}"
            ) from error

    return {
        "ok": True,
        "duplicado": False,
        "id": registro["CancelacionEntregaID"],
        "registro": registro,
    }




def sincronizar_cancelacion_con_google(cancelacion_id: Any) -> dict[str, Any]:
    """
    Replica a Google Sheets el estado actual de una gestión desde PostgreSQL.
    Solo se habilita en el host, donde PostgreSQL es la fuente de verdad.
    """
    if ES_STREAMLIT_CLOUD:
        raise RuntimeError(
            "La sincronización SQL → Google Sheets solo está disponible en el host."
        )

    cid = limpiar(cancelacion_id)
    if not cid:
        raise ValueError("El ID de la gestión es obligatorio.")

    tabla_sql = leer_hoja("CancelacionesEntrega")
    if tabla_sql is None or tabla_sql.empty:
        raise ValueError("No hay gestiones disponibles en PostgreSQL.")

    if "CancelacionEntregaID" not in tabla_sql.columns:
        raise ValueError("No se encontró CancelacionEntregaID en PostgreSQL.")

    coincidencias = tabla_sql.loc[
        tabla_sql["CancelacionEntregaID"].fillna("").astype(str).str.strip().eq(cid)
    ]
    if coincidencias.empty:
        raise ValueError(f"No existe la gestión {cid} en PostgreSQL.")

    registro = coincidencias.iloc[0].to_dict()

    # Campos vigentes del contrato, sin los campos eliminados de WhatsApp.
    campos = {
        clave: valor
        for clave, valor in registro.items()
        if clave not in {
            "CancelacionEntregaID",
            "TelefonoDestino",
            "EstadoWhatsApp",
            "FechaEnvioWhatsApp",
        }
    }

    asegurar_hoja_google("CancelacionesEntrega")
    try:
        actualizar_registro_google(
            "CancelacionesEntrega",
            "CancelacionEntregaID",
            cid,
            campos,
        )
    except Exception:
        # Si la fila todavía no existe en Sheets, se crea completa.
        registro_google = {
            clave: valor
            for clave, valor in registro.items()
            if clave not in {
                "TelefonoDestino",
                "EstadoWhatsApp",
                "FechaEnvioWhatsApp",
            }
        }
        agregar_registro_google("CancelacionesEntrega", registro_google)

    return {"ok": True, "id": cid}


def tomar_gestion(cancelacion_id: Any, responsable: str) -> dict[str,Any]:
    if not limpiar(responsable): raise ValueError("Indicá el responsable de la gestión.")
    return actualizar(cancelacion_id,{"EstadoCancelacion":"En gestión",
        "ResponsableGestion":limpiar(responsable),"FechaInicioGestion":ahora()})


def confirmar_resultado_operativo(cancelacion_id: Any, resultado: str, responsable: str,
                                  observacion: str="") -> dict[str,Any]:
    validos={"Entrega detenida","Ya despachado","Cancelada"}
    if resultado not in validos: raise ValueError("Resultado operativo inválido.")
    cambios={"EstadoCancelacion":resultado,"ResultadoOperativo":resultado,
        "ResponsableConfirmacion":limpiar(responsable),"FechaConfirmacion":ahora(),
        "ObservacionConfirmacion":limpiar(observacion)}
    if resultado=="Cancelada":
        cambios.update({"FechaCierre":ahora(),"ResultadoFinal":"Gestión cancelada"})
    return actualizar(cancelacion_id,cambios)


def registrar_ir(cancelacion_id: Any, numero_ir: str, responsable: str, observacion: str="") -> dict[str,Any]:
    if not limpiar(numero_ir): raise ValueError("El número de IR es obligatorio.")
    return actualizar(cancelacion_id,{"NumeroIR":limpiar(numero_ir),"FechaIR":ahora(),
        "EstadoCancelacion":"IR generado","ResponsableIR":limpiar(responsable),
        "ObservacionIR":limpiar(observacion)})


def confirmar_reingreso(cancelacion_id: Any, responsable: str, observacion: str="") -> dict[str,Any]:
    return actualizar(cancelacion_id,{"EstadoCancelacion":"Mercadería reingresada",
        "EstadoReingreso":"Confirmado","FechaReingreso":ahora(),
        "ResponsableReingreso":limpiar(responsable),"ObservacionReingreso":limpiar(observacion)})


def finalizar_gestion(cancelacion_id: Any, responsable: str, observacion: str="") -> dict[str,Any]:
    texto="Entrega detenida, IR generado y mercadería reingresada."
    if limpiar(observacion): texto += " "+limpiar(observacion)
    return actualizar(cancelacion_id,{"EstadoCancelacion":"Finalizada","EstadoReingreso":"Finalizado",
        "FechaCierre":ahora(),"ResponsableConfirmacion":limpiar(responsable),"ResultadoFinal":texto})
