from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

from photosort.label_embedding import (
    EMBEDDING_DIMENSION,
    LABEL_EMBEDDER_ONNX_PATH,
    LABEL_EMBEDDER_ONNX_SHA256,
    LABEL_EMBEDDER_TOKENIZER_PATH,
    LABEL_EMBEDDER_TOKENIZER_SHA256,
    LabelEmbedderLike,
    _mean_pool_and_normalize,
)

# specs/decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 4,
# specs/architecture/0002-testkonzept.md ("label_embedding.py"): analog test_aesthetics.py/
# test_classification.py - ein eigener Integritaets-Test je gepinntem Modell-Asset.


class TestLabelEmbedderAssets:
    def test_committed_onnx_file_matches_the_documented_sha256(self) -> None:
        digest = hashlib.sha256(LABEL_EMBEDDER_ONNX_PATH.read_bytes()).hexdigest()
        assert digest == LABEL_EMBEDDER_ONNX_SHA256

    def test_committed_tokenizer_file_matches_the_documented_sha256(self) -> None:
        digest = hashlib.sha256(LABEL_EMBEDDER_TOKENIZER_PATH.read_bytes()).hexdigest()
        assert digest == LABEL_EMBEDDER_TOKENIZER_SHA256


class TestMeanPoolAndNormalize:
    """Reine, DB-/Modell-freie Funktion (kein onnxruntime/tokenizers-Import noetig) - haelt die
    Pooling-/Normierungslogik selbst ohne echtes Modell testbar, analog aesthetics.py::
    _preprocess."""

    def test_pools_only_over_attended_tokens_and_ignores_padding(self) -> None:
        # Zwei "echte" Token-Embeddings + ein Padding-Token, das die Attention-Maske ausschliesst -
        # das Padding-Token hat absichtlich einen stark abweichenden Wert, um sicherzustellen, dass
        # es tatsaechlich ignoriert wird (nicht nur zufaellig neutral waere).
        token_embeddings = [[1.0, 0.0], [0.0, 1.0], [100.0, 100.0]]
        attention_mask = [1, 1, 0]
        pooled = _mean_pool_and_normalize(token_embeddings, attention_mask)
        # Erwarteter Mittelwert vor Normierung: (0.5, 0.5) -> normiert (1/sqrt(2), 1/sqrt(2)).
        expected = pytest.approx(1 / math.sqrt(2), abs=1e-6)
        assert pooled == [expected, expected]

    def test_output_is_l2_normalized(self) -> None:
        token_embeddings = [[3.0, 4.0]]
        attention_mask = [1]
        pooled = _mean_pool_and_normalize(token_embeddings, attention_mask)
        norm = math.sqrt(sum(value**2 for value in pooled))
        assert norm == pytest.approx(1.0, abs=1e-6)

    def test_degenerate_all_zero_mask_returns_zero_vector_without_crashing(self) -> None:
        # Verteidigungslinie gegen ZeroDivisionError/NaN bei einer (praktisch nie erwarteten)
        # komplett leeren Attention-Maske - analog aesthetics.py::compute_aesthetics_score's
        # dokumentiertem Fallback fuer eine degenerierte Eingabe.
        token_embeddings = [[1.0, 2.0]]
        attention_mask = [0]
        pooled = _mean_pool_and_normalize(token_embeddings, attention_mask)
        assert pooled == [0.0, 0.0]


class TestLabelEmbedderLikeProtocol:
    def test_a_fake_satisfies_the_protocol(self) -> None:
        class FakeLabelEmbedder:
            def embed(self, text: str) -> list[float]:
                return [0.0] * EMBEDDING_DIMENSION

        fake: LabelEmbedderLike = FakeLabelEmbedder()
        vector = fake.embed("hund")
        assert len(vector) == EMBEDDING_DIMENSION


class TestRealAssetOutputDimension:
    """Dedizierter Sanity-Test der ECHTEN Assets (specs/architecture/0002-testkonzept.md,
    label_embedding.py-Sektion) - direkt ueber onnxruntime/tokenizers, NICHT ueber
    build_label_embedder() (das laeuft wie build_face_detector/build_aesthetics_model NIE
    automatisiert, reine Ladezeit-Begruendung). Verifiziert 384-dim, L2-normiert, sowie dass
    ein deutlich naeherer Begriff ("Hund"/"Hunde") eine hoehere Kosinus-Aehnlichkeit hat als ein
    unverwandter ("Hund"/"Strand")."""

    def test_real_assets_produce_a_384_dim_l2_normalized_embedding(self) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(LABEL_EMBEDDER_TOKENIZER_PATH))
        session = ort.InferenceSession(
            str(LABEL_EMBEDDER_ONNX_PATH), providers=["CPUExecutionProvider"]
        )

        def embed(text: str) -> list[float]:
            encoding = tokenizer.encode(text)
            feed = {
                "input_ids": np.array([encoding.ids], dtype=np.int64),
                "attention_mask": np.array([encoding.attention_mask], dtype=np.int64),
                "token_type_ids": np.array([encoding.type_ids], dtype=np.int64),
            }
            outputs = session.run(None, feed)
            last_hidden_state = outputs[0][0]
            return _mean_pool_and_normalize(last_hidden_state.tolist(), encoding.attention_mask)

        hund = embed("Hund")
        hunde = embed("Hunde")
        strand = embed("Strand")

        assert len(hund) == EMBEDDING_DIMENSION
        norm = math.sqrt(sum(value**2 for value in hund))
        assert norm == pytest.approx(1.0, abs=1e-6)

        def cosine(a: list[float], b: list[float]) -> float:
            return sum(x * y for x, y in zip(a, b, strict=True))

        assert cosine(hund, hunde) > cosine(hund, strand)
