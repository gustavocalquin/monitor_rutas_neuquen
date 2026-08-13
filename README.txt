CLIMA EN RUTA - NEUQUÉN · PRUEBA LOCAL
=======================================

Esta carpeta es una versión de prueba. No modifica la app publicada ni el
repositorio de GitHub.

CAMBIOS DE ESTA VERSIÓN
-----------------------
- Nuevo nombre visible: Clima en Ruta - Neuquén.
- Compatible con la nueva base Excel sin columna ORDEN.
- LATITUD y LONGITUD se leen desde columnas separadas.
- CORREDOR contiene la secuencia ordenada de códigos.
- Una localidad puede pertenecer a varios corredores.
- Se pueden combinar corredores cuando comparten un nodo.
- Si existen caminos alternativos (por ejemplo Costa/Cordillera), se muestran
  como alternativas separadas.
- Sólo TIPO=LOCALIDAD aparece en Origen/Destino.
- Localidades seleccionables ordenadas alfabéticamente.
- Nuevo criterio conservador para Vialidad: un tramo oficial sólo colorea el
  recorrido cuando menciona al menos dos nodos incluidos. Esto evita que un
  tramo como "Chos Malal - Barrancas" contamine una consulta hacia otro rumbo.
- Los puntos sin asociación segura heredan el estado del punto asociado más próximo del recorrido.
- Si hay empate de distancia, se usa el estado más restrictivo.
- El fallback también se aplica al origen y al destino.
- El disclaimer se muestra debajo de "Actualizar datos" y antes de "Links de interés".
- Los teléfonos de emergencia quedan para el próximo update.

DATOS DE VIALIDAD
-----------------
La app NO consulta directamente al servidor de Vialidad.
1. Si existe cache/ParteDiario.csv, usa ese archivo.
2. Para esta prueba local, si falta el archivo intenta leer la copia cacheada
   que ya está publicada en el repositorio de GitHub.

EJECUTAR EN WINDOWS
-------------------
1. Abrí una terminal dentro de esta carpeta.
2. Instalá dependencias (sólo la primera vez):

   pip install -r requirements.txt

3. Ejecutá:

   python -m streamlit run app.py

PRUEBAS SUGERIDAS
-----------------
- Chos Malal -> Zapala
  Debe seguir el corredor principal y no tomar como propio un tramo hacia Barrancas.

- Chos Malal -> Tricao Malal
  Debe encontrar dos alternativas (Costa y Cordillera).

- Neuquén -> Manzano Amargo
  Debe poder continuar desde el corredor principal al corredor que nace en Las Ovejas.

- Revisar los desplegables
  Sólo deben aparecer LOCALIDADES y tienen que estar en orden alfabético.

- Revisar recorridos con huecos de asociación
  No deberían quedar nodos aislados en blanco si existe un punto asociado cercano.

PRUEBAS ARTIFICIALES DEL FALLBACK
---------------------------------
Se verificó la lógica A-B-C y A-B-C-D: proximidad primero y, ante empate,
el estado más restrictivo. También se verificó el fallback en origen y destino.


Versión de prueba local v3
--------------------------
- Los selectores de Origen y Destino ya no usan un campo de búsqueda, para evitar que se abra el teclado en móvil/APK.
- Las localidades se eligen desde una lista táctil ordenada alfabéticamente.
- La consulta se ejecuta únicamente al tocar "Buscar recorrido".
- Durante la consulta se muestra un indicador de carga.
- El disclaimer permanece entre "Actualizar datos" y "Links de interés".
