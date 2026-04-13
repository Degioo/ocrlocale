FROM python:3.12-slim

WORKDIR /app

# Necessario per i framework GUI (Tkinter/CustomTkinter) e per OpenCV (libgl1)
# Build-essential e cmake servono per poter compilare librerie come llama-cpp-python
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-tk \
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
COPY gui.py .
# (Eventuali modelli o file json)
COPY fields.json .
COPY llm_config_local.json .
COPY Avvia_OCR_Cannabis.bat .

# Di default, avvia la GUI
CMD ["python", "gui.py"]
