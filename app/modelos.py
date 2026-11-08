"""
Imputacion de los meses sin cobertura de telefonia (enero y febrero de 2026).

EL PROBLEMA
-----------
La base de movilidad cubre septiembre-diciembre de 2025 y marzo-agosto de
2026. Dentro de la ventana de trabajo faltan enero y febrero de 2026. No se
pueden dejar en cero: la ausencia de medicion no es ausencia del fenomeno.
Tampoco se pueden interpolar entre diciembre y marzo, porque eso supondria
que no hay estacionalidad justo en el tramo que mas la tiene: el pico de fin
de ano seguido del valle de enero y febrero.

Y la estacionalidad de esos dos meses no se puede aprender dentro de la
propia base de movilidad. Los diez meses observados son diez meses de
calendario distintos, y los dos que faltan son exactamente los dos que nunca
aparecen. La forma estacional tiene que venir de otra fuente.

LA FUENTE PRESTADA
------------------
La base de flujo migratorio cubre 2009 a junio de 2026 sin huecos. Aporta la
forma estacional del ingreso al pais, no el reparto por destino: la
composicion por mercado emisor cambia mucho entre destinos y usar la serie
nacional tal cual produciria el mismo patron en los seis tableros del curso.

De esa base se extrae un indice estacional por mes, promediado sobre los
anios completos de 2023 en adelante (la nota metodologica advierte un quiebre
entre 2022 y 2023, de modo que los niveles anteriores no son comparables). El
indice se calcula por separado para turistas y para excursionistas, porque
los dos calendarios no coinciden: el excursionista se mueve con los feriados
largos y el turista con las temporadas de vacaciones.

EL MODELO
---------
Para cada combinacion de subdestino s, origen o y segmento g:

    indice(g, mes)  =  promedio_anios [ ingresos(g, anio, mes) / media_anual(g, anio) ]

    nivel(s, o, g)  =  media_m [ visitantes(s, o, g, m) / indice(g, mes(m)) ]

    estimado(s, o, g, t)  =  nivel(s, o, g) * indice(g, mes(t))

El nivel es la demanda desestacionalizada del destino, que la movilidad si
mide. El indice es la forma del ano, que la movilidad no puede dar. Cada
fuente aporta lo que efectivamente observa.

POR QUE ESTE Y NO OTRO
----------------------
Se evaluaron tres modelos con el mismo protocolo de validacion:

  Ingenuo   la media de los meses observados, que es lo que hace un tablero
            que ignora la estacionalidad.
  Reparto   el factor de reparto directo, visitantes = r * ingresos del mes.
            Lee la serie migratoria mes a mes en lugar de su forma promedio,
            de modo que arrastra el ruido de cada mes concreto. Ademas solo
            puede validarse en ocho de los diez meses, porque la base
            migratoria termina en junio de 2026.
  Estacional  el descrito arriba.

Las metricas de las tres estan en el tablero. El estacional gana en los tres
indicadores de error y es el que alimenta la cifra publicada. Si manana el
ingenuo le ganara, habria que publicar el ingenuo.

LA VALIDACION
-------------
Una estimacion sin medida de error no es un resultado. Como solo hay diez
meses observados, se valida con dejar-uno-fuera: para cada mes observado se
vuelve a ajustar el modelo completo con los otros nueve y se predice ese mes.
Las diez predicciones son fuera de muestra. Se reportan MAPE, RMSE y MAE al
nivel en que el tablero publica la cifra: visitantes del mes por subdestino.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import datos as dt

ETIQUETA_ESTIMACION = "Estimacion"
ANIO_BASE_INDICE = 2023   # desde el quiebre metodologico de la base migratoria

LLAVES = ["subdestino", "origen", "segmento"]

NOMBRES = {"estacional": "Indice estacional por segmento",
           "reparto": "Factor de reparto directo",
           "ingenuo": "Media de los meses observados"}


# --------------------------------------------------------------------------
# Piezas del modelo
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def indice_estacional(migracion: pd.DataFrame) -> pd.DataFrame:
    """Indice estacional del ingreso al pais, por mes y por segmento.

    100 = mes promedio del ano. Se promedia sobre anios completos para que
    2026, que llega a junio, no arrastre el calculo hacia el primer semestre.
    """
    df = migracion[migracion["anio"] >= ANIO_BASE_INDICE].copy()
    completos = df.groupby("anio")["fecha"].nunique()
    df = df[df["anio"].isin(completos[completos == 12].index)]

    filas = []
    columnas = {dt.SEG_PERNOCTA: "turistas_pais",
                dt.SEG_PASO: "excursionistas_pais"}
    for segmento, col in columnas.items():
        tmp = df[["anio", "mes", col]].dropna().copy()
        tmp["indice"] = tmp[col] / tmp.groupby("anio")[col].transform("mean")
        agrupado = (tmp.groupby("mes", as_index=False)
                       .agg(indice=("indice", "mean"), anios=("anio", "nunique")))
        agrupado["segmento"] = segmento
        filas.append(agrupado)

    out = pd.concat(filas, ignore_index=True)
    out["indice_100"] = out["indice"] * 100
    out["nombre_mes"] = out["mes"].map(lambda m: dt.NOMBRES_MES[m - 1])
    return out.sort_values(["segmento", "mes"]).reset_index(drop=True)


def _observado(mensual: pd.DataFrame) -> pd.DataFrame:
    return (mensual.groupby(["fecha", *LLAVES], as_index=False)["visitantes"].sum())


def _con_indice(df: pd.DataFrame, indice: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["mes"] = pd.to_datetime(out["fecha"]).dt.month
    return out.merge(indice[["mes", "segmento", "indice"]],
                     on=["mes", "segmento"], how="left")


def _ajustar_estacional(entreno: pd.DataFrame, indice: pd.DataFrame) -> pd.Series:
    """Nivel desestacionalizado por subdestino, origen y segmento."""
    tmp = _con_indice(entreno, indice).dropna(subset=["indice"])
    tmp = tmp[tmp["indice"] > 0]
    tmp["nivel"] = tmp["visitantes"] / tmp["indice"]
    return tmp.groupby(LLAVES)["nivel"].mean()


def _predecir_estacional(objetivo: pd.DataFrame, nivel: pd.Series,
                         indice: pd.DataFrame) -> pd.Series:
    tmp = _con_indice(objetivo, indice)
    base = pd.Series([nivel.get(k, np.nan) for k in map(tuple, tmp[LLAVES].values)],
                     index=tmp.index)
    return base * tmp["indice"]


# --------------------------------------------------------------------------
# Validacion dejar-uno-fuera
# --------------------------------------------------------------------------
def _metricas(real: np.ndarray, estimado: np.ndarray) -> dict[str, float]:
    """MAPE, RMSE y MAE de un conjunto de predicciones.

    El MAPE deja fuera las observaciones en cero, donde el error relativo no
    esta definido. El numero de meses evaluados lo anade quien llama, que es
    quien sabe cuantos meses pudo cubrir cada modelo.
    """
    real, estimado = np.asarray(real, float), np.asarray(estimado, float)
    error = estimado - real
    positivo = real > 0
    return {
        "MAPE": float(np.mean(np.abs(error[positivo] / real[positivo])) * 100)
        if positivo.any() else float("nan"),
        "RMSE": float(np.sqrt(np.mean(error ** 2))),
        "MAE": float(np.mean(np.abs(error))),
    }


@st.cache_data(show_spinner=False)
def validar(mensual: pd.DataFrame, migracion: pd.DataFrame) -> dict:
    """Dejar-uno-fuera sobre los meses observados, para los tres modelos."""
    obs = _observado(mensual)
    indice = indice_estacional(migracion)
    ingresos = migracion.set_index("fecha")["ingresos_pais"].astype(float)
    meses = sorted(obs["fecha"].unique())

    partes = []
    for mes in meses:
        entreno = obs[obs["fecha"] != mes]
        prueba = obs[obs["fecha"] == mes].copy()
        llaves_prueba = list(map(tuple, prueba[LLAVES].values))

        # Modelo publicado
        nivel = _ajustar_estacional(entreno, indice)
        prueba["estacional"] = _predecir_estacional(prueba, nivel, indice).to_numpy()

        # Contendiente 1: media de los meses observados
        media = entreno.groupby(LLAVES)["visitantes"].mean()
        prueba["ingenuo"] = [media.get(k, np.nan) for k in llaves_prueba]

        # Contendiente 2: factor de reparto directo contra el mes concreto
        tmp = entreno.copy()
        tmp["ingresos"] = tmp["fecha"].map(ingresos)
        tmp = tmp.dropna(subset=["ingresos"])
        reparto = (tmp.groupby(LLAVES)
                      .apply(lambda g: g["visitantes"].sum() / g["ingresos"].sum(),
                             include_groups=False))
        prueba["reparto"] = [reparto.get(k, np.nan) for k in llaves_prueba]
        prueba["reparto"] *= ingresos.get(mes, np.nan)

        partes.append(prueba)

    detalle = pd.concat(partes, ignore_index=True)

    # Las metricas se calculan al nivel en que se publica la cifra.
    agregado = (detalle.groupby(["fecha", "subdestino"], as_index=False)
                       .agg(visitantes=("visitantes", "sum"),
                            # min_count=1: si ningun componente del mes tiene
                            # prediccion, el total queda vacio y no cero. El
                            # reparto directo no alcanza julio y agosto de
                            # 2026 porque la base migratoria termina en junio.
                            estacional=("estacional", lambda x: x.sum(min_count=1)),
                            ingenuo=("ingenuo", lambda x: x.sum(min_count=1)),
                            reparto=("reparto", lambda x: x.sum(min_count=1))))
    agregado["etiqueta_mes"] = dt.etiqueta_mes(agregado["fecha"])
    agregado["error_pct"] = ((agregado["estacional"] - agregado["visitantes"])
                             / agregado["visitantes"].replace(0, np.nan) * 100)

    metricas = {}
    for modelo in ("estacional", "ingenuo", "reparto"):
        valido = agregado.dropna(subset=[modelo])
        # El reparto directo no puede evaluarse donde la base migratoria no
        # llega: esos meses quedan fuera de su promedio y se declara cuantos.
        m = _metricas(valido["visitantes"].to_numpy(), valido[modelo].to_numpy())
        m["meses"] = int(valido["fecha"].nunique())
        m["nombre"] = NOMBRES[modelo]
        metricas[modelo] = m

    return {"detalle": detalle, "agregado": agregado, "metricas": metricas,
            "n_meses": len(meses), "indice": indice}


# --------------------------------------------------------------------------
# Estimacion de los meses sin cobertura
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def estimar(mensual: pd.DataFrame, migracion: pd.DataFrame) -> pd.DataFrame:
    """Estima enero y febrero de 2026 por subdestino, origen y segmento.

    La banda se construye con el MAPE fuera de muestra del propio modelo: es
    el error que cometio al predecir meses que no habia visto, no un supuesto
    nuevo anadido sobre la estimacion.
    """
    obs = _observado(mensual)
    indice = indice_estacional(migracion)
    nivel = _ajustar_estacional(obs, indice)

    objetivo = [pd.Timestamp(year=a, month=m, day=1)
                for a, m in dt.MESES_SIN_COBERTURA]
    combinaciones = obs[LLAVES].drop_duplicates()
    marco = (combinaciones.assign(_k=1)
             .merge(pd.DataFrame({"fecha": objetivo, "_k": 1}), on="_k")
             .drop(columns="_k"))

    marco["visitantes"] = _predecir_estacional(marco, nivel, indice).to_numpy()
    mape = validar(mensual, migracion)["metricas"]["estacional"]["MAPE"] / 100
    marco["banda_baja"] = marco["visitantes"] * (1 - mape)
    marco["banda_alta"] = marco["visitantes"] * (1 + mape)
    marco["etiqueta_mes"] = dt.etiqueta_mes(marco["fecha"])
    marco["tipo"] = ETIQUETA_ESTIMACION
    return marco.dropna(subset=["visitantes"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def serie_completa(mensual: pd.DataFrame, migracion: pd.DataFrame,
                   subdestinos: list[str] | None = None) -> pd.DataFrame:
    """Serie mensual observada mas los dos meses estimados, marcados como tales.

    La columna `tipo` es la que el tablero usa para dibujar la linea punteada
    en morado. Ninguna cifra estimada se presenta como observada, y entre el
    ultimo mes observado y el estimado no se traza continuidad implicita.
    """
    obs = (mensual.groupby(["fecha", "subdestino"], as_index=False)["visitantes"].sum()
                  .assign(tipo="Observado", banda_baja=np.nan, banda_alta=np.nan))
    est = (estimar(mensual, migracion)
           .groupby(["fecha", "subdestino"], as_index=False)
           .agg(visitantes=("visitantes", "sum"),
                banda_baja=("banda_baja", "sum"),
                banda_alta=("banda_alta", "sum"))
           .assign(tipo=ETIQUETA_ESTIMACION))

    out = pd.concat([obs, est], ignore_index=True)
    if subdestinos:
        out = out[out["subdestino"].isin(subdestinos)]
    out["etiqueta_mes"] = dt.etiqueta_mes(out["fecha"])
    return out.sort_values(["subdestino", "fecha"]).reset_index(drop=True)
