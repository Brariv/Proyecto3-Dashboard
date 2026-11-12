"""
Observatorio de Inteligencia Turistica — Rio Dulce y Livingston (Izabal).
Proyecto 3 · Grupo 5 · CC3084 Data Science, UVG.

Reto analitico asignado: conectividad fluvial y embudo de transferencia.

El tablero conserva la navegacion del Laboratorio 10: barra superior fija,
control segmentado para cambiar de modulo, menus emergentes para los filtros
y tarjetas agrupadas sobre fondo gris. No hay panel lateral: todo el control
vive en la barra de arriba.

Ejecutar:
    streamlit run app/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

import datos as dt
from componentes import barra_navegacion, chips, titulo_grande
from config import CSS
from vistas import conectividad, demanda, guia, hoteleria, presentacion, temporal

st.set_page_config(page_title="Observatorio Rio Dulce y Livingston",
                   page_icon="🛶", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Los cuatro modulos obligatorios, la guia de lectura y la slide de cierre
# --------------------------------------------------------------------------
SECCIONES = {
    "Demanda": ("Demanda y mercados emisores",
                "Cuanta visita recibe el destino, cuanto se queda y de donde viene",
                demanda.render),
    "Temporal": ("Dinamica temporal y pronostico",
                 "Como se mueve el calendario, que pesan los feriados y que falta por estimar",
                 temporal.render),
    "Hoteleria": ("Oferta hotelera y territorio",
                  "Capacidad instalada, ocupacion del departamento y peso de cada poligono",
                  hoteleria.render),
    "Conectividad": ("Conectividad fluvial",
                     "Cuantos de los que llegan a la puerta de entrada continuan a Livingston",
                     conectividad.render),
    "Guia": ("Guia de lectura",
             "Cobertura de cada fuente, reglas de calculo, colores y limitaciones",
             guia.render),
    "Presentacion": ("Presentacion para INGUAT",
                     "Destino, reto, hallazgos, recomendaciones, estimaciones y limites",
                     presentacion.render),
}

GRAFICAS = {
    "Demanda": ["V1 Evolucion de la visita", "V2 Turista frente a excursionista",
                "V3 Mercados emisores extranjeros", "V4 Nacionales y extranjeros",
                "V5 Volumen frente a estadia"],
    "Temporal": ["V6 Serie diaria y eventos", "V7 Impacto de las festividades",
                 "V8 Patron semanal", "V9 Pronostico de los meses sin cobertura",
                 "V10 Validacion del modelo", "V11 Estacionalidad prestada"],
    "Hoteleria": ["V12 Capacidad instalada", "V13 Ocupacion del departamento",
                  "V14 Ventana coincidente", "V15 Peso de cada poligono"],
    "Conectividad": ["V16 Embudo de transferencia", "V17 Tasa mes a mes",
                     "V18 Quien completa el viaje", "V19 Rezago del traslado",
                     "V20 La puerta maritima"],
    "Guia": [],
    "Presentacion": [],
}

# Un enfoque nacido del toque en una grafica se propaga a las demas.
CLAVES_FOCO = ["subdestino_foco", "mercado_foco", "evento_foco"]


# --------------------------------------------------------------------------
# Barra superior: navegacion + filtros en menus emergentes
# --------------------------------------------------------------------------
def navegacion() -> str:
    seccion = st.segmented_control(
        "Modulo", list(SECCIONES), default="Demanda", key="seccion",
        format_func=lambda s: SECCIONES[s][0], label_visibility="collapsed",
        width="stretch")
    return seccion or "Demanda"


def herramientas(mensual: pd.DataFrame, seccion: str) -> dict:
    """Fila de controles tipo barra de herramientas de iOS."""
    anio_min, anio_max = int(mensual["anio"].min()), int(mensual["anio"].max())
    anios = st.session_state.get("anios", (anio_min, anio_max))
    subdestinos = st.session_state.get("subdestinos", [])
    catalogo = GRAFICAS[seccion]

    cols = st.columns([1.15, 1.2, 1.3, 1.25, 1.0], gap="small")

    with cols[0]:
        rotulo = (f"Periodo · {anios[0]}" if anio_min == anio_max
                  else f"Periodo · {anios[0]}–{anios[1]}")
        with st.popover(rotulo, icon=":material/calendar_month:", width="stretch"):
            if anio_min == anio_max:
                st.caption(f"La movilidad del destino cubre un solo ano: {anio_min}.")
            else:
                anios = st.slider("Anos incluidos", anio_min, anio_max, anios,
                                  key="anios",
                                  help="Acota las fuentes de movilidad al rango elegido. "
                                       "Ocupacion, oferta y migracion declaran su propia "
                                       "cobertura en cada grafica.")

    with cols[1]:
        rotulo = ("Lugar · ambos poligonos" if not subdestinos
                  else f"Lugar · {', '.join(subdestinos)}")
        with st.popover(rotulo, icon=":material/place:", width="stretch"):
            subdestinos = st.multiselect(
                "Poligono del destino", dt.SUBDESTINOS, key="subdestinos",
                placeholder="Rio Dulce y Livingston",
                help="Los poligonos no se suman: quien estuvo en los dos figura "
                     "en ambos. El tablero los compara, nunca los totaliza.")

    with cols[2]:
        origen = st.session_state.get("origen", "Ambos")
        segmento = st.session_state.get("segmento", "Ambos")
        with st.popover(f"Visitante · {origen.lower()}",
                        icon=":material/tune:", width="stretch"):
            origen = st.segmented_control(
                "Procedencia", ["Ambos", "Nacional", "Extranjero"],
                default=origen, key="origen", width="stretch",
                help="Nacionales y extranjeros se reportan por separado: los "
                     "primeros llevan factor de expansion y los segundos no.")
            segmento = st.segmented_control(
                "Tipo de visitante",
                ["Ambos", dt.SEG_PERNOCTA, dt.SEG_PASO],
                default=segmento, key="segmento", width="stretch",
                format_func=lambda s: {dt.SEG_PERNOCTA: "Pernocta",
                                       dt.SEG_PASO: "Mismo dia"}.get(s, s))
            st.divider()
            detalle = st.segmented_control(
                "Profundidad del contenido",
                ["Resumen ejecutivo", "Analisis completo"],
                default=st.session_state.get("detalle", "Analisis completo"),
                key="detalle", width="stretch",
                help="El resumen ejecutivo deja solo la lectura principal de cada "
                     "grafica y oculta las notas metodologicas.")
        origen = origen or "Ambos"
        segmento = segmento or "Ambos"
        detalle = st.session_state.get("detalle") or "Analisis completo"

    with cols[3]:
        if catalogo:
            activas = st.session_state.get(f"activas_{seccion}", catalogo)
            with st.popover(f"Graficas · {len(activas)} de {len(catalogo)}",
                            icon=":material/bar_chart:", width="stretch"):
                activas = st.multiselect(
                    "Graficas visibles en este modulo", catalogo,
                    default=catalogo, key=f"activas_{seccion}",
                    placeholder="Ninguna grafica seleccionada")
        else:
            activas = []
            st.empty()

    with cols[4]:
        if st.button("Restablecer", icon=":material/restart_alt:",
                     width="stretch", help="Vuelve a la vista inicial."):
            for clave in ["anios", "subdestinos", "origen", "segmento",
                          "detalle", *CLAVES_FOCO, f"activas_{seccion}"]:
                st.session_state.pop(clave, None)
            st.rerun()

    return {"anios": tuple(anios), "subdestinos": subdestinos, "origen": origen,
            "segmento": segmento, "detalle": detalle, "graficas_activas": activas}


def estado_actual(opc: dict, cobertura: pd.DataFrame) -> None:
    """Pildoras que resumen, en una linea, que esta viendo el usuario.

    La primera siempre declara la cobertura de la fuente principal: el lector
    tiene que saber en todo momento que periodo respalda lo que esta mirando.
    """
    etiquetas = []
    if not cobertura.empty:
        fila = cobertura.iloc[0]
        etiquetas.append(f"Movilidad: {fila['meses']} meses observados")
    etiquetas.append("Ambos poligonos" if not opc["subdestinos"]
                     else " y ".join(opc["subdestinos"]))
    if opc["origen"] != "Ambos":
        etiquetas.append(f"Solo {opc['origen'].lower()}es")
    if opc["segmento"] != "Ambos":
        etiquetas.append(opc["segmento"])

    focos = {c: st.session_state.get(c) for c in CLAVES_FOCO}
    for clave, valor in focos.items():
        if valor:
            etiquetas.append(f"{clave.split('_')[0].capitalize()}: {valor}")
    chips(etiquetas)

    if any(focos.values()):
        if st.button("Quitar enfoque", icon=":material/close:", key="quitar_foco"):
            for clave in CLAVES_FOCO:
                st.session_state.pop(clave, None)
            st.rerun()


# --------------------------------------------------------------------------
def preparar(base: dict[str, pd.DataFrame], opc: dict) -> dict:
    """Arma el contexto que recibe cada modulo.

    Se entregan dos versiones de la movilidad: la filtrada por la barra de
    herramientas, que es la que alimenta las graficas, y la completa, que los
    modelos necesitan intacta para no ajustarse sobre un subconjunto que el
    usuario eligio por casualidad.
    """
    mensual = dt.filtrar(base["movilidad_mensual"], opc["anios"],
                         opc["subdestinos"], opc["origen"], opc["segmento"])
    diaria = dt.filtrar(base["movilidad_diaria"], opc["anios"],
                        opc["subdestinos"], opc["origen"])

    ctx = dict(opc)
    ctx.update({
        "mensual": mensual,
        "diaria": diaria,
        "mensual_completo": base["movilidad_mensual"],
        "diaria_completa": base["movilidad_diaria"],
        "ocupacion": base["ocupacion_izabal"],
        "ocupacion_pais": base["ocupacion"],
        "oferta": base["oferta_izabal"],
        "oferta_pais": base["oferta"],
        "migracion": base["migracion_mensual"],
        "migracion_izabal": base["migracion_izabal"],
    })
    return ctx


def main() -> None:
    base = dt.cargar()

    seccion = st.session_state.get("seccion") or "Demanda"
    titulo, _, _ = SECCIONES[seccion]
    barra_navegacion(titulo)

    seccion = navegacion()
    titulo, bajada, render = SECCIONES[seccion]
    titulo_grande(titulo, bajada)

    opc = herramientas(base["movilidad_mensual"], seccion)
    cob = dt.cobertura(base["movilidad_mensual"], base["movilidad_diaria"],
                       base["ocupacion_izabal"])
    estado_actual(opc, cob)

    ctx = preparar(base, opc)
    ctx["cobertura"] = cob
    render(ctx)


if __name__ == "__main__":
    main()
