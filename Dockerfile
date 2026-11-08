# Imagen del Observatorio de Rio Dulce y Livingston.
#
# La imagen NO contiene datos. Los archivos institucionales se montan como
# volumen en tiempo de ejecucion (ver docker-compose.yml), de modo que la
# imagen puede compartirse sin exponer informacion confidencial.
FROM python:3.12-slim

# Streamlit escribe su configuracion en el home del usuario y pandas necesita
# una zona horaria definida para las series mensuales.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Guatemala

WORKDIR /app

# Las dependencias van en una capa propia: cambiar el codigo no reinstala todo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY data/etl.py ./data/etl.py
COPY .streamlit/ ./.streamlit/

# data/raw llega por volumen y data/procesado lo escribe el ETL al arrancar.
RUN mkdir -p data/raw data/procesado

EXPOSE 8501

# El contenedor se considera sano solo cuando Streamlit responde.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; \
        urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# El ETL corre antes del servidor y es idempotente: si las tablas ya existen
# las regenera igual, de forma que un cambio en los archivos de origen se
# refleja con solo reiniciar el contenedor.
CMD ["sh", "-c", "python data/etl.py && streamlit run app/app.py --server.port=8501 --server.address=0.0.0.0"]
