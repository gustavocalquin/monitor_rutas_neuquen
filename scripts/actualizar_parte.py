#!/usr/bin/env python3
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import csv
import io
import sys
import tempfile

URL = "https://w2.dpvneuquen.gov.ar/ParteDiario.csv"
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "cache" / "ParteDiario.csv"

MIN_BYTES = 1000
MIN_ROWS = 5


def decode_bytes(data: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def validar(data: bytes) -> None:
    if len(data) < MIN_BYTES:
        raise ValueError(f"Archivo demasiado pequeño: {len(data)} bytes")

    text = decode_bytes(data)

    try:
        dialect = csv.Sniffer().sniff(text[:5000], delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";"

    rows = [
        row for row in csv.reader(io.StringIO(text), delimiter=delim)
        if any(str(x).strip() for x in row)
    ]

    if len(rows) < MIN_ROWS:
        raise ValueError(f"CSV con muy pocas filas: {len(rows)}")

    # El formato conocido tiene al menos ruta, tramo, estado, fecha y hora.
    valid_like = sum(1 for row in rows if len(row) >= 9)
    if valid_like < MIN_ROWS:
        raise ValueError("El contenido descargado no parece un parte válido")


def main():
    req = Request(
        URL,
        headers={"User-Agent": "Rutas-Neuquinas-Cache/1.0"}
    )

    try:
        with urlopen(req, timeout=35) as response:
            data = response.read()
    except (URLError, HTTPError, TimeoutError) as exc:
        print(f"No se pudo descargar el parte: {exc}", file=sys.stderr)
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
