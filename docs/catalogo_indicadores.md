# Catálogo formal de indicadores

Observatorio de Río Dulce y Livingston · Grupo 5 · CC3084, UVG.

Cada indicador visualizado en el tablero está documentado con los ocho campos
de la ficha técnica estándar. Las implementaciones citadas son las funciones
reales del repositorio, no pseudocódigo.

Notación común:

- $s$ = subdestino (polígono): Río Dulce o Livingston.
- $o$ = origen: Nacional o Extranjero.
- $g$ = segmento: *mayor a 1 día* (pernocta) o *menor a 1 día* (mismo día).
- $t$ = mes.
- $v_{s,o,g,t}$ = visitantes únicos; $d_{s,o,g,t}$ = días-persona.

---

## 1. Visitantes en un mes típico (piso y techo del destino)

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Cuántas personas distintas recibe el destino en un mes promedio. Como los dos polígonos comparten visitantes, no existe una cifra única: se reporta el rango dentro del cual está el total real. Le sirve al INGUAT para dimensionar el destino sin publicar una cifra que sobreestime. |
| **Fórmula matemática** | $\text{piso} = \frac{1}{\lvert T\rvert}\sum_{t\in T}\max_s \sum_{o,g} v_{s,o,g,t}$ <br> $\text{techo} = \frac{1}{\lvert T\rvert}\sum_{t\in T}\sum_{s}\sum_{o,g} v_{s,o,g,t}$ |
| **Implementación** | `datos.cota_destino()` — `por_sub = df.groupby(["fecha","subdestino"])["visitantes"].sum()`; luego `por_sub.groupby("fecha").max().mean()` y `.sum().mean()`. |
| **Agregación y granularidad** | Origen: polígono × mes × país × segmento. Métrica: destino × mes promedio. |
| **Unidad** | Personas. |
| **Fuentes** | `BD_moviidad_mensual.xlsx`, hoja `Izabal`; columnas `destino`, `fecha`, `visitantes`. |
| **Reglas y exclusiones** | **No se suman meses**: una misma persona puede aparecer en varios, así que la suma no es un total del periodo; se promedia. **No se suman polígonos** como si fueran un total: quien recorre los dos se duplica. |

---

## 2. Días-persona

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Volumen total de permanencia: suma de los días que cada visitante estuvo en el destino. Es el denominador natural de cualquier cálculo de presión sobre servicios. |
| **Fórmula matemática** | $D = \sum_{s,o,g,t} d_{s,o,g,t}$ |
| **Implementación** | `mensual["dias_persona"].sum()` |
| **Agregación y granularidad** | Origen: polígono × mes × país × segmento. Métrica: acumulado del periodo. |
| **Unidad** | Días-persona. |
| **Fuentes** | `BD_moviidad_mensual.xlsx`, hoja `Izabal`; columna `dias_persona`. |
| **Reglas y exclusiones** | A diferencia de los visitantes, los días-persona **sí** se acumulan entre meses: son un flujo, no una población. |

---

## 3. Estadía Media Ponderada

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Cuántos días permanece en el destino un turista que pernocta. Es el indicador que vincula afluencia con noches vendidas, y por tanto con el ingreso del alojamiento. |
| **Fórmula matemática** | $\text{EMP} = \dfrac{\sum_{s,o,t} d_{s,o,g^{*},t}}{\sum_{s,o,t} v_{s,o,g^{*},t}}$, con $g^{*}$ = *mayor a 1 día*. |
| **Implementación** | `datos.estadia_media()` — `pernocta = df[df["segmento"] == SEG_PERNOCTA]`; `pernocta["dias_persona"].sum() / pernocta["visitantes"].sum()`. |
| **Agregación y granularidad** | Origen: polígono × mes × país × segmento. Métrica: destino × periodo. |
| **Unidad** | Días por visitante. |
| **Fuentes** | `BD_moviidad_mensual.xlsx`; columnas `visitantes`, `dias_persona`, `es_consecutivo`. |
| **Reglas y exclusiones** | **Exclusivo del segmento con pernocta.** Al excursionista de menos de 24 h se le asigna permanencia 1 por definición; incluirlo arrastra el indicador hacia 1 día y subestima la permanencia real. **Prohibido promediar la columna `permanencia_prom`**: eso pesaría igual a un país de dos visitantes que al mercado nacional. |

---

## 4. Segmentación turista / excursionista

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Qué proporción de la visita pernocta y cuál entra y sale el mismo día. Separa el destino que vende camas del destino que solo recibe paso. |
| **Fórmula matemática** | $P_g = \dfrac{\sum_{s,o,t} v_{s,o,g,t}}{\sum_{s,o,g',t} v_{s,o,g',t}} \times 100$ |
| **Implementación** | `datos.segmentacion()` — `groupby("segmento")["visitantes"].sum()` normalizado por el total. |
| **Agregación y granularidad** | Origen: polígono × mes × país × segmento. Métrica: destino × periodo. |
| **Unidad** | Porcentaje. |
| **Fuentes** | `BD_moviidad_mensual.xlsx`; columna `es_consecutivo`. |
| **Reglas y exclusiones** | Los dos segmentos son exhaustivos y excluyentes dentro de cada combinación, de modo que el porcentaje suma 100 por construcción. |

---

## 5. Top de mercados emisores extranjeros

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Qué países alimentan la visita internacional. Sirve para priorizar promoción y conectividad. |
| **Fórmula matemática** | $\text{part}_p = \dfrac{\sum_{s,g,t} v_{s,p,g,t}}{\sum_{p'\neq \text{GT}}\sum_{s,g,t} v_{s,p',g,t}} \times 100$ |
| **Implementación** | `datos.mercados()` — filtra `origen == "Extranjero"`, ordena por visitantes y divide entre el total extranjero. |
| **Agregación y granularidad** | Origen: país × polígono × mes × segmento. Métrica: país × periodo. |
| **Unidad** | Personas y porcentaje del universo extranjero. |
| **Fuentes** | `BD_moviidad_mensual.xlsx`; columna `pais`. |
| **Reglas y exclusiones** | **Guatemala queda fuera del ranking.** Las cifras nacionales llevan factor de expansión y las extranjeras no, así que no son comparables en un mismo orden. Por la misma razón **la participación se calcula sobre el universo extranjero y nunca dividiendo entre el total**. Se excluyen las filas con país nulo. |

---

## 6. Lift de festividades

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Cuánto sube la afluencia un día de fiesta frente a un día corriente. Permite distinguir qué festividades mueven realmente al destino y cuáles solo figuran en el calendario. |
| **Fórmula matemática** | $\text{Lift}(e) = \left(\dfrac{\bar{P}_e}{\bar{P}_{\text{reg}}} - 1\right)\times 100$, donde $\bar{P}_e$ es la presencia media de los días del evento $e$ y $\bar{P}_{\text{reg}}$ la de los días regulares de meses con cobertura completa. |
| **Implementación** | `datos.lift_eventos()` — referencia: `por_dia[(evento=="Regular") & mes_completo]["presencia"].mean()`; luego `out["presencia_media"] / referencia - 1`. |
| **Agregación y granularidad** | Origen: polígono × día × país. Métrica: evento × polígono. |
| **Unidad** | Porcentaje sobre el día regular. |
| **Fuentes** | `BD_moviidad_diario.xlsx`, hoja `Izabal`; columnas `idfecha`, `evento`, `cantidad_visitantes`. |
| **Reglas y exclusiones** | La referencia usa **solo días regulares de meses con ≥28 días cubiertos**. Las ventanas cortas del archivo se levantaron alrededor de una festividad: incluirlas en la referencia subiría la base de comparación y apagaría artificialmente el lift de todos los eventos. La presencia diaria **no se suma** para obtener totales mensuales. |

---

## 7. Índice de patrón semanal

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Qué días de la semana concentran la presión. Define el problema operativo: la capacidad debe absorber el pico pero se paga todos los días. |
| **Fórmula matemática** | $I_{s,w} = \dfrac{\bar{P}_{s,w}}{\frac{1}{7}\sum_{w'} \bar{P}_{s,w'}} \times 100$ |
| **Implementación** | `datos.patron_semanal()` — media de presencia por día de semana, normalizada por la media del polígono. |
| **Agregación y granularidad** | Origen: polígono × día. Métrica: polígono × día de la semana. |
| **Unidad** | Índice (100 = día promedio). |
| **Fuentes** | `BD_moviidad_diario.xlsx`; columnas `dia_semana`, `cantidad_visitantes`. |
| **Reglas y exclusiones** | **Se excluyen los días de festividad**: caen en fechas fijas y, de incluirse, inflarían justamente el día de la semana en que ocurrieron. Solo meses con cobertura completa. |

---

## 8. Estimación de visitantes de enero y febrero de 2026

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Cifra imputada para los dos meses de la ventana de trabajo sin cobertura de telefonía móvil. Permite cerrar el año sin presentar un cero que el INGUAT leería como caída de visita. |
| **Fórmula matemática** | $\text{índice}(g,m) = \underset{a \in A}{\text{prom}} \dfrac{I_{g,a,m}}{\frac{1}{12}\sum_{m'} I_{g,a,m'}}$ <br> $\text{nivel}(s,o,g) = \underset{t \in T_{obs}}{\text{prom}} \dfrac{v_{s,o,g,t}}{\text{índice}(g, m(t))}$ <br> $\hat{v}_{s,o,g,t^{*}} = \text{nivel}(s,o,g)\times\text{índice}(g, m(t^{*}))$ |
| **Implementación** | `modelos.indice_estacional()`, `modelos._ajustar_estacional()`, `modelos.estimar()`. |
| **Agregación y granularidad** | Origen del índice: país × mes (migración). Origen del nivel: polígono × origen × segmento × mes (movilidad). Métrica: polígono × mes estimado. |
| **Unidad** | Personas. |
| **Fuentes** | `BD_moviidad_mensual.xlsx` (nivel) y `Base_Migracion_2009-2026jun.xlsx`, hoja `Datos` (forma estacional), columnas `Año`, `Mes cod`, `Tipo de Viajero`, `Viajero`. |
| **Reglas y exclusiones** | El índice usa **solo Turista + Excursionista** (la nota metodológica excluye *Viajero* y *Cruceristas* para medir demanda) y **solo años completos desde 2023** (quiebre metodológico declarado entre 2022 y 2023; 2026 llega a junio y sesgaría hacia el primer semestre). El índice se calcula por separado para cada segmento. Toda cifra estimada se publica en morado punteado, rotulada *Estimación*, con su banda de error. |

---

## 9. Métricas de error del pronóstico (MAPE, RMSE, MAE)

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Cuánto se equivoca el modelo al predecir meses que no vio. Sin esta cifra la estimación no es un resultado publicable. |
| **Fórmula matemática** | $\text{MAPE} = \frac{100}{n}\sum \left\lvert\frac{\hat{y}_i - y_i}{y_i}\right\rvert$ · $\text{RMSE} = \sqrt{\frac{1}{n}\sum (\hat{y}_i - y_i)^2}$ · $\text{MAE} = \frac{1}{n}\sum \lvert \hat{y}_i - y_i\rvert$ |
| **Implementación** | `modelos.validar()` con `modelos._metricas()`. Protocolo dejar-uno-fuera: para cada mes observado se reajusta el modelo completo sin ese mes. |
| **Agregación y granularidad** | Se calculan **al nivel en que se publica la cifra**: visitantes del mes por polígono. |
| **Unidad** | MAPE en porcentaje; RMSE y MAE en personas. |
| **Fuentes** | Las mismas del indicador 8. |
| **Reglas y exclusiones** | El MAPE excluye observaciones con $y_i = 0$. El modelo de *factor de reparto directo* solo se evalúa en 8 de los 10 meses porque la base migratoria termina en junio de 2026; el tablero declara el número de meses evaluados de cada modelo. |

---

## 10. Tasa de ocupación departamental

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Qué proporción de la capacidad hotelera de Izabal está ocupada cada mes. Es la única medida de uso del alojamiento disponible para el destino. |
| **Fórmula matemática** | $O_{d,t} = \text{índice}_{d,t}\times 100$; referencia nacional $\bar{O}_t = \frac{1}{22}\sum_d O_{d,t}$ |
| **Implementación** | `etl.ocupacion()` — `df["ocupacion_pct"] = df["indice_ocupacion"] * 100`; la referencia es la media simple de los departamentos del mes. |
| **Agregación y granularidad** | Origen: departamento × mes. Métrica: departamento × mes. |
| **Unidad** | Porcentaje. |
| **Fuentes** | `indice_ocupacion_mensual_2023_2025_1.csv`; columnas `anio`, `mes`, `departamento`, `indice_ocupacion`. |
| **Reglas y exclusiones** | **Es Izabal completo**, no el destino turístico: incluye Puerto Barrios y Morales. Serie continua ene 2023 – dic 2025, sin cortes de 2026. La referencia nacional es promedio simple, no ponderado por capacidad: sitúa a Izabal, no mide el país. |

---

## 11. Capacidad instalada de alojamiento

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Inventario físico de establecimientos, habitaciones y plazas cama del departamento. Sirve de denominador de la ocupación y describe la estructura de la oferta. |
| **Fórmula matemática** | $C_{d,a,k} = \sum \text{(establecimientos, habitaciones, plazas cama)}$ por departamento $d$, corte anual $a$ y tipo $k$. |
| **Implementación** | `datos.oferta_anual()` — `groupby(["anio","corte","tipo_alojamiento"]).sum()`. |
| **Agregación y granularidad** | Origen: departamento × corte × tipo. Métrica: departamento × corte. |
| **Unidad** | Establecimientos, habitaciones, plazas cama. |
| **Fuentes** | `oferta_hotelera_2022_2026.csv`. |
| **Reglas y exclusiones** | **No es una serie mensual** pese al nombre de la columna `trimestre`: son cinco cortes anuales. Se grafica como barras por corte y **nunca como una tendencia de cinco puntos**. Registra solo hospedajes, hoteles y pensiones: **no incluye plataformas digitales**, de modo que oferta y demanda miden universos distintos y ninguna división entre ambas se presenta como tasa de ocupación real. El corte 2026 es del primer trimestre y los anteriores del cuarto. |

---

## 12. Índice de peso del polígono

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Cuánto representa cada polígono frente al mayor del mes. Permite comparar subdestinos sin construir un total que duplicaría visitantes. |
| **Fórmula matemática** | $W_{s,t} = \dfrac{\sum_{o,g} v_{s,o,g,t}}{\max_{s'}\sum_{o,g} v_{s',o,g,t}} \times 100$ |
| **Implementación** | `datos.desagregacion()` — `mayor = por_sub.groupby("fecha")["visitantes"].transform("max")`. |
| **Agregación y granularidad** | Origen: polígono × mes. Métrica: polígono × mes. |
| **Unidad** | Porcentaje del polígono mayor. |
| **Fuentes** | `BD_moviidad_mensual.xlsx`. |
| **Reglas y exclusiones** | El denominador es el **polígono mayor**, no la suma. Sumar duplicaría a quien estuvo en los dos e inflaría el denominador, con lo que el peso de cada polígono saldría artificialmente bajo. |

---

## 13. Tasa de transferencia fluvial *(indicador central del reto)*

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Qué proporción de quienes pasan por Río Dulce, la puerta de entrada por carretera, continúa hasta Livingston, al que solo se llega por vía acuática. Es la medida de conectividad efectiva del destino y señala dónde está su cuello de botella. |
| **Fórmula matemática** | $\tau_t = \dfrac{\sum_{o,g} v_{\text{Liv},o,g,t}}{\sum_{o,g} v_{\text{RD},o,g,t}} \times 100$ <br> Agregado del periodo: $\bar{\tau} = \dfrac{\sum_t \sum_{o,g} v_{\text{Liv},o,g,t}}{\sum_t \sum_{o,g} v_{\text{RD},o,g,t}}\times 100$ (cociente de sumas). |
| **Implementación** | `datos.embudo()` — pivot por subdestino, `piv["destino_final"] / piv["puerta"]`. Desgloses por origen y segmento con el argumento `por`. |
| **Agregación y granularidad** | Origen: polígono × mes × país × segmento. Métrica: destino × mes, y destino × mes × (origen \| segmento). |
| **Unidad** | Porcentaje. |
| **Fuentes** | `BD_moviidad_mensual.xlsx`, hoja `Izabal`; columna `destino` (valores `Rio Dulce`, `Livingston`). |
| **Reglas y exclusiones** | **Es una aproximación, no una medición de trayectorias**: la base no contiene pares origen-destino entre polígonos; compara cuántas personas distintas estuvieron en cada uno. El agregado es **cociente de sumas**, no promedio de tasas mensuales, para que un mes pequeño no pese igual que uno grande. En el desglose por origen **cada serie usa su propio denominador** (extranjeros sobre extranjeros, nacionales sobre nacionales): nunca se dividen poblaciones construidas de forma distinta. Depende de dos supuestos que se verifican en los indicadores 14 y 15. |

---

## 14. Rezago del traslado (verificación del supuesto temporal)

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Con cuántos días de desfase se corresponden las curvas diarias de los dos polígonos. Verifica que la transferencia cabe dentro del mes y caracteriza el viaje como excursión o como estancia. |
| **Fórmula matemática** | $\rho_k = \text{corr}\big(P_{\text{RD},\,d},\; P_{\text{Liv},\,d+k}\big)$, para $k = 0,\dots,4$. |
| **Implementación** | `datos.rezago_transferencia()` — reindexa a frecuencia diaria y correlaciona contra `shift(-k)`. |
| **Agregación y granularidad** | Origen: polígono × día. Métrica: coeficiente por rezago. |
| **Unidad** | Coeficiente de correlación (−1 a 1). |
| **Fuentes** | `BD_moviidad_diario.xlsx`, hoja `Izabal`. |
| **Reglas y exclusiones** | Solo días de **meses con cobertura completa** y consecutivos; los tramos sueltos quedan fuera para que el desfase no se calcule entre días separados por meses. Es correlación de presencia diaria, **no seguimiento de personas**. Requiere al menos 10 pares por rezago. |

---

## 15. Tráfico de la puerta marítima (verificación del supuesto de exclusividad)

| Campo | Contenido |
|---|---|
| **Definición de negocio** | Cuánta visita puede entrar a Livingston sin pasar por Río Dulce. Acota el supuesto del embudo y documenta un cambio de clasificación que hoy impide cerrarlo. |
| **Fórmula matemática** | $M_{a,\text{tipo}} = \sum_{f \in F}\sum_{m} \text{viajeros}_{f,m,\text{tipo}}$, con $F$ = {Santo Tomás de Castilla, Puerto Barrios, Livingston}. |
| **Implementación** | `datos.puerta_maritima_anual()` sobre la tabla `migracion_izabal`, construida en `etl.migracion_izabal()` desde la base **sin filtrar por tipo**. |
| **Agregación y granularidad** | Origen: frontera × mes × país × tipo de viajero. Métrica: año × tipo de viajero. |
| **Unidad** | Cruces fronterizos. |
| **Fuentes** | `Base_Migracion_2009-2026jun.xlsx`, hoja `Datos`; columnas `Frontera`, `Tipo de Viajero`, `Viajero`. |
| **Reglas y exclusiones** | **Excepción deliberada a la regla general**: este es el único indicador que *no* filtra a Turista + Excursionista. Desde 2023 todo el tráfico de estos puertos se registra como *Viajero*, categoría que por definición no es visitante; filtrar dejaría el gráfico vacío y escondería justamente el hallazgo. Los cruces **no son comparables con visitantes del destino**: miden eventos de frontera, no personas presentes en un polígono. El hueco de 2022 corresponde al quiebre metodológico declarado en la base. |
