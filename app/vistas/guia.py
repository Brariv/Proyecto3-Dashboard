"""Guia de lectura: cobertura de las fuentes, reglas de calculo y limitaciones."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import datos as dt
from componentes import aviso, miles, nota
from config import (AZUL, CELESTE, GRIS, MORADO, NARANJA, ROSA, SALMON, VERDE,
                    VIOLETA)

GLOSARIO = [
    ("Tasa de transferencia",
     "Visitantes de Livingston divididos entre visitantes de Rio Dulce en el "
     "mismo mes. Aproxima que proporcion de quienes pasan por la puerta de "
     "entrada del destino continua hasta el destino final, al que solo se "
     "llega por via acuatica. No es un seguimiento de trayectorias: la base "
     "de movilidad no contiene pares de origen y destino entre poligonos."),
    ("Estadia media ponderada",
     "Suma de dias-persona dividida entre suma de visitantes, calculada "
     "exclusivamente sobre el segmento que pernocta. Al visitante de menos de "
     "24 horas se le asigna permanencia 1 por definicion, de modo que "
     "incluirlo arrastraria el indicador hacia 1 dia. Nunca se obtiene "
     "promediando la columna de permanencia del archivo de origen."),
    ("Visitantes unicos del mes",
     "Personas distintas que estuvieron en el poligono durante el mes. No se "
     "suman entre meses: quien visita en septiembre y en octubre es la misma "
     "persona y se contaria dos veces."),
    ("Presencia diaria",
     "Personas presentes en el poligono en un dia concreto. Es una medida "
     "distinta de la anterior y no se mezcla con ella. Sumar los dias de un "
     "mes no produce el total mensual de visitantes."),
    ("Lift de una festividad",
     "Exceso de afluencia de los dias de la festividad frente al dia regular "
     "promedio, en porcentaje. Un lift de +40 % significa que ese dia el "
     "destino recibe cuatro de cada diez personas mas que un dia corriente."),
    ("Indice estacional",
     "Forma del ano de una serie: cada mes expresado contra el mes promedio, "
     "donde 100 es el promedio. Es la pieza que el modelo de pronostico toma "
     "prestada de la base migratoria nacional."),
    ("MAPE",
     "Error porcentual medio del pronostico. Un MAPE de 13 % quiere decir "
     "que, en promedio, la estimacion se aleja un 13 % de la cifra real."),
    ("RMSE y MAE",
     "Error del pronostico en visitantes, no en porcentaje. El RMSE castiga "
     "mas los errores grandes; el MAE es el error tipico en valor absoluto."),
    ("Dejar-uno-fuera",
     "Forma de validar con pocos datos: cada mes se predice con un modelo "
     "reajustado sin ese mes. Las predicciones son por tanto fuera de "
     "muestra, que es la unica forma de medir el error de verdad."),
    ("Piso y techo del destino",
     "Los dos poligonos comparten visitantes: quien estuvo en Rio Dulce y en "
     "Livingston el mismo mes figura en los dos. El total real esta entre el "
     "poligono mayor (piso) y la suma de ambos (techo). El tablero reporta "
     "el rango en vez de inventar una cifra unica."),
]

REGLAS = [
    ("Un periodo sin cobertura se presenta vacio, nunca como cero",
     "La ausencia de medicion no es ausencia del fenomeno. Enero y febrero de "
     "2026 no tienen telefonia y aparecen como estimacion rotulada, no como "
     "una caida a cero. Las lineas diarias se cortan en los huecos en vez de "
     "unirse con una recta."),
    ("La permanencia promedio no se promedia",
     "La estadia media es siempre un cociente de sumas sobre el segmento que "
     "pernocta."),
    ("La base diaria no se suma para obtener el mes",
     "Mide presencia por dia; sumarla infla y duplica los visitantes unicos "
     "del mes. Las dos bases viven en tablas separadas del tablero."),
    ("Los poligonos no se suman para obtener el total",
     "Quien recorre los dos se duplica. El tablero los compara contra el "
     "mayor del mes y reporta el total como un rango."),
    ("Nacionales y extranjeros no se mezclan",
     "Las cifras nacionales incorporan un factor de expansion que las "
     "extranjeras no tienen. Se reportan en paneles con ejes propios y la "
     "participacion extranjera nunca se calcula dividiendo entre el total."),
    ("Las encuestas no se extrapolan a totales",
     "Ninguna de las encuestas del paquete tiene factor de expansion. El "
     "destino asignado ademas no cuenta con encuesta propia, de modo que el "
     "tablero no presenta ningun indicador de satisfaccion ni de gasto "
     "declarado."),
]


def _muestra_color(hex_: str, nombre: str, significado: str) -> str:
    return (f'<div style="display:flex;align-items:center;gap:10px;margin:6px 0">'
            f'<span style="width:26px;height:26px;border-radius:7px;'
            f'background:{hex_};display:inline-block;border:1px solid #DFE3F2"></span>'
            f'<span><b>{nombre}</b> <code>{hex_}</code> — {significado}</span></div>')


def _tabla_cobertura(ctx: dict) -> pd.DataFrame:
    mensual, diaria = ctx["mensual_completo"], ctx["diaria_completa"]
    ocup, oferta = ctx["ocupacion"], ctx["oferta"]
    mig, mig_iz = ctx["migracion"], ctx["migracion_izabal"]

    def rango(df: pd.DataFrame, col: str = "fecha") -> str:
        fechas = pd.to_datetime(df[col])
        return (f"{dt.etiqueta_mes([fechas.min()]).iloc[0]} a "
                f"{dt.etiqueta_mes([fechas.max()]).iloc[0]}")

    return pd.DataFrame([
        {"Fuente": "Movilidad mensual (telefonia)", "Cobertura": rango(mensual),
         "Granularidad": "Poligono x mes x pais x segmento",
         "Hueco declarado": "Ene y feb 2026 sin dato; se estiman"},
        {"Fuente": "Movilidad diaria (telefonia)", "Cobertura": rango(diaria),
         "Granularidad": "Poligono x dia x pais",
         "Hueco declarado": "Dos tramos continuos mas ventanas de evento"},
        {"Fuente": "Indice de ocupacion hotelera", "Cobertura": rango(ocup),
         "Granularidad": "Departamento x mes",
         "Hueco declarado": "Sin cortes 2026; es Izabal, no el destino"},
        {"Fuente": "Oferta de alojamiento",
         "Cobertura": f"{int(oferta['anio'].min())} a {int(oferta['anio'].max())}",
         "Granularidad": "Departamento x corte anual x tipo",
         "Hueco declarado": "Cinco fotos, no una serie mensual"},
        {"Fuente": "Flujo migratorio nacional", "Cobertura": rango(mig),
         "Granularidad": "Pais x mes x via x frontera",
         "Hueco declarado": "Quiebre metodologico entre 2022 y 2023"},
        {"Fuente": "Puertos de Izabal (migracion)", "Cobertura": rango(mig_iz),
         "Granularidad": "Puerto x mes x categoria de viajero",
         "Hueco declarado": "Sin 2022; desde 2023 todo es 'Viajero'"},
    ])


def render(ctx: dict) -> None:
    st.markdown("### Como usar este tablero")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("#### Alcance")
        st.markdown(
            "- Observatorio de **Rio Dulce y Livingston**, departamento de "
            "**Izabal**. Reto analitico asignado: **conectividad fluvial y "
            "embudo de transferencia**.\n"
            "- Responde preguntas de **gestion de destino**: cuanta visita "
            "llega, de donde viene, cuanto se queda, que pesan los feriados, "
            "como esta la capacidad hotelera del departamento y que proporcion "
            "de quienes pasan por la puerta de entrada completa el viaje.\n"
            "- **No** contiene gasto del visitante ni indicadores de "
            "satisfaccion: el destino asignado no cuenta con encuesta propia "
            "en el paquete de datos, y las de Antigua y Peten no son "
            "trasladables a Izabal.\n"
            "- **No** mide efectos causales. Las relaciones que muestra son "
            "asociaciones."
        )

        st.markdown("#### Tres reglas de lectura")
        st.markdown(
            "1. **Linea continua y color propio = dato observado. Linea "
            "punteada y color morado = estimacion de un modelo**, siempre con "
            "la etiqueta *Estimacion* y su banda de error.\n"
            "2. Las graficas marcadas como *Enlazada* cambian cuando usted "
            "toca algo en su pareja. El enfoque activo aparece en las "
            "pildoras de la barra superior y se quita desde ahi.\n"
            "3. Cuando una seleccion se queda sin datos, el tablero lo dice "
            "de forma explicita en lugar de mostrar una grafica vacia."
        )

        aviso("Las cifras provienen de registros institucionales cedidos para "
              "uso academico. <b>No son cifras oficiales de INGUAT</b> y el "
              "tablero no habilita descargas de microdatos.")

    with col2:
        st.markdown("#### Significado de los colores")
        st.markdown(
            _muestra_color(AZUL, "Azul", "demanda y puerta de entrada (Rio Dulce)") +
            _muestra_color(CELESTE, "Celeste", "destino final y series de apoyo (Livingston)") +
            _muestra_color(NARANJA, "Naranja", "mercado extranjero y ocupacion hotelera") +
            _muestra_color(VERDE, "Verde", "mercado nacional y resultado favorable") +
            _muestra_color(ROSA, "Rosa", "presion, alerta o resultado desfavorable") +
            _muestra_color(MORADO, "Morado", "toda cifra estimada o pronosticada") +
            _muestra_color(SALMON, "Salmon", "visitante de paso y categorias secundarias") +
            _muestra_color(VIOLETA, "Violeta", "navegacion y encabezados"),
            unsafe_allow_html=True)
        nota("Un color significa lo mismo en las cuatro secciones. Ninguna "
             "lectura depende solo del color: las series llevan etiqueta "
             "directa y las estimaciones se distinguen ademas por la linea "
             "punteada y por el rotulo <b>Estimacion</b>.")

    st.divider()
    st.markdown("#### Que periodo respalda cada cifra")
    st.caption("Las fuentes tienen coberturas distintas. Un filtro que deja a "
               "una fuente sin datos no deja sin datos a las demas, y ese es "
               "el error de lectura mas probable en un tablero como este.")
    st.dataframe(_tabla_cobertura(ctx), hide_index=True, width="stretch")

    aviso("La ventana en que la movilidad y la ocupacion hotelera coinciden es "
          "<b>septiembre a diciembre de 2025</b>, cuatro meses. Cualquier "
          "cruce entre afluencia y ocupacion fuera de esa ventana compara un "
          "dato contra un vacio, y por eso V14 no permite salirse de ella.")

    st.divider()
    st.markdown("#### Reglas de calculo que gobiernan el tablero")
    for titulo, detalle in REGLAS:
        with st.expander(titulo):
            st.write(detalle)

    st.divider()
    st.markdown("#### Glosario")
    for termino, definicion in GLOSARIO:
        with st.expander(termino):
            st.write(definicion)

    st.divider()
    st.markdown("#### Supuestos y limitaciones principales")
    st.markdown(
        "- **El embudo es una aproximacion.** La base de movilidad no "
        "contiene pares de origen y destino entre poligonos. La tasa de "
        "transferencia compara cuantas personas distintas estuvieron en cada "
        "poligono, no cuantas se trasladaron de uno al otro. V19 y V20 "
        "verifican los dos supuestos de los que depende esa lectura.\n"
        "- **No hay comparacion interanual con telefonia.** Los dos tramos de "
        "cobertura no comparten ningun mes del calendario, de modo que "
        "comparar un mes de 2025 contra el mismo mes de 2026 es imposible "
        "con esta fuente. Lo que si permite es un perfil estacional "
        "compuesto, que mezcla dos anios y se advierte como tal.\n"
        "- **Oferta y ocupacion son departamentales.** Izabal incluye Puerto "
        "Barrios y Morales, que no forman parte del destino asignado. El "
        "modulo 3 lo declara en su encabezado.\n"
        "- **Oferta y demanda miden universos distintos.** El inventario "
        "registra hospedajes, hoteles y pensiones, y no incluye plataformas "
        "digitales. Ninguna division entre afluencia y camas se presenta como "
        "una tasa de ocupacion real.\n"
        "- **La puerta maritima dejo de caracterizarse.** Desde 2023 el "
        "trafico de los puertos de Izabal se registra integramente como "
        "'Viajero', categoria que por definicion no es visitante. Es la "
        "limitacion mas seria para cerrar el embudo de Livingston."
    )

    st.divider()
    st.markdown("#### Origen de los datos y reproducibilidad")
    st.markdown(
        "El tablero no abre ningun archivo de origen. `data/etl.py` lee los "
        "archivos institucionales de `data/raw/`, aplica las reglas de "
        "calculo descritas arriba y escribe tablas limpias en "
        "`data/procesado/`. La aplicacion consume solo esas tablas, de modo "
        "que toda transformacion vive en un unico lugar auditable. "
        "Los archivos originales estan excluidos del repositorio mediante "
        "`.gitignore`, conforme a la clausula de confidencialidad del "
        "proyecto. El detalle de cada indicador esta en "
        "`docs/catalogo_indicadores.md` y las decisiones metodologicas en la "
        "memoria tecnica."
    )
