"""
Modulo 3 — Oferta hotelera y desagregacion territorial.

La oferta y la ocupacion se registran por departamento, no por destino
turistico. Todo lo que este modulo muestra es Izabal entero: Puerto Barrios,
Morales y el resto del departamento estan dentro de la cifra, y ni Rio Dulce
ni Livingston se pueden aislar de ella. El tablero lo declara en cada
grafica en vez de dar a entender un corte que los datos no tienen.

Dos advertencias que atraviesan el modulo:

  * La oferta no es una serie mensual pese al nombre de su columna. Son cinco
    cortes anuales, un inventario y no un flujo. Se dibuja como barras por
    corte y nunca como una tendencia de cinco puntos.
  * La oferta registra hospedajes, hoteles y pensiones. No incluye las
    plataformas digitales, que si aparecen declaradas en las encuestas de
    otros destinos. Oferta y demanda miden universos distintos, y por eso
    ninguna division entre ambas se presenta como una tasa de ocupacion real.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import datos as dt
from componentes import (aplicar_estilo, aviso, eje_meses, grupo, kpi,
                         lectura, miles, mostrar, nota, par_columnas,
                         sin_datos, titulo_grafica)
from config import (AZUL, CELESTE, COLOR_SUBDESTINO, GRIS, IOS_SEC, LINEA,
                    MORADO, NARANJA, ROSA, SALMON, SECUENCIAL, TINTA, VERDE)

COLOR_TIPO = {"Hotel": AZUL, "Hospedaje": CELESTE, "Pensión": SALMON,
              "Pension": SALMON}


# --------------------------------------------------------------------------
def _kpis(oferta: pd.DataFrame, ocup: pd.DataFrame) -> None:
    ultimo = oferta[oferta["anio"] == oferta["anio"].max()]
    corte = ultimo["corte"].iloc[0] if len(ultimo) else "sin dato"

    anio_oc = int(ocup["anio"].max()) if len(ocup) else None
    del_anio = ocup[ocup["anio"] == anio_oc] if anio_oc else ocup
    media = del_anio["ocupacion_pct"].mean() if len(del_anio) else float("nan")
    pico = del_anio.loc[del_anio["ocupacion_pct"].idxmax()] if len(del_anio) else None

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        with st.container(border=True):
            kpi("Establecimientos", miles(ultimo["establecimientos"].sum()),
                f"inventario del corte {corte}", "azul")
    with c2:
        with st.container(border=True):
            kpi("Habitaciones", miles(ultimo["habitaciones"].sum()),
                f"{miles(ultimo['plazas_cama'].sum())} plazas cama", "celeste")
    with c3:
        with st.container(border=True):
            kpi("Ocupacion media",
                "sin dato" if pd.isna(media) else f"{media:.0f} %",
                f"promedio de los meses de {anio_oc}", "verde")
    with c4:
        with st.container(border=True):
            if pico is None:
                kpi("Mes pico", "sin dato", "", "morado")
            else:
                kpi("Mes pico", f"{pico['ocupacion_pct']:.0f} %",
                    f"{pico['etiqueta_mes']}", "morado")


# --------------------------------------------------------------------------
def _v12_oferta(oferta: pd.DataFrame, medida: str) -> go.Figure:
    """Inventario por corte anual. Barras agrupadas, nunca una linea."""
    tabla = dt.oferta_anual(oferta)
    fig = go.Figure()
    for tipo in sorted(tabla["tipo_alojamiento"].unique()):
        parte = tabla[tabla["tipo_alojamiento"] == tipo].sort_values("anio")
        fig.add_bar(x=parte["corte"], y=parte[medida], name=tipo,
                    marker_color=COLOR_TIPO.get(tipo, GRIS),
                    hovertemplate=(f"<b>{tipo}</b><br>Corte %{{x}}<br>"
                                   "%{y:,.0f}<extra></extra>"))
    fig.update_layout(barmode="stack")
    rotulos = {"establecimientos": "Establecimientos",
               "habitaciones": "Habitaciones", "plazas_cama": "Plazas cama"}
    aplicar_estilo(fig, alto=340,
                   yaxis=dict(title=rotulos[medida], tickformat="~s"),
                   xaxis=dict(title="Corte del inventario"))
    return fig


def _v13_ocupacion(ocup: pd.DataFrame) -> go.Figure:
    """Serie mensual continua 2023-2025 del departamento, contra el pais."""
    tabla = ocup.sort_values("fecha")
    fig = go.Figure()
    fig.add_scatter(x=tabla["fecha"], y=tabla["ocupacion_pais_pct"],
                    name="Promedio de los 22 departamentos", mode="lines",
                    line=dict(color=GRIS, width=1.8, dash="dot"),
                    hovertemplate=("Pais<br>%{x|%b %Y}<br>"
                                   "%{y:.1f} %<extra></extra>"))
    fig.add_scatter(x=tabla["fecha"], y=tabla["ocupacion_pct"],
                    name="Izabal", mode="lines+markers",
                    line=dict(color=AZUL, width=2.5), marker=dict(size=6),
                    hovertemplate=("<b>Izabal</b><br>%{x|%b %Y}<br>"
                                   "%{y:.1f} %<extra></extra>"))
    aplicar_estilo(fig, alto=340,
                   yaxis=dict(title="Indice de ocupacion", ticksuffix=" %",
                              range=[0, 100]),
                   xaxis=dict(title=None))
    return eje_meses(fig, tabla["fecha"], cada=4)


def _v14_ventana(cruce: pd.DataFrame) -> go.Figure:
    """Afluencia y ocupacion en los cuatro meses en que ambas fuentes existen.

    Dos ejes porque son dos magnitudes distintas: personas y porcentaje. El
    eje derecho arranca en cero y llega a cien para que el lector no lea una
    pendiente que solo viene del recorte de escala.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    orden = cruce.sort_values("fecha")["etiqueta_mes"].unique().tolist()

    for sub in cruce["subdestino"].unique():
        parte = cruce[cruce["subdestino"] == sub].sort_values("fecha")
        fig.add_bar(x=parte["etiqueta_mes"], y=parte["visitantes"], name=sub,
                    marker_color=COLOR_SUBDESTINO.get(sub, GRIS),
                    hovertemplate=(f"<b>{sub}</b><br>%{{x}}<br>"
                                   "%{y:,.0f} visitantes<extra></extra>"),
                    secondary_y=False)
    ocup = cruce.drop_duplicates("fecha").sort_values("fecha")
    fig.add_scatter(x=ocup["etiqueta_mes"], y=ocup["ocupacion_pct"],
                    name="Ocupacion de Izabal", mode="lines+markers",
                    line=dict(color=NARANJA, width=3), marker=dict(size=10),
                    hovertemplate=("<b>Ocupacion de Izabal</b><br>%{x}<br>"
                                   "%{y:.1f} %<extra></extra>"),
                    secondary_y=True)

    fig.update_layout(barmode="group")
    aplicar_estilo(fig, alto=360, xaxis=dict(categoryorder="array",
                                             categoryarray=orden))
    fig.update_yaxes(title_text="Visitantes unicos del mes", tickformat="~s",
                     secondary_y=False)
    # Marcas fijas cada 25 puntos: con el rango automatico Plotly reparte el
    # eje secundario en valores como 24.2 % o 48.4 %, que no se leen.
    fig.update_yaxes(title_text="Ocupacion hotelera", ticksuffix=" %",
                     range=[0, 100], dtick=25, secondary_y=True,
                     showgrid=False)
    return fig


def _v15_poligonos(desag: pd.DataFrame) -> go.Figure:
    """Peso relativo de cada poligono contra el mayor del mes."""
    fig = go.Figure()
    orden = desag.sort_values("fecha")["etiqueta_mes"].unique().tolist()
    for sub in desag["subdestino"].unique():
        parte = desag[desag["subdestino"] == sub].sort_values("fecha")
        fig.add_bar(x=parte["etiqueta_mes"], y=parte["indice_vs_mayor"], name=sub,
                    marker_color=COLOR_SUBDESTINO.get(sub, GRIS),
                    customdata=parte[["visitantes"]],
                    hovertemplate=(f"<b>{sub}</b><br>%{{x}}<br>"
                                   "%{y:.1f} % del poligono mayor<br>"
                                   "%{customdata[0]:,.0f} visitantes<extra></extra>"))
    fig.update_layout(barmode="group")
    aplicar_estilo(fig, alto=340,
                   yaxis=dict(title="% del poligono mayor del mes",
                              ticksuffix=" %"),
                   xaxis=dict(tickangle=-40, categoryorder="array",
                              categoryarray=orden))
    return fig


# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    oferta = ctx["oferta"]
    ocup = ctx["ocupacion"]
    mensual = ctx["mensual"]
    activas = ctx["graficas_activas"]
    completo = ctx["detalle"] == "Analisis completo"

    aviso("Oferta y ocupacion se registran por departamento. Todo este modulo "
          "es Izabal completo: Puerto Barrios y Morales estan dentro de las "
          "cifras y no se pueden separar de Rio Dulce ni de Livingston. Es el "
          "unico modulo del tablero donde la unidad territorial no es el "
          "destino asignado.")

    grupo("Tarjetas principales")
    _kpis(oferta, ocup)

    # ------------------------------------------------------------- V12 / V13
    grupo("Capacidad instalada y su uso")
    ver12, ver13 = ("V12 Capacidad instalada" in activas,
                    "V13 Ocupacion del departamento" in activas)
    izq, der = par_columnas(ver12, ver13)

    if ver12:
        with izq, st.container(border=True):
            titulo_grafica("V12", "Capacidad instalada por corte anual",
                           "Como cambio el inventario de alojamiento entre 2022 y 2026")
            medida = st.segmented_control(
                "Medida", ["establecimientos", "habitaciones", "plazas_cama"],
                default="habitaciones", key="medida_oferta", width="stretch",
                format_func=lambda m: {"establecimientos": "Establecimientos",
                                       "habitaciones": "Habitaciones",
                                       "plazas_cama": "Plazas cama"}[m])
            mostrar(_v12_oferta(oferta, medida or "habitaciones"), "v12_oferta")
            tabla = dt.oferta_anual(oferta)
            primero = tabla[tabla["anio"] == tabla["anio"].min()]["habitaciones"].sum()
            ultimo = tabla[tabla["anio"] == tabla["anio"].max()]["habitaciones"].sum()
            lectura("La capacidad de Izabal esta practicamente congelada: entre "
                    f"el primer corte y el ultimo pasa de {miles(primero)} a "
                    f"{miles(ultimo)} habitaciones. El destino no esta "
                    "resolviendo su presion de temporada alta construyendo "
                    "mas cuartos.")
            if completo:
                nota("Son cinco cortes anuales, no una serie mensual, pese a "
                     "que la columna de origen se llame 'trimestre'. Se "
                     "dibujan como barras por corte justamente para no "
                     "sugerir una tendencia que cinco puntos no sostienen. El "
                     "corte de 2026 es del primer trimestre y los anteriores "
                     "del cuarto, de modo que tampoco son estrictamente "
                     "comparables entre si.")

    if ver13:
        with der, st.container(border=True):
            titulo_grafica("V13", "Ocupacion mensual del departamento",
                           "Como se mueve la ocupacion de Izabal frente al promedio del pais")
            if ocup.empty:
                sin_datos("No hay indice de ocupacion disponible.")
            else:
                mostrar(_v13_ocupacion(ocup), "v13_ocupacion")
                lectura("Izabal se mantiene por encima del promedio nacional "
                        "casi todo el periodo, con picos en Semana Santa y en "
                        "diciembre y un valle marcado en octubre. Es la firma "
                        "de un destino de temporada, no de uno de flujo "
                        "constante de negocios.")
            if completo:
                nota("Serie mensual continua de enero de 2023 a diciembre de "
                     "2025, sin huecos. La referencia nacional es el promedio "
                     "simple de los 22 departamentos del mes, no una media "
                     "ponderada por capacidad: sirve para situar a Izabal, no "
                     "para medir el pais.")

    # ------------------------------------------------------------- V14 / V15
    grupo("Donde las fuentes se tocan")
    ver14, ver15 = ("V14 Ventana coincidente" in activas,
                    "V15 Peso de cada poligono" in activas)
    izq, der = par_columnas(ver14, ver15)

    if ver14:
        with izq, st.container(border=True):
            titulo_grafica("V14", "Afluencia y ocupacion en la ventana coincidente",
                           "Que relacion hay entre visitantes y camas ocupadas "
                           "donde ambas fuentes existen",
                           ["Solo sep–dic 2025"])
            cruce = dt.ventana_coincidente(mensual, ocup)
            if cruce.empty:
                sin_datos("La ventana coincidente queda fuera del periodo "
                          "elegido en la barra superior.")
            else:
                mostrar(_v14_ventana(cruce), "v14_ventana")
                lectura("Los cuatro meses se mueven en el mismo sentido: "
                        "diciembre es a la vez el mes de mas afluencia y el de "
                        "mayor ocupacion, y octubre el valle de los dos. Con "
                        "cuatro puntos eso es coherencia, no correlacion "
                        "demostrada.")
            if completo:
                nota("La movilidad llega hasta agosto de 2026 y el indice de "
                     "ocupacion termina en diciembre de 2025: la interseccion "
                     "son exactamente estos cuatro meses. Cruzar las dos "
                     "fuentes fuera de esta ventana compara un dato contra un "
                     "vacio. Los dos ejes son distintos a proposito: personas "
                     "y porcentaje no comparten escala.")

    if ver15:
        with der, st.container(border=True):
            titulo_grafica("V15", "Peso de cada poligono",
                           "Cuanto representa Livingston frente a Rio Dulce cada mes")
            desag = dt.desagregacion(mensual)
            if desag.empty:
                sin_datos("No hay movilidad para el filtro actual.")
            else:
                mostrar(_v15_poligonos(desag), "v15_poligonos")
                liv = desag[desag["subdestino"] == dt.DESTINO_FINAL]
                if len(liv):
                    lectura(f"Livingston se mueve alrededor del "
                            f"{liv['indice_vs_mayor'].mean():.0f} % de Rio "
                            "Dulce y nunca se le acerca. El destino asignado "
                            "no son dos polos comparables, sino una puerta "
                            "grande y un destino final pequeno: eso es lo que "
                            "el modulo 4 va a medir.")
            if completo:
                nota("La comparacion es contra el poligono mayor del mes y no "
                     "contra una suma. Sumar los poligonos duplicaria a quien "
                     "estuvo en los dos y el denominador quedaria inflado, "
                     "con lo que el peso de cada uno saldria artificialmente "
                     "bajo.")
