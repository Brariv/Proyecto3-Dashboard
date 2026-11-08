"""
ETL del Observatorio de Rio Dulce y Livingston (Grupo 5 - Izabal).

Lee los archivos originales de INGUAT en `data/raw/` y escribe tablas limpias
en `data/procesado/` en formato parquet. El tablero nunca abre un .xlsx: lee
solo lo que este script produce, de modo que la transformacion queda en un
unico lugar auditable y la app arranca en menos de un segundo.

Ejecutar:
    python data/etl.py

Reglas que este script aplica y que no deben deshacerse:

1. Los subdestinos NO se suman. Rio Dulce y Livingston comparten visitantes:
   quien pasa el mes en ambos poligonos aparece contado en los dos. Las tablas
   se entregan desagregadas por subdestino y el tablero declara la cota.
2. La base diaria NO se suma para obtener el mes. Mide presencia por dia; la
   base mensual mide visitantes unicos. Son dos medidas distintas y viajan en
   dos archivos distintos.
3. `permanencia_prom` nunca se promedia. Se conservan `visitantes` y
   `dias_persona` para que la estadia se calcule como cociente de sumas.
4. Los visitantes nacionales llevan factor de expansion y los extranjeros no.
   Por eso se marca `origen` y las dos poblaciones se reportan por separado.
5. La ausencia de cobertura se escribe como fila ausente, nunca como cero.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw"
SALIDA = RAIZ / "data" / "procesado"

HOJA = "Izabal"           # hoja de las bases de movilidad que toca al grupo 5
DEPARTAMENTO = "Izabal"   # corte departamental de ocupacion y oferta

# Fronteras maritimas del departamento en la base de migracion. Son la unica
# via por la que un visitante internacional entra al destino sin pasar por el
# embudo terrestre de Rio Dulce.
FRONTERAS_IZABAL = ["04 Santo Tomás de Castilla", "05 Puerto Barrios",
                    "06 Livingston"]

MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _etiqueta_mes(fechas: pd.Series) -> pd.Series:
    """'Sep 2025' en espanol, sin depender del locale de la maquina."""
    f = pd.to_datetime(fechas)
    return (f.dt.month.map(lambda m: MESES_CORTOS[m - 1]).astype(str) + " "
            + f.dt.year.astype(str))


def _titulo(serie: pd.Series) -> pd.Series:
    """Normaliza nombres que llegan en MAYUSCULAS en una base y en Titulo en otra."""
    return (serie.astype("string").str.strip().str.title()
            .str.replace("Rio Dulce", "Rio Dulce", regex=False))


# --------------------------------------------------------------------------
# 1. Movilidad mensual: visitantes unicos por subdestino, mes y pais
# --------------------------------------------------------------------------
def movilidad_mensual() -> pd.DataFrame:
    df = pd.read_excel(CRUDO / "BD_moviidad_mensual.xlsx", sheet_name=HOJA)
    df = df.rename(columns={"destino": "subdestino"})

    df["subdestino"] = _titulo(df["subdestino"])
    df["pais"] = df["pais"].astype("string").str.strip().str.title()
    df = df[df["pais"].notna() & (df["pais"] != "Nan")]

    # El segmento define el tipo de visitante: con pernocta o de paso.
    df["segmento"] = np.where(df["es_consecutivo"].str.contains("mayor"),
                              "Turista (pernocta)", "Excursionista (mismo dia)")
    # Nacionales y extranjeros no comparten universo: los primeros llevan
    # factor de expansion. Se marcan para poder reportarlos por separado.
    df["origen"] = np.where(df["pais"] == "Guatemala", "Nacional", "Extranjero")

    df["fecha"] = pd.to_datetime(dict(year=df["anio"], month=df["mes"], day=1))
    df["etiqueta_mes"] = _etiqueta_mes(df["fecha"])

    cols = ["subdestino", "anio", "mes", "fecha", "etiqueta_mes", "pais",
            "origen", "segmento", "visitantes", "dias_persona"]
    return df[cols].sort_values(["fecha", "subdestino", "pais"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# 2. Movilidad diaria: presencia por dia, con marca de evento
# --------------------------------------------------------------------------
def movilidad_diaria() -> pd.DataFrame:
    df = pd.read_excel(CRUDO / "BD_moviidad_diario.xlsx", sheet_name=HOJA)
    df = df.rename(columns={"destino": "subdestino", "idfecha": "fecha",
                            "cantidad_visitantes": "presencia",
                            "Week": "semana_iso"})

    df["subdestino"] = _titulo(df["subdestino"])
    df["pais"] = df["pais"].astype("string").str.strip().str.title()
    df = df[df["pais"].notna() & (df["pais"] != "Nan")]
    df["origen"] = np.where(df["pais"] == "Guatemala", "Nacional", "Extranjero")

    df["fecha"] = pd.to_datetime(df["fecha"])
    df["evento"] = df["evento"].astype("string").str.strip()
    df["dia_semana"] = df["dia_semana"].astype("string").str.strip().str.title()
    df["fin_de_semana"] = df["dia_semana"].isin(["Sabado", "Sábado", "Domingo"])

    # La cobertura diaria tiene dos tramos continuos y varias ventanas sueltas
    # levantadas solo alrededor de un evento. Mezclarlas sesga cualquier
    # promedio, asi que cada dia queda marcado con el tipo de tramo al que
    # pertenece y el tablero promedia unicamente sobre los meses completos.
    dias_por_mes = (df.groupby(["anio", "mes"])["fecha"].nunique()
                      .rename("dias_cubiertos").reset_index())
    df = df.merge(dias_por_mes, on=["anio", "mes"], how="left")
    df["mes_completo"] = df["dias_cubiertos"] >= 28

    cols = ["subdestino", "fecha", "anio", "mes", "semana_iso", "dia_semana",
            "fin_de_semana", "pais", "origen", "evento", "presencia",
            "dias_cubiertos", "mes_completo"]
    return df[cols].sort_values(["fecha", "subdestino", "pais"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# 3. Ocupacion hotelera mensual por departamento (2023-2025)
# --------------------------------------------------------------------------
def ocupacion() -> pd.DataFrame:
    df = pd.read_csv(CRUDO / "indice_ocupacion_mensual_2023_2025_1.csv")
    df["departamento"] = df["departamento"].astype("string").str.strip()
    df["fecha"] = pd.to_datetime(dict(year=df["anio"], month=df["mes"], day=1))
    df["etiqueta_mes"] = _etiqueta_mes(df["fecha"])
    df["ocupacion_pct"] = df["indice_ocupacion"] * 100
    # Referencia nacional: promedio simple de los 22 departamentos del mes.
    nacional = (df.groupby("fecha")["ocupacion_pct"].mean()
                  .rename("ocupacion_pais_pct").reset_index())
    df = df.merge(nacional, on="fecha", how="left")
    return df.sort_values(["departamento", "fecha"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# 4. Oferta de alojamiento: cortes anuales, no serie mensual
# --------------------------------------------------------------------------
def oferta() -> pd.DataFrame:
    df = pd.read_csv(CRUDO / "oferta_hotelera_2022_2026.csv")
    df["departamento"] = df["departamento"].astype("string").str.strip()
    df["tipo_alojamiento"] = df["tipo_alojamiento"].astype("string").str.strip()
    # La columna se llama 'trimestre' pero son cortes anuales (uno por anio).
    # Se conserva para poder rotular de que corte viene cada observacion.
    df["corte"] = df["anio"].astype(str) + " T" + df["trimestre"].astype(str)
    return df.sort_values(["departamento", "anio", "tipo_alojamiento"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# 5. Flujo migratorio nacional: perfil estacional que alimenta el pronostico
# --------------------------------------------------------------------------
def migracion_cruda() -> pd.DataFrame:
    """Base migratoria completa, con las cuatro categorias de viajero."""
    df = pd.read_excel(CRUDO / "Base_Migracion_2009-2026jun.xlsx", sheet_name="Datos")
    df = df.rename(columns={"Año": "anio", "Mes cod": "mes", "Vía": "via",
                            "Frontera": "frontera", "País": "pais",
                            "Agrupación Residencia": "agrupacion",
                            "Tipo de Viajero": "tipo", "Viajero": "viajeros"})
    for c in ("via", "frontera", "pais", "agrupacion", "tipo"):
        df[c] = df[c].astype("string").str.strip()
    df["fecha"] = pd.to_datetime(dict(year=df["anio"], month=df["mes"], day=1))
    cols = ["anio", "mes", "fecha", "via", "frontera", "pais", "agrupacion",
            "tipo", "viajeros"]
    return df[cols].reset_index(drop=True)


def migracion(cruda: pd.DataFrame) -> pd.DataFrame:
    """Solo visitantes.

    'Viajero' cruza la frontera sin calificar como visitante (trabajo
    fronterizo, transito, tripulacion) y 'Cruceristas' dejo de reportarse en
    2023. Para medir demanda turistica la nota metodologica de la base indica
    usar Turista + Excursionista.
    """
    return cruda[cruda["tipo"].isin(["Turista", "Excursionista"])].reset_index(drop=True)


def migracion_mensual(mig: pd.DataFrame) -> pd.DataFrame:
    """Serie pais-mes de visitantes internacionales (Turista + Excursionista)."""
    out = (mig.groupby(["anio", "mes", "fecha"], as_index=False)["viajeros"].sum()
              .rename(columns={"viajeros": "ingresos_pais"}))
    por_tipo = (mig.pivot_table(index="fecha", columns="tipo", values="viajeros",
                                aggfunc="sum").reset_index()
                   .rename(columns={"Turista": "turistas_pais",
                                    "Excursionista": "excursionistas_pais"}))
    out = out.merge(por_tipo, on="fecha", how="left")
    out["etiqueta_mes"] = _etiqueta_mes(out["fecha"])
    return out.sort_values("fecha").reset_index(drop=True)


def migracion_izabal(cruda: pd.DataFrame) -> pd.DataFrame:
    """Cruces internacionales por las fronteras maritimas del departamento.

    Es la puerta que NO pasa por Rio Dulce y por eso acota el embudo fluvial
    del modulo 4. Aqui se conservan las cuatro categorias de viajero a
    proposito: el hecho relevante para el destino es que estos puertos
    cambiaron de clasificacion. Hasta 2021 su trafico se registraba como
    crucerista y desde 2023 se registra integramente como 'Viajero', que por
    definicion no es visitante. Filtrar a Turista + Excursionista, que es lo
    correcto para medir demanda, dejaria la tabla vacia y escondria
    justamente eso.
    """
    out = cruda[cruda["frontera"].isin(FRONTERAS_IZABAL)].copy()
    out["puerto"] = (out["frontera"].str.replace(r"^\d+\s+", "", regex=True))
    return (out.groupby(["anio", "mes", "fecha", "puerto", "tipo"],
                        as_index=False)["viajeros"].sum()
               .sort_values(["fecha", "puerto"]).reset_index(drop=True))


def es_visitante(mig_izabal: pd.DataFrame) -> pd.DataFrame:
    """Marca que parte del trafico portuario cuenta como visitante."""
    out = mig_izabal.copy()
    out["cuenta_como_visitante"] = out["tipo"].isin(["Turista", "Excursionista"])
    return out


# --------------------------------------------------------------------------
def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    cruda = migracion_cruda()
    mig = migracion(cruda)

    tablas = {
        "movilidad_mensual": movilidad_mensual(),
        "movilidad_diaria": movilidad_diaria(),
        "ocupacion": ocupacion(),
        "oferta": oferta(),
        "migracion_mensual": migracion_mensual(mig),
        "migracion_izabal": es_visitante(migracion_izabal(cruda)),
    }
    for nombre, tabla in tablas.items():
        destino = SALIDA / f"{nombre}.parquet"
        tabla.to_parquet(destino, index=False)
        print(f"  {nombre:22s} {tabla.shape[0]:>7,} filas x {tabla.shape[1]:>2} col"
              f"  ->  {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    print("ETL Observatorio Rio Dulce y Livingston")
    main()
