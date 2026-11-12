"""
Presentacion ejecutiva para INGUAT: la slide de cierre del tablero.

Sigue los puntos de la rubrica de presentacion (docs/Rubrica_presentacion_
proyectos_INGUAT.pdf):

  1. Enfoque ejecutivo: destino, reto asignado y decisiones que apoya.
  2. Demostracion en vivo: ruta por los cuatro modulos guiada por preguntas
     de gestion, con la interaccion que conviene mostrar en cada uno.
  3. Resultados y recomendaciones: tres hallazgos cuantitativos y tres
     recomendaciones vinculadas, con el resultado del reto y las
     estimaciones de enero-febrero de 2026 diferenciadas de lo observado.
  4. Sustento y limites: fuentes y periodos, validacion del pronostico y
     limitaciones que afectan las decisiones.

Todas las cifras se calculan en vivo sobre la base completa, sin los filtros
de la barra superior: la slide tiene que decir lo mismo cada vez que se abre,
sin depender de lo que se haya tocado durante la demostracion.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import datos as dt
import modelos as md
from componentes import aviso, grupo, kpi, lectura, miles, mostrar, nota
from config import MORADO, TINTA
from vistas.guia import _tabla_cobertura
from vistas.temporal import _v9_pronostico


# --------------------------------------------------------------------------
# Calculo de las cifras que cita la presentacion
# --------------------------------------------------------------------------
def _tasa(emb: pd.DataFrame) -> float:
    """Tasa agregada como cociente de sumas, igual que el KPI del modulo 4."""
    if emb.empty or emb["puerta"].sum() == 0:
        return float("nan")
    return float(emb["destino_final"].sum() / emb["puerta"].sum() * 100)


def _cifras(ctx: dict) -> dict:
    mensual = ctx["mensual_completo"]
    diaria = ctx["diaria_completa"]
    migracion = ctx["migracion"]
    ocup = ctx["ocupacion"]

    # Reto: embudo de transferencia Rio Dulce -> Livingston
    emb = dt.embudo(mensual)
    por_origen = dt.embudo(mensual, ["origen"])
    t_nac = _tasa(por_origen[por_origen["origen"] == "Nacional"])
    t_ext = _tasa(por_origen[por_origen["origen"] == "Extranjero"])
    mes_max = emb.loc[emb["tasa_pct"].idxmax()] if len(emb) else None
    mes_min = emb.loc[emb["tasa_pct"].idxmin()] if len(emb) else None
    rezago = dt.rezago_transferencia(dt.embudo_diario(diaria))
    rezago_top = rezago.loc[rezago["correlacion"].idxmax()] if len(rezago) else None

    # Temporal: festividades y presion hotelera
    lift = dt.lift_eventos(diaria)
    top_eventos = lift.head(3)
    desde, hasta = (pd.Timestamp(x) for x in dt.VENTANA_COINCIDENTE)
    ventana = ocup[(ocup["fecha"] >= desde) & (ocup["fecha"] <= hasta)]
    pico_ocup = ventana.loc[ventana["ocupacion_pct"].idxmax()] if len(ventana) else None

    # Pronostico de enero-febrero de 2026
    val = md.validar(mensual, migracion)
    serie = md.serie_completa(mensual, migracion)
    est = serie[serie["tipo"] == md.ETIQUETA_ESTIMACION]
    obs = serie[serie["tipo"] == "Observado"]
    dic = obs[obs["fecha"] == pd.Timestamp("2025-12-01")]

    def _sub(df: pd.DataFrame, sub: str, mes: int | None = None) -> pd.Series | None:
        parte = df[df["subdestino"] == sub]
        if mes is not None:
            parte = parte[parte["fecha"].dt.month == mes]
        return parte.iloc[0] if len(parte) else None

    return {
        "emb": emb, "tasa": _tasa(emb), "t_nac": t_nac, "t_ext": t_ext,
        "brecha": t_ext / t_nac if t_nac else np.nan,
        "mes_max": mes_max, "mes_min": mes_min, "rezago_top": rezago_top,
        "top_eventos": top_eventos, "pico_ocup": pico_ocup,
        "metricas": val["metricas"], "n_meses": val["n_meses"],
        "serie": serie, "est": est, "dic": dic, "sub": _sub,
        "piso_techo": dt.cota_destino(mensual),
        "estadia_liv": dt.estadia_media(mensual[mensual["subdestino"] == dt.DESTINO_FINAL]),
        "estadia_rio": dt.estadia_media(mensual[mensual["subdestino"] == dt.PUERTA]),
    }


# --------------------------------------------------------------------------
# Piezas visuales
# --------------------------------------------------------------------------
def _tarjeta(numero: str, titulo: str, cuerpo: str, pie: str = "",
             color: str = TINTA) -> None:
    st.markdown(
        f'<div style="display:flex;gap:12px;align-items:flex-start">'
        f'<div style="min-width:34px;height:34px;border-radius:10px;'
        f'background:{color}1F;color:{color};font-weight:700;display:flex;'
        f'align-items:center;justify-content:center">{numero}</div>'
        f'<div><div style="font-weight:650;font-size:1.0rem;margin-bottom:4px">'
        f'{titulo}</div><div style="font-size:.9rem;line-height:1.45">{cuerpo}</div>'
        + (f'<div style="font-size:.78rem;opacity:.75;margin-top:6px">{pie}</div>'
           if pie else "")
        + '</div></div>',
        unsafe_allow_html=True)


def _pct(x: float, dec: int = 1) -> str:
    return "sin dato" if pd.isna(x) else f"{x:.{dec}f} %"


# --------------------------------------------------------------------------
# Secciones de la slide
# --------------------------------------------------------------------------
def _enfoque(c: dict) -> None:
    grupo("1 · Enfoque ejecutivo")
    col1, col2 = st.columns([1.1, 1], gap="large")
    with col1:
        with st.container(border=True):
            st.markdown("#### El destino y el reto")
            st.markdown(
                "**Rio Dulce y Livingston, Izabal.** Rio Dulce es la puerta de "
                "entrada por carretera; Livingston solo se alcanza por agua. "
                "El destino funciona como un **embudo**: casi todos pasan por "
                "la puerta, solo una parte completa el viaje.\n\n"
                "**Reto asignado: conectividad fluvial y embudo de "
                "transferencia.** ¿Que proporcion de quienes llegan a Rio "
                "Dulce continua a Livingston, quien lo hace y cuando?")
    with col2:
        with st.container(border=True):
            st.markdown("#### Decisiones que el observatorio apoya")
            st.markdown(
                "- **Promocion:** a que mercado dirigir el producto Livingston.\n"
                "- **Operacion fluvial:** cuando reforzar lanchas, muelles y "
                "seguridad.\n"
                "- **Planificacion de temporada:** que esperar en los meses "
                "sin medicion (ene–feb 2026).\n"
                "- **Coordinacion hotelera:** en que meses la ocupacion del "
                "departamento se acerca a su techo.")

    k1, k2, k3, k4 = st.columns(4, gap="small")
    piso, techo = c["piso_techo"]
    with k1, st.container(border=True):
        kpi("Visitantes por mes en el destino",
            f"{miles(piso)}–{miles(techo)}", "rango piso–techo, meses observados", "azul")
    with k2, st.container(border=True):
        kpi("Tasa de transferencia", _pct(c["tasa"]),
            "de Rio Dulce continua a Livingston", "celeste")
    with k3, st.container(border=True):
        kpi("Estadia media en Livingston", f"{c['estadia_liv']:.1f} dias",
            f"Rio Dulce {c['estadia_rio']:.1f} dias · solo turistas", "verde")
    with k4, st.container(border=True):
        kpi("Error del pronostico (MAPE)",
            _pct(c["metricas"]["estacional"]["MAPE"]),
            f"validacion dejar-uno-fuera, {c['n_meses']} meses", "morado")


def _ruta_demo() -> None:
    grupo("2 · Ruta de la demostracion en vivo")
    pasos = [
        ("Demanda", "¿Cuanta visita llega, cuanto se queda y de donde viene?",
         "Filtro Visitante → Extranjero; tocar un pais en V3 y ver como V5 lo "
         "resalta; tocar un poligono en V1 para enfocarlo."),
        ("Temporal", "¿Que pesan los feriados y que esperamos en ene–feb?",
         "Tocar una festividad en V7 y ver como V6 la resalta; mostrar la "
         "linea morada punteada de V9 y el MAPE de V10."),
        ("Hoteleria", "¿Hay capacidad para los picos?",
         "Recorrer capacidad (V12), ocupacion (V13), la ventana coincidente "
         "sep–dic 2025 (V14) y el filtro Lugar para comparar poligonos (V15)."),
        ("Conectividad", "¿Cuantos completan el viaje a Livingston?",
         "Embudo V16, tasa mes a mes V17, cambiar el desglose de V18 entre "
         "procedencia y tipo de visitante; validar supuestos con V19 y V20."),
    ]
    cols = st.columns(4, gap="small")
    for i, (col, (modulo, pregunta, accion)) in enumerate(zip(cols, pasos), 1):
        with col, st.container(border=True):
            st.markdown(f"**Modulo {i} · {modulo}**")
            st.markdown(f"*{pregunta}*")
            st.caption(accion)


def _hallazgos(c: dict) -> None:
    grupo("3 · Tres hallazgos y tres recomendaciones")

    mx, mn, rz = c["mes_max"], c["mes_min"], c["rezago_top"]
    ev = c["top_eventos"]
    eventos_txt = ", ".join(f"{r.evento} (+{r.lift_pct:.0f} %)"
                            for r in ev.itertuples()) or "sin festividades medidas"
    po = c["pico_ocup"]
    sub = c["sub"]
    rd_ene, rd_feb = sub(c["est"], dt.PUERTA, 1), sub(c["est"], dt.PUERTA, 2)
    liv_ene, liv_feb = sub(c["est"], dt.DESTINO_FINAL, 1), sub(c["est"], dt.DESTINO_FINAL, 2)
    rd_dic = sub(c["dic"], dt.PUERTA)

    caida = (np.nan if rd_dic is None or rd_feb is None
             else (rd_feb["visitantes"] / rd_dic["visitantes"] - 1) * 100)

    def _rango(r: pd.Series | None) -> str:
        if r is None:
            return "sin estimacion"
        return (f"<b>{miles(r['visitantes'])}</b> "
                f"({miles(r['banda_baja'])}–{miles(r['banda_alta'])})")

    filas = [
        (
            "H1", "El extranjero completa el viaje; el nacional se queda en la puerta",
            f"De cada 100 visitantes de Rio Dulce, <b>{c['tasa']:.0f}</b> llegan a "
            f"Livingston. Entre extranjeros la tasa es <b>{_pct(c['t_ext'])}</b> y "
            f"entre nacionales <b>{_pct(c['t_nac'])}</b>: una brecha de "
            f"<b>{c['brecha']:.1f}x</b>. La tasa va de {_pct(mn['tasa_pct'])} "
            f"({mn['etiqueta_mes']}) a {_pct(mx['tasa_pct'])} ({mx['etiqueta_mes']}).",
            "Movilidad mensual, sep 2025–ago 2026 sin ene–feb · Modulo 4, V16–V18",
            "R1", "Producto fluvial para el mercado nacional",
            "Paquete Rio Dulce–Livingston (lancha + actividad o noche en Livingston) "
            "promovido en el mercado nacional, que es el grueso de la puerta pero "
            "el que menos continua. Meta medible: subir la tasa nacional en V18.",
            "Alta: ataca el mayor volumen de visitantes que no completa el viaje.",
        ),
        (
            "H2", "Los feriados duplican la afluencia y el hotel ya opera cerca del techo",
            f"Las festividades con mayor impacto sobre un dia regular son "
            f"{eventos_txt}. La ocupacion hotelera de Izabal llego a "
            f"<b>{po['ocupacion_pct']:.0f} %</b> en "
            f"{dt.etiqueta_mes([po['fecha']]).iloc[0]} frente a "
            f"{po['ocupacion_pais_pct']:.0f} % del pais. El traslado fluvial ocurre "
            f"el mismo dia (correlacion {rz['correlacion']:.2f} con rezago "
            f"{int(rz['rezago_dias'])}).",
            "Movilidad diaria abr 2025–sep 2026; ocupacion de Izabal, ventana "
            "sep–dic 2025 · Modulos 2 y 3",
            "R2", "Plan operativo de feriados para el corredor fluvial",
            "Reforzar frecuencia de lanchas, control de capacidad en muelles y "
            "seguridad fluvial en Año Nuevo, Semana Santa y feriados de octubre, "
            "coordinado con hoteles para los meses de ocupacion mas alta.",
            "Alta: los picos son predecibles en fecha y el traslado es el mismo dia.",
        ),
        (
            "H3", "Ene–feb 2026: temporada baja estimada, no medida",
            f"<span style='color:{MORADO}'><b>Estimacion</b></span> para Rio Dulce: "
            f"enero {_rango(rd_ene)} y febrero {_rango(rd_feb)} visitantes; Livingston "
            f"enero {_rango(liv_ene)} y febrero {_rango(liv_feb)}. Febrero quedaria "
            f"<b>{abs(caida):.0f} % {'por debajo' if caida < 0 else 'por encima'}</b> "
            f"de diciembre observado. Error esperado: MAPE "
            f"{_pct(c['metricas']['estacional']['MAPE'])}.",
            "Telefonia + indice estacional de flujo migratorio 2023–2025 · Modulo 2, V9–V11",
            "R3", "Campaña de temporada baja y confirmacion del dato",
            "Activar promocion de ene–feb hacia los mercados extranjeros con mayor "
            "transferencia y, cuando llegue la telefonia de esos meses, contrastarla "
            "con la estimacion antes de usarla en metas.",
            "Media: la cifra es una estimacion con ±"
            f"{c['metricas']['estacional']['MAPE']:.0f} % de error.",
        ),
    ]

    colores = {"H1": "#4361EE", "H2": "#F72585", "H3": MORADO}
    for h, ht, hc, hf, r, rt, rc, prioridad in filas:
        izq, der = st.columns([1.15, 1], gap="small")
        with izq, st.container(border=True):
            _tarjeta(h, ht, hc, f"Fuente: {hf}", colores[h])
        with der, st.container(border=True):
            _tarjeta(r, rt, rc, f"Prioridad {prioridad}", "#60A125")

    lectura("Cada recomendacion se apoya en el hallazgo de su misma fila y se "
            "puede seguir en el tablero: R1 en V18, R2 en V7 y V13, R3 en V9.")


def _estimaciones(c: dict) -> None:
    grupo("4 · Estimaciones de enero–febrero 2026, separadas de lo observado")
    izq, der = st.columns([1.6, 1], gap="small")
    with izq, st.container(border=True):
        mostrar(_v9_pronostico(c["serie"]), clave="pres_v9")
        nota("Linea continua = dato observado. Linea punteada morada con banda = "
             "estimacion del modelo. Entre diciembre y marzo no hay medicion de "
             "telefonia.")
    with der, st.container(border=True):
        tabla = (c["est"].assign(
            Mes=lambda d: d["etiqueta_mes"],
            Poligono=lambda d: d["subdestino"],
            Estimado=lambda d: d["visitantes"].map(miles),
            Banda=lambda d: d["banda_baja"].map(miles) + " – " + d["banda_alta"].map(miles))
            [["Mes", "Poligono", "Estimado", "Banda"]])
        st.markdown("**Cifras estimadas (visitantes del mes)**")
        st.dataframe(tabla, hide_index=True, width="stretch")

        m = c["metricas"]
        st.markdown("**Validacion dejar-uno-fuera**")
        st.dataframe(pd.DataFrame([
            {"Modelo": v["nombre"], "MAPE": f"{v['MAPE']:.1f} %",
             "MAE": miles(v["MAE"]), "Meses": v["meses"]}
            for v in (m["estacional"], m["ingenuo"], m["reparto"])]),
            hide_index=True, width="stretch")
        st.caption("Se publica el modelo con menor error fuera de muestra. La "
                   "banda es ± el MAPE del propio modelo.")


def _sustento(ctx: dict) -> None:
    grupo("5 · Sustento y limites")
    izq, der = st.columns([1.3, 1], gap="small")
    with izq, st.container(border=True):
        st.markdown("**Fuentes y periodos**")
        st.dataframe(_tabla_cobertura(ctx)[["Fuente", "Cobertura", "Hueco declarado"]],
                     hide_index=True, width="stretch")
    with der, st.container(border=True):
        st.markdown("**Limitaciones que afectan las decisiones**")
        st.markdown(
            "- **El embudo es una aproximacion:** compara personas distintas "
            "en cada poligono, no trayectorias. Afecta la meta de R1.\n"
            "- **Puerta maritima sin caracterizar:** desde 2023 los puertos de "
            "Izabal registran todo como 'Viajero'. Parte de Livingston podria "
            "llegar por mar sin pasar por Rio Dulce.\n"
            "- **Ocupacion y oferta son de Izabal**, no del destino, y solo "
            "coinciden con la movilidad en sep–dic 2025.\n"
            "- **Ene–feb 2026 es estimacion**, no dato: no debe usarse como "
            "linea base de metas sin confirmarla.\n"
            "- **Sin gasto ni satisfaccion:** el destino no tiene encuesta propia.")

    aviso("Cifras de registros institucionales cedidos para uso academico. "
          "<b>No son cifras oficiales de INGUAT.</b>")


# --------------------------------------------------------------------------
def render(ctx: dict) -> None:
    c = _cifras(ctx)
    nota("Esta vista resume la presentacion ante INGUAT. Sus cifras usan la "
         "base completa y no cambian con los filtros de la barra superior.")
    _enfoque(c)
    _ruta_demo()
    _hallazgos(c)
    _estimaciones(c)
    _sustento(ctx)
