# Diagnóstico de Clima en Ruta — Neuquén

Revisión: 14 de noviembre de 2026, horario de Argentina.
Base revisada: `64ad20d00a3bb5ff9c55f9f6c467e1332333afc5`, rama `main`.

## Resultado

El fallo comprobado es de descarga desde GitHub Actions, no un cambio de columnas en el parte ni un cambio de la página de Vialidad Nacional. La aplicación usa una copia de **Vialidad Provincial del Neuquén**. No tiene una integración directa con Vialidad Nacional.

- La última copia en GitHub contiene 106 tramos con fecha **03/11/2026 15:00**.
- Hay **43 ejecuciones consecutivas fallidas**, desde el 04/11/2026 a las 16:35 de Argentina. La ejecución anterior, del mismo día a las 04:18, fue exitosa.
- La última ejecución examinada, del 14/11/2026 a las 21:47, falla al descargar con `No se pudo descargar el parte: <urlopen error timed out>`, aproximadamente a los 35 segundos. No llega a validar ni guardar el archivo.
- Desde esta computadora, la URL configurada responde HTTP 200: 18.985 bytes, 106 tramos, fecha **14/11/2026 14:00**. Mantiene los mismos 11 encabezados que la copia antigua.

Esto confirma una diferencia de acceso entre el entorno de GitHub y la computadora local. Los datos no permiten distinguir entre un bloqueo a la red de GitHub, un problema de resolución/conectividad o una falla intermitente del servidor. No se confirmó una causa de red más específica.

Evidencia: [ejecución fallida y registros](https://github.com/gustavocalquin/monitor_rutas_neuquen/actions/runs/43659912054), [primera ejecución fallida de la serie](https://github.com/gustavocalquin/monitor_rutas_neuquen/actions/runs/41898334534), [script original](https://github.com/gustavocalquin/monitor_rutas_neuquen/blob/64ad20d00a3bb5ff9c55f9f6c467e1332333afc5/scripts/actualizar_parte.py), [copia original](https://github.com/gustavocalquin/monitor_rutas_neuquen/blob/64ad20d00a3bb5ff9c55f9f6c467e1332333afc5/cache/ParteDiario.csv).

## Comparación de fuentes y estructura

| Aspecto | Integración de la app | Página nacional indicada |
|---|---|---|
| Fuente | Vialidad Provincial del Neuquén | Vialidad Nacional |
| Acceso | Descarga programada de `ParteDiario.csv`; la app lee la copia local | Tabla cargada por JavaScript desde Google Sheets |
| Estructura | `CodigoTramo`, `RutaNumero`, `RutaProvincial`, `RutaTramo`, `RutaTipo`, `RutaLongitud`, `RutaEstado`, `RutaSeccion`, `RutaObservacion`, `Fecha`, `Hora` | `filtro-provincia`, `filtro-ruta`, `filtro-tramo`, `estado`, `calzada`, `extension`, `conoce-mas`, `observaciones`, `actualizado` |
| Estado | Códigos como `T`, `TCP`, `I` | Texto con HTML, por ejemplo `HABILITADA` |
| Fecha | Fecha y hora separadas | Un campo `actualizado` |

La [página nacional](https://www.argentina.gob.ar/transporte/vialidad-nacional/estado-de-rutas) responde HTTP 200. Su HTML contiene una tabla inicialmente vacía y configura `ponchoTableDependantCustom` con la planilla `17AqjqeNvM4nG6cOUsUFKFaKXMiNmztYfzHIxeM9FcXk`, hoja `tablavisible`. Se comprobó también que la [exportación de esa hoja](https://docs.google.com/spreadsheets/d/17AqjqeNvM4nG6cOUsUFKFaKXMiNmztYfzHIxeM9FcXk/gviz/tq?tqx=out:csv&sheet=tablavisible) responde y contiene registros de Neuquén.

No hay una captura histórica de esa página en el repositorio con la cual fechar un cambio. Su estructura actual es diferente de la fuente provincial y **no se puede sustituir la URL del CSV por la página nacional**: requiere otro adaptador y una política explícita para combinar fuentes, jurisdicciones y fechas. `HABILITADA` tampoco equivale automáticamente a circulación sin precauciones.

Otro cambio observable: el enlace provincial antiguo `https://w2.dpvneuquen.gov.ar/estadorutas.php` redirige a `https://www.dpvneuquen.gov.ar/`. La portada actual enlaza el PDF en `https://w2.dpvneuquen.gov.ar/ParteDiario.pdf`. La URL del CSV sigue respondiendo; no se encontró una sustitución necesaria de esa fuente.

## Defectos adicionales comprobados en el código

1. El lector incluye el encabezado como registro: devuelve 107 filas para 106 tramos.
2. Lee columnas por posición y rellena filas incompletas con cadenas vacías. Puede interpretar incorrectamente contenido inesperado.
3. La validación de la descarga sólo verifica tamaño, número de filas y un mínimo de columnas; no comprueba encabezados ni fechas.
4. La app no controla antigüedad. Conserva y presenta el parte del 3 de noviembre aunque fallen las actualizaciones.
5. Los errores de carga se silencian. El botón «Actualizar datos» sólo limpia la caché de Streamlit; no ejecuta el workflow ni descarga un parte provincial nuevo.

## Corrección preparada y aplicada localmente

La corrección se preparó y validó localmente durante el diagnóstico. Esta publicación incorpora los cambios al repositorio; la conectividad desde GitHub debe comprobarse en una ejecución posterior del actualizador.

- Nuevo módulo compartido `vialidad.py`: lectura por encabezados, sin fila ficticia, compatible con columnas reordenadas y separadores coma, punto y coma, tabulación y barra vertical.
- Rechazo de archivos vacíos, HTML, encabezados incompatibles, filas truncadas, identificaciones inválidas y fechas inválidas.
- Política explícita de vigencia: se omiten registros de más de **48 horas** y registros con fecha futura; se informa el motivo al usuario. Las 48 horas son un umbral de la aplicación, no una garantía oficial de vigencia.
- La app conserva el clima cuando no hay parte válido, muestra el detalle del error y nombra correctamente a Vialidad Provincial como fuente.
- Tres intentos de descarga para errores de conexión y respuestas HTTP transitorias, con esperas de 2 y 4 segundos. Los errores permanentes, como 404, no se reintentan.
- Se mantiene la escritura atómica y la última copia válida cuando falla la descarga o la validación.
- Enlaces oficiales actualizados, fecha del parte calculada cronológicamente y workflow de pruebas añadido.
- La copia local del parte fue actualizada mediante el script corregido al **14/11/2026 14:00**.

## Pruebas realizadas

**14 pruebas automatizadas aprobadas**, incluidas tres situaciones de la interfaz Streamlit dentro de una prueba de integración: parte vigente, parte vencido y contenido HTML inválido. El clima se simuló para que estas pruebas sean reproducibles y no dependan de Open-Meteo.

Se comprobaron encabezados reordenados, cuatro delimitadores, codificaciones, encabezado sin datos, fecha inválida, mezcla de fechas actuales/antiguas/futuras, límite de 48 horas, recuperación tras timeout, agotamiento de reintentos, HTTP 404 y conservación de la copia ante fallos.

También se ejecutó una descarga real satisfactoria desde la computadora, compilación de los archivos Python y revisión de espacios del parche. La base Excel carga 34 puntos. La prueba de interfaz consulta Chos Malal → Zapala sin excepciones.

Para repetir desde la carpeta descomprimida:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/actualizar_parte.py
python -m streamlit run app.py
```

## Qué queda pendiente para producción

La corrección evita mostrar como actuales los datos vencidos y mejora la tolerancia y el diagnóstico, pero **no demuestra resuelto el timeout desde GitHub**. No se ejecutaron los cambios en un runner de GitHub.

Después de publicar la corrección, ejecutar manualmente «Actualizar parte de Vialidad» y verificar la descarga y el commit. Si persiste el timeout, comparar resolución DNS, conexión TCP/TLS y acceso HTTPS desde ese runner con una red que sí responda. Con 43 fallos consecutivos, no conviene asumir que bastarán los reintentos. Una alternativa operativa es un actualizador programado en una máquina/red con acceso comprobado, o coordinar con Vialidad el acceso desde GitHub. Eso requiere decidir infraestructura y credenciales; no se configuró automáticamente.

La integración adicional con Vialidad Nacional y la revisión del algoritmo que hereda estados entre puntos requieren cambios separados. El parche no altera ese algoritmo ni pretende certificar todos los recorridos. Sin el mensaje exacto de un fallo visible de la app, no puede atribuirse cualquier excepción adicional a este problema de descarga.
