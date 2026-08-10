RUTAS NEUQUINAS - V8.4 CACHE DE VIALIDAD
==========================================

Cambios principales
-------------------
- La app NO consulta directamente al servidor de Vialidad.
- Siempre lee: cache/ParteDiario.csv
- GitHub Actions intenta actualizar esa copia a:
    09:00
    15:00
    18:00
    22:00
  hora Argentina (UTC-3).
- Si la descarga falla o el archivo parece inválido, el script termina sin
  reemplazar la última copia buena.
- Si el parte descargado es idéntico al anterior, no hace commit.
- El botón "Actualizar datos" de Streamlit no genera peticiones a Vialidad:
  limpia la caché de Streamlit y vuelve a consultar clima / releer archivos.

Archivos nuevos
---------------
cache/ParteDiario.csv
scripts/actualizar_parte.py
.github/workflows/actualizar-parte.yml

Subir a GitHub
--------------
Para que funcione online, hay que subir TODO el contenido de este paquete,
incluidas las carpetas ocultas .github/workflows y cache.

En GitHub Actions, el workflow necesita permiso para escribir en el repositorio.
El YAML ya declara:

    permissions:
      contents: write

Si GitHub bloquea el push por configuración del repositorio:
Settings -> Actions -> General -> Workflow permissions
y seleccionar "Read and write permissions".

Prueba manual
-------------
Una vez subido:
GitHub -> Actions -> "Actualizar parte de Vialidad" -> Run workflow

Si funciona, cache/ParteDiario.csv sólo cambiará cuando Vialidad publique
un contenido diferente.

Local
-----
    pip install -r requirements.txt
    python -m streamlit run app.py

Para probar manualmente la descarga del parte:
    python scripts/actualizar_parte.py
