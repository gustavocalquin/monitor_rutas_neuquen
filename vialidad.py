"""Formato y vigencia del parte de Vialidad Provincial del Neuquén."""

import csv
import io
from datetime import datetime, timedelta, timezone

TZ_ARG = timezone(timedelta(hours=-3))
MAX_ANTIGUEDAD = timedelta(hours=48)
CAMPOS = {
    "CodigoTramo": "codigo_tramo",
    "RutaNumero": "ruta",
    "RutaProvincial": "ruta_provincial",
    "RutaTramo": "tramo",
    "RutaTipo": "superficie",
    "RutaLongitud": "longitud",
    "RutaEstado": "estado_codigo",
    "RutaSeccion": "restriccion",
    "RutaObservacion": "observaciones",
    "Fecha": "fecha",
    "Hora": "hora",
}


def decodificar_bytes(contenido):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return contenido.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo decodificar el parte")


def fecha_fila(fila):
    return datetime.strptime(
        f"{fila['fecha']} {fila['hora']}", "%d/%m/%Y %H:%M"
    ).replace(tzinfo=TZ_ARG)


def leer_csv_vialidad(texto):
    """Lee por nombre de columna; rechaza HTML, filas truncadas y fechas inválidas."""
    texto = texto.lstrip("\ufeff\r\n ")
    encabezado = texto.splitlines()[0] if texto else ""
    try:
        delimitador = csv.Sniffer().sniff(encabezado, delimiters=",;\t|").delimiter
    except csv.Error as exc:
        raise ValueError("El contenido no tiene un encabezado CSV válido") from exc
    reader = csv.DictReader(io.StringIO(texto), delimiter=delimitador, strict=True)
    nombres = [nombre.strip() for nombre in (reader.fieldnames or [])]
    if len(nombres) != len(set(nombres)) or not set(CAMPOS).issubset(nombres):
        raise ValueError("El parte no tiene las columnas esperadas de Vialidad Provincial")
    reader.fieldnames = nombres
    filas = []
    try:
        for raw in reader:
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"Fila incompleta o con columnas de más: {reader.line_num}")
            fila = {destino: raw[origen].strip() for origen, destino in CAMPOS.items()}
            if not fila["codigo_tramo"].isdigit() or not fila["ruta"].isdigit() or not fila["tramo"]:
                raise ValueError(f"Identificación de tramo inválida: fila {reader.line_num}")
            if fila["ruta_provincial"] not in ("0", "1"):
                raise ValueError(f"Jurisdicción inválida: fila {reader.line_num}")
            if not fila["estado_codigo"]:
                raise ValueError(f"Estado vacío: fila {reader.line_num}")
            fecha_fila(fila)
            filas.append(fila)
    except csv.Error as exc:
        raise ValueError("El parte contiene CSV mal formado") from exc
    if not filas:
        raise ValueError("El parte no contiene tramos")
    return filas


def separar_por_vigencia(filas, ahora=None):
    """No presenta como actuales registros de más de 48 h o fechas futuras."""
    ahora = ahora or datetime.now(TZ_ARG)
    vigentes, descartadas = [], []
    for fila in filas:
        antiguedad = ahora - fecha_fila(fila)
        (vigentes if timedelta(0) <= antiguedad <= MAX_ANTIGUEDAD else descartadas).append(fila)
    return vigentes, descartadas
