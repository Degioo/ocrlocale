FROM python:3.12-slim

WORKDIR /app

# Necessario OpenCV (libgl1) + pyzbar (libzbar0) + tools per compilare C++
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libzbar0 \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia i sorgenti
COPY app/ app/
COPY main.py .
COPY web_app.py .
COPY fields.json .
COPY llm_config_local.json .
COPY Avvia_docker.bat .

# Avvia l'interfaccia grafica tramite Streamlit sulla porta 8501
CMD ["streamlit", "run", "web_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
