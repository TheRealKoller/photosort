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

# Schichtschluessel: `pyproject.toml` traegt die Abhaengigkeitsliste, `uv.lock` deren Aufloesung.
# `uv.lock` ist NUR Schluessel, keine Installationsquelle - das Image loest weiterhin frisch aus
# [project].dependencies auf. Ein Lock-Refresh verwirft damit die Fremdpaket-Schicht, ohne dass
# die Installation an den Lock gekoppelt waere.
COPY pyproject.toml uv.lock ./

# Manifest, Fetch-Skript und Modell-Assets bekommen eine eigene Schicht vor den Fremdpaketen: der
# Download haengt nicht an `src/` und bleibt im Cache, solange sich Manifest und Skript nicht
# aendern. Das Skript liest das Manifest ueber seinen Dateipfad, nicht ueber das installierte
# Paket; die Dateien werden per SHA256 geprueft und erst nach bestandener Pruefung geschrieben.
COPY src/photosort/model_assets.py src/photosort/model_assets.py
COPY scripts/fetch_model_assets.py scripts/fetch_model_assets.py
RUN python scripts/fetch_model_assets.py

# Fremdpakete aus [project].dependencies, per tomllib gelesen. Diese Schicht haengt nur an
# pyproject.toml/uv.lock, nicht an src/ - eine Quellcode-Aenderung installiert sie nicht neu.
RUN python -c "import pathlib, tomllib; data = tomllib.loads(pathlib.Path('pyproject.toml').read_text()); pathlib.Path('/tmp/requirements.txt').write_text('\n'.join(data['project']['dependencies']) + '\n')"
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Erst jetzt der Quellcode. Die bereits heruntergeladenen Assets bleiben beim Zusammenfuehren
# erhalten und sind beim folgenden Projekt-Install Teil von [tool.setuptools.package-data].
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

# Zweite Absicherung neben der Zuweisung in label_embedding.py: onnxruntime sendet sonst unter
# Linux Telemetrie an Microsoft. Gilt fuer backend und worker, die beide dieses Image nutzen.
ENV ORT_DISABLE_TELEMETRY=1

# --no-deps: die Fremdpakete liegen bereits aus der Schicht oben im Image. Der Projekt-Install
# nimmt nur noch Paket und Asset-Daten aus dem Quellbaum.
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

CMD ["uvicorn", "photosort.main:app", "--host", "0.0.0.0", "--port", "8000"]
