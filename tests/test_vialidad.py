import csv
import io
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts import actualizar_parte as updater
from vialidad import CAMPOS, TZ_ARG, decodificar_bytes, leer_csv_vialidad, separar_por_vigencia

AHORA = datetime(2026, 11, 14, 22, tzinfo=TZ_ARG)


def parte(fecha="14/11/2026", delimitador=",", columnas=None):
    columnas = columnas or list(CAMPOS)
    salida = io.StringIO()
    writer = csv.DictWriter(salida, fieldnames=columnas, delimiter=delimitador)
    writer.writeheader()
    for i in range(6):
        writer.writerow(dict(zip(CAMPOS, [str(i), "40", "0", "Zapala - Las Lajas",
            "Pavim", "54", "TCP", "", "Precaución; equipos, operando. " * 8, fecha, "14:00"])))
    return salida.getvalue()


class FormatoTests(unittest.TestCase):
    def test_no_incluye_encabezado_y_preserva_campos(self):
        filas = leer_csv_vialidad(parte())
        self.assertEqual(len(filas), 6)
        self.assertEqual(filas[0]["ruta"], "40")
        self.assertEqual(filas[0]["tramo"], "Zapala - Las Lajas")
        self.assertIn("equipos, operando", filas[0]["observaciones"])

    def test_columnas_reordenadas_y_delimitadores(self):
        esperado = leer_csv_vialidad(parte())
        for delimitador in (",", ";", "\t", "|"):
            with self.subTest(delimitador=delimitador):
                self.assertEqual(leer_csv_vialidad(parte(delimitador=delimitador,
                    columnas=list(reversed(CAMPOS)))), esperado)

    def test_codificaciones(self):
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            self.assertEqual(leer_csv_vialidad(decodificar_bytes(parte().encode(encoding))),
                             leer_csv_vialidad(parte()))

    def test_rechaza_html_vacio_truncado_y_fecha_invalida(self):
        for contenido in ("", "<html>" + "error," * 2000 + "</html>",
                          parte().replace("RutaNumero", "OtraColumna"),
                          parte().rsplit(",", 1)[0], parte(fecha="31/02/2026")):
            with self.subTest(contenido=contenido[:30]), self.assertRaises(ValueError):
                leer_csv_vialidad(contenido)

    def test_rechaza_encabezado_sin_datos(self):
        with self.assertRaises(ValueError):
            leer_csv_vialidad(parte().splitlines()[0])

    def test_fechas_mezcladas_y_futuras(self):
        nuevas = leer_csv_vialidad(parte())
        viejas = leer_csv_vialidad(parte(fecha="03/11/2026"))
        futuras = leer_csv_vialidad(parte(fecha="15/11/2026"))
        vigentes, descartadas = separar_por_vigencia(nuevas + viejas + futuras, AHORA)
        self.assertEqual(vigentes, nuevas)
        self.assertEqual(descartadas, viejas + futuras)

    def test_limite_48_horas(self):
        filas = leer_csv_vialidad(parte())
        limite = datetime(2026, 11, 16, 14, tzinfo=TZ_ARG)
        self.assertEqual(separar_por_vigencia(filas, limite)[0], filas)
        self.assertFalse(separar_por_vigencia(filas, limite + timedelta(seconds=1))[0])

    def test_validador_rechaza_parte_vencido(self):
        updater.validar(parte().encode(), AHORA)
        with self.assertRaises(ValueError):
            updater.validar(parte(fecha="03/11/2026").encode(), AHORA)


class DescargaTests(unittest.TestCase):
    @patch.object(updater.time, "sleep")
    @patch.object(updater, "urlopen")
    def test_reintenta_timeout_y_recupera(self, abrir, dormir):
        from unittest.mock import MagicMock
        respuesta = MagicMock()
        respuesta.__enter__.return_value.read.return_value = b"csv"
        abrir.side_effect = [URLError("timed out"), respuesta]
        self.assertEqual(updater.descargar(), b"csv")
        self.assertEqual(abrir.call_count, 2)
        dormir.assert_called_once_with(2)

    @patch.object(updater.time, "sleep")
    @patch.object(updater, "urlopen", side_effect=URLError("timed out"))
    def test_agota_reintentos(self, abrir, dormir):
        with self.assertRaises(URLError):
            updater.descargar()
        self.assertEqual(abrir.call_count, 3)

    @patch.object(updater.time, "sleep")
    @patch.object(updater, "urlopen", side_effect=HTTPError(updater.URL, 404, "Not Found", {}, None))
    def test_no_reintenta_404(self, abrir, dormir):
        with self.assertRaises(HTTPError):
            updater.descargar()
        abrir.assert_called_once()
        dormir.assert_not_called()

    def test_fallo_descarga_o_validacion_conserva_cache(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "ParteDiario.csv"
            destino.write_bytes(b"copia anterior")
            with patch.object(updater, "DEST", destino):
                with patch.object(updater, "descargar", side_effect=URLError("timeout")):
                    self.assertEqual(updater.main(), 1)
                self.assertEqual(destino.read_bytes(), b"copia anterior")
                with patch.object(updater, "descargar", return_value=b"<html>error</html>"):
                    self.assertEqual(updater.main(), 1)
                self.assertEqual(destino.read_bytes(), b"copia anterior")

    def test_guarda_solo_descarga_validada(self):
        data = parte().encode()
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "cache" / "ParteDiario.csv"
            with patch.object(updater, "DEST", destino), \
                 patch.object(updater, "descargar", return_value=data), \
                 patch.object(updater, "validar", side_effect=lambda d: updater_validar(d, AHORA)):
                self.assertEqual(updater.main(), 0)
            self.assertEqual(destino.read_bytes(), data)
            self.assertEqual(list(destino.parent.glob("*.tmp")), [])


updater_validar = updater.validar

if __name__ == "__main__":
    unittest.main()
