import csv
import io
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import openpyxl
import requests
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "Rutas Neuquinas - DB.xlsx"
VIALIDAD_CACHE_PATH = BASE_DIR / "cache" / "ParteDiario.csv"
GITHUB_CACHE_URL = (
    "https://raw.githubusercontent.com/gustavocalquin/monitor_rutas_neuquen/"
    "refs/heads/main/cache/ParteDiario.csv"
)
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
TZ_ARG = ZoneInfo("America/Argentina/Buenos_Aires")

LINKS_INTERES = {
    "📢 Información de rutas · WhatsApp":
        "https://whatsapp.com/channel/0029Vakr9GiIyPtaTYFeIe2J",
    "🛣️ Vialidad Provincial del Neuquén":
        "https://w2.dpvneuquen.gov.ar/estadorutas.php",
    "🌦️ Alertas del SMN":
        "https://www.smn.gob.ar/alertas",
}

DISCLAIMER = (
    "Información orientativa. Los datos pueden contener errores, demoras o diferencias "
    "respecto del estado real de las rutas. Antes de viajar, verificá las condiciones "
    "con organismos oficiales."
)


def normalizar(texto):
    texto = str(texto or "").upper().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def separar_corredores(valor):
    """Convierte una celda CORREDOR en una lista de secuencias de códigos."""
    return [c.strip() for c in str(valor or "").split(",") if c.strip()]


@st.cache_data
def cargar_base():
    libro = openpyxl.load_workbook(DB_PATH, data_only=True)
    puntos = []

    requeridos = [
        "ID", "CODIGO", "CORREDOR", "NOMBRE", "LATITUD", "LONGITUD",
        "TIPO", "RUTA", "PRIORIDAD", "NOTA",
    ]

    for hoja in libro.worksheets:
        encabezados = [
            normalizar(c.value) if c.value is not None else ""
            for c in hoja[1]
        ]
        idx = {nombre: i for i, nombre in enumerate(encabezados)}
        if not all(c in idx for c in requeridos):
            continue

        for fila in hoja.iter_rows(min_row=2, values_only=True):
            if not fila[idx["NOMBRE"]]:
                continue

            try:
                lat = float(str(fila[idx["LATITUD"]]).replace(",", "."))
                lon = float(str(fila[idx["LONGITUD"]]).replace(",", "."))
            except Exception as exc:
                raise ValueError(
                    f"Coordenadas inválidas en {fila[idx['NOMBRE']]}"
                ) from exc

            puntos.append({
                "id": str(fila[idx["ID"]] or "").strip(),
                "codigo": normalizar(fila[idx["CODIGO"]]),
                "corredores": separar_corredores(fila[idx["CORREDOR"]]),
                "nombre": normalizar(fila[idx["NOMBRE"]]),
                "lat": lat,
                "lon": lon,
                "tipo": normalizar(fila[idx["TIPO"]]),
                "ruta": normalizar(fila[idx["RUTA"]]),
                "prioridad": normalizar(fila[idx["PRIORIDAD"]]),
                "nota": str(fila[idx["NOTA"]] or "").strip(),
                "hoja": hoja.title,
            })

    if not puntos:
        raise ValueError("No encontré una hoja con la estructura esperada.")

    return puntos


def construir_corredores(puntos):
    """Obtiene las trazas únicas directamente de las celdas CORREDOR."""
    codigos_validos = {p["codigo"] for p in puntos}
    corredores = []
    vistos = set()

    for punto in puntos:
        for corredor in punto["corredores"]:
            codigos = [normalizar(c) for c in corredor.split("-") if c.strip()]
            if len(codigos) < 2:
                continue
            faltantes = [c for c in codigos if c not in codigos_validos]
            if faltantes:
                raise ValueError(
                    f"El corredor {corredor} contiene códigos inexistentes: "
                    + ", ".join(faltantes)
                )
            clave = tuple(codigos)
            if clave not in vistos:
                vistos.add(clave)
                corredores.append(codigos)

    return corredores


def construir_grafo(corredores):
    """Cada par consecutivo del corredor es una conexión transitable en ambos sentidos."""
    grafo = defaultdict(set)
    for corredor in corredores:
        for a, b in zip(corredor, corredor[1:]):
            grafo[a].add(b)
            grafo[b].add(a)
    return grafo


def buscar_recorridos(puntos, origen_nombre, destino_nombre, max_alternativas=6):
    """
    Busca recorridos simples entre dos localidades.

    La red se arma con las secuencias de CORREDOR, por lo que permite:
    - recorrer un corredor en ambos sentidos;
    - cambiar de corredor en un nodo compartido;
    - conservar alternativas reales (ej. Costa/Cordillera).
    """
    por_nombre = {p["nombre"]: p for p in puntos}
    por_codigo = {p["codigo"]: p for p in puntos}
    origen = por_nombre[origen_nombre]["codigo"]
    destino = por_nombre[destino_nombre]["codigo"]

    corredores = construir_corredores(puntos)
    grafo = construir_grafo(corredores)

    if origen not in grafo or destino not in grafo:
        return []

    caminos = []
    limite_nodos = len(puntos) + 1

    def dfs(actual, camino, visitados):
        if len(caminos) >= 80:
            return
        if len(camino) > limite_nodos:
            return
        if actual == destino:
            caminos.append(tuple(camino))
            return

        for siguiente in sorted(grafo.get(actual, ())):
            if siguiente in visitados:
                continue
            dfs(siguiente, camino + [siguiente], visitados | {siguiente})

    dfs(origen, [origen], {origen})

    if not caminos:
        return []

    # Evitamos recorridos artificialmente largos cuando la red tenga ciclos.
    minimo = min(len(c) for c in caminos)
    candidatos = [c for c in caminos if len(c) <= minimo + 4]
    candidatos.sort(key=lambda c: (len(c), c))

    unicos = []
    vistos = set()
    for camino in candidatos:
        if camino in vistos:
            continue
        vistos.add(camino)
        unicos.append([por_codigo[c] for c in camino])
        if len(unicos) >= max_alternativas:
            break

    return unicos


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


def decodificar_bytes(contenido):
    for enc in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return contenido.decode(enc)
        except UnicodeDecodeError:
            pass
    return contenido.decode("utf-8", errors="replace")


@st.cache_data(ttl=300)
def cargar_vialidad():
    """
    Nunca consulta directamente al servidor de Vialidad.
    Primero usa cache/ParteDiario.csv. Para facilitar la prueba local, si el
    archivo no está presente intenta leer la copia cacheada del repositorio.
    """
    if VIALIDAD_CACHE_PATH.exists():
        contenido = VIALIDAD_CACHE_PATH.read_bytes()
    else:
        r = requests.get(
            GITHUB_CACHE_URL,
            headers={"User-Agent": "Clima-en-Ruta-Neuquen/local-test"},
            timeout=20,
        )
        r.raise_for_status()
        contenido = r.content

    return leer_csv_vialidad(decodificar_bytes(contenido))


@st.cache_data(ttl=300)
def consultar_clima(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "America/Argentina/Buenos_Aires",
        "forecast_days": 2,
        "current": ",".join([
            "temperature_2m", "precipitation", "rain", "snowfall",
            "weather_code", "wind_speed_10m", "wind_gusts_10m",
        ]),
        "hourly": ",".join([
            "temperature_2m", "precipitation", "rain", "snowfall",
            "weather_code", "wind_speed_10m", "wind_gusts_10m", "visibility",
        ]),
    }
    r = requests.get(
        WEATHER_URL,
        params=params,
        headers={"User-Agent": "Clima-en-Ruta-Neuquen/0.90"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def estado_info(codigo):
    c = normalizar(codigo)
    if c in ("I", "INT"):
        return 3, "🔴", "INTRANSITABLE"
    if c == "TCP":
        return 2, "🟡", "TRANSITABLE CON PRECAUCIÓN"
    if c == "T":
        return 1, "🟢", "TRANSITABLE"
    return 0, "⚪", c or "SIN DATO"


def nivel_visual_fila(fila):
    severidad, _, _ = estado_info(fila["estado_codigo"])
    if severidad >= 3:
        return 4, "🔴", "INTRANSITABLE"

    texto = normalizar(
        f'{fila.get("restriccion", "")} {fila.get("observaciones", "")}'
    )
    claves_naranja = (
        "CADENA", "HIELO", "NIEVE", "HORARIO", "NOCTURNO", "RESTRICCION",
        "PORTACION", "OBLIGATORIO", "OBLIGATORIA", "CALZADA RESBALADIZA",
    )
    if severidad == 2 and any(clave in texto for clave in claves_naranja):
        return 3, "🟠", "PRECAUCIÓN / RESTRICCIÓN IMPORTANTE"
    if severidad == 2:
        return 2, "🟡", "TRANSITABLE CON PRECAUCIÓN"
    if severidad == 1:
        return 1, "🟢", "TRANSITABLE"
    return 0, "⚪", "SIN DATO"


def menciones_en_recorrido(fila, recorrido):
    texto = normalizar(fila.get("tramo", ""))
    return [
        (i, p) for i, p in enumerate(recorrido)
        if p["nombre"] and p["nombre"] in texto
    ]


def completar_estados_por_proximidad(resultado, recorrido):
    """
    Completa nodos sin asociación segura usando el nodo asociado más próximo
    dentro del recorrido. Si hay empate de distancia, conserva el estado más
    restrictivo de los candidatos empatados.

    Si ningún nodo del recorrido pudo asociarse con seguridad al parte, los
    estados permanecen sin asociación.
    """
    posiciones_validas = [
        i for i, p in enumerate(recorrido)
        if resultado[p["codigo"]]["nivel"] > 0
    ]
    if not posiciones_validas:
        return resultado

    for i, punto in enumerate(recorrido):
        actual = resultado[punto["codigo"]]
        if actual["nivel"] > 0:
            continue

        distancia_minima = min(abs(i - j) for j in posiciones_validas)
        candidatos = [
            j for j in posiciones_validas
            if abs(i - j) == distancia_minima
        ]
        elegido = max(
            candidatos,
            key=lambda j: resultado[recorrido[j]["codigo"]]["nivel"],
        )
        fuente = resultado[recorrido[elegido]["codigo"]]
        actual["nivel"] = fuente["nivel"]
        actual["icono"] = fuente["icono"]
        actual["texto"] = fuente["texto"]
        actual["filas"] = list(fuente["filas"])
        actual["heredado"] = True
        actual["fuente_codigo"] = recorrido[elegido]["codigo"]

    return resultado


def estados_oficiales_por_punto(filas, recorrido):
    """
    Asocia estados sólo cuando un tramo oficial menciona al menos DOS nodos
    del recorrido elegido. Esto evita que, por ejemplo, "Chos Malal - Barrancas"
    pinte Chos Malal de rojo al consultar un viaje hacia Zapala.

    Luego completa los huecos con el estado asociado más próximo del mismo
    recorrido, incluyendo origen y destino.
    """
    resultado = {
        p["codigo"]: {
            "nivel": 0,
            "icono": "⚪",
            "texto": "SIN ASOCIACIÓN SEGURA AL PARTE",
            "filas": [],
            "heredado": False,
            "fuente_codigo": None,
        }
        for p in recorrido
    }

    for fila in filas:
        mencionados = menciones_en_recorrido(fila, recorrido)
        if len(mencionados) < 2:
            continue

        posiciones = [i for i, _ in mencionados]
        minimo, maximo = min(posiciones), max(posiciones)
        afectados = recorrido[minimo:maximo + 1]
        nivel, icono, texto = nivel_visual_fila(fila)

        for punto in afectados:
            actual = resultado[punto["codigo"]]
            actual["filas"].append(fila)
            if nivel > actual["nivel"]:
                actual["nivel"] = nivel
                actual["icono"] = icono
                actual["texto"] = texto

    return completar_estados_por_proximidad(resultado, recorrido)


def filas_vialidad_relevantes(filas, recorrido):
    """Muestra sólo filas que pueden ubicarse con seguridad dentro del recorrido."""
    encontrados = []
    vistos = set()

    for fila in filas:
        if len(menciones_en_recorrido(fila, recorrido)) < 2:
            continue
        clave = (fila["ruta"], fila["tramo"], fila["fecha"], fila["hora"])
        if clave not in vistos:
            vistos.add(clave)
            encontrados.append(fila)

    return encontrados


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


def mostrar_links():
    st.markdown("### Links de interés")
    for etiqueta, url in LINKS_INTERES.items():
        st.link_button(etiqueta, url, use_container_width=True)


def selector_tactil(etiqueta, clave, opciones, excluir=None):
    """Selector móvil sin campo de escritura ni apertura del teclado."""
    disponibles = [o for o in opciones if o != excluir]
    actual = st.session_state.get(clave)
    if actual not in disponibles:
        actual = None
        st.session_state[clave] = None

    st.markdown(f"**{etiqueta}**")
    texto_boton = actual or "Seleccionar…"
    with st.popover(texto_boton, use_container_width=True):
        with st.container(height=360, border=False):
            for opcion in disponibles:
                if st.button(
                    opcion,
                    key=f"{clave}_{opcion}",
                    use_container_width=True,
                    type="primary" if opcion == actual else "secondary",
                ):
                    st.session_state[clave] = opcion
                    st.session_state["consulta_activa"] = None
                    st.rerun()

    return st.session_state.get(clave)


def mostrar_pie():
    st.markdown("---")
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.warning(DISCLAIMER, icon="⚠️")
    mostrar_links()


def mostrar_recorrido(recorrido, filas_vialidad, clima, indice=1, total=1):
    if total > 1:
        st.markdown(f"## Alternativa {indice}")

    rutas = [p["ruta"] for p in recorrido if p["ruta"]]
    rutas_txt = " · ".join(dict.fromkeys(rutas)) or "sin ruta de referencia"
    st.markdown(
        f"""
        <div class="route-card">
            <div class="route-name">{recorrido[0]['nombre']} → {recorrido[-1]['nombre']}</div>
            <div class="route-sub">
                {len(recorrido)} puntos monitoreados · {rutas_txt}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    estado_puntos = estados_oficiales_por_punto(filas_vialidad, recorrido)

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

    validos = [
        (p, clima[p["codigo"]]["current"])
        for p in recorrido
        if clima.get(p["codigo"])
    ]
    if validos:
        mas_frio_p, mas_frio = min(validos, key=lambda x: x[1]["temperature_2m"])
        max_raf_p, max_raf = max(validos, key=lambda x: x[1]["wind_gusts_10m"])
        st.markdown("### Resumen meteorológico")
        st.markdown(
            f"""
            <div class="route-card">
                <div class="route-temp">{mas_frio['temperature_2m']:.0f}°</div>
                <div>{icono_tiempo(mas_frio['weather_code'])} {descripcion_tiempo(mas_frio['weather_code'])}</div>
                <div class="route-sub">
                    Mínimo actual en {mas_frio_p['nombre']} ·
                    ráfagas máximas {max_raf['wind_gusts_10m']:.0f} km/h en {max_raf_p['nombre']}
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
                    {icono_tiempo(actual['weather_code'])} {descripcion_tiempo(actual['weather_code'])}<br>
                    💨 Viento {actual['wind_speed_10m']:.0f} km/h ·
                    ráfagas {actual['wind_gusts_10m']:.0f} km/h
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander(f"Pronóstico corto · {punto['nombre']}"):
                for h in horas_futuras(datos):
                    vis = f"{h['visibilidad']/1000:.1f} km" if h["visibilidad"] is not None else "s/d"
                    st.markdown(
                        f"**+{h['offset']} h · {h['hora']:%H:%M}** — "
                        f"{h['temperatura']:.1f} °C · {icono_tiempo(h['codigo'])} "
                        f"{descripcion_tiempo(h['codigo'])}"
                    )
                    st.caption(
                        f"Precip. {h['precipitacion']:.1f} mm · Nieve {h['nieve']:.1f} cm · "
                        f"Ráfagas {h['rafagas']:.0f} km/h · Visib. {vis}"
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
    oficiales = filas_vialidad_relevantes(filas_vialidad, recorrido)
    if not oficiales:
        st.info(
            "No pude asociar con seguridad un registro específico de Vialidad "
            "con este recorrido. El clima y los puntos monitoreados siguen disponibles."
        )
    else:
        oficiales.sort(key=lambda f: estado_info(f["estado_codigo"])[0], reverse=True)
        for fila in oficiales:
            _, icono, estado = estado_info(fila["estado_codigo"])
            with st.container(border=True):
                st.markdown(f"**{icono} {fila['tramo']}**")
                st.write(estado)
                if fila["restriccion"]:
                    st.write(f"🚫 {fila['restriccion']}")
                if fila["observaciones"]:
                    st.write(f"📌 {fila['observaciones']}")
                st.caption(f"Ruta {fila['ruta']} · Parte: {fila['fecha']} {fila['hora']}")


def main():
    st.set_page_config(
        page_title="Clima en Ruta - Neuquén",
        page_icon="🚌",
        layout="centered",
    )
    st.markdown("""
    <style>
    .block-container { max-width: 760px; padding-top: 2.2rem; padding-bottom: 2.5rem; }
    .app-title { font-size: 1.9rem; font-weight: 800; line-height: 1.15; margin: .2rem 0 .35rem 0; }
    .app-sub { opacity: .72; margin-bottom: .8rem; }
    .route-card { border: 1px solid rgba(128,128,128,.22); border-radius: 22px; padding: 17px; background: rgba(128,128,128,.04); margin: 12px 0; }
    .route-name { font-size: 1.2rem; font-weight: 750; }
    .route-temp { font-size: 2.7rem; font-weight: 800; line-height: 1; margin: 7px 0 5px 0; }
    .route-sub { opacity: .72; font-size: .93rem; }
    .poi-box { border-left: 4px solid #f0a000; padding: 11px 13px; margin: 10px 0; border-radius: 10px; background: rgba(240,160,0,.08); }
    .stButton > button, .stLinkButton > a { border-radius: 16px; min-height: 3rem; }
    div[data-testid="stPopover"] > button { border-radius: 16px; min-height: 3rem; }
    </style>
    """, unsafe_allow_html=True)

    try:
        puntos = cargar_base()
        construir_corredores(puntos)  # valida referencias al arrancar
    except Exception as exc:
        st.error(f"No pude cargar la base de localidades: {exc}")
        st.stop()

    localidades = sorted(
        [p for p in puntos if p["tipo"] == "LOCALIDAD"],
        key=lambda p: p["nombre"],
    )
    nombres_localidades = [p["nombre"] for p in localidades]

    for clave in ("origen_sel", "destino_sel", "consulta_activa"):
        if clave not in st.session_state:
            st.session_state[clave] = None

    st.markdown('<div class="app-title">Clima en Ruta - Neuquén</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-sub">Seleccioná origen y destino para consultar el recorrido</div>',
        unsafe_allow_html=True,
    )

    origen = selector_tactil("Origen", "origen_sel", nombres_localidades)
    destino = selector_tactil(
        "Destino", "destino_sel", nombres_localidades, excluir=origen
    )

    puede_buscar = bool(origen and destino)
    if st.button(
        "🔎 Buscar recorrido",
        use_container_width=True,
        type="primary",
        disabled=not puede_buscar,
    ):
        st.session_state["consulta_activa"] = (origen, destino)

    consulta = st.session_state.get("consulta_activa")
    if not consulta:
        st.caption(
            "Elegí origen y destino y tocá Buscar recorrido para consultar el estado."
        )
        mostrar_pie()
        st.stop()

    origen_consulta, destino_consulta = consulta

    with st.spinner("Consultando estado de rutas y clima…"):
        recorridos = buscar_recorridos(
            puntos, origen_consulta, destino_consulta
        )
        if not recorridos:
            st.error(
                "No encontré un corredor o combinación de corredores que conecte "
                "ese origen con ese destino."
            )
            mostrar_pie()
            st.stop()

        try:
            filas_vialidad = cargar_vialidad()
        except Exception:
            filas_vialidad = []

        # Una sola consulta meteorológica por nodo aunque aparezca en varias alternativas.
        puntos_unicos = {}
        for recorrido in recorridos:
            for p in recorrido:
                puntos_unicos[p["codigo"]] = p

        clima = {}
        for codigo, punto in puntos_unicos.items():
            try:
                clima[codigo] = consultar_clima(punto["lat"], punto["lon"])
            except Exception:
                clima[codigo] = None

    if len(recorridos) > 1:
        st.info(
            f"Encontré {len(recorridos)} alternativas posibles entre "
            f"{origen_consulta} y {destino_consulta}."
        )

    if not filas_vialidad:
        st.warning(
            "No pude leer el último parte cacheado de Vialidad. "
            "La información meteorológica sigue disponible."
        )

    for i, recorrido in enumerate(recorridos, start=1):
        if i > 1:
            st.markdown("---")
        mostrar_recorrido(recorrido, filas_vialidad, clima, i, len(recorridos))

    mostrar_pie()

    parte_txt = ""
    if filas_vialidad:
        fechas_horas = [
            (str(f.get("fecha", "")).strip(), str(f.get("hora", "")).strip())
            for f in filas_vialidad
            if str(f.get("fecha", "")).strip() or str(f.get("hora", "")).strip()
        ]
        if fechas_horas:
            fecha, hora = fechas_horas[-1]
            parte_txt = f" · Parte Vialidad: {fecha} {hora}".rstrip()

    st.caption(
        f"Consulta {datetime.now(TZ_ARG):%d/%m/%Y %H:%M}{parte_txt} · Open-Meteo"
    )


if __name__ == "__main__":
    main()
