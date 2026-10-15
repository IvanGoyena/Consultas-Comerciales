from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

from utils.estado_actualizacion import registrar_version_fuente


GITHUB_OWNER = "IvanGoyena"
GITHUB_REPO = "Logistica-Peirano"
GITHUB_BRANCH = "main"
RAW_BASE = "https://raw.githubusercontent.com"


class GitHubReaderError(RuntimeError):
    pass


def _ruta_normalizada(ruta_github: str) -> str:
    return str(ruta_github).replace("\\", "/").lstrip("/")


def _url_raw(ruta_github: str) -> str:
    ruta = quote(_ruta_normalizada(ruta_github), safe="/")
    return (
        f"{RAW_BASE}/{quote(GITHUB_OWNER)}/{quote(GITHUB_REPO)}/"
        f"{quote(GITHUB_BRANCH)}/{ruta}"
    )


def descargar_archivo_github(
    ruta_github: str,
) -> tuple[bytes, dict]:
    ruta_github = _ruta_normalizada(ruta_github)

    request = Request(
        _url_raw(ruta_github),
        method="GET",
        headers={
            "User-Agent": "Sistema-Comercial-Peirano",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )

    try:
        with urlopen(request, timeout=45) as response:
            datos = response.read()
            headers = response.headers

    except HTTPError as error:
        raise GitHubReaderError(
            f"GitHub RAW HTTP {error.code}: {ruta_github}"
        ) from error

    except URLError as error:
        raise GitHubReaderError(
            f"No se pudo conectar con GitHub RAW: {error}"
        ) from error

    if not datos:
        raise GitHubReaderError(
            f"GitHub devolvió el archivo vacío: {ruta_github}"
        )

    version = (
        str(headers.get("ETag", "")).strip()
        or str(headers.get("Last-Modified", "")).strip()
        or f"bytes:{len(datos)}"
    )

    return datos, {
        "ruta_github": ruta_github,
        "sha": version,
        "size": len(datos),
        "name": Path(ruta_github).name,
    }


def _leer_csv_bytes(datos: bytes) -> pd.DataFrame:
    errores = []

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(
                BytesIO(datos),
                sep=None,
                engine="python",
                encoding=encoding,
            )
        except Exception as error:
            errores.append(
                f"{encoding}: {type(error).__name__}"
            )

    raise GitHubReaderError(
        "No se pudo interpretar el CSV descargado. "
        + " | ".join(errores)
    )


def _leer_excel_bytes(datos: bytes) -> pd.DataFrame:
    return pd.read_excel(BytesIO(datos))


def _leer_dataframe_github_sin_cache(
    ruta_github: str,
) -> pd.DataFrame:
    datos, metadata = descargar_archivo_github(ruta_github)

    registrar_version_fuente(
        f"github:{ruta_github}",
        metadata.get("sha", ""),
    )

    extension = Path(ruta_github).suffix.lower()

    print(
        "Leyendo versión actual desde GitHub RAW: "
        f"{ruta_github}"
    )

    if extension == ".csv":
        return _leer_csv_bytes(datos)

    if extension in {".xlsx", ".xls", ".xlsm"}:
        return _leer_excel_bytes(datos)

    if extension == ".parquet":
        return pd.read_parquet(BytesIO(datos))

    raise GitHubReaderError(
        f"Formato GitHub no soportado: {extension or 'sin extensión'}"
    )


@st.cache_data(ttl=300, max_entries=64, show_spinner=False)
def _leer_dataframe_github_cache(
    ruta_github: str,
) -> pd.DataFrame:
    return _leer_dataframe_github_sin_cache(ruta_github)


def leer_archivo_github(
    ruta_github: str,
    *,
    cache: bool = False,
) -> pd.DataFrame:
    return _leer_dataframe_github_cache(
        _ruta_normalizada(ruta_github)
    ).copy()


def limpiar_cache_github_reader() -> None:
    _leer_dataframe_github_cache.clear()
