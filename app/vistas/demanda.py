"""
Modulo 1 — Monitor de demanda y mercados emisores (diagnostico macro).

Responde cuatro preguntas: cuanta visita recibe el destino en un mes tipico,
cuanto tiempo se queda, que parte pernocta y de donde viene.

Las tres reglas que gobiernan este modulo:

  * Los visitantes mensuales no se suman entre meses. Una misma persona puede
    aparecer en varios meses, de modo que la suma no es un total del periodo.
    El KPI es el promedio mensual.
  * Los poligonos no se suman entre si. El total del destino vive entre el
    poligono mayor (piso) y la suma de los dos (techo), y el tablero muestra
    ese rango en vez de inventar una cifra unica.
  * La estadia media se calcula sobre el segmento con pernocta, como cociente
    de sumas. Nunca se promedia la columna de permanencia.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import datos as dt
from componentes import (aplicar_estilo, grupo, kpi, lectura, miles, mostrar,
                         mostrar_tactil, nota, par_columnas, sin_datos,
                         titulo_grafica)
from config import (AZUL, CELESTE, COLOR_ORIGEN, COLOR_SEGMENTO,
                    COLOR_SUBDESTINO, GRIS, IOS_SEC, LINEA, NARANJA, ROSA,
                    SALMON, TINTA, VERDE)


# --------------------------------------------------------------------------
def _kpis(mensual: pd.DataFrame) -> None:
    piso, techo = dt.cota_destino(mensual)
    promedio = dt.promedio_mensual(mensual)
    estadia = dt.estadia_media(mensual)
    dias = mensual["dias_persona"].sum()

    seg = dt.segmentacion(mensual)
    pernocta = seg.loc[seg["segmento"] == dt.SEG_PERNOCTA, "porcentaje"]
    pct_pernocta = float(pernocta.iloc[0]) if len(pernocta) else float("nan")

    meses = mensual["fecha"].nunique()

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        with st.container(border=True):
            kpi("Visitantes en un mes tipico", miles(piso),
                f"piso del destino · techo {miles(techo)}", "azul")
    with c2:
        with st.container(border=True):
            kpi("Dias-persona", miles(dias),
                f"acumulados en {meses} meses observados", "celeste")
    with c3:
        with st.container(border=True):
            kpi("Estadia media ponderada",
                "sin dato" if pd.isna(estadia) else f"{estadia:.2f} dias",
                "solo segmento con pernocta", "verde")
    with c4:
        with st.container(border=True):
            kpi("Pernocta",
                "sin dato" if pd.isna(pct_pernocta) else f"{pct_pernocta:.1f} %",
                "del total de visitantes del destino", "morado")

    nota(f"El promedio mensual sin separar poligonos es de {miles(promedio)} "
         "visitantes, pero esa cifra duplica a quien estuvo en Rio Dulce y en "
         "Livingston el mismo mes. El piso toma el poligono mayor de cada mes "
         "y el techo suma los dos: el total real del destino esta entre ambos "
         "y solo INGUAT, con la base sin desagregar, puede fijarlo.")


# --------------------------------------------------------------------------
def _v1_evolucion(mensual: pd.DataFrame, foco: str | None) -> alt.Chart:
    """Serie mensual por poligono. El toque fija el enfoque del modulo."""
    serie = dt.visitantes_mes(mensual, ["subdestino"])
    seleccion = alt.selection_point(name="toque", fields=["subdestino"],
                                    on="click", clear="dblclick")
    opacidad = (alt.value(1.0) if foco is None else
                alt.condition(alt.datum.subdestino == foco,
                              alt.value(1.0), alt.value(0.25)))
    orden = list(serie.sort_values("fecha")["etiqueta_mes"].unique())

    base = alt.Chart(serie).encode(
        x=alt.X("etiqueta_mes:N", title=None, sort=orden,
                axis=alt.Axis(labelAngle=-40)),
        y=alt.Y("visitantes:Q", title="Visitantes unicos del mes",
                axis=alt.Axis(format="~s")),
        color=alt.Color("subdestino:N", title=None,
                        scale=alt.Scale(domain=list(COLOR_SUBDESTINO),
                                        range=list(COLOR_SUBDESTINO.values())),
                        legend=alt.Legend(orient="top", direction="horizontal")),
        opacity=opacidad,
        tooltip=[alt.Tooltip("etiqueta_mes:N", title="Mes"),
                 alt.Tooltip("subdestino:N", title="Poligono"),
                 alt.Tooltip("visitantes:Q", title="Visitantes", format=",.0f"),
                 alt.Tooltip("dias_persona:Q", title="Dias-persona", format=",.0f")])

    return (base.mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=58))
                .add_params(seleccion).properties(height=330))


def _v2_segmento(mensual: pd.DataFrame) -> go.Figure:
    """Pernocta frente a mismo dia, mes a mes y en proporcion."""
    serie = (mensual.groupby(["fecha", "segmento"], as_index=False)["visitantes"].sum())
    serie["etiqueta_mes"] = dt.etiqueta_mes(serie["fecha"])
    total = serie.groupby("fecha")["visitantes"].transform("sum")
    serie["porcentaje"] = serie["visitantes"] / total * 100

    fig = go.Figure()
    for segmento in (dt.SEG_PASO, dt.SEG_PERNOCTA):
        parte = serie[serie["segmento"] == segmento]
        fig.add_bar(x=parte["etiqueta_mes"], y=parte["porcentaje"],
                    name=segmento, marker_color=COLOR_SEGMENTO[segmento],
                    customdata=parte[["visitantes"]],
                    hovertemplate=(f"<b>{segmento}</b><br>%{{x}}<br>"
                                   "%{y:.1f} % del mes<br>"
                                   "%{customdata[0]:,.0f} visitantes<extra></extra>"))
    fig.update_layout(barmode="stack")
    aplicar_estilo(fig, alto=330,
                   yaxis=dict(title="% de los visitantes del mes", range=[0, 100]),
                   xaxis=dict(tickangle=-40))
    return fig


def _v3_mercados(mensual: pd.DataFrame, foco: str | None) -> alt.Chart:
    """Top 10 de mercados emisores extranjeros. El toque enfoca V5."""
    top = dt.mercados(mensual, top=10)
    if top.empty:
        return None
    seleccion = alt.selection_point(name="toque", fields=["pais"],
                                    on="click", clear="dblclick")
    color = (alt.value(NARANJA) if foco is None else
             alt.condition(alt.datum.pais == foco,
                           alt.value(NARANJA), alt.value("#F2D4AE")))
    texto = alt.Chart(top).mark_text(align="left", dx=5, color=TINTA,
                                     fontSize=11).encode(
        y=alt.Y("pais:N", sort="-x", title=None),
        x=alt.X("visitantes:Q"),
        text=alt.Text("pct_del_universo:Q", format=".1f"))

    barras = alt.Chart(top).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("pais:N", sort="-x", title=None),
        x=alt.X("visitantes:Q", title="Visitantes extranjeros acumulados",
                axis=alt.Axis(format="~s")),
        color=color,
        tooltip=[alt.Tooltip("pais:N", title="Mercado"),
                 alt.Tooltip("visitantes:Q", title="Visitantes", format=",.0f"),
                 alt.Tooltip("pct_del_universo:Q",
                             title="% del universo extranjero", format=".1f")]
    ).add_params(seleccion)

    return (barras + texto).properties(height=330)


def _v4_origen(mensual: pd.DataFrame) -> go.Figure:
    """Nacionales y extranjeros en paneles separados, cada uno con su eje.

    No comparten escala a proposito: la cifra nacional incorpora un factor de
    expansion que la extranjera no tiene, de modo que ponerlas en el mismo eje
    sugeriria una comparacion que los datos no permiten.
    """
    serie = (mensual.groupby(["fecha", "origen"], as_index=False)["visitantes"].sum())
    serie["etiqueta_mes"] = dt.etiqueta_mes(serie["fecha"])

    fig = make_subplots(rows=1, cols=2, shared_xaxes=False,
                        subplot_titles=("Nacionales (con factor de expansion)",
                                        "Extranjeros (conteo directo)"))
    for i, origen in enumerate(("Nacional", "Extranjero"), start=1):
        parte = serie[serie["origen"] == origen]
        fig.add_bar(x=parte["etiqueta_mes"], y=parte["visitantes"],
                    name=origen, marker_color=COLOR_ORIGEN[origen],
                    showlegend=False, row=1, col=i,
                    hovertemplate=(f"<b>{origen}</b><br>%{{x}}<br>"
                                   "%{y:,.0f} visitantes<extra></extra>"))
    fig.update_annotations(font=dict(size=12, color=IOS_SEC))
    aplicar_estilo(fig, alto=330, xaxis=dict(tickangle=-40),
                   xaxis2=dict(tickangle=-40, gridcolor=LINEA, linecolor=LINEA,
                               tickfont=dict(size=11, color=IOS_SEC)),
                   yaxis=dict(title="Visitantes", tickformat="~s"),
                   yaxis2=dict(title="Visitantes", tickformat="~s",
                               gridcolor=LINEA, linecolor=LINEA,
                               tickfont=dict(size=11, color=IOS_SEC)))
    return fig


def _v5_volumen_estadia(mensual: pd.DataFrame, foco: str | None) -> go.Figure:
    """Volumen frente a estadia por mercado, solo sobre el segmento que pernocta."""
    pernocta = mensual[mensual["segmento"] == dt.SEG_PERNOCTA]
    por_pais = (pernocta.groupby(["pais", "origen"], as_index=False)
                        .agg(visitantes=("visitantes", "sum"),
                             dias=("dias_persona", "sum")))
    por_pais = por_pais[por_pais["visitantes"] >= 50].copy()
    if por_pais.empty:
        return None
    por_pais["estadia"] = por_pais["dias"] / por_pais["visitantes"]
    # La referencia es la estadia ponderada del destino (cociente de sumas),
    # la misma que la tarjeta principal. El promedio simple de las estadias
    # por mercado daria otra cifra, mas baja, porque pesaria igual a un
    # mercado de cien visitantes que al nacional.
    media = dt.estadia_media(mensual)

    fig = go.Figure()
    for origen in por_pais["origen"].unique():
        parte = por_pais[por_pais["origen"] == origen]
        destacado = [14 if p == foco else 9 for p in parte["pais"]]
        bordes = [TINTA if p == foco else "white" for p in parte["pais"]]
        fig.add_scatter(
            x=parte["visitantes"], y=parte["estadia"], mode="markers+text",
            name=origen, text=parte["pais"], textposition="top center",
            textfont=dict(size=9, color=IOS_SEC),
            marker=dict(size=destacado, color=COLOR_ORIGEN[origen],
                        line=dict(width=1.5, color=bordes)),
            hovertemplate=("<b>%{text}</b><br>%{x:,.0f} visitantes con pernocta"
                           "<br>%{y:.2f} dias de estadia media<extra></extra>"))
    fig.add_hline(y=media, line_dash="dot", line_color=GRIS,
                  annotation_text=f"Estadia media del destino: {media:.2f} dias",
                  annotation_font=dict(size=11, color=IOS_SEC))
    aplicar_estilo(fig, alto=400,
                   xaxis=dict(title="Visitantes con pernocta (escala logaritmica)",
                              type="log", tickformat="~s"),
                   yaxis=dict(title="Dias de estadia media"))
    return fig


# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    mensual = ctx["mensual"]
    activas = ctx["graficas_activas"]
    completo = ctx["detalle"] == "Analisis completo"
    foco_sub = st.session_state.get("subdestino_foco")
    foco_mercado = st.session_state.get("mercado_foco")

    if mensual.empty:
        sin_datos("No hay movilidad para la combinacion elegida. "
                  "Amplia el periodo o quita algun filtro de la barra superior.")
        return

    grupo("Tarjetas principales")
    _kpis(mensual)

    # ---------------------------------------------------------------- V1 / V2
    grupo("Cuanta visita llega y cuanta se queda")
    ver1, ver2 = ("V1 Evolucion de la visita" in activas,
                  "V2 Turista frente a excursionista" in activas)
    izq, der = par_columnas(ver1, ver2)

    if ver1:
        with izq, st.container(border=True):
            titulo_grafica("V1", "Evolucion de la visita por poligono",
                           "Cuantos visitantes unicos recibe cada poligono cada mes",
                           ["Enlazada · toca una serie"])
            grafico = _v1_evolucion(mensual, foco_sub)
            tocado = mostrar_tactil(grafico, "v1_evolucion", "subdestino")
            if tocado and tocado != foco_sub:
                st.session_state["subdestino_foco"] = tocado
                st.rerun()
            lectura("Rio Dulce concentra el volumen y Livingston se mueve en un "
                    "orden de magnitud menor. Toca una de las dos series para "
                    "enfocar el resto del modulo en ese poligono.")
            if completo:
                nota("Las dos lineas no se suman. Cada una cuenta visitantes "
                     "unicos de su poligono, y quien paso por los dos esta en "
                     "las dos. El hueco entre diciembre de 2025 y marzo de 2026 "
                     "es ausencia de cobertura de telefonia, no caida de visita: "
                     "el modulo 2 lo estima.")

    if ver2:
        with der, st.container(border=True):
            titulo_grafica("V2", "Turista frente a excursionista",
                           "Que proporcion de la visita pernocta y cual es de paso")
            mostrar(_v2_segmento(mensual), "v2_segmento")
            seg = dt.segmentacion(mensual)
            if not seg.empty:
                paso = seg.loc[seg["segmento"] == dt.SEG_PASO, "porcentaje"]
                pct = float(paso.iloc[0]) if len(paso) else 0.0
                lectura(f"Cerca del {pct:.0f} % de la visita entra y sale el "
                        "mismo dia. Es un destino de paso mas que de estancia, "
                        "y ese es el hecho que ordena el resto del tablero: "
                        "mas visitantes no se traduce automaticamente en mas "
                        "noches vendidas.")
            if completo:
                nota("Al visitante de menos de 24 horas se le asigna "
                     "permanencia 1 por definicion. Por eso se le excluye del "
                     "calculo de la estadia media: incluirlo arrastraria el "
                     "indicador hacia 1 dia y subestimaria la permanencia real "
                     "del turista que si pernocta.")

    # ---------------------------------------------------------------- V3 / V4
    grupo("De donde viene la visita")
    ver3, ver4 = ("V3 Mercados emisores extranjeros" in activas,
                  "V4 Nacionales y extranjeros" in activas)
    izq, der = par_columnas(ver3, ver4)

    if ver3:
        with izq, st.container(border=True):
            titulo_grafica("V3", "Top 10 de mercados emisores extranjeros",
                           "Que paises alimentan la visita internacional del destino",
                           ["Enlazada · toca una barra"])
            grafico = _v3_mercados(mensual, foco_mercado)
            if grafico is None:
                sin_datos("No hay visitantes extranjeros en el filtro actual.")
            else:
                tocado = mostrar_tactil(grafico, "v3_mercados", "pais")
                if tocado and tocado != foco_mercado:
                    st.session_state["mercado_foco"] = tocado
                    st.rerun()
                lectura("El mercado extranjero del destino es regional: "
                        "El Salvador, Estados Unidos y Honduras concentran mas "
                        "de la mitad. La cifra al lado de cada barra es el "
                        "porcentaje dentro del universo extranjero.")
            if completo:
                nota("El ranking excluye a Guatemala a proposito. Las cifras "
                     "nacionales incorporan un factor de expansion que las "
                     "extranjeras no tienen, de modo que ranquear a los dos "
                     "juntos compararia magnitudes construidas de forma "
                     "distinta. Por la misma razon el porcentaje se calcula "
                     "sobre el universo extranjero y no sobre el total.")

    if ver4:
        with der, st.container(border=True):
            titulo_grafica("V4", "Nacionales y extranjeros, por separado",
                           "Que tamano tiene cada universo mes a mes")
            mostrar(_v4_origen(mensual), "v4_origen")
            peso = dt.peso_nacional(mensual).set_index("origen")["visitantes"]
            if {"Nacional", "Extranjero"} <= set(peso.index):
                razon = peso["Nacional"] / peso["Extranjero"]
                lectura(f"Por cada visitante extranjero registrado hay del orden "
                        f"de {razon:,.0f} nacionales. Izabal es, antes que nada, "
                        "un destino de turismo interno, y cualquier estrategia "
                        "de promocion internacional parte de esa base.")
            if completo:
                nota("Los dos paneles tienen ejes propios y no comparten escala. "
                     "La razon entre ambos es indicativa, no una participacion "
                     "de mercado: para eso haria falta que las dos cifras "
                     "estuvieran construidas con el mismo metodo.")

    # ---------------------------------------------------------------------- V5
    if "V5 Volumen frente a estadia" in activas:
        grupo("Que mercados dejan mas noches")
        with st.container(border=True):
            titulo_grafica("V5", "Volumen frente a estadia por mercado",
                           "Que mercados traen muchos visitantes y cuales traen "
                           "pocos pero de estancia larga",
                           ["Enlazada · recibe el toque de V3"])
            grafico = _v5_volumen_estadia(mensual, foco_mercado)
            if grafico is None:
                sin_datos("No hay mercados con suficientes visitantes con "
                          "pernocta en el filtro actual.")
            else:
                mostrar(grafico, "v5_volumen_estadia")
                lectura("El cuadrante interesante es el de arriba a la "
                        "izquierda: mercados pequenos cuya estadia supera la "
                        "media del destino. Son los que mas noches dejan por "
                        "visitante captado y los candidatos naturales de una "
                        "promocion de nicho.")
            if completo:
                nota("Solo entran mercados con 50 o mas visitantes con "
                     "pernocta en el periodo: por debajo de ese umbral la "
                     "estadia media se vuelve inestable. El eje horizontal es "
                     "logaritmico porque el mercado nacional es tres ordenes "
                     "de magnitud mayor que el resto.")
