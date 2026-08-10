
import csv
import io
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import openpyxl
import requests
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "Rutas Neuquinas - DB.xlsx"
VIALIDAD_CACHE_PATH = BASE_DIR / "cache" / "ParteDiario.csv"

CSV_URL = "https://w2.dpvneuquen.gov.ar/ParteDiario.csv"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
TZ_ARG = ZoneInfo("America/Argentina/Salta")

LINKS_INTERES = {
    "📢 Rutas neuquinas · WhatsApp":
        "https://whatsapp.com/channel/0029Vakr9GiIyPtaTYFeIe2J",
    "🛣️ Vialidad Provincial del Neuquén":
        "https://w2.dpvneuquen.gov.ar/estadorutas.php",
    "🌦️ Alertas del SMN":
        "https://www.smn.gob.ar/alertas",
}


st.set_page_config(
    page_title="Rutas Neuquinas - Estado del tránsito y del tiempo",
    page_icon="🚌",
    layout="centered",
)

st.markdown("""
<style>
.block-container {
    max-width: 760px;
    padding-top: 2.2rem;
    padding-bottom: 2.5rem;
}
.app-title {
    font-size: 1.8rem;
    font-weight: 800;
    line-height: 1.15;
    margin: .2rem 0 .35rem 0;
}
.app-sub {
    opacity: .72;
    margin-bottom: 1.1rem;
}
.route-card {
    border: 1px solid rgba(128,128,128,.22);
    border-radius: 22px;
    padding: 17px;
    background: rgba(128,128,128,.04);
    margin: 12px 0;
}
.route-name {
    font-size: 1.2rem;
    font-weight: 750;
}
.route-temp {
    font-size: 2.7rem;
    font-weight: 800;
    line-height: 1;
    margin: 7px 0 5px 0;
}
.route-sub {
    opacity: .72;
    font-size: .93rem;
}
.poi-box {
    border-left: 4px solid #f0a000;
    padding: 11px 13px;
    margin: 10px 0;
    border-radius: 10px;
    background: rgba(240,160,0,.08);
}
.point-line {
    font-size: .92rem;
    opacity: .8;
}
.stButton > button,
.stLinkButton > a {
    border-radius: 16px;
    min-height: 3rem;
}
</style>
""", unsafe_allow_html=True)


def normalizar(texto):
    texto = str(texto or "").upper().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def parse_latlong(valor):
    partes = [p.strip() for p in str(valor).split(",")]
    if len(partes) != 2:
        raise ValueError(f"Coordenadas inválidas: {valor}")
    return float(partes[0]), float(partes[1])


@st.cache_data
def cargar_base():
    libro = openpyxl.load_workbook(DB_PATH, data_only=True)
    puntos = []

    for hoja in libro.worksheets:
        encabezados = [
            normalizar(c.value) if c.value is not None else ""
            for c in hoja[1]
        ]
        idx = {nombre: i for i, nombre in enumerate(encabezados)}

        requeridos = [
            "ID", "CODIGO", "CORREDOR", "ORDEN", "NOMBRE",
            "LATITUD - LONGITUD", "TIPO", "RUTA", "PRIORIDAD", "NOTA"
        ]

        if not all(c in idx for c in requeridos):
            continue

        for fila in hoja.iter_rows(min_row=2, values_only=True):
            if not fila[idx["NOMBRE"]]:
                continue

            lat, lon = parse_latlong(fila[idx["LATITUD - LONGITUD"]])

            orden_raw = fila[idx["ORDEN"]]
            try:
                orden = int(str(orden_raw))
            except Exception:
                continue

            puntos.append({
                "id": str(fila[idx["ID"]] or "").strip(),
                "codigo": normalizar(fila[idx["CODIGO"]]),
                "corredor": str(fila[idx["CORREDOR"]] or "").strip(),
                "orden": orden,
                "nombre": normalizar(fila[idx["NOMBRE"]]),
                "lat": lat,
                "lon": lon,
                "tipo": normalizar(fila[idx["TIPO"]]),
                "ruta": normalizar(fila[idx["RUTA"]]),
                "prioridad": normalizar(fila[idx["PRIORIDAD"]]),
                "nota": str(fila[idx["NOTA"]] or "").strip(),
                "hoja": hoja.title,
            })

    puntos.sort(key=lambda p: (p["corredor"], p["orden"]))
    return puntos



def leer_csv_vialidad(texto):
    try:
        dialecto = csv.Sniffer().sniff(texto[:5000], delimiters=",;\t|")
        delimitador = dialecto.delimiter
    except csv.Error:
        delimitador = ";"

    filas = []
    for f in csv.reader(io.StringIO(texto), delimiter=delimitador):
        if not any(str(x).strip() for x in f):
            continue
        campos = f + [""] * max(0, 11 - len(f))
        filas.append({
            "ruta": str(campos[1]).strip(),
            "tramo": str(campos[3]).strip(),
            "superficie": str(campos[4]).strip(),
            "longitud": str(campos[5]).strip(),
            "estado_codigo": str(campos[6]).strip(),
            "restriccion": str(campos[7]).strip(),
            "observaciones": str(campos[8]).strip(),
            "fecha": str(campos[9]).strip(),
            "hora": str(campos[10]).strip(),
        })
    return filas


@st.cache_data(ttl=300)
def cargar_vialidad():
    """
    Lee exclusivamente la copia local del último parte válido.
    La actualización de este archivo la realiza GitHub Actions;
    los usuarios de la app nunca consultan directamente a Vialidad.
    """
    if not VIALIDAD_CACHE_PATH.exists():
        raise FileNotFoundError("No existe una copia local del parte de Vialidad.")

    contenido = VIALIDAD_CACHE_PATH.read_bytes()

    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            texto = contenido.decode(enc)
            break
        except UnicodeDecodeError:
            texto = None

    if texto is None:
        texto = contenido.decode("utf-8", errors="replace")

    return leer_csv_vialidad(texto)


@st.cache_data(ttl=300)
def consultar_clima(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "America/Argentina/Salta",
        "forecast_days": 2,
        "current": ",".join([
            "temperature_2m",
            "precipitation",
            "rain",
            "snowfall",
            "weather_code",
            "wind_speed_10m",
            "wind_gusts_10m",
        ]),
        "hourly": ",".join([
            "temperature_2m",
            "precipitation",
            "rain",
            "snowfall",
            "weather_code",
            "wind_speed_10m",
            "wind_gusts_10m",
            "visibility",
        ]),
    }
    r = requests.get(
        WEATHER_URL,
        params=params,
        headers={"User-Agent": "Monitor-Rutas-Neuquen/0.84"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def estado_info(codigo):
    c = normalizar(codigo)
    if c in ("I", "INT"):
        return 3, "🔴", "INTRANSITABLE"
    if c == "TCP":
        return 2, "🟡", "TRANSITABLE CON PRECAUCION"
    if c == "T":
        return 1, "🟢", "TRANSITABLE"
    return 0, "⚪", c or "SIN DATO"


def descripcion_tiempo(codigo):
    mapa = {
        0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado",
        3: "Cubierto", 45: "Niebla", 48: "Niebla con escarcha",
        51: "Llovizna leve", 53: "Llovizna moderada", 55: "Llovizna intensa",
        56: "Llovizna helada leve", 57: "Llovizna helada intensa",
        61: "Lluvia leve", 63: "Lluvia moderada", 65: "Lluvia intensa",
        66: "Lluvia helada leve", 67: "Lluvia helada intensa",
        71: "Nevada leve", 73: "Nevada moderada", 75: "Nevada intensa",
        77: "Granos de nieve", 80: "Chaparrones leves",
        81: "Chaparrones moderados", 82: "Chaparrones intensos",
        85: "Chaparrones de nieve leves", 86: "Chaparrones de nieve intensos",
        95: "Tormenta", 96: "Tormenta con granizo leve",
        99: "Tormenta con granizo intenso",
    }
    return mapa.get(codigo, f"Código {codigo}")


def icono_tiempo(codigo):
    if codigo == 0: return "☀️"
    if codigo in (1, 2): return "🌤️"
    if codigo == 3: return "☁️"
    if codigo in (45, 48): return "🌫️"
    if codigo in (51, 53, 55, 61, 63, 65, 80, 81, 82): return "🌧️"
    if codigo in (56, 57, 66, 67): return "🧊"
    if codigo in (71, 73, 75, 77, 85, 86): return "🌨️"
    if codigo in (95, 96, 99): return "⛈️"
    return "🌡️"


def horas_futuras(datos, offsets=(1, 2, 3, 6)):
    hourly = datos["hourly"]
    tiempos = [datetime.fromisoformat(t) for t in hourly["time"]]
    ahora = datetime.now(TZ_ARG).replace(tzinfo=None)

    base = next((i for i, t in enumerate(tiempos) if t > ahora), None)
    if base is None:
        return []

    resultado = []
    for offset in offsets:
        i = base + offset - 1
        if i >= len(tiempos):
            continue
        resultado.append({
            "offset": offset,
            "hora": tiempos[i],
            "temperatura": hourly["temperature_2m"][i],
            "precipitacion": hourly["precipitation"][i],
            "nieve": hourly["snowfall"][i],
            "codigo": hourly["weather_code"][i],
            "rafagas": hourly["wind_gusts_10m"][i],
            "visibilidad": hourly["visibility"][i],
        })
    return resultado


def seleccionar_recorrido(puntos, origen, destino):
    po = next(p for p in puntos if p["nombre"] == origen)
    pd = next(p for p in puntos if p["nombre"] == destino)

    if po["corredor"] != pd["corredor"]:
        return []

    minimo = min(po["orden"], pd["orden"])
    maximo = max(po["orden"], pd["orden"])

    seleccion = [
        p for p in puntos
        if p["corredor"] == po["corredor"]
        and minimo <= p["orden"] <= maximo
    ]
    seleccion.sort(key=lambda p: p["orden"])

    if po["orden"] > pd["orden"]:
        seleccion.reverse()

    return seleccion



def ruta_equivalente(ruta_punto, ruta_vialidad):
    """
    Compara RN22/RP43/RN40 con la forma en que Vialidad escribe la ruta.
    Se prioriza el número, porque el CSV puede variar en prefijos/formato.
    """
    rp = normalizar(ruta_punto)
    rv = normalizar(ruta_vialidad)

    numero_p = "".join(c for c in rp if c.isdigit())
    numero_v = "".join(c for c in rv if c.isdigit())

    return bool(numero_p and numero_v and numero_p == numero_v)


def nivel_visual_fila(fila):
    """
    Traduce exclusivamente información OFICIAL de Vialidad a color.

    ROJO   = intransitable.
    NARANJA= transitable con precaución + condición/restricción importante
             mencionada en el parte (hielo, nieve, cadenas, horario, etc.).
    AMARILLO = transitable con precaución.
    VERDE  = transitable.
    """
    severidad, _, estado = estado_info(fila["estado_codigo"])

    if severidad >= 3:
        return 4, "🔴", "INTRANSITABLE"

    texto = normalizar(
        f'{fila.get("restriccion", "")} {fila.get("observaciones", "")}'
    )

    claves_naranja = (
        "CADENA",
        "HIELO",
        "NIEVE",
        "HORARIO",
        "NOCTURNO",
        "RESTRICCION",
        "PORTACION",
        "OBLIGATORIO",
        "OBLIGATORIA",
        "CALZADA RESBALADIZA",
    )

    if severidad == 2 and any(clave in texto for clave in claves_naranja):
        return 3, "🟠", "PRECAUCION / RESTRICCION IMPORTANTE"

    if severidad == 2:
        return 2, "🟡", "TRANSITABLE CON PRECAUCION"

    if severidad == 1:
        return 1, "🟢", "TRANSITABLE"

    return 0, "⚪", "SIN DATO"


def estados_oficiales_por_punto(filas, recorrido):
    """
    Asocia filas de Vialidad a los puntos del recorrido sin inventar estados.

    Regla principal:
    - Si un parte menciona dos o más puntos conocidos de la misma ruta,
      se considera que cubre el intervalo comprendido entre ellos.
    - Si menciona un solo punto conocido, se asocia únicamente a ese punto.
    - Si no menciona ningún punto de nuestra base, no se fuerza una asociación.

    Si varias filas afectan el mismo punto, se conserva la condición más severa.
    """
    resultado = {
        p["codigo"]: {
            "nivel": 0,
            "icono": "⚪",
            "texto": "SIN ASOCIACION SEGURA AL PARTE",
            "filas": [],
        }
        for p in recorrido
    }

    for fila in filas:
        puntos_misma_ruta = [
            p for p in recorrido
            if ruta_equivalente(p["ruta"], fila["ruta"])
        ]

        if not puntos_misma_ruta:
            continue

        texto_tramo = normalizar(fila.get("tramo", ""))

        mencionados = [
            p for p in puntos_misma_ruta
            if p["nombre"] and p["nombre"] in texto_tramo
        ]

        afectados = []

        if len(mencionados) >= 2:
            minimo = min(p["orden"] for p in mencionados)
            maximo = max(p["orden"] for p in mencionados)

            afectados = [
                p for p in puntos_misma_ruta
                if minimo <= p["orden"] <= maximo
            ]

        elif len(mencionados) == 1:
            afectados = mencionados

        else:
            continue

        nivel, icono, texto = nivel_visual_fila(fila)

        for punto in afectados:
            actual = resultado[punto["codigo"]]
            actual["filas"].append(fila)

            if nivel > actual["nivel"]:
                actual["nivel"] = nivel
                actual["icono"] = icono
                actual["texto"] = texto

    return resultado


def completar_estados_conservadores(recorrido, estados):
    """
    Completa puntos sin asociación directa usando una regla conservadora.

    Para cada punto sin estado:
    - busca la referencia conocida más cercana hacia atrás y hacia adelante
      dentro de la misma ruta;
    - si existen ambas, usa la condición más restrictiva;
    - si sólo existe una, hereda esa condición;
    - si no hay ninguna referencia conocida para esa ruta, permanece gris.

    La inferencia sólo afecta la visualización del semáforo. No modifica
    ni inventa registros del parte oficial.
    """
    resultado = {
        codigo: dict(valor)
        for codigo, valor in estados.items()
    }

    # Trabajamos por ruta para no mezclar estados de RN22, RN40, RP43, etc.
    rutas = []
    for p in recorrido:
        if p["ruta"] and p["ruta"] not in rutas:
            rutas.append(p["ruta"])

    for ruta in rutas:
        puntos_ruta = [
            p for p in recorrido
            if p["ruta"] == ruta
        ]

        for i, punto in enumerate(puntos_ruta):
            actual = resultado[punto["codigo"]]

            if actual["nivel"] > 0:
                continue

            anterior = None
            siguiente = None

            for j in range(i - 1, -1, -1):
                candidato = resultado[puntos_ruta[j]["codigo"]]
                if candidato["nivel"] > 0:
                    anterior = candidato
                    break

            for j in range(i + 1, len(puntos_ruta)):
                candidato = resultado[puntos_ruta[j]["codigo"]]
                if candidato["nivel"] > 0:
                    siguiente = candidato
                    break

            candidatos = [c for c in (anterior, siguiente) if c is not None]

            if not candidatos:
                continue

            elegido = max(candidatos, key=lambda c: c["nivel"])

            resultado[punto["codigo"]] = {
                "nivel": elegido["nivel"],
                "icono": elegido["icono"],
                "texto": elegido["texto"],
                "filas": [],
            }

    return resultado

def filas_vialidad_relevantes(filas, recorrido):
    rutas = {normalizar(p["ruta"]) for p in recorrido if p["ruta"]}
    nombres = [p["nombre"] for p in recorrido]

    encontrados = []
    vistos = set()

    for fila in filas:
        ruta = normalizar(fila["ruta"])
        texto = normalizar(
            f'{fila["tramo"]} {fila["observaciones"]} {fila["restriccion"]}'
        )

        if not any(r.replace("RN", "").replace("RP", "") in ruta for r in rutas):
            continue

        if not any(nombre in texto for nombre in nombres):
            continue

        clave = (fila["ruta"], fila["tramo"], fila["fecha"], fila["hora"])
        if clave not in vistos:
            vistos.add(clave)
            encontrados.append(fila)

    return encontrados


puntos = cargar_base()
localidades = [p for p in puntos if p["tipo"] == "LOCALIDAD"]

st.markdown('<div class="app-title">Rutas Neuquinas - Estado del tránsito y del tiempo</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-sub">Seleccioná origen y destino para consultar el recorrido</div>',
    unsafe_allow_html=True,
)

nombres_localidades = [p["nombre"] for p in localidades]

c1, c2 = st.columns(2)

with c1:
    origen = st.selectbox(
        "Origen",
        ["Seleccionar…"] + nombres_localidades,
        index=0,
    )

with c2:
    destinos = [
        n for n in nombres_localidades
        if n != origen
    ]
    destino = st.selectbox(
        "Destino",
        ["Seleccionar…"] + destinos,
        index=0,
    )

if origen == "Seleccionar…" or destino == "Seleccionar…":
    st.caption("La información aparecerá cuando selecciones ambos puntos.")
    st.markdown("---")
    st.markdown("### Links de interés")
    for etiqueta, url in LINKS_INTERES.items():
        st.link_button(etiqueta, url, use_container_width=True)
    st.stop()


recorrido = seleccionar_recorrido(puntos, origen, destino)

if not recorrido:
    st.error("No encontré un corredor que conecte ese origen con ese destino.")
    st.stop()


st.markdown(
    f"""
    <div class="route-card">
        <div class="route-name">{origen} → {destino}</div>
        <div class="route-sub">
            {len(recorrido)} puntos monitoreados ·
            {" · ".join(dict.fromkeys(p["ruta"] for p in recorrido))}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Consultamos el parte antes de dibujar el recorrido, porque los colores
# de cada punto dependen exclusivamente de Vialidad.
try:
    filas_vialidad = cargar_vialidad()
    estado_puntos = estados_oficiales_por_punto(filas_vialidad, recorrido)
    estado_puntos = completar_estados_conservadores(recorrido, estado_puntos)
except Exception as e:
    filas_vialidad = []
    estado_puntos = {
        p["codigo"]: {
            "nivel": 0,
            "icono": "⚪",
            "texto": "SIN DATO OFICIAL",
            "filas": [],
        }
        for p in recorrido
    }
    st.warning("No pude leer el último parte guardado de Vialidad.")


st.markdown("### Recorrido")
st.caption(
    "🟢 Transitable · 🟡 Precaución · 🟠 Restricción/condición importante · "
    "🔴 Intransitable · ⚪ Sin asociación segura"
)

for punto in recorrido:
    estado = estado_puntos[punto["codigo"]]

    texto = f'{estado["icono"]} **{punto["nombre"]}**'
    if punto["ruta"]:
        texto += f' · {punto["ruta"]}'
    st.markdown(texto)


# Clima: sólo consultamos los puntos realmente incluidos en el viaje.
clima = {}

with st.spinner("Consultando clima del recorrido…"):
    for punto in recorrido:
        try:
            clima[punto["codigo"]] = consultar_clima(punto["lat"], punto["lon"])
        except Exception:
            clima[punto["codigo"]] = None


validos = [
    (p, clima[p["codigo"]]["current"])
    for p in recorrido
    if clima.get(p["codigo"])
]

if validos:
    mas_frio_p, mas_frio = min(
        validos,
        key=lambda x: x[1]["temperature_2m"]
    )
    max_raf_p, max_raf = max(
        validos,
        key=lambda x: x[1]["wind_gusts_10m"]
    )

    st.markdown("### Resumen meteorológico")

    st.markdown(
        f"""
        <div class="route-card">
            <div class="route-temp">{mas_frio['temperature_2m']:.0f}°</div>
            <div>
                {icono_tiempo(mas_frio['weather_code'])}
                {descripcion_tiempo(mas_frio['weather_code'])}
            </div>
            <div class="route-sub">
                Mínimo actual en {mas_frio_p['nombre']} ·
                ráfagas máximas {max_raf['wind_gusts_10m']:.0f} km/h
                en {max_raf_p['nombre']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown("### Puntos del recorrido")

for punto in recorrido:
    datos = clima.get(punto["codigo"])
    if not datos:
        continue

    actual = datos["current"]
    es_poi = punto["tipo"] == "PUNTO DE INTERES"

    if es_poi:
        st.markdown(
            f"""
            <div class="poi-box">
                <b>{punto['nombre']}</b> · {punto['ruta']}<br>
                🌡 {actual['temperature_2m']:.1f} °C ·
                {icono_tiempo(actual['weather_code'])}
                {descripcion_tiempo(actual['weather_code'])}<br>
                💨 Viento {actual['wind_speed_10m']:.0f} km/h ·
                ráfagas {actual['wind_gusts_10m']:.0f} km/h
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander(f"Pronóstico corto · {punto['nombre']}"):
            for h in horas_futuras(datos):
                vis = (
                    f"{h['visibilidad']/1000:.1f} km"
                    if h["visibilidad"] is not None else "s/d"
                )
                st.markdown(
                    f"**+{h['offset']} h · {h['hora']:%H:%M}** — "
                    f"{h['temperatura']:.1f} °C · "
                    f"{icono_tiempo(h['codigo'])} "
                    f"{descripcion_tiempo(h['codigo'])}"
                )
                st.caption(
                    f"Precip. {h['precipitacion']:.1f} mm · "
                    f"Nieve {h['nieve']:.1f} cm · "
                    f"Ráfagas {h['rafagas']:.0f} km/h · "
                    f"Visib. {vis}"
                )
    else:
        with st.container(border=True):
            c1, c2 = st.columns([1.4, 1])
            with c1:
                st.markdown(f"**{punto['nombre']}**")
                st.write(
                    f"{icono_tiempo(actual['weather_code'])} "
                    f"{descripcion_tiempo(actual['weather_code'])}"
                )
                st.caption(
                    f"Viento {actual['wind_speed_10m']:.0f} km/h · "
                    f"ráfagas {actual['wind_gusts_10m']:.0f} km/h"
                )
            with c2:
                st.metric("Ahora", f"{actual['temperature_2m']:.1f} °C")


st.markdown("### Estado oficial")

try:
    oficiales = filas_vialidad_relevantes(filas_vialidad, recorrido)
except Exception as e:
    oficiales = []
    st.warning(f"No pude procesar el parte de Vialidad: {e}")

if not oficiales:
    st.info(
        "No pude asociar automáticamente un registro específico de Vialidad "
        "con este recorrido. El clima y los puntos de interés siguen disponibles."
    )
else:
    oficiales.sort(
        key=lambda f: estado_info(f["estado_codigo"])[0],
        reverse=True
    )

    for fila in oficiales:
        _, icono, estado = estado_info(fila["estado_codigo"])
        with st.container(border=True):
            st.markdown(f"**{icono} {fila['tramo']}**")
            st.write(estado)

            if fila["restriccion"]:
                st.write(f"🚫 {fila['restriccion']}")

            if fila["observaciones"]:
                st.write(f"📌 {fila['observaciones']}")

            st.caption(
                f"Ruta {fila['ruta']} · Parte: {fila['fecha']} {fila['hora']}"
            )


st.markdown("---")

if st.button("🔄 Actualizar datos", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.markdown("### Links de interés")

for etiqueta, url in LINKS_INTERES.items():
    st.link_button(etiqueta, url, use_container_width=True)

# Mostramos de cuándo es realmente el parte oficial guardado.
try:
    _filas_parte = cargar_vialidad()
    _fechas_horas = [
        (str(f.get("fecha", "")).strip(), str(f.get("hora", "")).strip())
        for f in _filas_parte
        if str(f.get("fecha", "")).strip() or str(f.get("hora", "")).strip()
    ]
    _parte_txt = ""
    if _fechas_horas:
        _fecha, _hora = _fechas_horas[-1]
        _parte_txt = f" · Parte Vialidad: {_fecha} {_hora}".rstrip()
except Exception:
    _parte_txt = ""

st.caption(
    f"Consulta {datetime.now(TZ_ARG):%d/%m/%Y %H:%M}"
    f"{_parte_txt} · Open-Meteo"
)
