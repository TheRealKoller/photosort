"""Manifest der Modelldateien, die nicht eingecheckt, sondern geladen werden.

Je Asset: Dateiname unter `assets/`, Bezugsadresse mit FESTER Revision, Groesse und SHA256. Nur
Konstanten, und nichts davon ist ueberschreibbar - keine Umgebungsvariable, kein Build-Argument,
kein Schalter. Ein ueberschreibbarer Hash waere keiner: Vertrauensanker einer geladenen Datei ist
dieser Wert, nicht die Quelle und nicht der Transport.

Geladen wird ausschliesslich ueber `backend/scripts/fetch_model_assets.py` (Image-Build, CI,
Bare-Metal-Setup). Kein Anwendungsmodul laedt selbst; `face_analysis.py` und `label_embedding.py`
kennen aus diesem Manifest nur den Dateinamen. Dieses Modul importiert nur die Standardbibliothek,
damit das Ladeprogramm es vor `pip install .` lesen kann und sein Importgraph keinen
Netzwerk-Client enthaelt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"


@dataclass(frozen=True)
class ModelAsset:
    filename: str
    url: str
    size: int
    sha256: str


LABEL_EMBEDDER_ONNX = ModelAsset(
    filename="label_embedder.onnx",
    url=(
        "https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/resolve/"
        "2c4055b12046f11709e9df2c122e59ffbdc2f900/onnx/model_int8.onnx"
    ),
    size=118_054_609,
    sha256="d6ea442ff6a891daefed7c83b2f596fc5dc66bf697e4d006236f64f34bbcf4c8",
)

# YuNet, MIT-Lizenz.
FACE_DETECTOR = ModelAsset(
    filename="face_detection_yunet_2023mar.onnx",
    url=(
        "https://huggingface.co/opencv/face_detection_yunet/resolve/"
        "3cc26e7f1014a5ee5d74a42acee58bafc9d0a310/face_detection_yunet_2023mar.onnx"
    ),
    size=232_589,
    sha256="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
)

# SFace, Apache-2.0, fp32, 128 Dimensionen.
FACE_RECOGNIZER = ModelAsset(
    filename="face_recognition_sface_2021dec.onnx",
    url=(
        "https://huggingface.co/opencv/face_recognition_sface/resolve/"
        "3d7082438a6e4551e840c9b2bb60b71e8da4b524/face_recognition_sface_2021dec.onnx"
    ),
    size=38_696_353,
    sha256="0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
)

MODEL_ASSETS: tuple[ModelAsset, ...] = (LABEL_EMBEDDER_ONNX, FACE_DETECTOR, FACE_RECOGNIZER)
