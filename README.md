# Clima en Ruta · Neuquén

Consultá recorridos, clima y partes de Vialidad para viajar por Neuquén.

## Descargar para Android

### [Descargar APK · versión 1.0](https://github.com/gustavocalquin/monitor_rutas_neuquen/raw/refs/heads/main/downloads/Clima-en-Ruta-Neuquen-1.0.apk)

Abrí el enlace desde tu teléfono, descargá el archivo y abrilo para instalarlo. Si Android lo solicita, permití la instalación desde la aplicación con la que abriste el APK.

- Android 8.0 o posterior, con Android System WebView actualizado.
- Necesita internet para consultar clima y actualizar el parte.
- Incluye 15 localidades y 34 puntos de la base original; no necesita WebIntoApp ni un servidor propio.
- Es una instalación con firma nueva. No se garantiza que actualice el APK anterior de WebIntoApp.
- Firma y paquete verificados; los 210 pares de localidades coinciden con el programa original. La instalación en un teléfono real todavía no fue comprobada.

[Guía y código Android](android/README.md) · [SHA-256 del APK](downloads/SHA256SUMS.txt)

## Fuentes y vigencia

La fuente del parte es **Vialidad Provincial del Neuquén**, que también incluye tramos de rutas nacionales. La página de Vialidad Nacional es un enlace de consulta independiente.

La versión Android intenta descargar el parte directamente; ante un fallo de acceso, recurre a la copia de GitHub y luego a la última copia del teléfono. Sólo presenta registros de las últimas 48 horas y sin fecha futura. El clima se consulta en Open-Meteo para cada punto del recorrido.

La aplicación Python/Streamlit usa `cache/ParteDiario.csv`, actualizado por GitHub Actions. Si la descarga falla, conserva la copia anterior y avisa cuando los datos quedan fuera de vigencia. [Diagnóstico y pruebas de la corrección](DIAGNOSTICO.md).

## Ejecutar la versión Python

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Pruebas:

```sh
python -m unittest discover -s tests -v
node android/tests/core.test.js
```

## Información orientativa

Los datos pueden contener errores, demoras o diferencias respecto del estado real de las rutas. Los estados estimados por cercanía no confirman la condición de cada tramo. Antes de viajar, verificá las condiciones con los organismos oficiales.

- [Vialidad Provincial del Neuquén](https://www.dpvneuquen.gov.ar/)
- [Parte diario provincial](https://w2.dpvneuquen.gov.ar/ParteDiario.pdf)
- [Vialidad Nacional · Estado de rutas](https://www.argentina.gob.ar/transporte/vialidad-nacional/estado-de-rutas)
- [Alertas del SMN](https://www.smn.gob.ar/alertas)
