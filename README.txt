
MONITOR DE RUTAS - PROTOTIPO V7

Corredor incorporado:
- Las Ovejas → Andacollo
- Andacollo → Chos Malal
- Chos Malal → Las Lajas
- Las Lajas → Zapala
- Zapala → Cutral Co
- Cutral Co → Neuquén

Puntos críticos provisionales:
- El Llano
- Sector Chorriaca–Naunauco
- Sector Zapala–Cutral Co

Estos puntos están pensados para validarse posteriormente con los choferes.

También incorpora Links de interés:
- Canal de WhatsApp Rutas neuquinas
- Vialidad Provincial del Neuquén
- Alertas del SMN

EJECUTAR

    python -m streamlit run app.py

Luego abrir:

    http://localhost:8501

NOTA
La app intenta localizar automáticamente los registros oficiales de cada
sector dentro del CSV de Vialidad. Si no encuentra un registro específico,
lo informa en pantalla y continúa mostrando la información meteorológica.
