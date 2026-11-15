"""Prueba el recorrido con clima simulado y distintos estados del parte."""
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from test_vialidad import parte
from vialidad import TZ_ARG


class AppTests(unittest.TestCase):
    def test_vigente_vencido_e_invalido(self):
        root = Path(__file__).resolve().parents[1]
        ahora = datetime.now(TZ_ARG)
        fecha = (ahora - timedelta(hours=1)).strftime("%d/%m/%Y")
        hora = (ahora - timedelta(hours=1)).strftime("%H:%M")
        vigente = parte(fecha=fecha).replace('14:00', hora)
        viejo = parte(fecha=(ahora - timedelta(days=10)).strftime("%d/%m/%Y"))
        clima = MagicMock()
        clima.json.return_value = {
            "current": {"temperature_2m": 10, "wind_gusts_10m": 20,
                        "wind_speed_10m": 10, "weather_code": 0},
            "hourly": {"time": []},
        }
        with tempfile.TemporaryDirectory() as carpeta:
            base = Path(carpeta)
            for nombre in ("app.py", "Rutas Neuquinas - DB.xlsx"):
                shutil.copy2(root / nombre, base / nombre)
            (base / "cache").mkdir()
            for nombre, contenido in (("vigente", vigente), ("vencido", viejo),
                                      ("invalido", "<html>Error del servidor</html>")):
                with self.subTest(nombre=nombre):
                    st.cache_data.clear()
                    (base / "cache" / "ParteDiario.csv").write_text(contenido, encoding="utf-8")
                    with patch("requests.get", return_value=clima):
                        app = AppTest.from_file(str(base / "app.py"), default_timeout=20)
                        app.session_state["consulta_activa"] = ("CHOS MALAL", "ZAPALA")
                        app.run()
                    self.assertFalse(app.exception)
                    avisos = [w.value for w in app.warning]
                    self.assertEqual(any("No hay un parte vigente" in w for w in avisos),
                                     nombre != "vigente")
                    self.assertTrue(any("Resumen meteorológico" in m.value for m in app.markdown))
                    if nombre == "invalido":
                        self.assertTrue(any("Detalle del problema" in e.label for e in app.expander))
        st.cache_data.clear()
