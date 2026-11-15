# Clima en Ruta · Neuquén — Android 1.0

Adaptación del paquete `Clima_en_Ruta_Neuquen_local_v3.zip` a Android, creada el 14/11/2026. No necesita Streamlit, WebIntoApp ni una URL propia alojada en un servidor. La pantalla y los 34 puntos de la base están dentro del APK. Las 15 localidades, los recorridos y su orden se contrastaron con el programa Python original en los 210 pares de localidades distintas.

## Instalación

1. Copiar `Clima-en-Ruta-Neuquen-1.0.apk` al teléfono Android y abrirlo.
2. Si Android lo solicita, permitir a esa aplicación (por ejemplo Archivos) instalar el APK.
3. Abrir «Clima en Ruta», elegir origen y destino y tocar «Consultar recorrido».

Requiere Android 8.0 o posterior y Android System WebView actualizado. Se compila para Android 15 (API 35), con mínimo API 26. Usa sólo el permiso de internet: no solicita ubicación, contactos ni archivos. Las localidades se eligen de la base incluida.

Es una aplicación nueva, identificada por `ar.com.climaenruta.neuquen`, con una firma nueva. No se usaron las credenciales ni la firma de WebIntoApp. No se garantiza que sustituya el APK anterior como actualización. No es una publicación en Google Play.

## Datos

- El teléfono consulta `https://w2.dpvneuquen.gov.ar/ParteDiario.csv` directamente.
- Ante fallo de acceso o encabezado inesperado, intenta la copia del repositorio de GitHub. Si también falla, usa la última copia que el teléfono haya guardado.
- Valida el CSV por encabezados, excluye el encabezado como tramo y omite registros de más de 48 horas o con fecha futura. Una copia vencida no se muestra como estado actual.
- El clima se obtiene de Open-Meteo para cada punto del recorrido. La interfaz muestra los errores por punto, conserva las consultas exitosas y permite reintentar.
- «Actualizar datos» hace consultas nuevas. Necesita internet; no funciona como pronóstico sin conexión.
- Los estados estimados por cercanía se identifican como tales. Se conserva el algoritmo de asociación original, que exige dos menciones de puntos y completa huecos por proximidad. No es un cálculo de navegación GPS ni verifica cada metro de la ruta.
- Se mantienen las alternativas, el resumen meteorológico, el pronóstico corto y los enlaces oficiales. Los enlaces se abren fuera de la app.

## Qué se verificó

- Compilación de Java, recursos y DEX; contenido y manifest del APK.
- Firma APK v2/v3 válida y alineación del paquete.
- 210 pares de localidades: igualdad de recorridos y orden con Python.
- CSV real de 106 tramos, columnas reordenadas, cuatro separadores, fechas inválidas, fechas futuras, antigüedad y aislamiento de tramos de otro recorrido.
- Interfaz a 390 × 844 píxeles: selectores, exclusión de origen/destino iguales, consulta, pronóstico, enlaces, datos vencidos, HTML inválido y fallo meteorológico; sin errores JavaScript ni desbordamiento horizontal.
- Vialidad y Open-Meteo respondieron desde la computadora de desarrollo.

**Límite de verificación:** no había un teléfono ni un emulador Android conectado. La aplicación no se instaló ni ejecutó en Android durante esta entrega. Las pruebas de pantalla usaron Chrome móvil simulado y un puente Android simulado, con respuestas de ejemplo obtenidas de las fuentes. Esas respuestas de ejemplo sólo están en las pruebas, no se presentan como datos reales en el APK. La primera instalación y conexión desde el teléfono siguen pendientes.

## Código y compilación

El proyecto utiliza HTML/CSS/JavaScript incluido en el APK y una actividad Android que consulta por HTTPS. El contenido remoto se trata como datos; no se navega a sitios externos dentro de la vista con acceso a Java. No hay anuncios, rastreadores ni dependencias Java de terceros.

Herramientas de compilación en Windows: Python 3.10+, JDK 21 en PATH y Android SDK Build Tools 35.0.0. El SDK no se incluye en el ZIP de código.

```powershell
python download_tools.py
python build.py
node tests/core.test.js
```

La firma de esta versión se conserva en un respaldo privado del propietario y no se publica en GitHub. Para actualizar el APK instalado, restaurar `clima-en-ruta.jks` y `password.txt` en `android/signing/` antes de compilar. Sin esos archivos, el script genera otra firma que no puede actualizar la instalación existente. Aumentar `versionCode` y `versionName` para cada actualización.

La salida se guarda en `build/Clima-en-Ruta-Neuquen-1.0.apk`. `build.py` produce `app/assets/index.html` a partir de `app/web/`; modificar los originales de esa carpeta, no el archivo generado.

Prueba visual opcional: instalar Playwright en `checks/` con `npm install --prefix checks playwright`; ejecutar `node checks/ui-test.js` en una máquina con Chrome en la ruta indicada en el archivo. Esa prueba usa fechas de ejemplo del 14/11/2026; para repetirla en otra fecha se deben actualizar las muestras o fijar el reloj del navegador. La prueba de lógica no depende del reloj actual.

Referencias de herramientas: [AAPT2](https://developer.android.com/tools/aapt2), [apksigner](https://developer.android.com/tools/apksigner).
