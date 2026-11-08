# Observatorio de Inteligencia Turística — Río Dulce y Livingston

Tablero del **Grupo 5** · Destino asignado: **Río Dulce y Livingston (Izabal)** ·
Reto analítico: **conectividad fluvial y embudo de transferencia**.
CC3084 Data Science · Universidad del Valle de Guatemala · Semestre II 2026.

---

## Aviso sobre los datos

Los archivos de `data/raw/` son registros institucionales cedidos para uso
académico. **No se versionan ni se redistribuyen**: `.gitignore` excluye tanto
`data/raw/` como las tablas derivadas de `data/procesado/`, y la imagen de
Docker no los incluye (entran por volumen en tiempo de ejecución). El tablero
no habilita descargas de microdatos.

Para levantar el proyecto hay que colocar manualmente la carpeta de datos en
`data/raw/`.

---

## Cómo levantarlo

### Con Docker (forma recomendada para calificar)

```bash
docker compose up --build
```

Abrir <http://localhost:8501>. El contenedor corre el ETL al arrancar y luego
sirve el tablero. Los archivos originales se montan en solo lectura desde
`./data/raw`.

### Sin Docker

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
.venv/bin/python data/etl.py
.venv/bin/streamlit run app/app.py
```

---

## Estructura del repositorio

```
Proyecto3/
├── app/
│   ├── app.py              navegación, barra de filtros y contexto compartido
│   ├── config.py           paleta, tipografía y plantillas de gráfica
│   ├── componentes.py      piezas de interfaz reutilizables (KPI, notas, ejes)
│   ├── datos.py            carga, filtros y reglas de agregación del destino
│   ├── modelos.py          imputación de ene–feb 2026 y su validación
│   └── vistas/
│       ├── demanda.py      Módulo 1 · demanda y mercados emisores
│       ├── temporal.py     Módulo 2 · calendario, eventos y pronóstico
│       ├── hoteleria.py    Módulo 3 · oferta hotelera y territorio
│       ├── conectividad.py Módulo 4 · embudo de transferencia fluvial
│       └── guia.py         guía de lectura, cobertura y limitaciones
├── data/
│   ├── etl.py              único punto donde se leen los archivos de origen
│   ├── raw/                archivos institucionales (NO versionado)
│   └── procesado/          tablas limpias en parquet (NO versionado)
├── docs/
│   └── catalogo_indicadores.md   ficha técnica de cada indicador del tablero
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

### Flujo de datos

```
data/raw/*.xlsx|csv  →  data/etl.py  →  data/procesado/*.parquet  →  app/datos.py  →  vistas
```

La aplicación **nunca** abre un archivo de origen. Toda transformación vive en
`data/etl.py`, de modo que las reglas de cálculo quedan en un único lugar
auditable y el tablero arranca en menos de un segundo.

| Tabla derivada | Qué contiene | Cobertura |
|---|---|---|
| `movilidad_mensual` | visitantes únicos y días-persona por polígono, mes, país y segmento | sep–dic 2025 y mar–ago 2026 |
| `movilidad_diaria` | presencia por día y país, con marca de evento | dos tramos continuos más ventanas de evento |
| `ocupacion` | índice de ocupación mensual por departamento | ene 2023 – dic 2025 |
| `oferta` | establecimientos, habitaciones y plazas cama | cinco cortes anuales 2022–2026 |
| `migracion_mensual` | ingresos internacionales al país (turista + excursionista) | ene 2009 – jun 2026 |
| `migracion_izabal` | cruces por los puertos del departamento, por categoría | ene 2009 – jun 2026 |

---

## Los cuatro módulos

| Módulo | Qué responde | Gráficas |
|---|---|---|
| **1 · Demanda y mercados emisores** | cuánta visita llega, cuánto se queda, de dónde viene | V1–V5 |
| **2 · Dinámica temporal y pronóstico** | calendario, peso de los feriados, imputación de ene–feb 2026 | V6–V11 |
| **3 · Oferta hotelera y territorio** | capacidad instalada, ocupación y peso de cada polígono | V12–V15 |
| **4 · Conectividad fluvial** | qué proporción de la puerta de entrada completa el viaje | V16–V20 |

Más la **Guía de lectura**, que declara la cobertura de cada fuente, las reglas
de cálculo, el significado de los colores y las limitaciones.

### Gráficas enlazadas

Tres enlaces, todos por toque directo sobre la gráfica:

1. **V1 → módulo 1**: tocar una serie fija el polígono en foco.
2. **V3 → V5**: tocar un mercado lo resalta en el gráfico de volumen × estadía.
3. **V7 → V6**: tocar una festividad sombrea sus días en la serie diaria.

El foco activo aparece como píldora en la barra superior y se quita desde ahí.

---

## Reglas metodológicas que el código impone

Están implementadas en `data/etl.py` y `app/datos.py`, no solo documentadas:

1. **Un periodo sin cobertura se presenta vacío, nunca como cero.** Las líneas
   diarias se cortan (`connectgaps=False`) y ene–feb 2026 aparecen como
   estimación rotulada, en morado punteado y con banda de error.
2. **La permanencia promedio no se promedia.** `estadia_media()` es un cociente
   de sumas calculado solo sobre el segmento con pernocta.
3. **La base diaria no se suma para obtener el mes.** Viven en tablas separadas.
4. **Los subdestinos no se suman.** `cota_destino()` devuelve piso y techo; el
   tablero reporta el rango en vez de inventar un total.
5. **Nacionales y extranjeros no se mezclan.** Paneles con ejes propios; la
   participación extranjera nunca se calcula dividiendo entre el total.
6. **Las encuestas no se extrapolan.** El destino no tiene encuesta propia en
   el paquete, así que el tablero no muestra satisfacción ni gasto declarado.

---

## El pronóstico de enero y febrero de 2026

Los diez meses observados son diez meses de calendario distintos, y los dos que
faltan son exactamente los dos que nunca aparecen: la estacionalidad de enero y
febrero no se puede aprender dentro de la base de movilidad. El modelo la toma
de la base migratoria nacional.

```
índice(segmento, mes)  = promedio sobre años completos ≥2023 de
                         ingresos(segmento, año, mes) / media_anual(segmento, año)

nivel(polígono, origen, segmento) = media sobre meses observados de
                                    visitantes / índice(segmento, mes)

estimado = nivel × índice(segmento, mes objetivo)
```

Validado con **dejar-uno-fuera** sobre los diez meses observados, contra dos
contendientes. Las tres métricas están en el tablero (V10):

| Modelo | MAPE | RMSE | MAE | Meses evaluados |
|---|---|---|---|---|
| **Índice estacional por segmento** (publicado) | **13.2 %** | **13 262** | **9 435** | 10 |
| Media de los meses observados | 16.4 % | 16 313 | 11 029 | 10 |
| Factor de reparto directo | 18.6 % | 20 481 | 13 613 | 8 |

El factor de reparto directo solo puede evaluarse en ocho meses porque la base
migratoria termina en junio de 2026.

---

## Hallazgos principales

1. **El embudo está casi cerrado.** Alrededor del **10 %** de quienes pasan por
   Río Dulce llegan a Livingston. El cuello de botella del destino no es atraer
   visita, es convertir el paso por la puerta en visita al destino final.
2. **El embudo filtra por mercado.** El visitante extranjero completa el viaje
   el **31 %** de las veces y el nacional el **9 %**: una brecha de 3.5 veces
   sostenida en los diez meses. Río Dulce es destino final para el nacional y
   escala para el extranjero — dos productos distintos en el mismo territorio.
3. **El traslado es de ida y vuelta en el día.** La correlación diaria entre
   ambos polígonos es máxima con rezago **cero** (0.86) y cae con el desfase.
   Explica por qué Livingston recibe visita pero captura poca pernocta.
4. **La puerta marítima dejó de medirse como turismo.** Hasta 2021 el tráfico
   de los puertos de Izabal se registraba como crucerista; desde 2023 se
   registra íntegramente como *Viajero*, categoría que por definición no es
   visitante. Sin recuperar esa caracterización el embudo no se puede cerrar.
5. **La capacidad está congelada.** El inventario pasa de 2 957 a 3 014
   habitaciones entre el primer corte y el último, mientras la ocupación
   departamental llega al 92 % en diciembre de 2025.

---

## Limitaciones declaradas

- El embudo es una **aproximación**: la base de movilidad no contiene pares de
  origen y destino entre polígonos. V19 y V20 verifican sus dos supuestos.
- **No hay comparación interanual** con telefonía: los dos tramos de cobertura
  no comparten ningún mes del calendario.
- **Oferta y ocupación son departamentales**: Izabal incluye Puerto Barrios y
  Morales, que no forman parte del destino asignado.
- **Oferta y demanda miden universos distintos**: el inventario no incluye
  plataformas digitales, así que ninguna división entre ambos se presenta como
  tasa de ocupación real.
# Proyecto3-Dashboard
