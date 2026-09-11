from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

# NIMA (idealo/image-quality-assessment, Apache-2.0, MobileNet-Backbone) ueber tensorflow
# (CPU-only). Eigenes Modul statt Erweiterung von classification.py - haelt die schwere
# tensorflow-Abhaengigkeit auf genau den Importpfad begrenzt, der sie tatsaechlich braucht: NUR
# build_aesthetics_model() importiert tensorflow, lokal (analog zum lokalen mediapipe-Import in
# classification.py::_to_mp_image) - der Rest dieses Moduls (Preprocessing, Normierung) ist reines
# PIL/NumPy und braucht kein installiertes tensorflow, um importiert/getestet zu werden.

# Gepinnte, im Repository eingecheckte Modell-Datei, kein Laufzeit-Download. Quelle:
# idealo/image-quality-assessment (Apache-2.0),
# https://raw.githubusercontent.com/idealo/image-quality-assessment/master/models/MobileNet/
# weights_mobilenet_aesthetic_0.07.hdf5 - "aesthetic"-Variante (nicht "technical"), weil
# ausdruecklich "Bildqualitaet/Schoenheit" (aesthetic quality) statt technischer Bildfehler
# (technical quality, z.B. Kompressionsartefakte) verlangt ist.
#
# WICHTIG (Keras/H5-Modell-Deserialisierung): diese Datei ist eine reine Keras-GEWICHTE-Datei.
# Geladen wird sie ueber `model.load_weights()` auf eine im Code rekonstruierte Architektur (siehe
# build_aesthetics_model unten), NIE ueber `tf.keras.models.load_model()`. Sie traegt keinen
# eingebetteten `model_config`-Header (die Keras-SavedModel-Architektur-Serialisierung, die
# Lambda-Layer/beliebigen Python-Code enthalten koennte), nur benannte Gewichts-Arrays; da
# HDF5-Gewichtsgruppen keinen Python-Code enthalten koennen, ist das
# Lambda-Layer-Deserialisierungsrisiko fuer dieses Asset-Format strukturell nicht anwendbar. Die
# SHA256-Integritaetspruefung bleibt trotzdem als Schutz gegen nachtraegliche Manipulation; sie
# bricht in tests/test_aesthetics.py::TestAestheticsModelAsset (ein Fall).
_ASSET_PATH = Path(__file__).parent / "assets" / "weights_mobilenet_aesthetic_0.07.hdf5"

AESTHETICS_MODEL_SHA256 = "e563ad91b3d47410e45f7238f07ab8f6abd1bd0c4b18a4b0af9c681a21a91cb2"

# NIMA/MobileNet-Eingabegroesse (idealo-Repo: src/utils/utils.py, MobileNet-Standardgroesse).
_INPUT_SIZE = 224

# NIMA liefert eine Wahrscheinlichkeitsverteilung ueber 10 Ratingklassen (Index 0 = Rating 1, Index
# 9 = Rating 10, NIMA-Papier-Konvention).
_RATING_COUNT = 10


class AestheticsModelLike(Protocol):
    """Die schmale Teilmenge der Keras-Model-API, die compute_aesthetics braucht - erlaubt ein
    Test-Double ohne echtes tensorflow-Modell."""

    def predict(self, batch: np.ndarray) -> np.ndarray: ...


def _preprocess(image: Image.Image) -> np.ndarray:
    """Bereitet ein Bild fuer die NIMA/MobileNet-Inferenz vor: RGB, auf 224x224 skaliert, auf
    [-1, 1] normiert (`mobilenet.preprocess_input`-Konvention des idealo-Repos: `x / 127.5 -
    1.0`). Reine PIL/NumPy-Verarbeitung, KEIN tensorflow-Import noetig - haelt diese Funktion
    tensorflow-frei und ohne echtes Modell testbar (siehe compute_aesthetics-Tests)."""
    resized = image.convert("RGB").resize((_INPUT_SIZE, _INPUT_SIZE))
    array = np.asarray(resized, dtype=np.float32)
    normalized = (array / 127.5) - 1.0
    return normalized[np.newaxis, ...]


def compute_aesthetics_score(distribution: Sequence[float]) -> float:
    """`aesthetics`-Kriterium: normiert den Erwartungswert einer NIMA-Ratingverteilung (10 Werte,
    Index 0 = Rating 1, Index 9 = Rating 10) auf [0, 1] ueber `(mean - 1) / 9`, geclippt.
    Degenerierte Eingaben (leere Liste, Summe 0 - z.B. ein Modell-Ladefehler, der eine
    leere/ungueltige Vorhersage liefert) ergeben den dokumentierten Fallback-Wert 0.0 statt eines
    ZeroDivisionError/NaN."""
    total = sum(distribution)
    if total <= 0:
        return 0.0
    mean = sum((index + 1) * value for index, value in enumerate(distribution)) / total
    return max(0.0, min(1.0, (mean - 1.0) / 9.0))


def compute_aesthetics(image: Image.Image, model: AestheticsModelLike) -> float:
    """Fuehrt die echte NIMA-Inferenz aus und normiert das Ergebnis - `model` ist injizierbar
    (siehe AestheticsModelLike), die reale Modellkonstruktion (build_aesthetics_model) laeuft in
    keinem automatisierten Test (Infrastruktur-/CI-Risiko, analog build_face_detector)."""
    batch = _preprocess(image)
    prediction = np.asarray(model.predict(batch))
    distribution = [float(value) for value in prediction.reshape(-1)]
    return compute_aesthetics_score(distribution)


def build_aesthetics_model() -> AestheticsModelLike:
    """Baut das echte NIMA/MobileNet-Modell durch Rekonstruktion der idealo-Architektur
    (MobileNet-Backbone ohne Klassifikationskopf, GlobalAveragePooling, Dropout(0.75),
    Dense(10, softmax) - src/handlers/model_builder.py im idealo-Repo) und Laden NUR der Gewichte
    (`load_weights`, siehe Security-Hinweis beim ASSET_PATH oben) statt eines vollstaendigen
    `load_model()`-Aufrufs. Lokaler tensorflow-Import (analog zum lokalen mediapipe-Import in
    classification.py), damit die schwere Abhaengigkeit nicht in einen leichteren Importpfad
    einsickert, der sie nicht braucht. Wird NIE in einem automatisierten Test aufgerufen
    (Infrastruktur-/CI-Risiko)."""
    from tensorflow.keras.applications.mobilenet import MobileNet
    from tensorflow.keras.layers import Dense, Dropout
    from tensorflow.keras.models import Model

    base_model = MobileNet(
        input_shape=(_INPUT_SIZE, _INPUT_SIZE, 3), include_top=False, pooling="avg", weights=None
    )
    x = Dropout(0.75)(base_model.output)
    x = Dense(_RATING_COUNT, activation="softmax")(x)
    model = Model(base_model.input, x)
    model.load_weights(str(_ASSET_PATH))
    typed_model: AestheticsModelLike = model
    return typed_model
