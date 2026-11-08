"""
Modulo 4 — Monitor especializado: conectividad fluvial y embudo de transferencia.

Es el reto analitico del grupo 5. Livingston no tiene acceso por carretera:
se llega por via fluvial desde Rio Dulce o por via maritima desde el mar. Eso
convierte al destino asignado en un embudo con una forma muy concreta: una
puerta de entrada grande por la que pasa casi todo el mundo, y un destino
final al que solo llega una parte.

El indicador central del modulo es la tasa de transferencia:

    tasa(t) = visitantes de Livingston(t) / visitantes de Rio Dulce(t)

Lo que mide y lo que no mide
----------------------------
La base de movilidad no contiene pares de origen y destino entre poligonos.
Registra, para cada mes, cuantas personas distintas estuvieron en cada uno.
La razon entre las dos cifras es por tanto una aproximacion a la continuidad
del viaje, no una medicion de trayectorias. Es valida en la medida en que se
cumplan dos supuestos, que el modulo verifica en vez de dar por buenos:

  1. Que casi nadie llegue a Livingston sin pasar por Rio Dulce. V20 revisa
     la via maritima, que es la unica alternativa.
  2. Que el traslado ocurra dentro del mismo mes. V19 lo revisa sobre la base
     diaria mirando con que rezago se corresponden las dos curvas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos as dt
from componentes import (aplicar_estilo, aviso, grupo, kpi, lectura, miles,
                         mostrar, nota, par_columnas, sin_datos, titulo_grafica)
from config import (AZUL, CELESTE, COLOR_ORIGEN, COLOR_SEGMENTO,
                    COLOR_SUBDESTINO, GRIS, IOS_SEC, LINEA, MORADO, NARANJA,
                    ROSA, SALMON, TINTA, VERDE, VIOLETA)


# --------------------------------------------------------------------------
def _kpis(mensual: pd.DataFrame) -> None:
    emb = dt.embudo(mensual)
    tasa = emb["destino_final"].sum() / emb["puerta"].sum() * 100 if len(emb) else np.nan

    por_origen = dt.embudo(mensual, ["origen"])
    def _tasa(origen: str) -> float:
        parte = por_origen[por_origen["origen"] == origen]
        if parte.empty or parte["puerta"].sum() == 0:
            return float("nan")
        return parte["destino_final"].sum() / parte["puerta"].sum() * 100

    t_ext, t_nac = _tasa("Extranjero"), _tasa("Nacional")
    brecha = t_ext / t_nac if t_nac else np.nan

    liv = mensual[mensual["subdestino"] == dt.DESTINO_FINAL]
    rio = mensual[mensual["subdestino"] == dt.PUERTA]
    est_liv, est_rio = dt.estadia_media(liv), dt.estadia_media(rio)

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        with st.container(border=True):
            kpi("Tasa de transferencia",
                "sin dato" if pd.isna(tasa) else f"{tasa:.1f} %",
                "de Rio Dulce continua a Livingston", "azul")
    with c2:
        with st.container(border=True):
            kpi("Transferencia extranjera",
                "sin dato" if pd.isna(t_ext) else f"{t_ext:.1f} %",
                f"nacional {t_nac:.1f} %" if not pd.isna(t_nac) else "", "naranja")
    with c3:
        with st.container(border=True):
            kpi("Brecha entre mercados",
                "sin dato" if pd.isna(brecha) else f"{brecha:.1f}x",
                "el extranjero completa el viaje mas veces", "rosa")
    with c4:
        with st.container(border=True):
            kpi("Estadia en Livingston",
                "sin dato" if pd.isna(est_liv) else f"{est_liv:.2f} dias",
                f"Rio Dulce {est_rio:.2f} dias" if not pd.isna(est_rio) else "",
                "verde")


# --------------------------------------------------------------------------
def _v16_embudo(mensual: pd.DataFrame) -> go.Figure:
    """El embudo en su forma mas directa: cuantos entran y cuantos llegan."""
    emb = dt.embudo(mensual)
    if emb.empty:
        return None
    puerta = emb["puerta"].mean()
    final = emb["destino_final"].mean()
    tasa = final / puerta * 100 if puerta else np.nan

    fig = go.Figure(go.Funnel(
        y=[f"{dt.PUERTA}<br><span style='font-size:11px'>puerta de entrada</span>",
           f"{dt.DESTINO_FINAL}<br><span style='font-size:11px'>solo por via acuatica</span>"],
        x=[puerta, final],
        textinfo="value+percent initial",
        texttemplate="%{value:,.0f}<br>%{percentInitial:.1%}",
        textfont=dict(size=15, color="white"),
        marker=dict(color=[COLOR_SUBDESTINO[dt.PUERTA],
                           COLOR_SUBDESTINO[dt.DESTINO_FINAL]],
                    line=dict(width=0)),
        connector=dict(line=dict(color=LINEA, width=2)),
        hovertemplate="<b>%{y}</b><br>%{x:,.0f} visitantes en un mes tipico<extra></extra>"))
    aplicar_estilo(fig, alto=330, margin=dict(l=130, r=20, t=30, b=20))
    return fig


def _v17_tasa_mensual(mensual: pd.DataFrame) -> go.Figure:
    """Tasa de transferencia mes a mes, con la media del periodo como referencia."""
    emb = dt.embudo(mensual).dropna(subset=["tasa_pct"])
    if emb.empty:
        return None
    media = emb["destino_final"].sum() / emb["puerta"].sum() * 100

    fig = go.Figure()
    fig.add_bar(x=emb["etiqueta_mes"], y=emb["tasa_pct"],
                marker_color=[ROSA if v > media else AZUL for v in emb["tasa_pct"]],
                customdata=emb[["puerta", "destino_final"]],
                hovertemplate=("%{x}<br>Tasa %{y:.1f} %<br>"
                               "Puerta %{customdata[0]:,.0f}<br>"
                               "Destino final %{customdata[1]:,.0f}<extra></extra>"),
                showlegend=False)
    fig.add_hline(y=media, line_dash="dot", line_color=GRIS,
                  annotation_text=f"Media del periodo: {media:.1f} %",
                  annotation_font=dict(size=11, color=IOS_SEC))
    aplicar_estilo(fig, alto=340,
                   yaxis=dict(title="Tasa de transferencia", ticksuffix=" %"),
                   xaxis=dict(tickangle=-40))
    return fig


def _v18_quien_completa(mensual: pd.DataFrame, corte: str) -> go.Figure:
    """Tasa de transferencia desglosada por procedencia o por tipo de visitante."""
    campo = "origen" if corte == "Procedencia" else "segmento"
    emb = dt.embudo(mensual, [campo]).dropna(subset=["tasa_pct"])
    if emb.empty:
        return None
    colores = COLOR_ORIGEN if campo == "origen" else COLOR_SEGMENTO

    fig = go.Figure()
    for valor in emb[campo].unique():
        parte = emb[emb[campo] == valor].sort_values("fecha")
        fig.add_scatter(x=parte["etiqueta_mes"], y=parte["tasa_pct"], name=valor,
                        mode="lines+markers",
                        line=dict(color=colores.get(valor, GRIS), width=2.5),
                        marker=dict(size=8),
                        customdata=parte[["puerta", "destino_final"]],
                        hovertemplate=(f"<b>{valor}</b><br>%{{x}}<br>"
                                       "Tasa %{y:.1f} %<br>"
                                       "Puerta %{customdata[0]:,.0f}<br>"
                                       "Destino final %{customdata[1]:,.0f}<extra></extra>"))
    aplicar_estilo(fig, alto=340,
                   yaxis=dict(title="Tasa de transferencia", ticksuffix=" %",
                              rangemode="tozero"),
                   xaxis=dict(tickangle=-40))
    return fig


def _v19_rezago(diaria: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """Con que desfase se corresponden las curvas diarias de los dos poligonos."""
    emb = dt.embudo_diario(diaria)
    tabla = dt.rezago_transferencia(emb)
    if tabla.empty:
        return None, tabla

    mejor = tabla.loc[tabla["correlacion"].idxmax()]
    fig = go.Figure()
    fig.add_bar(x=tabla["rezago_dias"], y=tabla["correlacion"],
                marker_color=[VIOLETA if r == mejor["rezago_dias"] else "#B5BDE3"
                              for r in tabla["rezago_dias"]],
                customdata=tabla[["n"]],
                hovertemplate=("Rezago de %{x} dias<br>"
                               "Correlacion %{y:.3f}<br>"
                               "%{customdata[0]:.0f} dias comparados<extra></extra>"),
                showlegend=False)
    aplicar_estilo(fig, alto=300,
                   yaxis=dict(title="Correlacion con la puerta de entrada",
                              range=[0, 1]),
                   xaxis=dict(title="Dias de rezago de Livingston",
                              dtick=1))
    return fig, tabla


def _v20_puerta_maritima(mig_izabal: pd.DataFrame) -> go.Figure:
    """Trafico de los puertos del departamento, por categoria de viajero."""
    tabla = dt.puerta_maritima_anual(mig_izabal)
    if tabla.empty:
        return None
    colores = {"Cruceristas": CELESTE, "Turista": AZUL,
               "Excursionista": SALMON, "Viajero": GRIS}
    fig = go.Figure()
    for tipo in ["Turista", "Excursionista", "Cruceristas", "Viajero"]:
        parte = tabla[tabla["tipo"] == tipo].sort_values("anio")
        if parte.empty:
            continue
        cuenta = "cuenta como visitante" if tipo in ("Turista", "Excursionista") \
            else "NO cuenta como visitante"
        fig.add_bar(x=parte["anio"], y=parte["viajeros"], name=tipo,
                    marker_color=colores.get(tipo, GRIS),
                    hovertemplate=(f"<b>{tipo}</b> ({cuenta})<br>%{{x}}<br>"
                                   "%{y:,.0f} cruces<extra></extra>"))
    fig.update_layout(barmode="stack")
    aplicar_estilo(fig, alto=340,
                   yaxis=dict(title="Cruces por los puertos de Izabal",
                              tickformat="~s"),
                   xaxis=dict(title=None, dtick=2))
    return fig


# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    mensual = ctx["mensual"]
    diaria = ctx["diaria"]
    activas = ctx["graficas_activas"]
    completo = ctx["detalle"] == "Analisis completo"

    if ctx["subdestinos"] and len(ctx["subdestinos"]) == 1:
        aviso("El embudo necesita los dos poligonos. Quita el filtro de lugar "
              "en la barra superior para que este modulo pueda calcularse.")
        return
    if mensual.empty:
        sin_datos("No hay movilidad para la combinacion elegida.")
        return

    grupo("Tarjetas principales")
    _kpis(mensual)

    # ------------------------------------------------------------- V16 / V17
    grupo("La forma del embudo")
    ver16, ver17 = ("V16 Embudo de transferencia" in activas,
                    "V17 Tasa mes a mes" in activas)
    izq, der = par_columnas(ver16, ver17)

    if ver16:
        with izq, st.container(border=True):
            titulo_grafica("V16", "Embudo de transferencia",
                           "De cada cien personas en la puerta de entrada, "
                           "cuantas llegan al destino final")
            figura = _v16_embudo(mensual)
            if figura is None:
                sin_datos("No hay datos suficientes para construir el embudo.")
            else:
                mostrar(figura, "v16_embudo")
                lectura("Alrededor de nueve de cada diez personas que pasan por "
                        "Rio Dulce no llegan a Livingston. El cuello de botella "
                        "del destino no esta en atraer visita, que ya llega en "
                        "volumen, sino en convertir el paso por la puerta en "
                        "una visita al destino final.")
            if completo:
                nota("Las cifras son el promedio mensual de cada poligono "
                     "sobre los meses observados, no un acumulado. La razon "
                     "entre ambas aproxima la continuidad del viaje: la base "
                     "de movilidad no contiene pares de origen y destino entre "
                     "poligonos, de modo que no se estan siguiendo "
                     "trayectorias individuales.")

    if ver17:
        with der, st.container(border=True):
            titulo_grafica("V17", "Tasa de transferencia mes a mes",
                           "En que meses el embudo se abre y en cuales se cierra")
            figura = _v17_tasa_mensual(mensual)
            if figura is None:
                sin_datos("No hay meses con ambos poligonos en el filtro actual.")
            else:
                mostrar(figura, "v17_tasa")
                emb = dt.embudo(mensual).dropna(subset=["tasa_pct"])
                mejor = emb.loc[emb["tasa_pct"].idxmax()]
                peor = emb.loc[emb["tasa_pct"].idxmin()]
                lectura(f"La tasa va de {peor['tasa_pct']:.1f} % en "
                        f"{peor['etiqueta_mes']} a {mejor['tasa_pct']:.1f} % en "
                        f"{mejor['etiqueta_mes']}. El embudo se abre en "
                        "temporada alta: cuando llega mas visita, ademas una "
                        "proporcion mayor completa el viaje. Las dos cosas "
                        "empujan en la misma direccion y concentran la presion "
                        "sobre Livingston justo cuando menos holgura tiene.")
            if completo:
                nota("Las barras por encima de la media del periodo van en "
                     "rosa, que es el color de presion en todo el tablero. "
                     "La media se calcula como cociente de las sumas y no "
                     "como promedio de las tasas mensuales, para que un mes "
                     "pequeno no pese igual que uno grande.")

    # ------------------------------------------------------------- V18 / V19
    grupo("Quien completa el viaje y cuando")
    ver18, ver19 = ("V18 Quien completa el viaje" in activas,
                    "V19 Rezago del traslado" in activas)
    izq, der = par_columnas(ver18, ver19)

    if ver18:
        with izq, st.container(border=True):
            titulo_grafica("V18", "Quien completa el viaje",
                           "Que perfil de visitante continua hasta Livingston")
            corte = st.segmented_control(
                "Desglose", ["Procedencia", "Tipo de visitante"],
                default="Procedencia", key="corte_embudo", width="stretch")
            figura = _v18_quien_completa(mensual, corte or "Procedencia")
            if figura is None:
                sin_datos("No hay desglose disponible para el filtro actual.")
            else:
                mostrar(figura, "v18_perfil")
                por_origen = dt.embudo(mensual, ["origen"])
                ext = por_origen[por_origen["origen"] == "Extranjero"]
                nac = por_origen[por_origen["origen"] == "Nacional"]
                if len(ext) and len(nac) and nac["puerta"].sum():
                    t_ext = ext["destino_final"].sum() / ext["puerta"].sum() * 100
                    t_nac = nac["destino_final"].sum() / nac["puerta"].sum() * 100
                    lectura(
                        f"Este es el hallazgo central del modulo. El visitante "
                        f"extranjero completa el viaje el {t_ext:.0f} % de las "
                        f"veces y el nacional solo el {t_nac:.0f} %: una brecha "
                        f"de {t_ext/t_nac:.1f} veces que se mantiene en los diez "
                        "meses observados. Rio Dulce funciona como destino final "
                        "para el visitante nacional y como escala para el "
                        "extranjero, y eso significa que son dos productos "
                        "distintos vendidos en el mismo territorio.")
            if completo:
                nota("Las dos series tienen su propio denominador: la tasa "
                     "extranjera se calcula sobre los extranjeros de la puerta "
                     "y la nacional sobre los nacionales. No se dividen "
                     "poblaciones distintas entre si, y la brecha es por tanto "
                     "comparable pese a que las dos cifras de origen se "
                     "construyan de forma distinta.")

    if ver19:
        with der, st.container(border=True):
            titulo_grafica("V19", "Rezago del traslado",
                           "Si el pico de Livingston sigue al de Rio Dulce, "
                           "y con cuantos dias de diferencia",
                           ["Base diaria"])
            figura, tabla = _v19_rezago(diaria)
            if figura is None:
                sin_datos("No hay tramos diarios continuos suficientes para "
                          "medir el rezago.")
            else:
                mostrar(figura, "v19_rezago")
                mejor = tabla.loc[tabla["correlacion"].idxmax()]
                lectura(
                    f"La correspondencia mas alta esta en el rezago de "
                    f"{mejor['rezago_dias']:.0f} dias ({mejor['correlacion']:.2f}) "
                    "y cae a medida que el desfase crece. El traslado ocurre "
                    "dentro del mismo dia: la lancha sale y vuelve, y el "
                    "visitante de Livingston es en buena parte un visitante "
                    "de excursion. Eso valida el supuesto de que la "
                    "transferencia cabe dentro del mes y explica por que "
                    "Livingston captura poca pernocta pese a recibir visita.")
            if completo:
                nota("Se comparan solo dias de meses con cobertura completa y "
                     "consecutivos; los tramos sueltos quedan fuera para que "
                     "el desfase no se calcule entre dias que en realidad "
                     "estan separados por meses. Es correlacion de presencia "
                     "diaria, no seguimiento de personas.")

    # ---------------------------------------------------------------------- V20
    if "V20 La puerta maritima" in activas:
        grupo("El limite del modelo")
        with st.container(border=True):
            titulo_grafica("V20", "La otra puerta: la via maritima",
                           "Cuanta visita puede llegar a Livingston sin pasar "
                           "por Rio Dulce",
                           ["Base migratoria 2009–2026"])
            figura = _v20_puerta_maritima(ctx["migracion_izabal"])
            if figura is None:
                sin_datos("No hay registros de las fronteras maritimas de Izabal.")
            else:
                mostrar(figura, "v20_maritima")
                lectura(
                    "El supuesto del embudo es que casi nadie llega a "
                    "Livingston sin pasar por Rio Dulce, y la via maritima es "
                    "la unica alternativa. En su mejor ano esos puertos "
                    "movieron alrededor de cincuenta mil cruces frente a los "
                    "cerca de ciento setenta mil visitantes mensuales del "
                    "destino, de modo que el supuesto se sostiene en orden de "
                    "magnitud. Pero hay un cambio que importa mas que el "
                    "volumen: hasta 2021 ese trafico se registraba como "
                    "crucerista y desde 2023 se registra integramente como "
                    "'Viajero', categoria que por definicion no es visitante. "
                    "Hoy la puerta maritima del destino no se esta midiendo "
                    "como demanda turistica.")
            if completo:
                nota("Fronteras 04 Santo Tomas de Castilla, 05 Puerto Barrios "
                     "y 06 Livingston. La serie se muestra con las cuatro "
                     "categorias de viajero a proposito: filtrar a Turista mas "
                     "Excursionista, que es lo correcto para medir demanda, "
                     "dejaria el grafico vacio desde 2023 y escondria "
                     "justamente el cambio de clasificacion. El hueco de 2022 "
                     "corresponde al quiebre metodologico que declara la nota "
                     "de la base. Esta es la primera recomendacion operativa "
                     "del tablero: sin recuperar la caracterizacion de ese "
                     "trafico, el embudo de Livingston no se puede cerrar.")
