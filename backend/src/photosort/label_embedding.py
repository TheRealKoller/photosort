from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
# decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 4: eigenes,
# isoliertes Modul (analog aesthetics.py) - haelt die neue onnxruntime/tokenizers-Abhaengigkeit
# auf genau den Importpfad begrenzt, der sie tatsaechlich braucht (nur build_label_embedder()
# importiert die beiden Pakete, lokal, analog dem lokalen tensorflow-Import in
# aesthetics.py::build_aesthetics_model). Der Rest dieses Moduls (Pooling/Normierung) ist reines
# Python/keine schwere Abhaengigkeit noetig, um importiert/getestet zu werden.

# Modellwahl (ADR 0032 Punkt 4, research-engineer, 2026-08-23):
# sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, int8-quantisierte ONNX-Variante -
# ueber onnxruntime+tokenizers ausgefuehrt, KEIN PyTorch/TensorFlow-Hub (Begruendung siehe ADR).
#
# Konkretes Asset-Paar (developer-Verifikation beim TDD-Einstieg, 2026-08-23): statt selbst eine
# fp32 -> int8-Quantisierung durchzufuehren (bräuchte torch+optimum als temporaere Build-
# Abhaengigkeit, zusaetzliches Risiko/Aufwand ohne fachlichen Mehrwert), wird die bereits
# vorquantisierte ONNX-Variante von "Xenova/paraphrase-multilingual-MiniLM-L12-v2"
# (huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2, MIT-Lizenz, Transformers.js-
# Community-Export DESSELBEN in der ADR genannten Basismodells, config.json bestaetigt
# "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" als _name_or_path, hidden_size=384)
# verwendet - "onnx/model_int8.onnx" + "tokenizer.json". Beide werden SHA256-gepinnt verifiziert,
# aber NICHT mehr beide eingecheckt (Copilot-Review-Fund, PR #201 - korrigiert diesen zuvor
# veralteten Satz): "tokenizer.json" (label_embedder_tokenizer.json, 17 MB) bleibt wie gewohnt
# committet, "model_int8.onnx" (label_embedder.onnx, ~113 MiB) ueberschreitet GitHubs 100-MiB-
# Push-Limit und wird stattdessen bei Bedarf per verifiziertem Download bezogen (kein Commit-
# Versuch mehr!) - siehe specs/decisions/0033-modell-asset-download-statt-commit-label-embedder.md,
# scripts/fetch-label-embedder-model.sh (aufgerufen aus backend/Dockerfile, .github/workflows/
# ci.yml, sowie einmalig manuell im lokalen Bare-Metal-Dev-Setup, docs/setup.md). Reale Groesse
# VOR dem urspruenglichen (inzwischen wieder entfernten) Commit gemessen (ADR-Pflicht):
# model_int8.onnx 118.054.609 Bytes (~113 MiB), tokenizer.json 17.082.913 Bytes (~16 MiB) - liegt
# innerhalb der in der ADR grob geschaetzten Bandbreite (~100-150 MB), kein Ruecksprache-Anlass.
# Ein-Wort-Cosinus-Stichprobe vor dem Commit verifiziert (siehe TestRealAssetOutputDimension):
# "Hund"/"Hunde"/"dog" clustern (Kosinus 0.92-0.99), "Katze"/"Strand" liegen deutlich darunter
# (< 0.4) - CATEGORY_LABEL_SIMILARITY_THRESHOLD=0.78 (remote_classification.py) liegt komfortabel
# zwischen beiden Gruppen.
LABEL_EMBEDDER_ONNX_PATH = Path(__file__).parent / "assets" / "label_embedder.onnx"
LABEL_EMBEDDER_TOKENIZER_PATH = Path(__file__).parent / "assets" / "label_embedder_tokenizer.json"

LABEL_EMBEDDER_ONNX_SHA256 = "d6ea442ff6a891daefed7c83b2f596fc5dc66bf697e4d006236f64f34bbcf4c8"
LABEL_EMBEDDER_TOKENIZER_SHA256 = (
    "b60b6b43406a48bf3638526314f3d232d97058bc93472ff2de930d43686fa441"
)

# hidden_size des Basismodells (config.json, verifiziert vor dem Commit) - 384-dimensionale
# Sentence-Embeddings, ADR 0032 Punkt 4.
EMBEDDING_DIMENSION = 384


class LabelEmbedderLike(Protocol):
    """Schmale, injizierbare Schnittstelle (ADR 0032 Punkt 4) - bewusst SYNCHRON (reine, schnelle
    CPU-Inferenz auf kurzen Texten, kein Netzwerk, analog AestheticsModelLike.predict/
    FaceDetectorLike), erlaubt ein Fake in Unit-Tests ohne echtes Modell."""

    def embed(self, text: str) -> list[float]: ...


def _mean_pool_and_normalize(
    token_embeddings: Sequence[Sequence[float]], attention_mask: Sequence[int]
) -> list[float]:
    """Reine, modellfreie Pooling-/Normierungsfunktion (Standard-Rezept fuer Sentence-Transformer-
    Modelle dieser Familie, ADR 0032 Punkt 4): mittelt die Token-Embeddings NUR ueber tatsaechlich
    attendierte Positionen (attention_mask == 1, Padding wird ignoriert), normiert das Ergebnis
    anschliessend L2 auf Einheitslaenge. Degenerierte Eingabe (komplett leere Maske, in der Praxis
    nie erwartet - jedes tokenisierte Label hat mindestens ein Token) liefert einen Nullvektor
    statt eines ZeroDivisionError/NaN, analog aesthetics.py::compute_aesthetics_score."""
    dimension = len(token_embeddings[0]) if token_embeddings else 0
    summed = [0.0] * dimension
    count = 0
    for embedding, mask_value in zip(token_embeddings, attention_mask, strict=True):
        if not mask_value:
            continue
        count += 1
        for index, value in enumerate(embedding):
            summed[index] += value

    if count == 0:
        return [0.0] * dimension

    pooled = [value / count for value in summed]
    norm = sum(value**2 for value in pooled) ** 0.5
    if norm == 0.0:
        return pooled
    return [value / norm for value in pooled]


def build_label_embedder() -> LabelEmbedderLike:
    """Baut das echte, lokale Text-Embedding-Modell (ADR 0032 Punkt 4): laedt den gepinnten
    Tokenizer + die gepinnte ONNX-Session (beide Assets oben, SHA256-verifiziert per eigenem Test,
    KEIN Laufzeit-Download), tokenisiert einen kurzen Text, fuehrt eine InferenceSession-Inferenz
    aus und mean-poolt+normiert das Ergebnis (siehe _mean_pool_and_normalize). Laeuft WIE
    build_face_detector/build_aesthetics_model NIE in einem automatisierten Test (Ladezeit-
    Begruendung, Teststrategie-Abschnitt der Spec) - lokale Importe von onnxruntime/tokenizers
    (analog dem lokalen tensorflow-Import in aesthetics.py), damit die Abhaengigkeit nicht in
    einen leichteren Importpfad einsickert, der sie nicht braucht."""
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(LABEL_EMBEDDER_TOKENIZER_PATH))
    session = ort.InferenceSession(
        str(LABEL_EMBEDDER_ONNX_PATH), providers=["CPUExecutionProvider"]
    )

    class _OnnxLabelEmbedder:
        def embed(self, text: str) -> list[float]:
            import numpy as np

            encoding = tokenizer.encode(text)
            feed = {
                "input_ids": np.array([encoding.ids], dtype=np.int64),
                "attention_mask": np.array([encoding.attention_mask], dtype=np.int64),
                "token_type_ids": np.array([encoding.type_ids], dtype=np.int64),
            }
            outputs = session.run(None, feed)
            last_hidden_state = outputs[0][0]
            return _mean_pool_and_normalize(
                last_hidden_state.tolist(), encoding.attention_mask
            )

    embedder: LabelEmbedderLike = _OnnxLabelEmbedder()
    return embedder
