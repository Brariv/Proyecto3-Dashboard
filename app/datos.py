"""
Capa de datos del Observatorio de Rio Dulce y Livingston.

Todo el tablero lee de aqui. El modulo no abre ningun .xlsx: consume las
tablas que `data/etl.py` dejo en `data/procesado/`. Si manana cambia un
archivo de origen, se vuelve a correr el ETL y el tablero no se toca.

Aqui viven ademas las reglas de agregacion del destino, que son la parte del
proyecto donde es mas facil equivocarse:

  * La estadia media es un cociente de sumas sobre el segmento con pernocta,
    nunca el promedio de la columna `permanencia_prom`.
  * Los subdestinos no se suman. `cota_destino` devuelve el piso y el techo
    del total, y el tablero muestra los dos.
  * La base diaria y la base mensual no se mezclan.
  * Un mes sin cobertura no existe como fila; nunca vale cero.
"""

from __future__ import annotations

import runpy
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
PROCESADO = RAIZ / "data" / "procesado"

TABLAS = ["movilidad_mensual", "movilidad_diaria", "ocupacion", "oferta",
          "migracion_mensual", "migracion_izabal"]

DESTINO = "Rio Dulce y Livingston"
DEPARTAMENTO = "Izabal"
SUBDESTINOS = ["Rio Dulce", "Livingston"]

# El embudo del modulo 4: Rio Dulce es la puerta de entrada por carretera y
# Livingston solo se alcanza por via fluvial o maritima.
PUERTA = "Rio Dulce"
DESTINO_FINAL = "Livingston"

SEG_PERNOCTA = "Turista (pernocta)"
SEG_PASO = "Excursionista (mismo dia)"

NOMBRES_MES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def etiqueta_mes(fechas) -> pd.Series:
    """'Sep 2025' en espanol, sin depender del locale del contenedor."""
    f = pd.to_datetime(pd.Series(fechas).reset_index(drop=True))
    return (f.dt.month.map(lambda m: NOMBRES_MES[m - 1]) + " "
            + f.dt.year.astype(str))

# Meses dentro de la ventana de trabajo que la telefonia no cubre y que el
# modulo 2 tiene que estimar.
MESES_SIN_COBERTURA = [(2026, 1), (2026, 2)]

# Unica ventana en que movilidad y ocupacion hotelera coinciden.
VENTANA_COINCIDENTE = ("2025-09-01", "2025-12-01")


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------
def _asegurar_datos() -> None:
    if all((PROCESADO / f"{t}.parquet").exists() for t in TABLAS):
        return
    # Primera ejecucion: construye las tablas limpias desde data/raw.
    runpy.run_path(str(RAIZ / "data" / "etl.py"), run_name="__main__")


@st.cache_data(show_spinner="Cargando datos del observatorio...")
def cargar() -> dict[str, pd.DataFrame]:
    _asegurar_datos()
    datos = {t: pd.read_parquet(PROCESADO / f"{t}.parquet") for t in TABLAS}

    for clave in ("movilidad_mensual", "movilidad_diaria"):
        datos[clave]["fecha"] = pd.to_datetime(datos[clave]["fecha"])
    datos["movilidad_mensual"]["nombre_mes"] = (
        datos["movilidad_mensual"]["mes"].map(lambda m: NOMBRES_MES[m - 1]))

    # Cortes departamentales: el tablero es de Izabal, pero conserva el pais
    # como referencia de contexto en las tablas que lo traen.
    datos["ocupacion_izabal"] = (
        datos["ocupacion"][datos["ocupacion"]["departamento"] == DEPARTAMENTO]
        .reset_index(drop=True))
    datos["oferta_izabal"] = (
        datos["oferta"][datos["oferta"]["departamento"] == DEPARTAMENTO]
        .reset_index(drop=True))
    return datos


# --------------------------------------------------------------------------
# Cobertura: que fuente respalda que periodo
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def cobertura(mensual: pd.DataFrame, diaria: pd.DataFrame,
              ocup: pd.DataFrame) -> pd.DataFrame:
    """Tabla de cobertura por fuente, para el indicador visible del tablero."""
    filas = []
    for nombre, df, col in (("Movilidad mensual", mensual, "fecha"),
                            ("Movilidad diaria", diaria, "fecha"),
                            ("Ocupacion hotelera", ocup, "fecha")):
        if df.empty:
            continue
        meses = sorted(pd.to_datetime(df[col]).dt.to_period("M").unique())
        filas.append({"fuente": nombre, "desde": meses[0].to_timestamp(),
                      "hasta": meses[-1].to_timestamp(), "meses": len(meses)})
    return pd.DataFrame(filas)


def meses_observados(mensual: pd.DataFrame) -> list[pd.Timestamp]:
    return sorted(mensual["fecha"].unique())


# --------------------------------------------------------------------------
# Filtros
# --------------------------------------------------------------------------
def filtrar(df: pd.DataFrame, anios: tuple[int, int] | None = None,
            subdestinos: list[str] | None = None,
            origen: str | None = None,
            segmento: str | None = None) -> pd.DataFrame:
    out = df
    if anios is not None and "anio" in out.columns:
        out = out[(out["anio"] >= anios[0]) & (out["anio"] <= anios[1])]
    if subdestinos and "subdestino" in out.columns:
        out = out[out["subdestino"].isin(subdestinos)]
    if origen and origen != "Ambos" and "origen" in out.columns:
        out = out[out["origen"] == origen]
    if segmento and segmento != "Ambos" and "segmento" in out.columns:
        out = out[out["segmento"] == segmento]
    return out


# --------------------------------------------------------------------------
# Indicadores del modulo 1
# --------------------------------------------------------------------------
def estadia_media(df: pd.DataFrame) -> float:
    """Estadia Media Ponderada = suma de dias persona / suma de visitantes.

    Se calcula exclusivamente sobre el segmento con pernocta. Al excursionista
    se le asigna permanencia 1 por definicion, de modo que incluirlo arrastra
    el indicador hacia 1 y subestima la permanencia real del turista.
    Prohibido promediar la columna `permanencia_prom`.
    """
    pernocta = df[df["segmento"] == SEG_PERNOCTA]
    visitantes = pernocta["visitantes"].sum()
    if visitantes <= 0:
        return float("nan")
    return pernocta["dias_persona"].sum() / visitantes


def visitantes_mes(df: pd.DataFrame, por: list[str] | None = None) -> pd.DataFrame:
    """Visitantes unicos y dias persona por mes (y por lo que se pida)."""
    llaves = ["fecha", *(por or [])]
    out = (df.groupby(llaves, as_index=False)
             .agg(visitantes=("visitantes", "sum"),
                  dias_persona=("dias_persona", "sum")))
    out["etiqueta_mes"] = etiqueta_mes(out["fecha"])
    return out.sort_values(llaves).reset_index(drop=True)


def promedio_mensual(df: pd.DataFrame) -> float:
    """Visitantes promedio por mes del subdestino o conjunto filtrado.

    Se promedia y no se suma: una misma persona presente en dos meses se
    contaria dos veces, de modo que la suma de meses no es un total de
    visitantes del periodo.
    """
    por_mes = df.groupby("fecha")["visitantes"].sum()
    return float(por_mes.mean()) if len(por_mes) else float("nan")


def cota_destino(df: pd.DataFrame) -> tuple[float, float]:
    """Piso y techo del total del destino, por mes promedio.

    Los subdestinos comparten visitantes: quien estuvo en Rio Dulce y en
    Livingston el mismo mes figura en ambos poligonos. Sumarlos duplica, y
    quedarse con uno solo deja fuera a quien no visito el otro. El total real
    vive entre el subdestino mayor (piso) y la suma (techo).
    """
    por_sub = df.groupby(["fecha", "subdestino"])["visitantes"].sum()
    if por_sub.empty:
        return float("nan"), float("nan")
    por_mes = por_sub.groupby("fecha")
    piso = por_mes.max().mean()
    techo = por_mes.sum().mean()
    return float(piso), float(techo)


def segmentacion(df: pd.DataFrame) -> pd.DataFrame:
    """Proporcion de turistas con pernocta frente a visitantes de paso."""
    out = (df.groupby("segmento", as_index=False)["visitantes"].sum()
             .rename(columns={"visitantes": "visitantes"}))
    total = out["visitantes"].sum()
    out["porcentaje"] = out["visitantes"] / total * 100 if total else np.nan
    return out.sort_values("visitantes", ascending=False).reset_index(drop=True)


def mercados(df: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    """Top de mercados emisores extranjeros, con el nacional aparte.

    Los visitantes nacionales incorporan un factor de expansion que los
    extranjeros no tienen. Por eso no se ranquean juntos ni se calcula la
    participacion de extranjeros dividiendo entre el total.
    """
    por_pais = (df.groupby(["pais", "origen"], as_index=False)["visitantes"].sum()
                  .sort_values("visitantes", ascending=False))
    extranjeros = por_pais[por_pais["origen"] == "Extranjero"].head(top).copy()
    base_ext = por_pais[por_pais["origen"] == "Extranjero"]["visitantes"].sum()
    extranjeros["pct_del_universo"] = (extranjeros["visitantes"] / base_ext * 100
                                       if base_ext else np.nan)
    return extranjeros.reset_index(drop=True)


def peso_nacional(df: pd.DataFrame) -> pd.DataFrame:
    """Nacionales y extranjeros reportados por separado, nunca como una razon."""
    return (df.groupby("origen", as_index=False)
              .agg(visitantes=("visitantes", "sum"),
                   dias_persona=("dias_persona", "sum")))


# --------------------------------------------------------------------------
# Indicadores del modulo 2
# --------------------------------------------------------------------------
def serie_diaria(df: pd.DataFrame, por: list[str] | None = None) -> pd.DataFrame:
    llaves = ["fecha", *(por or [])]
    out = (df.groupby(llaves, as_index=False)
             .agg(presencia=("presencia", "sum")))
    meta = (df.groupby(llaves, as_index=False)
              .agg(evento=("evento", "first"), dia_semana=("dia_semana", "first"),
                   mes_completo=("mes_completo", "first")))
    return out.merge(meta, on=llaves, how="left").sort_values(llaves)


def lift_eventos(diaria: pd.DataFrame, subdestino: str | None = None) -> pd.DataFrame:
    """Impacto porcentual de cada festividad frente al dia regular promedio.

    Lift(e) = presencia media de los dias del evento / presencia media de los
    dias regulares - 1. Se calcula sobre el mismo subdestino y usando solo los
    dias regulares de meses con cobertura completa, para que la base de
    comparacion no quede contaminada por ventanas levantadas unicamente
    alrededor de una festividad.
    """
    df = diaria if subdestino is None else diaria[diaria["subdestino"] == subdestino]
    por_dia = (df.groupby(["fecha", "evento", "mes_completo"], as_index=False)
                 ["presencia"].sum())

    base = por_dia[(por_dia["evento"] == "Regular") & por_dia["mes_completo"]]
    referencia = base["presencia"].mean()
    if not np.isfinite(referencia) or referencia <= 0:
        return pd.DataFrame(columns=["evento", "dias", "presencia_media", "lift_pct"])

    out = (por_dia[por_dia["evento"] != "Regular"]
           .groupby("evento", as_index=False)
           .agg(dias=("fecha", "nunique"), presencia_media=("presencia", "mean")))
    out["lift_pct"] = (out["presencia_media"] / referencia - 1) * 100
    out["referencia"] = referencia
    return out.sort_values("lift_pct", ascending=False).reset_index(drop=True)


def patron_semanal(diaria: pd.DataFrame) -> pd.DataFrame:
    """Presencia media por dia de la semana, solo sobre dias regulares.

    Las festividades se excluyen: caen en dias fijos del calendario y, de
    incluirse, inflarian justamente el dia de la semana en que ocurren.
    """
    orden = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    df = diaria[(diaria["evento"] == "Regular") & diaria["mes_completo"]]
    por_dia = (df.groupby(["fecha", "subdestino", "dia_semana"], as_index=False)
                 ["presencia"].sum())
    out = (por_dia.groupby(["subdestino", "dia_semana"], as_index=False)
                  .agg(presencia_media=("presencia", "mean"),
                       dias=("fecha", "nunique")))
    normaliza = {"Miércoles": "Miercoles", "Sábado": "Sabado"}
    out["dia_semana"] = out["dia_semana"].replace(normaliza)
    out["orden"] = out["dia_semana"].map({d: i for i, d in enumerate(orden)})
    media = out.groupby("subdestino")["presencia_media"].transform("mean")
    out["indice"] = out["presencia_media"] / media * 100
    return out.dropna(subset=["orden"]).sort_values(["subdestino", "orden"])


# --------------------------------------------------------------------------
# Indicadores del modulo 3
# --------------------------------------------------------------------------
def oferta_anual(oferta_dep: pd.DataFrame) -> pd.DataFrame:
    """Inventario fisico por corte anual. No es una serie: son cinco fotos."""
    return (oferta_dep.groupby(["anio", "corte", "tipo_alojamiento"], as_index=False)
                      .agg(establecimientos=("establecimientos", "sum"),
                           habitaciones=("habitaciones", "sum"),
                           plazas_cama=("plazas_cama", "sum"))
                      .sort_values(["anio", "tipo_alojamiento"]))


def ventana_coincidente(mensual: pd.DataFrame, ocup: pd.DataFrame) -> pd.DataFrame:
    """Cruce afluencia x ocupacion, acotado a los cuatro meses en que ambas existen.

    Movilidad llega hasta agosto de 2026 y el indice de ocupacion termina en
    diciembre de 2025: la interseccion es septiembre-diciembre de 2025 y
    cualquier lectura conjunta fuera de ahi compara un dato contra un vacio.
    """
    desde, hasta = (pd.Timestamp(x) for x in VENTANA_COINCIDENTE)
    mov = mensual[(mensual["fecha"] >= desde) & (mensual["fecha"] <= hasta)]
    mov = (mov.groupby(["fecha", "subdestino"], as_index=False)["visitantes"].sum())
    oc = ocup[(ocup["fecha"] >= desde) & (ocup["fecha"] <= hasta)][
        ["fecha", "ocupacion_pct", "ocupacion_pais_pct"]]
    out = mov.merge(oc, on="fecha", how="inner")
    out["etiqueta_mes"] = etiqueta_mes(out["fecha"])
    return out.sort_values(["fecha", "subdestino"]).reset_index(drop=True)


def desagregacion(mensual: pd.DataFrame) -> pd.DataFrame:
    """Comparativa relativa entre subdestinos, sin construir un total sumando.

    El peso de cada poligono se expresa contra el subdestino mayor del mes y
    no contra una suma, porque la suma duplica a quien estuvo en los dos.
    """
    por_sub = (mensual.groupby(["fecha", "subdestino"], as_index=False)
                      .agg(visitantes=("visitantes", "sum"),
                           dias_persona=("dias_persona", "sum")))
    mayor = por_sub.groupby("fecha")["visitantes"].transform("max")
    por_sub["indice_vs_mayor"] = por_sub["visitantes"] / mayor * 100
    por_sub["etiqueta_mes"] = etiqueta_mes(por_sub["fecha"])
    return por_sub.sort_values(["fecha", "subdestino"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# Indicadores del modulo 4: embudo de transferencia fluvial
# --------------------------------------------------------------------------
def embudo(mensual: pd.DataFrame, por: list[str] | None = None) -> pd.DataFrame:
    """Tasa de transferencia Rio Dulce -> Livingston.

    Livingston no tiene acceso por carretera: se llega por via fluvial desde
    Rio Dulce o por via maritima. La razon entre los visitantes de un poligono
    y los del otro aproxima que proporcion de quienes llegan a la puerta de
    entrada continua hasta el destino final.

        tasa_transferencia(t) = visitantes_Livingston(t) / visitantes_RioDulce(t)

    Es una aproximacion y no una medicion de trayectorias: la base de
    movilidad no contiene pares origen-destino entre poligonos.
    """
    llaves = ["fecha", *(por or [])]
    piv = (mensual.pivot_table(index=llaves, columns="subdestino",
                               values="visitantes", aggfunc="sum")
                  .reset_index())
    for col in (PUERTA, DESTINO_FINAL):
        if col not in piv.columns:
            piv[col] = np.nan
    piv = piv.rename(columns={PUERTA: "puerta", DESTINO_FINAL: "destino_final"})
    piv["tasa_transferencia"] = piv["destino_final"] / piv["puerta"].replace(0, np.nan)
    piv["tasa_pct"] = piv["tasa_transferencia"] * 100
    piv["etiqueta_mes"] = etiqueta_mes(piv["fecha"])
    return piv.sort_values(llaves).reset_index(drop=True)


def embudo_diario(diaria: pd.DataFrame) -> pd.DataFrame:
    """Misma razon sobre la base diaria, para leer el rezago del traslado."""
    piv = (diaria.pivot_table(index=["fecha", "evento", "dia_semana", "mes_completo"],
                              columns="subdestino", values="presencia",
                              aggfunc="sum").reset_index())
    for col in (PUERTA, DESTINO_FINAL):
        if col not in piv.columns:
            piv[col] = np.nan
    piv = piv.rename(columns={PUERTA: "puerta", DESTINO_FINAL: "destino_final"})
    piv["tasa_pct"] = piv["destino_final"] / piv["puerta"].replace(0, np.nan) * 100
    return piv.sort_values("fecha").reset_index(drop=True)


def rezago_transferencia(diario: pd.DataFrame, max_rezago: int = 4) -> pd.DataFrame:
    """Correlacion entre la presencia en la puerta y la del destino final.

    Si el traslado fluvial toma un dia, el pico de Livingston deberia seguir
    al de Rio Dulce con uno o dos dias de desfase. Se evalua solo sobre tramos
    de dias consecutivos de meses completos.
    """
    df = diario[diario["mes_completo"]].dropna(subset=["puerta", "destino_final"])
    df = df.set_index("fecha").asfreq("D")
    filas = []
    for k in range(0, max_rezago + 1):
        pareja = pd.DataFrame({"puerta": df["puerta"],
                               "destino_final": df["destino_final"].shift(-k)}).dropna()
        if len(pareja) > 10:
            filas.append({"rezago_dias": k,
                          "correlacion": pareja["puerta"].corr(pareja["destino_final"]),
                          "n": len(pareja)})
    return pd.DataFrame(filas)


def puerta_maritima(mig_izabal: pd.DataFrame, por_tipo: bool = False) -> pd.DataFrame:
    """Cruces internacionales por los puertos del departamento.

    Son el limite del modelo de embudo: quien entra por el puerto de
    Livingston llega al destino final sin pasar por Rio Dulce.

    La tabla conserva la categoria de viajero porque el hecho relevante es un
    cambio de clasificacion, no un cambio de trafico: hasta 2021 el movimiento
    de estos puertos se registraba como crucerista y desde 2023 se registra
    integramente como 'Viajero', que por definicion no cuenta como visitante.
    """
    llaves = ["anio", "fecha", "puerto"] + (["tipo"] if por_tipo else [])
    out = mig_izabal.groupby(llaves, as_index=False)["viajeros"].sum()
    out["etiqueta_mes"] = etiqueta_mes(out["fecha"])
    return out.sort_values(["fecha", "puerto"]).reset_index(drop=True)


def puerta_maritima_anual(mig_izabal: pd.DataFrame) -> pd.DataFrame:
    """Trafico anual de los puertos, separado por categoria de viajero."""
    out = (mig_izabal.groupby(["anio", "tipo"], as_index=False)["viajeros"].sum())
    out["cuenta_como_visitante"] = out["tipo"].isin(["Turista", "Excursionista"])
    return out.sort_values(["anio", "tipo"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def variacion(actual: float, previo: float) -> float | None:
    if previo in (0, None) or pd.isna(previo) or pd.isna(actual) or previo == 0:
        return None
    return (actual / previo - 1) * 100
