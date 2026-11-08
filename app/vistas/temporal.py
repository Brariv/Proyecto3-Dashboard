"""
Modulo 2 — Dinamica temporal, eventos y pronostico predictivo.

Tres bloques. El primero lee el calendario con la base diaria: que dias se
llena el destino y cuanto pesa cada festividad frente a un dia corriente. El
segundo estima los dos meses que la telefonia no cubre. El tercero muestra
el error con que se estimaron, porque una cifra estimada sin medida de error
no es un resultado.

Toda cifra estimada se dibuja en morado y con linea punteada, y lleva la
etiqueta 'Estimacion'. Es la misma regla de lectura en todo el tablero.
"""

from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos as dt
import modelos as md
from componentes import (aplicar_estilo, aviso, eje_meses, grupo, kpi,
                         lectura, miles, mostrar, mostrar_tactil, nota,
                         par_columnas, sin_datos, titulo_grafica)
from config import (AZUL, CELESTE, COLOR_MODELO, COLOR_SEGMENTO,
                    COLOR_SUBDESTINO, GRIS, IOS_SEC, LINEA, MORADO, NARANJA,
                    ROSA, SALMON, TINTA, VERDE)


# --------------------------------------------------------------------------
def _v6_serie_diaria(diaria: pd.DataFrame, evento_foco: str | None) -> go.Figure:
    """Presencia diaria por poligono, con las ventanas de evento sombreadas."""
    serie = dt.serie_diaria(diaria, ["subdestino"])
    if serie.empty:
        return None

    fig = go.Figure()
    for sub in serie["subdestino"].unique():
        parte = serie[serie["subdestino"] == sub].sort_values("fecha")
        # Los tramos sin cobertura se cortan en vez de unirse con una recta:
        # una linea continua sobre el hueco inventaria datos que no existen.
        parte = parte.set_index("fecha").asfreq("D").reset_index()
        fig.add_scatter(x=parte["fecha"], y=parte["presencia"], name=sub,
                        mode="lines", connectgaps=False,
                        line=dict(color=COLOR_SUBDESTINO.get(sub, GRIS), width=1.6),
                        hovertemplate=(f"<b>{sub}</b><br>%{{x|%d %b %Y}}<br>"
                                       "%{y:,.0f} personas presentes<extra></extra>"))

    # Sombreado de los dias del evento enfocado
    if evento_foco and evento_foco != "Regular":
        dias = sorted(serie.loc[serie["evento"] == evento_foco, "fecha"].unique())
        for dia in dias:
            fig.add_vrect(x0=pd.Timestamp(dia) - pd.Timedelta(hours=12),
                          x1=pd.Timestamp(dia) + pd.Timedelta(hours=12),
                          fillcolor=ROSA, opacity=0.16, line_width=0, layer="below")

    aplicar_estilo(fig, alto=360,
                   yaxis=dict(title="Personas presentes en el dia", tickformat="~s"),
                   xaxis=dict(title=None))
    return eje_meses(fig, serie["fecha"], cada=2)


def _v7_lift(diaria: pd.DataFrame, subdestino: str, foco: str | None) -> alt.Chart:
    """Impacto porcentual de cada festividad frente al dia regular promedio."""
    tabla = dt.lift_eventos(diaria, subdestino)
    if tabla.empty:
        return None
    seleccion = alt.selection_point(name="toque", fields=["evento"],
                                    on="click", clear="dblclick")
    color = alt.condition(alt.datum.lift_pct > 0, alt.value(VERDE), alt.value(ROSA))
    if foco:
        color = alt.condition(alt.datum.evento == foco,
                              alt.value(NARANJA), color)

    return (alt.Chart(tabla).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("evento:N", sort="-x", title=None),
        x=alt.X("lift_pct:Q", title="% frente al dia regular promedio"),
        color=color,
        tooltip=[alt.Tooltip("evento:N", title="Festividad"),
                 alt.Tooltip("lift_pct:Q", title="Lift", format="+.1f"),
                 alt.Tooltip("presencia_media:Q", title="Presencia media",
                             format=",.0f"),
                 alt.Tooltip("referencia:Q", title="Dia regular promedio",
                             format=",.0f"),
                 alt.Tooltip("dias:Q", title="Dias observados")]
    ).add_params(seleccion).properties(height=330))


def _v8_semanal(diaria: pd.DataFrame) -> go.Figure:
    """Indice de presencia por dia de la semana, por poligono."""
    tabla = dt.patron_semanal(diaria)
    if tabla.empty:
        return None
    fig = go.Figure()
    for sub in tabla["subdestino"].unique():
        parte = tabla[tabla["subdestino"] == sub].sort_values("orden")
        fig.add_scatter(x=parte["dia_semana"], y=parte["indice"], name=sub,
                        mode="lines+markers",
                        line=dict(color=COLOR_SUBDESTINO.get(sub, GRIS), width=2.5),
                        marker=dict(size=9),
                        customdata=parte[["presencia_media", "dias"]],
                        hovertemplate=(f"<b>{sub}</b><br>%{{x}}<br>"
                                       "Indice %{y:.0f} (100 = dia promedio)<br>"
                                       "%{customdata[0]:,.0f} personas en promedio<br>"
                                       "%{customdata[1]:.0f} dias observados<extra></extra>"))
    fig.add_hline(y=100, line_dash="dot", line_color=GRIS,
                  annotation_text="Dia promedio", annotation_position="right",
                  annotation_font=dict(size=11, color=IOS_SEC))
    aplicar_estilo(fig, alto=330,
                   yaxis=dict(title="Indice (100 = dia promedio)"),
                   xaxis=dict(title=None))
    return fig


# --------------------------------------------------------------------------
def _v9_pronostico(serie: pd.DataFrame) -> go.Figure:
    """Serie observada mas los dos meses estimados, visualmente separados.

    La estimacion va en morado y punteada, con su banda de error. Entre el
    ultimo observado y el primer estimado se traza un conector punteado, no
    una continuacion de la linea solida.
    """
    fig = go.Figure()
    for sub in serie["subdestino"].unique():
        parte = serie[serie["subdestino"] == sub].sort_values("fecha")
        obs = parte[parte["tipo"] == "Observado"]
        est = parte[parte["tipo"] == md.ETIQUETA_ESTIMACION].sort_values("fecha")
        color = COLOR_SUBDESTINO.get(sub, GRIS)

        fig.add_scatter(x=obs["fecha"], y=obs["visitantes"], name=f"{sub} · observado",
                        mode="lines+markers", line=dict(color=color, width=2.5),
                        marker=dict(size=7), connectgaps=False,
                        hovertemplate=(f"<b>{sub}</b> · observado<br>%{{x|%b %Y}}<br>"
                                       "%{y:,.0f} visitantes<extra></extra>"))
        if est.empty:
            continue
        fig.add_scatter(x=est["fecha"], y=est["banda_alta"], mode="lines",
                        line=dict(width=0), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=est["fecha"], y=est["banda_baja"], mode="lines",
                        line=dict(width=0), fill="tonexty",
                        fillcolor="rgba(162,21,141,0.14)", showlegend=False,
                        hoverinfo="skip")
        fig.add_scatter(x=est["fecha"], y=est["visitantes"],
                        name=f"{sub} · estimacion", mode="lines+markers",
                        line=dict(color=MORADO, width=2.5, dash="dot"),
                        marker=dict(size=8, symbol="diamond"),
                        customdata=est[["banda_baja", "banda_alta"]],
                        hovertemplate=(f"<b>{sub}</b> · ESTIMACION<br>%{{x|%b %Y}}<br>"
                                       "%{y:,.0f} visitantes<br>"
                                       "Banda: %{customdata[0]:,.0f} a "
                                       "%{customdata[1]:,.0f}<extra></extra>"))
    aplicar_estilo(fig, alto=380,
                   yaxis=dict(title="Visitantes unicos del mes", tickformat="~s"),
                   xaxis=dict(title=None))
    return eje_meses(fig, serie["fecha"])


def _v10_validacion(agregado: pd.DataFrame) -> go.Figure:
    """Error fuera de muestra, mes a mes, del modelo publicado."""
    tabla = agregado.dropna(subset=["error_pct"]).sort_values("fecha")
    fig = go.Figure()
    for sub in tabla["subdestino"].unique():
        parte = tabla[tabla["subdestino"] == sub]
        fig.add_bar(x=parte["etiqueta_mes"], y=parte["error_pct"], name=sub,
                    marker_color=COLOR_SUBDESTINO.get(sub, GRIS),
                    customdata=parte[["visitantes", "estacional"]],
                    hovertemplate=(f"<b>{sub}</b><br>%{{x}}<br>"
                                   "Error %{y:+.1f} %<br>"
                                   "Observado %{customdata[0]:,.0f}<br>"
                                   "Estimado %{customdata[1]:,.0f}<extra></extra>"))
    fig.add_hline(y=0, line_color=GRIS, line_width=1)
    aplicar_estilo(fig, alto=330,
                   yaxis=dict(title="Error de la estimacion (%)",
                              ticksuffix=" %"),
                   xaxis=dict(tickangle=-40))
    return fig


def _v11_estacionalidad(indice: pd.DataFrame) -> go.Figure:
    """El indice estacional que el modelo toma prestado de la base migratoria."""
    fig = go.Figure()
    for segmento in indice["segmento"].unique():
        parte = indice[indice["segmento"] == segmento].sort_values("mes")
        fig.add_scatter(x=parte["nombre_mes"], y=parte["indice_100"],
                        name=segmento, mode="lines+markers",
                        line=dict(color=COLOR_SEGMENTO.get(segmento, GRIS), width=2.5),
                        marker=dict(size=8),
                        hovertemplate=(f"<b>{segmento}</b><br>%{{x}}<br>"
                                       "Indice %{y:.0f}<extra></extra>"))
    fig.add_hline(y=100, line_dash="dot", line_color=GRIS,
                  annotation_text="Mes promedio del ano",
                  annotation_font=dict(size=11, color=IOS_SEC))
    for mes in ("Ene", "Feb"):
        fig.add_vrect(x0=mes, x1=mes, line_width=14, line_color="rgba(162,21,141,0.12)",
                      layer="below")
    aplicar_estilo(fig, alto=330,
                   yaxis=dict(title="Indice estacional (100 = mes promedio)"),
                   xaxis=dict(title=None))
    return fig


# --------------------------------------------------------------------------
def _tarjetas_modelo(metricas: dict, estimado: pd.DataFrame) -> None:
    mejor = metricas["estacional"]
    ingenuo = metricas["ingenuo"]
    mejora = (1 - mejor["MAPE"] / ingenuo["MAPE"]) * 100

    # Misma regla que el modulo 1: los poligonos no se suman en un total. Se
    # reporta el piso (el poligono mayor) y el techo (la suma) del mes.
    por_mes = (estimado.groupby(["fecha", "subdestino"])["visitantes"].sum()
                       .groupby("fecha"))
    piso, techo = por_mes.max(), por_mes.sum()
    ene, feb = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        with st.container(border=True):
            kpi("MAPE fuera de muestra", f"{mejor['MAPE']:.1f} %",
                f"sobre {mejor['meses']} meses, dejar-uno-fuera", "morado")
    with c2:
        with st.container(border=True):
            kpi("RMSE", miles(mejor["RMSE"]),
                f"MAE {miles(mejor['MAE'])} visitantes", "celeste")
    with c3:
        with st.container(border=True):
            kpi("Enero 2026 (estimado)", miles(piso.get(ene, float("nan"))),
                f"piso · techo {miles(techo.get(ene, float('nan')))}", "morado")
    with c4:
        with st.container(border=True):
            kpi("Febrero 2026 (estimado)", miles(piso.get(feb, float("nan"))),
                f"piso · el modelo mejora {mejora:.0f} % a la media simple",
                "morado")


# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    diaria = ctx["diaria"]
    activas = ctx["graficas_activas"]
    completo = ctx["detalle"] == "Analisis completo"
    evento_foco = st.session_state.get("evento_foco")

    # ====================================================== calendario diario
    grupo("El calendario del destino")

    if "V6 Serie diaria y eventos" in activas:
        with st.container(border=True):
            titulo_grafica("V6", "Presencia diaria en el destino",
                           "Como se llena y se vacia el destino dia a dia",
                           ["Enlazada · recibe el toque de V7"])
            if diaria.empty:
                sin_datos("No hay base diaria para el filtro actual.")
            else:
                eventos = ["Todos"] + sorted(
                    e for e in diaria["evento"].unique() if e != "Regular")
                elegido = st.selectbox(
                    "Resaltar una festividad", eventos,
                    index=eventos.index(evento_foco) if evento_foco in eventos else 0,
                    key="selector_evento",
                    help="Sombrea en el grafico los dias de la festividad elegida.")
                if elegido != "Todos" and elegido != evento_foco:
                    st.session_state["evento_foco"] = elegido
                    st.rerun()
                figura = _v6_serie_diaria(
                    diaria, None if elegido == "Todos" else elegido)
                if figura is None:
                    sin_datos("No hay base diaria para el filtro actual.")
                else:
                    mostrar(figura, "v6_diaria")
                lectura("La linea se corta donde la telefonia no midio. Los "
                        "tramos continuos son septiembre a diciembre de 2025 y "
                        "marzo a agosto de 2026; lo demas son ventanas cortas "
                        "levantadas solo alrededor de una festividad.")
            if completo:
                nota("Esta base mide presencia por dia y no visitantes unicos. "
                     "Sumar los dias de un mes no produce el total mensual: "
                     "quien pasa tres dias en el destino aparece en los tres. "
                     "Para el total del mes esta la base mensual del modulo 1.")

    ver7, ver8 = ("V7 Impacto de las festividades" in activas,
                  "V8 Patron semanal" in activas)
    izq, der = par_columnas(ver7, ver8)

    if ver7:
        with izq, st.container(border=True):
            titulo_grafica("V7", "Impacto de cada festividad",
                           "Cuanto sube la afluencia un dia de fiesta frente a uno corriente",
                           ["Enlazada · toca una barra"])
            sub = (ctx["subdestinos"][0] if len(ctx["subdestinos"]) == 1
                   else dt.PUERTA)
            grafico = _v7_lift(diaria, sub, evento_foco)
            if grafico is None:
                sin_datos("No hay dias regulares suficientes para construir "
                          "la referencia de comparacion.")
            else:
                st.caption(f"Calculado sobre {sub}.")
                tocado = mostrar_tactil(grafico, "v7_lift", "evento")
                if tocado and tocado != evento_foco:
                    st.session_state["evento_foco"] = tocado
                    st.rerun()
                lectura("Lift es el exceso de afluencia de la festividad frente "
                        "al dia regular promedio. Un lift de +40 % significa que "
                        "ese dia el destino recibe cuatro de cada diez personas "
                        "mas que un dia corriente. Toca una barra para "
                        "sombrear esos dias en V6.")
            if completo:
                nota("La referencia se calcula solo con dias marcados como "
                     "'Regular' dentro de meses con cobertura completa. Las "
                     "ventanas cortas del archivo se levantaron alrededor de "
                     "una festividad, de modo que incluir sus dias en la "
                     "referencia subiria la base de comparacion y apagaria "
                     "artificialmente el lift de todos los eventos.")

    if ver8:
        with der, st.container(border=True):
            titulo_grafica("V8", "Patron semanal",
                           "Que dias de la semana concentran la presion")
            grafico = _v8_semanal(diaria)
            if grafico is None:
                sin_datos("No hay meses con cobertura completa en el filtro actual.")
            else:
                mostrar(grafico, "v8_semanal")
                lectura("El destino es de fin de semana. La diferencia entre el "
                        "valle de entre semana y el pico de sabado y domingo "
                        "define el problema operativo real: la capacidad "
                        "instalada tiene que absorber el pico pero se paga "
                        "todos los dias.")
            if completo:
                nota("Se excluyen los dias de festividad. Caen en fechas fijas "
                     "del calendario y, de incluirse, inflarian justamente el "
                     "dia de la semana en que ocurrieron.")

    # ======================================================== pronostico
    grupo("Los meses que la telefonia no cubre")

    mensual_completo = ctx["mensual_completo"]
    migracion = ctx["migracion"]
    validacion = md.validar(mensual_completo, migracion)
    estimado = md.estimar(mensual_completo, migracion)
    serie = md.serie_completa(mensual_completo, migracion,
                              ctx["subdestinos"] or None)

    aviso("Enero y febrero de 2026 no tienen cobertura de telefonia movil. "
          "Las cifras de esos dos meses son estimaciones del modelo, se "
          "dibujan en morado y punteado, y llevan su banda de error. No son "
          "mediciones y no deben citarse como tales. Un periodo sin cobertura "
          "no vale cero: la ausencia de medicion no es ausencia del fenomeno.")

    _tarjetas_modelo(validacion["metricas"], estimado)

    if "V9 Pronostico de los meses sin cobertura" in activas:
        with st.container(border=True):
            titulo_grafica("V9", "Serie mensual con los meses estimados",
                           "Como se ve el ano completo una vez imputados enero y febrero",
                           ["Estimacion · morado punteado"])
            mostrar(_v9_pronostico(serie), "v9_pronostico")
            lectura("Los dos meses estimados caen por debajo de diciembre y por "
                    "encima del valle de octubre: el modelo reproduce la caida "
                    "posterior a la temporada alta sin convertirla en un cero. "
                    "La banda morada es el margen de error que el propio modelo "
                    "cometio al predecir meses que no habia visto.")
            if completo:
                nota("El modelo combina dos fuentes. La movilidad aporta el "
                     "nivel de demanda de cada poligono, que es lo que si "
                     "mide. La base migratoria aporta la forma del ano, que la "
                     "movilidad no puede dar porque los diez meses observados "
                     "no incluyen ni enero ni febrero. "
                     "estimado = nivel desestacionalizado x indice del mes.")

    ver10, ver11 = ("V10 Validacion del modelo" in activas,
                    "V11 Estacionalidad prestada" in activas)
    izq, der = par_columnas(ver10, ver11)

    if ver10:
        with izq, st.container(border=True):
            titulo_grafica("V10", "Error del modelo, mes a mes",
                           "Cuanto se equivoco al predecir meses que si conocemos",
                           ["Estimacion"])
            mostrar(_v10_validacion(validacion["agregado"]), "v10_validacion")

            tabla = (pd.DataFrame(validacion["metricas"]).T
                     [["nombre", "MAPE", "RMSE", "MAE", "meses"]]
                     .rename(columns={"nombre": "Modelo", "meses": "Meses evaluados"}))
            tabla["MAPE"] = tabla["MAPE"].map(lambda x: f"{x:.1f} %")
            for col in ("RMSE", "MAE"):
                tabla[col] = tabla[col].map(miles)
            st.dataframe(tabla.set_index("Modelo"), width="stretch")

            lectura("La validacion es dejar-uno-fuera: cada mes se predice con "
                    "un modelo ajustado sin ese mes, de modo que las diez "
                    "predicciones son fuera de muestra. El modelo publicado le "
                    "gana a la media simple en los tres indicadores de error, "
                    "y esa es la unica razon por la que se publica.")
            if completo:
                nota("El factor de reparto directo, que es la lectura literal "
                     "de la guia, queda tercero y solo puede evaluarse en ocho "
                     "meses: la base migratoria termina en junio de 2026 y no "
                     "alcanza julio ni agosto. Lee la serie nacional mes a mes "
                     "y arrastra su ruido; promediar la forma de tres anios lo "
                     "corrige. Abril de 2026 es el mes peor estimado: Semana "
                     "Santa pesa mucho mas en Izabal que en el ingreso "
                     "internacional al pais.")

    if ver11:
        with der, st.container(border=True):
            titulo_grafica("V11", "La estacionalidad que se toma prestada",
                           "Que forma tiene el ano segun la base migratoria nacional")
            mostrar(_v11_estacionalidad(validacion["indice"]), "v11_estacional")
            indice = validacion["indice"]
            ene = indice[(indice["mes"] == 1)]["indice_100"].mean()
            feb = indice[(indice["mes"] == 2)]["indice_100"].mean()
            lectura(f"Enero queda en {ene:.0f} y febrero en {feb:.0f} sobre un "
                    "mes promedio de 100. Esa diferencia es toda la "
                    "informacion que la movilidad no podia aportar, y es "
                    "exactamente lo que el modelo va a buscar a la base "
                    "migratoria.")
            if completo:
                nota("Promedio de los anios completos desde 2023. Se excluye "
                     "2022 hacia atras por el quiebre metodologico que declara "
                     "la nota de la base, y 2026 porque llega hasta junio y "
                     "arrastraria el indice hacia el primer semestre. Los dos "
                     "calendarios se calculan por separado porque el "
                     "excursionista se mueve con los feriados largos y el "
                     "turista con las temporadas de vacaciones.")
