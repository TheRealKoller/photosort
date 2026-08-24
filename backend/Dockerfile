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

# Lokales Text-Embedding-Modell-Asset per verifiziertem Download statt Git-Commit
# (specs/decisions/0033-modell-asset-download-statt-commit-label-embedder.md): das Asset
# (label_embedder.onnx, ~113 MiB) ueberschreitet GitHubs 100-MiB-Hard-Limit fuer einen regulaeren
# Push und ist deshalb nicht mehr Teil des Git-Repositorys. Funktional aequivalent zu
# scripts/fetch-label-embedder-model.sh (Repo-Wurzel-Skript fuer CI/lokales Bare-Metal-Dev-Setup),
# hier als eigener RUN-Schritt statt eines direkten Skript-Aufrufs, weil der Docker-Build-Kontext
# dieses Images auf ./backend beschraenkt ist (docker-compose.yml: "build: ./backend") -
# scripts/liegt eine Ebene darueber, ausserhalb des Kontexts, ein COPY von dort ist nicht moeglich,
# ohne den Build-Kontext auf das gesamte Repository auszuweiten. Derselbe SHA256-Hash wie im
# Skript (aus dem bereits kopierten src/photosort/label_embedding.py gelesen, nicht hier ein
# zweites Mal fest verdrahtet) - muss vor "pip install ." vorliegen, damit
# [tool.setuptools.package-data] (pyproject.toml) es wie die uebrigen Assets ins installierte
# Package uebernimmt. python3 statt curl - vermeidet eine neue apt-Abhaengigkeit fuer einen
# einzelnen Download, python3 ist im Basisimage bereits vorhanden.
RUN EXPECTED_SHA256="$(sed -n 's/^LABEL_EMBEDDER_ONNX_SHA256 = "\([0-9a-f]\{64\}\)"$/\1/p' src/photosort/label_embedding.py)" \
    && python3 -c "import urllib.request; urllib.request.urlretrieve('https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/resolve/main/onnx/model_int8.onnx', 'src/photosort/assets/label_embedder.onnx')" \
    && echo "${EXPECTED_SHA256}  src/photosort/assets/label_embedder.onnx" | sha256sum -c -

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "photosort.main:app", "--host", "0.0.0.0", "--port", "8000"]
