FROM python:3.12-slim

WORKDIR /app

# Laufzeit-Abhaengigkeiten fuer mediapipe/opencv-contrib-python (transitive mediapipe-Abhaengigkeit,
# specs/features/0024-top-photo-selection-category-mix.md) - python:3.12-slim (Debian) bringt diese
# von OpenCV dynamisch gelinkten Bibliotheken nicht mit, ein reines "pip install mediapipe" schlaegt
# darum zur Laufzeit mit "ImportError: libGL.so.1/libxcb.so.1/... cannot open shared object file"
# fehl (verifiziert per echtem `docker build` + Container-Smoke-Test waehrend der Umsetzung - das
# vorab in der Spec genannte Risiko betraf nur die Wheel-Installierbarkeit, nicht den tatsaechlichen
# Laufzeit-Import in diesem konkreten Basisimage). --no-install-recommends haelt das Image schlank,
# kein GUI-/X11-Server noetig - nur die von OpenCV dynamisch verlinkten Bibliotheken.
# libegl1/libgles2 (2026-08-14 ergaenzt): eine neuere mediapipe-Version verlangt beim
# Instanziieren von FaceDetector zusaetzlich libEGL.so.1 und libGLESv2.so.2 (auch im
# reinen CPU-Betrieb, ohne echte GPU/GPU-Delegate) - ohne diese beiden Pakete schlaegt
# jede FaceDetector-Nutzung mit "OSError: libEGL.so.1/libGLESv2.so.2: cannot open shared
# object file" fehl.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libxcb1 \
    libegl1 \
    libgles2 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml alembic.ini ./
COPY src ./src
COPY alembic ./alembic

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "photosort.main:app", "--host", "0.0.0.0", "--port", "8000"]
