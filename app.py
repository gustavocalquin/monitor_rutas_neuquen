
import csv
import io
from datetime import datetime

import requests
import streamlit as st


CSV_URL = "https://w2.dpvneuquen.gov.ar/ParteDiario.csv"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

LINKS_INTERES = {
    "📢 Rutas neuquinas · WhatsApp": "https://whatsapp.com/channel/0029Vakr9GiIyPtaTYFeIe2J",
    "🛣️ Vialidad Provincial del Neuquén": "https://w2.dpvneuquen.gov.ar/estadorutas.php",
    "🌦️ Alertas del SMN": "https://www.smn.gob.ar/alertas",
}

# Localidades y puntos críticos del corredor.
# Los puntos críticos son provisionales y están pensados para validarlos
# posteriormente con la experiencia de los choferes.
PUNTOS = {
    "Las Ovejas": {"lat": -36.98898, "lon": -70.74954},
    "Andacollo": {"lat": -37.17974, "lon": -70.66999},
    "El Llano": {"lat": -37.223813, "lon": -70.620403},
    "Chos Malal": {"lat": -37.37853, "lon": -70.27191},

    # Punto intermedio indicado para vigilar el sector Chorriaca–Naunauco.
    "Sector Chorriaca–Naunauco": {
        "lat": -37.792825,
        "lon": -70.093634,
    },

    "Las Lajas": {"lat": -38.5304, "lon": -70.3674},
    "Zapala": {"lat": -38.8992, "lon": -70.0544},

    # Punto intermedio indicado para vigilar el sector Zapala–Cutral Co.
    "Sector Zapala–Cutral Co": {
        "lat": -38.934102,
        "lon": -69.671256,
    },

    "Cutral Co": {"lat": -38.9360, "lon": -69.2300},
    "Neuquén": {"lat": -38.9516, "lon": -68.0591},
}


# "patrones_oficiales" son distintas formas posibles de identificar
# registros del CSV de Vialidad. Si una forma no aparece en el parte,
# la app prueba las siguientes.
TRAMOS = {
    "Las Ovejas → Andacollo": {
        "ruta_preferida": "43",
        "patrones_oficiales": [
            ("Andacollo", "Cayanta", "Bella Vista", "Las Ovejas"),
            ("Andacollo", "Las Ovejas"),
        ],
        "puntos_clima": ["Las Ovejas", "Andacollo"],
        "puntos_interes": [],
    },

    "Andacollo → Chos Malal": {
        "ruta_preferida": "43",
        "patrones_oficiales": [
            ("La Primavera", "El Llano", "Andacollo"),
            ("Chos Malal", "La Primavera"),
        ],
        "puntos_clima": ["Andacollo", "El Llano", "Chos Malal"],
        "puntos_interes": ["El Llano"],
    },

    "Chos Malal → Las Lajas": {
        "ruta_preferida": "40",
        "patrones_oficiales": [
            ("Chos Malal", "Las Lajas"),
            ("Chos Malal", "Naunauco"),
            ("Naunauco", "Chorriaca"),
            ("Chorriaca", "Las Lajas"),
        ],
        "puntos_clima": [
            "Chos Malal",
            "Sector Chorriaca–Naunauco",
            "Las Lajas",
        ],
        "puntos_interes": ["Sector Chorriaca–Naunauco"],
    },

    "Las Lajas → Zapala": {
        "ruta_preferida": "40",
        "patrones_oficiales": [
            ("Las Lajas", "Zapala"),
            ("Las Lajas", "Covunco"),
            ("Covunco", "Zapala"),
        ],
        "puntos_clima": ["Las Lajas", "Zapala"],
        "puntos_interes": [],
    },

    "Zapala → Cutral Co": {
        "ruta_preferida": "22",
        "patrones_oficiales": [
            ("Zapala", "Cutral Co"),
            ("Zapala", "Cutral-Có"),
            ("Zapala", "Cutral"),
        ],
        "puntos_clima": [
            "Zapala",
            "Sector Zapala–Cutral Co",
            "Cutral Co",
        ],
        "puntos_interes": ["Sector Zapala–Cutral Co"],
    },

    "Cutral Co → Neuquén": {
        "ruta_preferida": "22",
        "patrones_oficiales": [
            ("Cutral Co", "Neuquén"),
            ("Cutral-Có", "Neuquén"),
            ("Cutral", "Neuquén"),
            ("Cutral Co", "Senillosa"),
            ("Senillosa", "Neuquén"),
        ],
        "puntos_clima": ["Cutral Co", "Neuquén"],
        "puntos_interes": [],
    },
}


st.set_page_config(
    page_title="Estado de Ruta",
    page_icon="🚌",
    layout="centered",
)

st.markdown("""
<style>
.block-container {
    max-width: 720px;
    padding-top: 1.2rem;
    padding-bottom: 2.5rem;
}

.home-title {
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: .2rem;
}

.home-sub {
    opacity: .72;
    margin-bottom: 1.3rem;
}

.route-card {
    border: 1px solid rgba(128,128,128,.22);
    border-radius: 24px;
    padding: 18px;
    background: rgba(128,128,128,.04);
    margin: 12px 0;
}

.route-name {
    font-size: 1.25rem;
    font-weight: 750;
    margin-bottom: 6px;
}

.route-temp {
    font-size: 2.8rem;
    font-weight: 800;
    line-height: 1;
    margin: 7px 0 5px 0;
}

.route-sub {
    opacity: .72;
    font-size: .95rem;
}

.poi-box {
    border-left: 4px solid #f0a000;
    padding: 11px 13px;
    margin: 12px 0;
    border-radius: 10px;
    background: rgba(240,160,0,.08);
}

.links-box {
    border: 1px solid rgba(128,128,128,.18);
    border-radius: 18px;
    padding: 12px 14px;
    margin-top: 18px;
    background: rgba(128,128,128,.025);
}

.stButton > button,
.stLinkButton > a {
    border-radius: 16px;
    min-height: 3rem;
}
</style>
""", unsafe_allow_html=True)


def descargar_csv():
    r = requests.get(
        CSV_URL,
        headers={"User-Agent": "Monitor-Rutas-Neuquen/0.7"},
        timeout=20,
    )
    r.raise_for_status()

    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return r.content.decode(encoding)
        except UnicodeDecodeError:
            pass

    return r.content.decode("utf-8", errors="replace")


def leer_filas(texto):
    try:
        dialecto = csv.Sniffer().sniff(texto[:5000], delimiters=",;\t|")
        delimitador = dialecto.delimiter
    except csv.Error:
        delimitador = ";"

    return [
        fila
        for fila in csv.reader(io.StringIO(texto), delimiter=delimitador)
        if any(celda.strip() for celda in fila)
    ]


def limpiar(valor):
    return valor.strip() if valor else ""


def parsear_fila(fila):
    campos = fila + [""] * max(0, 11 - len(fila))
    return {
        "ruta": limpiar(campos[1]),
        "tramo": limpiar(campos[3]),
        "superficie": limpiar(campos[4]),
        "longitud": limpiar(campos[5]),
        "estado_codigo": limpiar(campos[6]),
        "restriccion": limpiar(campos[7]),
        "observaciones": limpiar(campos[8]),
        "fecha": limpiar(campos[9]),
        "hora": limpiar(campos[10]),
    }


def fila_contiene(fila, palabras):
    texto = " | ".join(fila).casefold()
    return all(p.casefold() in texto for p in palabras)


def ruta_coincide(fila, ruta_preferida):
    if not ruta_preferida or len(fila) < 2:
        return True
    return ruta_preferida.casefold() in limpiar(fila[1]).casefold()


def buscar_segmentos(filas, cfg):
    """
    Busca todas las coincidencias útiles del tramo y evita duplicados.

    Primero prioriza la ruta indicada (43, 40, 22). Si una fila puede
    identificarse con más de un patrón, se muestra una sola vez.
    """
    resultados = []
    vistos = set()

    for palabras in cfg["patrones_oficiales"]:
        candidatos = [
            fila for fila in filas
            if fila_contiene(fila, palabras)
            and ruta_coincide(fila, cfg.get("ruta_preferida"))
        ]

        # Fallback: si Vialidad cambia la forma de escribir la ruta,
        # al menos intentamos localizar el tramo por nombre.
        if not candidatos:
            candidatos = [
                fila for fila in filas
                if fila_contiene(fila, palabras)
            ]

        for fila in candidatos:
            clave = tuple(fila)
            if clave not in vistos:
                vistos.add(clave)
                resultados.append(parsear_fila(fila))

    return resultados


def estado_info(codigo):
    codigo = (codigo or "").upper()

    if codigo in ("I", "INT"):
        return 3, "🔴", "INTRANSITABLE"

    if codigo == "TCP":
        return 2, "🟡", "TRANSITABLE CON PRECAUCIÓN"

    if codigo == "T":
        return 1, "🟢", "TRANSITABLE"

    return 0, "⚪", codigo or "SIN DATO"


def peor_estado(segmentos):
    if not segmentos:
        return "⚪", "SIN DATO OFICIAL"

    peor = max(
        segmentos,
        key=lambda s: estado_info(s["estado_codigo"])[0]
    )

    _, icono, texto = estado_info(peor["estado_codigo"])
    return icono, texto


def descripcion_tiempo(codigo):
    codigos = {
        0: "Despejado",
        1: "Mayormente despejado",
        2: "Parcialmente nublado",
        3: "Cubierto",
        45: "Niebla",
        48: "Niebla con escarcha",
        51: "Llovizna leve",
        53: "Llovizna moderada",
        55: "Llovizna intensa",
        56: "Llovizna helada leve",
        57: "Llovizna helada intensa",
        61: "Lluvia leve",
        63: "Lluvia moderada",
        65: "Lluvia intensa",
        66: "Lluvia helada leve",
        67: "Lluvia helada intensa",
        71: "Nevada leve",
        73: "Nevada moderada",
        75: "Nevada intensa",
        77: "Granos de nieve",
        80: "Chaparrones leves",
        81: "Chaparrones moderados",
        82: "Chaparrones intensos",
        85: "Chaparrones de nieve leves",
        86: "Chaparrones de nieve intensos",
        95: "Tormenta",
        96: "Tormenta con granizo leve",
        99: "Tormenta con granizo intenso",
    }

    return codigos.get(codigo, f"Código {codigo}")


def icono_tiempo(codigo):
    if codigo == 0:
        return "☀️"
    if codigo in (1, 2):
        return "🌤️"
    if codigo == 3:
        return "☁️"
    if codigo in (45, 48):
        return "🌫️"
    if codigo in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "🌧️"
    if codigo in (56, 57, 66, 67):
        return "🧊"
    if codigo in (71, 73, 75, 77, 85, 86):
        return "🌨️"
    if codigo in (95, 96, 99):
        return "⛈️"

    return "🌡️"


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
        headers={"User-Agent": "Monitor-Rutas-Neuquen/0.7"},
        timeout=20,
    )
    r.raise_for_status()

    return r.json()


def horas_futuras(datos, offsets=(1, 2, 3, 6)):
    hourly = datos["hourly"]
    tiempos = [datetime.fromisoformat(t) for t in hourly["time"]]
    ahora = datetime.now()

    base = next(
        (i for i, t in enumerate(tiempos) if t > ahora),
        None,
    )

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
            "viento": hourly["wind_speed_10m"][i],
            "rafagas": hourly["wind_gusts_10m"][i],
            "visibilidad": hourly["visibility"][i],
        })

    return resultado


def resumen_clima(nombres, clima):
    registros = []

    for nombre in nombres:
        actual = clima[nombre]["current"]

        registros.append({
            "nombre": nombre,
            "temp": actual["temperature_2m"],
            "codigo": actual["weather_code"],
            "viento": actual["wind_speed_10m"],
            "rafagas": actual["wind_gusts_10m"],
        })

    mas_frio = min(registros, key=lambda x: x["temp"])
    mas_rafaga = max(registros, key=lambda x: x["rafagas"])

    return mas_frio, mas_rafaga


@st.cache_data(ttl=300)
def cargar_vialidad():
    return leer_filas(descargar_csv())


@st.cache_data(ttl=300)
def cargar_clima_punto(nombre):
    punto = PUNTOS[nombre]
    return consultar_clima(punto["lat"], punto["lon"])


st.markdown(
    '<div class="home-title">Estado de Ruta</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="home-sub">Seleccioná un tramo para consultar su estado y el clima</div>',
    unsafe_allow_html=True,
)

opciones = ["Seleccioná un tramo…"] + list(TRAMOS.keys())

nombre_tramo = st.selectbox(
    "Tramo",
    opciones,
    index=0,
)

if nombre_tramo == "Seleccioná un tramo…":
    st.caption(
        "Corredor: Las Ovejas · Andacollo · Chos Malal · "
        "Las Lajas · Zapala · Cutral Co · Neuquén"
    )

    st.markdown("---")
    st.markdown("### Links de interés")

    for etiqueta, url in LINKS_INTERES.items():
        st.link_button(etiqueta, url, use_container_width=True)

    st.stop()


cfg = TRAMOS[nombre_tramo]

try:
    filas = cargar_vialidad()

    clima = {
        punto: cargar_clima_punto(punto)
        for punto in cfg["puntos_clima"]
    }

except Exception as e:
    st.error(f"No pude cargar los datos: {e}")
    st.stop()


segmentos = buscar_segmentos(filas, cfg)

icono_estado, texto_estado = peor_estado(segmentos)
mas_frio, mas_rafaga = resumen_clima(cfg["puntos_clima"], clima)

st.markdown(
    f"""
    <div class="route-card">
        <div class="route-name">{nombre_tramo}</div>
        <div>{icono_estado} <b>{texto_estado}</b></div>
        <div class="route-temp">{mas_frio['temp']:.0f}°</div>
        <div class="route-sub">
            {icono_tiempo(mas_frio['codigo'])}
            {descripcion_tiempo(mas_frio['codigo'])}
            · mínimo actual en {mas_frio['nombre']}
        </div>
        <div class="route-sub">
            💨 Ráfagas máximas {mas_rafaga['rafagas']:.0f} km/h
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


for punto in cfg["puntos_interes"]:
    actual = clima[punto]["current"]

    st.markdown(
        f"""
        <div class="poi-box">
            <b>⚠ Punto de interés: {punto}</b><br>
            🌡 {actual['temperature_2m']:.1f} °C ·
            {icono_tiempo(actual['weather_code'])}
            {descripcion_tiempo(actual['weather_code'])}<br>
            💨 Viento {actual['wind_speed_10m']:.0f} km/h ·
            ráfagas {actual['wind_gusts_10m']:.0f} km/h
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown("### Estado oficial")

if not segmentos:
    st.info(
        "No encontré un registro específico de este tramo en el parte actual. "
        "El clima se sigue mostrando normalmente."
    )

for segmento in segmentos:
    _, seg_icono, seg_estado = estado_info(segmento["estado_codigo"])

    with st.container(border=True):
        st.markdown(f"**{seg_icono} {segmento['tramo']}**")
        st.write(seg_estado)

        if segmento["restriccion"]:
            st.write(f"🚫 {segmento['restriccion']}")

        if segmento["observaciones"]:
            st.write(f"📌 {segmento['observaciones']}")

        st.caption(
            f"Ruta {segmento['ruta']} · "
            f"Parte: {segmento['fecha']} {segmento['hora']}"
        )


st.markdown("### Clima del tramo")

for punto in cfg["puntos_clima"]:
    actual = clima[punto]["current"]

    with st.container(border=True):
        c1, c2 = st.columns([1.45, 1])

        with c1:
            st.markdown(f"**{punto}**")
            st.write(
                f"{icono_tiempo(actual['weather_code'])} "
                f"{descripcion_tiempo(actual['weather_code'])}"
            )
            st.caption(
                f"Viento {actual['wind_speed_10m']:.0f} km/h · "
                f"ráfagas {actual['wind_gusts_10m']:.0f} km/h"
            )

        with c2:
            st.metric(
                "Ahora",
                f"{actual['temperature_2m']:.1f} °C",
            )


for punto in cfg["puntos_interes"]:
    st.markdown(f"### Próximas horas · {punto}")

    for h in horas_futuras(clima[punto]):
        vis = (
            f"{h['visibilidad']/1000:.1f} km"
            if h["visibilidad"] is not None
            else "s/d"
        )

        with st.container(border=True):
            c1, c2 = st.columns([1, 1])

            with c1:
                st.markdown(
                    f"**+{h['offset']} h · {h['hora']:%H:%M}**"
                )
                st.write(
                    f"{icono_tiempo(h['codigo'])} "
                    f"{descripcion_tiempo(h['codigo'])}"
                )

            with c2:
                st.metric(
                    "Temp.",
                    f"{h['temperatura']:.1f} °C",
                )

            st.caption(
                f"Precip. {h['precipitacion']:.1f} mm · "
                f"Nieve {h['nieve']:.1f} cm · "
                f"Ráfagas {h['rafagas']:.0f} km/h · "
                f"Visib. {vis}"
            )


st.markdown("---")

if st.button("🔄 Actualizar datos", use_container_width=True):
    st.cache_data.clear()
    st.rerun()


st.markdown("### Links de interés")

for etiqueta, url in LINKS_INTERES.items():
    st.link_button(
        etiqueta,
        url,
        use_container_width=True,
    )


st.caption(
    f"Consulta {datetime.now():%d/%m/%Y %H:%M} · "
    "Estado oficial: Vialidad Provincial del Neuquén · "
    "Meteorología: Open-Meteo"
)
