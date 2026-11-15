#!/usr/bin/env python3
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import sys
import tempfile
import time
from http.client import HTTPException

URL = "https://w2.dpvneuquen.gov.ar/ParteDiario.csv"
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "cache" / "ParteDiario.csv"
sys.path.insert(0, str(ROOT))
from vialidad import decodificar_bytes, leer_csv_vialidad, separar_por_vigencia

MIN_BYTES = 1000
MIN_ROWS = 5


def validar(data: bytes, ahora=None) -> None:
    if len(data) < MIN_BYTES:
        raise ValueError(f"Archivo demasiado pequeño: {len(data)} bytes")

    rows = leer_csv_vialidad(decodificar_bytes(data))

    if len(rows) < MIN_ROWS:
        raise ValueError(f"CSV con muy pocas filas: {len(rows)}")

    vigentes, _ = separar_por_vigencia(rows, ahora)
    if not vigentes:
        raise ValueError("El parte no contiene registros vigentes (máximo 48 horas)")


def descargar(intentos=3):
    req = Request(
        URL,
        headers={"User-Agent": "Rutas-Neuquinas-Cache/1.0"}
    )

    for intento in range(1, intentos + 1):
        try:
            with urlopen(req, timeout=35) as response:
                return response.read()
        except (URLError, OSError, HTTPException) as exc:
            print(f"Descarga {intento}/{intentos} falló ({URL}): {exc}", file=sys.stderr)
            if isinstance(exc, HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            if intento == intentos:
                raise
            time.sleep(2 ** intento)


def main():
    try:
        data = descargar()
    except (URLError, OSError, HTTPException) as exc:
        print(f"No se pudo descargar el parte; se conserva la copia anterior: {exc}", file=sys.stderr)
        return 1

    try:
        validar(data)
    except Exception as exc:
        print(f"El archivo descargado no pasó la validación: {exc}", file=sys.stderr)
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)

    # Escritura atómica: nunca pisamos la última copia buena con algo incompleto.
    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=DEST.parent,
        prefix="ParteDiario.",
        suffix=".tmp",
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    tmp_path.replace(DEST)
    print(f"Parte actualizado correctamente: {DEST} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
