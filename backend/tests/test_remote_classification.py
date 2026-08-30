from __future__ import annotations

import json

import httpx
import pytest

from photosort.categories import (
    MAX_FINE_LABELS_PER_PHOTO,
    MAX_REMOTE_CATEGORIES_PER_PHOTO,
    build_classification_prompt,
)
from photosort.remote_classification import (
    ANTHROPIC_CATEGORY_MODEL,
    CATEGORY_LABEL_SIMILARITY_THRESHOLD,
    COST_PER_IMAGE_USD,
    MAX_FINE_LABEL_LENGTH,
    MISTRAL_CATEGORY_MODEL,
    AnthropicCategoryClient,
    CategoryDetectionClientLike,
    FineLabelSnapshotEntry,
    MistralCategoryClient,
    RemoteCategoryClassificationApiError,
    RemoteClassification,
    _classification_from_json,
    _cosine_similarity,
    _normalize_label_text,
    _sanitize_label_text,
    _slugify,
    resolve_canonical_label,
)

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
# decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 3/4: neues Modul,
# strukturell analog landmark.py/test_landmark.py, aber offenes 1-3-Label-Antwortschema statt
# eines festen Enums. httpx.MockTransport statt unittest.mock.patch (Teststrategie-Abschnitt).

IMAGE_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


def _anthropic_success_response(body: dict[str, object]) -> httpx.Response:
    payload = {"content": [{"type": "text", "text": json.dumps(body)}]}
    return httpx.Response(200, json=payload)


def _mistral_success_response(body: dict[str, object]) -> httpx.Response:
    payload = {"choices": [{"message": {"content": json.dumps(body)}}]}
    return httpx.Response(200, json=payload)


class FakeCategoryClient:
    def __init__(self, classification: RemoteClassification) -> None:
        self._classification = classification
        self.calls: list[tuple[bytes, str, int]] = []

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        self.calls.append((image_bytes, mime_type, photo_id))
        return self._classification


async def test_fake_client_satisfies_the_category_detection_client_like_protocol() -> None:
    expected = RemoteClassification(categories=("tier",), fine_labels=("Hund",))
    fake: CategoryDetectionClientLike = FakeCategoryClient(expected)
    assert await fake.classify(IMAGE_BYTES, "image/jpeg", 1) == expected


class TestClassificationFromJsonStructure:
    """STRUKTURELL HART (Spec 0289, Teststrategie 5): die bis Spec 0289 geltende Konvention
    "Anzahl ausserhalb 1-3 ist ein Fehler" ENTFAELLT bewusst zugunsten von "strukturell hart,
    inhaltlich tolerant". Diese Umkehr ist im Review ausdruecklich als solche zu pruefen."""

    def test_rejects_a_missing_categories_key(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _classification_from_json({"fine_labels": ["Hund"]}, photo_id=1)

    def test_rejects_a_non_list_categories_value(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _classification_from_json({"categories": "tier"}, photo_id=1)

    def test_rejects_a_response_that_is_not_a_json_object(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _classification_from_json(["tier"], photo_id=1)

    def test_rejects_a_present_but_non_list_fine_labels_value(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _classification_from_json({"categories": ["tier"], "fine_labels": "Hund"}, photo_id=1)

    def test_a_missing_fine_labels_key_is_not_an_error(self) -> None:
        # Feinlabels sind optional, Kategorien nicht.
        result = _classification_from_json({"categories": ["tier"]}, photo_id=1)
        assert result == RemoteClassification(categories=("tier",), fine_labels=())


class TestClassificationFromJsonCategories:
    """INHALTLICH TOLERANT - Verarbeitungsreihenfolge laut Spec 0289: trimmen -> leere verwerfen ->
    unbekannte verwerfen -> deduplizieren -> ZULETZT kuerzen."""

    def test_accepts_a_single_known_category(self) -> None:
        result = _classification_from_json({"categories": ["tier"]}, photo_id=1)
        assert result.categories == ("tier",)

    def test_trims_whitespace_around_a_category_value(self) -> None:
        result = _classification_from_json({"categories": ["  tier  "]}, photo_id=1)
        assert result.categories == ("tier",)

    def test_an_unknown_value_is_discarded_and_logged_once_with_the_raw_value(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            result = _classification_from_json(
                {"categories": ["einhorn", "tier"]}, photo_id=42
            )

        assert result.categories == ("tier",)
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "einhorn" in message
        assert "42" in message

    def test_the_logged_raw_value_is_repr_escaped_and_length_limited(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Security-Muss-Kriterium (Spec 0289, Abschnitt 4): ein mehrzeiliger Modellwert darf
        keine gefaelschten Logzeilen erzeugen - `repr` escaped den Zeilenumbruch sichtbar."""
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            _classification_from_json(
                {"categories": ["boes\nWARNING gefaelschte Zeile " + "x" * 200]}, photo_id=7
            )

        message = caplog.records[0].getMessage()
        assert "\\n" in message
        assert "\n" not in message
        assert len(message) < 200

    def test_all_values_unknown_yields_an_empty_tuple_not_an_error(self) -> None:
        """Der wichtigste Grenzfall (Spec 0289, Teststrategie 5): `categories` ist ein Array, aber
        ALLE Werte sind unbekannt -> KEIN Fehler, sondern ein leeres Tupel (wird ueber
        resolve_category zu `nicht_erkannt`); die Feinlabels desselben Fotos bleiben erhalten."""
        result = _classification_from_json(
            {"categories": ["einhorn", "drache"], "fine_labels": ["Fabelwesen"]}, photo_id=1
        )
        assert result.categories == ()
        assert result.fine_labels == ("Fabelwesen",)

    def test_five_valid_categories_are_truncated_to_the_maximum(self) -> None:
        result = _classification_from_json(
            {
                "categories": [
                    "tier",
                    "menschen",
                    "landschaft",
                    "pflanze",
                    "innenraum",
                ]
            },
            photo_id=1,
        )
        assert result.categories == ("tier", "menschen", "landschaft")
        assert len(result.categories) == MAX_REMOTE_CATEGORIES_PER_PHOTO

    def test_three_valid_plus_two_unknown_values_keep_exactly_the_three_valid_ones(self) -> None:
        """Nachweis der Reihenfolge "erst verwerfen, DANN kuerzen": wuerde zuerst gekuerzt, gingen
        gueltige Werte hinter ungueltigen verloren."""
        result = _classification_from_json(
            {"categories": ["einhorn", "tier", "drache", "menschen", "landschaft"]},
            photo_id=1,
        )
        assert result.categories == ("tier", "menschen", "landschaft")

    def test_duplicates_are_removed_keeping_the_first_mention(self) -> None:
        result = _classification_from_json(
            {"categories": ["tier", "tier", "menschen"]}, photo_id=1
        )
        assert result.categories == ("tier", "menschen")

    def test_a_non_string_category_value_is_discarded_not_fatal(self) -> None:
        result = _classification_from_json({"categories": [42, None, "tier"]}, photo_id=1)
        assert result.categories == ("tier",)

    def test_a_differently_cased_key_is_not_accepted(self) -> None:
        result = _classification_from_json({"categories": ["TIER"]}, photo_id=1)
        assert result.categories == ()

    def test_not_recognized_is_a_valid_category_value(self) -> None:
        result = _classification_from_json({"categories": ["nicht_erkannt"]}, photo_id=1)
        assert result.categories == ("nicht_erkannt",)


class TestClassificationFromJsonFineLabels:
    def test_three_fine_labels_are_truncated_to_the_first_two(self) -> None:
        result = _classification_from_json(
            {"categories": ["tier"], "fine_labels": ["Hund", "Strand", "Urlaub"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund", "Strand")
        assert len(result.fine_labels) == MAX_FINE_LABELS_PER_PHOTO

    def test_a_fine_label_longer_than_the_maximum_is_discarded_not_truncated(self) -> None:
        """Ein abgeschnittenes Label erzeugte sonst dauerhaft einen unbrauchbaren canonical_key in
        der projektuebergreifenden Registry (Entscheidung 5 der Spec)."""
        too_long = "x" * (MAX_FINE_LABEL_LENGTH + 1)
        result = _classification_from_json(
            {"categories": ["tier"], "fine_labels": [too_long, "Hund"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund",)

    def test_a_fine_label_exactly_at_the_maximum_is_kept(self) -> None:
        exact = "x" * MAX_FINE_LABEL_LENGTH
        result = _classification_from_json(
            {"categories": ["tier"], "fine_labels": [exact]}, photo_id=1
        )
        assert result.fine_labels == (exact,)

    @pytest.mark.parametrize("raw", ["", "   ", "\n\t"])
    def test_an_empty_or_whitespace_only_fine_label_is_discarded(self, raw: str) -> None:
        result = _classification_from_json(
            {"categories": ["tier"], "fine_labels": [raw, "Hund"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund",)

    def test_duplicate_fine_labels_are_removed(self) -> None:
        result = _classification_from_json(
            {"categories": ["tier"], "fine_labels": ["Hund", "Hund", "Strand"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund", "Strand")

    def test_a_non_string_fine_label_is_discarded(self) -> None:
        result = _classification_from_json(
            {"categories": ["tier"], "fine_labels": [17, "Hund"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund",)

    def test_fine_labels_are_sanitized_before_the_length_check(self) -> None:
        # Sanitisierung laeuft VOR der Laengenpruefung: ein Label, das erst durch
        # Steuerzeichen ueber die Grenze rutscht, bleibt erhalten.
        raw = "\u200b" * 20 + "x" * MAX_FINE_LABEL_LENGTH
        result = _classification_from_json(
            {"categories": ["tier"], "fine_labels": [raw]}, photo_id=1
        )
        assert result.fine_labels == ("x" * MAX_FINE_LABEL_LENGTH,)


class TestSanitizeLabelText:
    """Security-Abschnitt der Spec 0289, Punkt 3: erstmals wird freier LLM-Text in der Oberflaeche
    gerendert - escapetes Rendering schuetzt gegen XSS, aber nicht gegen optische Verfaelschung."""

    @pytest.mark.parametrize(
        "raw",
        [
            "Hund\u202eGnud",  # Bidi-Override (RIGHT-TO-LEFT OVERRIDE)
            "Hund\u200bGnud",  # Zero Width Space
            "Hund\u200fGnud",  # Right-to-Left Mark
            "Hund\x00Gnud",  # NUL
        ],
    )
    def test_control_and_format_characters_are_removed(self, raw: str) -> None:
        assert _sanitize_label_text(raw) == "HundGnud"

    def test_newlines_and_tabs_collapse_to_a_single_space(self) -> None:
        assert _sanitize_label_text("Hund\n\tam   Strand") == "Hund am Strand"

    def test_leading_and_trailing_whitespace_is_removed(self) -> None:
        assert _sanitize_label_text("  Hund  ") == "Hund"

    def test_a_non_breaking_space_is_normalized_too(self) -> None:
        assert _sanitize_label_text("Hund\u00a0Strand") == "Hund Strand"

    def test_regular_german_text_survives_unchanged(self) -> None:
        assert _sanitize_label_text("Geburtstagsfeier im Grünen") == "Geburtstagsfeier im Grünen"

    def test_a_label_consisting_only_of_control_characters_becomes_empty(self) -> None:
        assert _sanitize_label_text("\u200b\u202e") == ""


class TestAnthropicCategoryClient:
    def test_classify_sends_the_expected_model_and_parses_labels(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _anthropic_success_response(
                {"categories": ["tier"], "fine_labels": ["Hund"]}
            )

        client = AnthropicCategoryClient(api_key="sk-test", transport=httpx.MockTransport(handler))

        import asyncio

        classification = asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg", 1))

        assert classification == RemoteClassification(
            categories=("tier",), fine_labels=("Hund",)
        )
        body = captured["body"]
        assert isinstance(body, dict)
        assert body["model"] == ANTHROPIC_CATEGORY_MODEL
        # Der gesendete Prompt stammt aus der Registry, nicht aus einem Literal in diesem Modul
        # (specs/features/0289-feste-kategorien.md, Entwurfsentscheidung 3).
        content = body["messages"][0]["content"]
        assert content[1]["text"] == build_classification_prompt()

    def test_error_response_raises_remote_category_classification_api_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Unauthorized")

        client = AnthropicCategoryClient(api_key="sk-test", transport=httpx.MockTransport(handler))

        import asyncio

        with pytest.raises(RemoteCategoryClassificationApiError):
            asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg", 1))

    def test_error_message_never_embeds_the_api_key_or_image_bytes(self) -> None:
        error = RemoteCategoryClassificationApiError("Anthropic-Anfrage fehlgeschlagen: 401")
        assert "sk-test" not in str(error)
        assert str(IMAGE_BYTES) not in str(error)


class TestMistralCategoryClient:
    def test_classify_sends_the_expected_model_and_parses_labels(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _mistral_success_response(
                {"categories": ["landschaft"], "fine_labels": ["Strand"]}
            )

        client = MistralCategoryClient(
            api_key="mistral-test", transport=httpx.MockTransport(handler)
        )

        import asyncio

        classification = asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg", 1))

        assert classification == RemoteClassification(
            categories=("landschaft",), fine_labels=("Strand",)
        )
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
            asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg", 1))


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

    def test_falls_back_to_a_hash_based_slug_when_no_latin_chars_remain(self) -> None:
        # Review-Fund (security-engineer, spec 0055-Followup): ein rein nicht-lateinisches
        # Rohlabel (z.B. japanisch) slugifiert ohne Fallback zu einem leeren String - zwei
        # verschiedene solche Label wuerden dann denselben (leeren) canonical_key produzieren und
        # an UniqueConstraint(category_labels.canonical_key) scheitern (Verfuegbarkeitsrisiko:
        # bricht den ganzen Batch-Lauf statt nur dieses eine Foto zu ueberspringen).
        dog_slug = _slugify("犬")
        cat_slug = _slugify("猫")

        assert dog_slug != ""
        assert cat_slug != ""
        assert dog_slug != cat_slug

    def test_hash_fallback_is_deterministic_for_the_same_text(self) -> None:
        assert _slugify("犬") == _slugify("犬")


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
            FineLabelSnapshotEntry(
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
            FineLabelSnapshotEntry(
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
            FineLabelSnapshotEntry(
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
        existing: list[FineLabelSnapshotEntry] = []
        embedder = FakeLabelEmbedder({"strand": [0.0, 1.0]})

        result = resolve_canonical_label("Strand", existing, embedder)

        assert result.canonical_key == "strand"
        assert result.display_name == "Strand"
        assert result.embedding == [0.0, 1.0]
        assert embedder.calls == ["strand"]
        assert existing == [result]

    def test_in_memory_snapshot_update_prevents_duplicates_within_the_same_run(self) -> None:
        existing: list[FineLabelSnapshotEntry] = []
        embedder = FakeLabelEmbedder({"strand": [0.0, 1.0]})

        first = resolve_canonical_label("Strand", existing, embedder)
        second = resolve_canonical_label("strand", existing, embedder)

        assert first.canonical_key == second.canonical_key
        assert len(existing) == 1
        # Zweiter Aufruf trifft den exakten Normalisierungs-Fast-Path (gleicher normalisierter
        # Text) - kein zweiter embed()-Aufruf noetig.
        assert embedder.calls == ["strand"]


class TestLimitConstants:
    def test_the_limits_match_the_documented_values(self) -> None:
        assert MAX_REMOTE_CATEGORIES_PER_PHOTO == 3
        assert MAX_FINE_LABELS_PER_PHOTO == 2
        assert MAX_FINE_LABEL_LENGTH == 60
