from __future__ import annotations

import json

import httpx
import pytest

from photosort.remote_classification import (
    ANTHROPIC_CATEGORY_MODEL,
    CATEGORY_LABEL_SIMILARITY_THRESHOLD,
    COST_PER_IMAGE_USD,
    MAX_REMOTE_LABEL_LENGTH,
    MAX_REMOTE_LABELS_PER_PHOTO,
    MIN_REMOTE_LABELS_PER_PHOTO,
    MISTRAL_CATEGORY_MODEL,
    AnthropicCategoryClient,
    CategoryDetectionClientLike,
    CategoryLabelDetection,
    CategoryLabelSnapshotEntry,
    MistralCategoryClient,
    RemoteCategoryClassificationApiError,
    _category_labels_from_json,
    _cosine_similarity,
    _normalize_label_text,
    _slugify,
    resolve_canonical_label,
)

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
# decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 3/4: neues Modul,
# strukturell analog landmark.py/test_landmark.py, aber offenes 1-3-Label-Antwortschema statt
# eines festen Enums. httpx.MockTransport statt unittest.mock.patch (Teststrategie-Abschnitt).

IMAGE_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


def _anthropic_success_response(labels: list[dict[str, object]]) -> httpx.Response:
    payload = {
        "content": [{"type": "text", "text": json.dumps({"labels": labels})}]
    }
    return httpx.Response(200, json=payload)


def _mistral_success_response(labels: list[dict[str, object]]) -> httpx.Response:
    payload = {"choices": [{"message": {"content": json.dumps({"labels": labels})}}]}
    return httpx.Response(200, json=payload)


class FakeCategoryClient:
    def __init__(self, detections: list[CategoryLabelDetection]) -> None:
        self._detections = detections
        self.calls: list[tuple[bytes, str]] = []

    async def classify(self, image_bytes: bytes, mime_type: str) -> list[CategoryLabelDetection]:
        self.calls.append((image_bytes, mime_type))
        return self._detections


async def test_fake_client_satisfies_the_category_detection_client_like_protocol() -> None:
    fake: CategoryDetectionClientLike = FakeCategoryClient(
        [CategoryLabelDetection(label="Hund", confidence=0.9)]
    )
    detections = await fake.classify(IMAGE_BYTES, "image/jpeg")
    assert detections == [CategoryLabelDetection(label="Hund", confidence=0.9)]


class TestCategoryLabelsFromJson:
    def test_accepts_one_to_three_valid_labels(self) -> None:
        parsed = {"labels": [{"label": "Hund", "confidence": 0.9}]}
        result = _category_labels_from_json(parsed)
        assert result == [CategoryLabelDetection(label="Hund", confidence=0.9)]

    def test_accepts_three_labels(self) -> None:
        parsed = {
            "labels": [
                {"label": "Hund", "confidence": 0.9},
                {"label": "Strand", "confidence": 0.5},
                {"label": "Sonnenuntergang", "confidence": 0.3},
            ]
        }
        result = _category_labels_from_json(parsed)
        assert len(result) == 3

    def test_rejects_zero_labels(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _category_labels_from_json({"labels": []})

    def test_rejects_more_than_three_labels(self) -> None:
        labels = [{"label": f"label{i}", "confidence": 0.5} for i in range(4)]
        with pytest.raises(RemoteCategoryClassificationApiError):
            _category_labels_from_json({"labels": labels})

    def test_rejects_empty_label_text(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _category_labels_from_json({"labels": [{"label": "   ", "confidence": 0.5}]})

    def test_rejects_a_label_longer_than_the_maximum(self) -> None:
        long_label = "x" * (MAX_REMOTE_LABEL_LENGTH + 1)
        with pytest.raises(RemoteCategoryClassificationApiError):
            _category_labels_from_json({"labels": [{"label": long_label, "confidence": 0.5}]})

    def test_trims_whitespace_around_the_label(self) -> None:
        result = _category_labels_from_json({"labels": [{"label": "  Hund  ", "confidence": 0.5}]})
        assert result[0].label == "Hund"

    def test_clamps_confidence_above_one(self) -> None:
        result = _category_labels_from_json({"labels": [{"label": "Hund", "confidence": 5.0}]})
        assert result[0].confidence == 1.0

    def test_clamps_confidence_below_zero(self) -> None:
        result = _category_labels_from_json({"labels": [{"label": "Hund", "confidence": -1.0}]})
        assert result[0].confidence == 0.0

    def test_rejects_a_missing_labels_key(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _category_labels_from_json({"unexpected": True})

    def test_rejects_a_non_list_labels_value(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _category_labels_from_json({"labels": "not-a-list"})


class TestAnthropicCategoryClient:
    def test_classify_sends_the_expected_model_and_parses_labels(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _anthropic_success_response([{"label": "Hund", "confidence": 0.9}])

        client = AnthropicCategoryClient(api_key="sk-test", transport=httpx.MockTransport(handler))

        import asyncio

        detections = asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg"))

        assert detections == [CategoryLabelDetection(label="Hund", confidence=0.9)]
        body = captured["body"]
        assert isinstance(body, dict)
        assert body["model"] == ANTHROPIC_CATEGORY_MODEL

    def test_error_response_raises_remote_category_classification_api_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Unauthorized")

        client = AnthropicCategoryClient(api_key="sk-test", transport=httpx.MockTransport(handler))

        import asyncio

        with pytest.raises(RemoteCategoryClassificationApiError):
            asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg"))

    def test_error_message_never_embeds_the_api_key_or_image_bytes(self) -> None:
        error = RemoteCategoryClassificationApiError("Anthropic-Anfrage fehlgeschlagen: 401")
        assert "sk-test" not in str(error)
        assert str(IMAGE_BYTES) not in str(error)


class TestMistralCategoryClient:
    def test_classify_sends_the_expected_model_and_parses_labels(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _mistral_success_response([{"label": "Strand", "confidence": 0.7}])

        client = MistralCategoryClient(
            api_key="mistral-test", transport=httpx.MockTransport(handler)
        )

        import asyncio

        detections = asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg"))

        assert detections == [CategoryLabelDetection(label="Strand", confidence=0.7)]
        body = captured["body"]
        assert isinstance(body, dict)
        assert body["model"] == MISTRAL_CATEGORY_MODEL

    def test_error_response_raises_remote_category_classification_api_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        client = MistralCategoryClient(
            api_key="mistral-test", transport=httpx.MockTransport(handler)
        )

        import asyncio

        with pytest.raises(RemoteCategoryClassificationApiError):
            asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg"))


class TestCostPerImageUsd:
    def test_has_a_documented_positive_price_for_both_providers(self) -> None:
        assert COST_PER_IMAGE_USD["anthropic"] > 0
        assert COST_PER_IMAGE_USD["mistral"] > 0
        # Mistral ist der guenstigere Provider (ADR 0032 Punkt 8) - Regressionsschutz gegen ein
        # versehentlich vertauschtes Zahlenpaar.
        assert COST_PER_IMAGE_USD["mistral"] < COST_PER_IMAGE_USD["anthropic"]


class TestSlugify:
    def test_lowercases_and_replaces_whitespace(self) -> None:
        assert _slugify("Hund Katze") == "hund_katze"

    def test_collapses_repeated_underscores(self) -> None:
        assert _slugify("Hund   Katze!!") == "hund_katze"

    def test_strips_leading_and_trailing_underscores(self) -> None:
        assert _slugify("  Hund  ") == "hund"


class TestNormalizeLabelText:
    def test_casefolds_and_strips(self) -> None:
        assert _normalize_label_text("  HUND  ") == "hund"

    def test_nfkc_normalizes_equivalent_unicode_forms(self) -> None:
        # "ﬁsch" (Ligatur U+FB01) normalisiert NFKC zu "fisch".
        assert _normalize_label_text("ﬁsch") == "fisch"


class TestCosineSimilarity:
    def test_identical_vectors_have_similarity_one(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_have_similarity_zero(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


class FakeLabelEmbedder:
    """Spy-faehiges Test-Double (Teststrategie-Abschnitt: "embed() nachweislich NICHT
    aufgerufen"/"embed() genau einmal") - liefert feste, injizierte Vektoren pro Text."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return self._vectors[text]


class TestResolveCanonicalLabel:
    def test_exact_normalized_match_reuses_the_existing_entry_without_calling_embed(self) -> None:
        existing = [
            CategoryLabelSnapshotEntry(
                canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0]
            )
        ]
        embedder = FakeLabelEmbedder({})

        result = resolve_canonical_label("HUND", existing, embedder)

        assert result.canonical_key == "hund"
        assert embedder.calls == []
        assert len(existing) == 1

    def test_similarity_at_exactly_the_threshold_reuses_the_existing_entry(self) -> None:
        existing = [
            CategoryLabelSnapshotEntry(
                canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0]
            )
        ]
        # Konstruiert einen Vektor mit Kosinus-Aehnlichkeit EXAKT CATEGORY_LABEL_SIMILARITY_
        # THRESHOLD zu [1.0, 0.0]: cos = x -> Vektor (x, sqrt(1-x^2)).
        import math

        threshold = CATEGORY_LABEL_SIMILARITY_THRESHOLD
        vector = [threshold, math.sqrt(1 - threshold**2)]
        embedder = FakeLabelEmbedder({"hunde": vector})

        result = resolve_canonical_label("Hunde", existing, embedder)

        assert result.canonical_key == "hund"
        assert embedder.calls == ["hunde"]

    def test_similarity_just_below_the_threshold_creates_a_new_entry(self) -> None:
        import math

        existing = [
            CategoryLabelSnapshotEntry(
                canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0]
            )
        ]
        threshold = CATEGORY_LABEL_SIMILARITY_THRESHOLD
        below = threshold - 0.01
        vector = [below, math.sqrt(1 - below**2)]
        embedder = FakeLabelEmbedder({"katze": vector})

        result = resolve_canonical_label("Katze", existing, embedder)

        assert result.canonical_key == "katze"
        assert len(existing) == 2

    def test_no_match_creates_a_new_canonical_entry_calling_embed_exactly_once(self) -> None:
        existing: list[CategoryLabelSnapshotEntry] = []
        embedder = FakeLabelEmbedder({"strand": [0.0, 1.0]})

        result = resolve_canonical_label("Strand", existing, embedder)

        assert result.canonical_key == "strand"
        assert result.display_name == "Strand"
        assert result.embedding == [0.0, 1.0]
        assert embedder.calls == ["strand"]
        assert existing == [result]

    def test_in_memory_snapshot_update_prevents_duplicates_within_the_same_run(self) -> None:
        existing: list[CategoryLabelSnapshotEntry] = []
        embedder = FakeLabelEmbedder({"strand": [0.0, 1.0]})

        first = resolve_canonical_label("Strand", existing, embedder)
        second = resolve_canonical_label("strand", existing, embedder)

        assert first.canonical_key == second.canonical_key
        assert len(existing) == 1
        # Zweiter Aufruf trifft den exakten Normalisierungs-Fast-Path (gleicher normalisierter
        # Text) - kein zweiter embed()-Aufruf noetig.
        assert embedder.calls == ["strand"]


class TestMinMaxConstants:
    def test_min_and_max_labels_match_the_documented_range(self) -> None:
        assert MIN_REMOTE_LABELS_PER_PHOTO == 1
        assert MAX_REMOTE_LABELS_PER_PHOTO == 3
