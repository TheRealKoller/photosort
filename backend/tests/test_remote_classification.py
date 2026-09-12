from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from photosort.cloud_vision import (
    ANTHROPIC_VISION_MODEL,
    MISTRAL_VISION_MODEL,
    CloudRequestThrottle,
    TokenUsage,
    _sanitize_label_text,
)
from photosort.motifs import MOTIF_REGISTRY, build_motif_prompt
from photosort.pricing import ASSUMED_USAGE_BY_PROVIDER
from photosort.remote_classification import (
    _MAX_RESPONSE_TOKENS,
    CATEGORY_LABEL_SIMILARITY_THRESHOLD,
    MAX_FINE_LABEL_LENGTH,
    MAX_FINE_LABELS_PER_PHOTO,
    AnthropicCategoryClient,
    CategoryDetectionClientLike,
    FineLabelSnapshotEntry,
    MistralCategoryClient,
    RemoteCategoryClassificationApiError,
    RemoteClassification,
    _classification_from_json,
    _cosine_similarity,
    _normalize_label_text,
    _slugify,
    resolve_canonical_label,
)

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
# decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 3/4: neues Modul,
# strukturell analog landmark.py/test_landmark.py. Seit specs/features/0427-motive-mit-staerke.md
# (PR 2) liefert die Antwort einen STAERKEVEKTOR ueber dem geschlossenen Achter-Motivset plus ein
# Ausschluss-Feld statt einer Kandidatenliste. httpx.MockTransport statt unittest.mock.patch
# (Teststrategie-Abschnitt).

IMAGE_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


def _vector(**overrides: float) -> dict[str, float]:
    """Der VOLLSTAENDIGE Achter-Vektor in Registry-Reihenfolge, nicht genannte Motive bei `0.0`.

    Aus `MOTIF_REGISTRY` abgeleitet und nicht als zweite Liste geschrieben: ein neuntes Motiv
    veraenderte sonst das Produkt, ohne einen dieser Faelle rot zu machen."""
    return {key: overrides.get(key, 0.0) for key in MOTIF_REGISTRY}


# specs/features/0382-cloud-rate-limits-aussitzen.md: der Schrittmacher ist an beiden
# Client-Klassen ein Pflicht-Schluesselwortparameter OHNE Default. Die Bestandsfaelle bekommen
# deshalb einen wirkungslosen (`min_interval_seconds=0.0` heisst "kein Schrittmacher").


def _no_throttle() -> CloudRequestThrottle:
    return CloudRequestThrottle(min_interval_seconds=0.0)


def _recording_throttle(waits: list[float]) -> CloudRequestThrottle:
    """Kein Mindestabstand, aber jede Wiederholungs-Wartezeit als Zahl in `waits` - und ohne eine
    einzige echte Sekunde Wartezeit."""

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    return CloudRequestThrottle(min_interval_seconds=0.0, clock=lambda: 0.0, sleep=sleep)


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
    expected = RemoteClassification(
        motif_strengths=_vector(tiere=0.8), fine_labels=("Hund",), excluded=False
    )
    fake: CategoryDetectionClientLike = FakeCategoryClient(expected)
    assert await fake.classify(IMAGE_BYTES, "image/jpeg", 1) == expected


class TestClassificationFromJsonStructure:
    """STRUKTURELL HART, INHALTLICH TOLERANT (Spec 0427, PR 2 Schritt 1): `motifs` tritt an die
    Stelle von `categories`, die Haerte der Struktur bleibt unveraendert."""

    def test_rejects_a_missing_motifs_key(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _classification_from_json({"fine_labels": ["Hund"]}, photo_id=1)

    def test_rejects_a_non_object_motifs_value(self) -> None:
        """Eine LISTE unter `motifs` ist strukturell falsch und kein tolerierbarer Inhalt - das
        Antwortschema nennt eine Abbildung Schluessel -> Zahl."""
        with pytest.raises(RemoteCategoryClassificationApiError):
            _classification_from_json({"motifs": ["tiere"]}, photo_id=1)

    def test_rejects_a_response_that_is_not_a_json_object(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _classification_from_json(["tiere"], photo_id=1)

    def test_rejects_a_present_but_non_list_fine_labels_value(self) -> None:
        with pytest.raises(RemoteCategoryClassificationApiError):
            _classification_from_json({"motifs": {"tiere": 0.5}, "fine_labels": "Hund"}, photo_id=1)

    def test_a_missing_fine_labels_key_is_not_an_error(self) -> None:
        # Feinlabels sind optional, der Staerkevektor nicht.
        result = _classification_from_json({"motifs": {"tiere": 0.5}}, photo_id=1)
        assert result == RemoteClassification(
            motif_strengths=_vector(tiere=0.5), fine_labels=(), excluded=False
        )


class TestClassificationFromJsonMotifs:
    """INHALTLICH TOLERANT (Spec 0427, PR 2 Schritt 1): ein unbekannter Schluessel wird verworfen,
    eine unbrauchbare Zahl wird zu `0.0` - beides mit genau einer WARNING-Zeile, nie mit einem
    Fehler."""

    def test_the_vector_always_carries_all_eight_motifs(self) -> None:
        """Der Vektor ist VOLLSTAENDIG oder er existiert nicht: ein Motiv, das die Antwort nicht
        nennt, steht mit `0.0` da und fehlt nicht. `upsert_assessment` schreibt genau diese
        Abbildung, und `PhotoOut.motifs` traegt acht Eintraege."""
        result = _classification_from_json({"motifs": {"tiere": 0.5}}, photo_id=1)

        assert result.motif_strengths == _vector(tiere=0.5)
        assert list(result.motif_strengths) == list(MOTIF_REGISTRY)

    def test_a_strong_building_and_weak_people_answer_keeps_exactly_that_relation(self) -> None:
        """Akzeptanzkriterium "Bauwerk deutlich, Menschen schwach - nicht umgekehrt": die Zahlen
        des Modells kommen unveraendert an, keine Vorrangreihenfolge greift dazwischen."""
        result = _classification_from_json(
            {"motifs": {"bauwerk_sehenswuerdigkeit": 0.9, "menschen": 0.2}}, photo_id=1
        )

        assert result.motif_strengths["bauwerk_sehenswuerdigkeit"] == 0.9
        assert result.motif_strengths["menschen"] == 0.2
        assert (
            result.motif_strengths["bauwerk_sehenswuerdigkeit"] > result.motif_strengths["menschen"]
        )

    def test_the_swapped_answer_yields_the_swapped_relation(self) -> None:
        """Die Gegenprobe zum Fall oben. Der Fall mit GLEICHEN Zahlen gehoert ausdruecklich nicht
        dazu - er deckte jede Implementierung."""
        result = _classification_from_json(
            {"motifs": {"bauwerk_sehenswuerdigkeit": 0.2, "menschen": 0.9}}, photo_id=1
        )

        assert (
            result.motif_strengths["menschen"] > result.motif_strengths["bauwerk_sehenswuerdigkeit"]
        )

    def test_an_unknown_key_is_discarded_and_logged_once_with_the_raw_value(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            result = _classification_from_json(
                {"motifs": {"einhorn": 0.9, "tiere": 0.4}}, photo_id=42
            )

        assert result.motif_strengths == _vector(tiere=0.4)
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "einhorn" in message
        assert "42" in message

    def test_the_logged_raw_value_is_repr_escaped_and_length_limited(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Sicherheitsauflage S11: ein mehrzeiliger Modellwert darf keine gefaelschten Logzeilen
        erzeugen - `repr` escaped den Zeilenumbruch sichtbar, die Laenge bleibt begrenzt."""
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            _classification_from_json(
                {"motifs": {"boes\nWARNING gefaelschte Zeile " + "x" * 200: 0.5}}, photo_id=7
            )

        message = caplog.records[0].getMessage()
        assert "\\n" in message
        assert "\n" not in message
        assert len(message) < 200

    def test_all_keys_unknown_yields_eight_zeros_not_an_error(self) -> None:
        """Der wichtigste Grenzfall: `motifs` ist ein Objekt, aber ALLE Schluessel sind unbekannt
        -> KEIN Fehler, sondern acht Nullen; die Feinlabels desselben Fotos bleiben erhalten."""
        result = _classification_from_json(
            {"motifs": {"einhorn": 0.9, "drache": 0.8}, "fine_labels": ["Fabelwesen"]}, photo_id=1
        )

        assert result.motif_strengths == _vector()
        assert result.fine_labels == ("Fabelwesen",)

    def test_an_empty_motifs_object_yields_eight_zeros(self) -> None:
        result = _classification_from_json({"motifs": {}}, photo_id=1)
        assert result.motif_strengths == _vector()

    def test_a_key_is_not_normalized_before_the_membership_check(self) -> None:
        """Reine Mitgliedschaftspruefung im geschlossenen Schluesselraum - kein `strip()`, kein
        `casefold()`, kein Praefixvergleich (`motifs.py::is_motif_key`)."""
        result = _classification_from_json(
            {"motifs": {"TIERE": 0.9, " tiere": 0.8, "tiere_": 0.7}}, photo_id=1
        )
        assert result.motif_strengths == _vector()

    def test_the_exclusion_key_is_not_a_motif(self) -> None:
        """ "Dokument und Screenshot" ist ein Ausschluss-SIGNAL und steht ausserhalb der Registry -
        als Motivschluessel wird er wie jeder andere unbekannte Wert verworfen."""
        result = _classification_from_json({"motifs": {"dokument_screenshot": 1.0}}, photo_id=1)

        assert result.motif_strengths == _vector()
        assert "dokument_screenshot" not in result.motif_strengths

    def test_a_non_string_key_is_discarded_not_fatal(self) -> None:
        parsed = {"motifs": {42: 0.9, "tiere": 0.4}}
        result = _classification_from_json(parsed, photo_id=1)
        assert result.motif_strengths == _vector(tiere=0.4)

    def test_a_former_category_key_is_no_longer_accepted(self) -> None:
        """Die entfallenden Kategorieschluessel sind keine Motive - eine Antwort im alten
        Vokabular liefert acht Nullen, nie eine stille Teilaussage."""
        result = _classification_from_json(
            {"motifs": {"pflanze": 0.9, "innenraum": 0.8, "nicht_erkannt": 1.0}}, photo_id=1
        )
        assert result.motif_strengths == _vector()


class TestClassificationFromJsonExcluded:
    """Sicherheitsauflage S10 - die Stelle mit dem groessten Hebel dieser Story: ein einziger Wert
    nimmt ein Foto aus JEDER Motivauswahl und ist von Hand nicht korrigierbar."""

    def test_a_real_true_is_taken(self) -> None:
        result = _classification_from_json({"motifs": {}, "excluded": True}, photo_id=1)
        assert result.excluded is True

    def test_a_real_false_is_taken(self) -> None:
        result = _classification_from_json({"motifs": {}, "excluded": False}, photo_id=1)
        assert result.excluded is False

    def test_a_missing_field_is_false(self) -> None:
        result = _classification_from_json({"motifs": {}}, photo_id=1)
        assert result.excluded is False

    @pytest.mark.parametrize("raw", ["true", "ja", 1, 0.5, [], {}, "false", None, -1])
    def test_a_non_bool_value_is_false_never_coerced(self, raw: object) -> None:
        """Kein `bool(...)` auf einen Fremdwert und keine Umdeutung von `1`, `"true"` oder `"ja"` -
        jeder nicht-leere Fremdwert fuehrte sonst zum Ausschluss."""
        result = _classification_from_json({"motifs": {}, "excluded": raw}, photo_id=1)
        assert result.excluded is False

    def test_a_discarded_excluded_value_logs_one_warning_with_a_fixed_reason_token(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """S11: die Zeile traegt ein festes Grund-Token und KEINEN Fremdtext."""
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            _classification_from_json({"motifs": {}, "excluded": "JA-GANZ-SICHER"}, photo_id=42)

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "photo_id=42" in message
        assert "kein_wahrheitswert" in message
        assert "JA-GANZ-SICHER" not in message

    def test_a_missing_excluded_key_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Nichts wurde verworfen - eine fehlende Angabe ist keine entartete."""
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            _classification_from_json({"motifs": {"tiere": 0.5}}, photo_id=1)

        assert caplog.records == []

    def test_high_strengths_survive_an_exclusion_unchanged(self) -> None:
        """Der Ausschluss gewinnt in der AUSWAHL, er loescht aber keine Zahl: die Staerken bleiben
        gespeichert und werden nicht auf 0 gesetzt."""
        result = _classification_from_json(
            {"motifs": {"menschen": 0.9}, "excluded": True}, photo_id=1
        )

        assert result.excluded is True
        assert result.motif_strengths["menschen"] == 0.9


class TestClassificationFromJsonFineLabels:
    def test_three_fine_labels_are_truncated_to_the_first_two(self) -> None:
        result = _classification_from_json(
            {"motifs": {"tiere": 0.5}, "fine_labels": ["Hund", "Strand", "Urlaub"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund", "Strand")
        assert len(result.fine_labels) == MAX_FINE_LABELS_PER_PHOTO

    def test_a_fine_label_longer_than_the_maximum_is_discarded_not_truncated(self) -> None:
        """Ein abgeschnittenes Label erzeugte sonst dauerhaft einen unbrauchbaren canonical_key in
        der projektuebergreifenden Registry (Entscheidung 5 der Spec)."""
        too_long = "x" * (MAX_FINE_LABEL_LENGTH + 1)
        result = _classification_from_json(
            {"motifs": {"tiere": 0.5}, "fine_labels": [too_long, "Hund"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund",)

    def test_a_fine_label_exactly_at_the_maximum_is_kept(self) -> None:
        exact = "x" * MAX_FINE_LABEL_LENGTH
        result = _classification_from_json(
            {"motifs": {"tiere": 0.5}, "fine_labels": [exact]}, photo_id=1
        )
        assert result.fine_labels == (exact,)

    @pytest.mark.parametrize("raw", ["", "   ", "\n\t"])
    def test_an_empty_or_whitespace_only_fine_label_is_discarded(self, raw: str) -> None:
        result = _classification_from_json(
            {"motifs": {"tiere": 0.5}, "fine_labels": [raw, "Hund"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund",)

    def test_duplicate_fine_labels_are_removed(self) -> None:
        result = _classification_from_json(
            {"motifs": {"tiere": 0.5}, "fine_labels": ["Hund", "Hund", "Strand"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund", "Strand")

    def test_a_non_string_fine_label_is_discarded(self) -> None:
        result = _classification_from_json(
            {"motifs": {"tiere": 0.5}, "fine_labels": [17, "Hund"]}, photo_id=1
        )
        assert result.fine_labels == ("Hund",)

    def test_fine_labels_are_sanitized_before_the_length_check(self) -> None:
        # Sanitisierung laeuft VOR der Laengenpruefung: ein Label, das erst durch
        # Steuerzeichen ueber die Grenze rutscht, bleibt erhalten.
        raw = "\u200b" * 20 + "x" * MAX_FINE_LABEL_LENGTH
        result = _classification_from_json(
            {"motifs": {"tiere": 0.5}, "fine_labels": [raw]}, photo_id=1
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
                {"motifs": {"tiere": 0.7}, "excluded": False, "fine_labels": ["Hund"]}
            )

        client = AnthropicCategoryClient(
            api_key="sk-test",
            model=ANTHROPIC_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )

        classification = asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg", 1))

        assert classification == RemoteClassification(
            motif_strengths=_vector(tiere=0.7), fine_labels=("Hund",), excluded=False
        )
        body = captured["body"]
        assert isinstance(body, dict)
        assert body["model"] == ANTHROPIC_VISION_MODEL
        # Sicherheitsauflage S8: der gesendete Prompt stammt AUSSCHLIESSLICH aus
        # `motifs.py::MOTIF_REGISTRY`, nicht aus einem Literal in diesem Modul. Die
        # Feinlabel-Grenze uebergibt die Aufrufstelle.
        content = body["messages"][0]["content"]
        assert content[1]["text"] == build_motif_prompt(max_fine_labels=MAX_FINE_LABELS_PER_PHOTO)

    def test_error_response_raises_remote_category_classification_api_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Unauthorized")

        client = AnthropicCategoryClient(
            api_key="sk-test",
            model=ANTHROPIC_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )

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
                {"motifs": {"landschaft": 0.6}, "excluded": False, "fine_labels": ["Strand"]}
            )

        client = MistralCategoryClient(
            api_key="mistral-test",
            model=MISTRAL_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )

        classification = asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg", 1))

        assert classification == RemoteClassification(
            motif_strengths=_vector(landschaft=0.6), fine_labels=("Strand",), excluded=False
        )
        body = captured["body"]
        assert isinstance(body, dict)
        assert body["model"] == MISTRAL_VISION_MODEL
        content = body["messages"][0]["content"]
        assert content[1]["text"] == build_motif_prompt(max_fine_labels=MAX_FINE_LABELS_PER_PHOTO)

    def test_error_response_raises_remote_category_classification_api_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        client = MistralCategoryClient(
            api_key="mistral-test",
            model=MISTRAL_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )

        with pytest.raises(RemoteCategoryClassificationApiError):
            asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg", 1))


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
            FineLabelSnapshotEntry(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0])
        ]
        embedder = FakeLabelEmbedder({})

        result = resolve_canonical_label("HUND", existing, embedder)

        assert result.canonical_key == "hund"
        assert embedder.calls == []
        assert len(existing) == 1

    def test_similarity_at_exactly_the_threshold_reuses_the_existing_entry(self) -> None:
        existing = [
            FineLabelSnapshotEntry(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0])
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
            FineLabelSnapshotEntry(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0])
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
        assert MAX_FINE_LABELS_PER_PHOTO == 2
        assert MAX_FINE_LABEL_LENGTH == 60


# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 1: `RemoteClassification.usage` traegt den realen Token-Verbrauch bis zum
# Worker. Default `None` - bestehende Test-Doubles und die Protocol-Signatur bleiben unveraendert.

ANTHROPIC_API_KEY = "sk-ant-test-key-not-a-real-secret"
MISTRAL_API_KEY = "mistral-test-key-not-a-real-secret"

_VALID_BODY: dict[str, object] = {
    "motifs": {"landschaft": 0.8},
    "excluded": False,
    "fine_labels": ["Duene"],
}


class TestRemoteClassificationUsage:
    def test_can_be_constructed_without_usage(self) -> None:
        classification = RemoteClassification(
            motif_strengths=_vector(landschaft=0.8), fine_labels=()
        )

        assert classification.usage is None

    def test_carries_the_usage_when_given(self) -> None:
        classification = RemoteClassification(
            motif_strengths=_vector(),
            fine_labels=(),
            usage=TokenUsage(input_tokens=5, output_tokens=6),
        )

        assert classification.usage == TokenUsage(input_tokens=5, output_tokens=6)

    def test_the_strength_mapping_is_immutable_after_parsing(self) -> None:
        """`frozen=True` sichert nur die Referenz - fuer den INHALT braucht es
        `MappingProxyType`, analog dem Feinlabel-Tupel daneben."""
        classification = _classification_from_json({"motifs": {"tiere": 0.4}}, photo_id=1)

        with pytest.raises(TypeError):
            classification.motif_strengths["menschen"] = 1.0  # type: ignore[index]


class TestAnthropicCategoryClientFillsUsage:
    async def test_classify_reports_the_token_usage_of_the_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": json.dumps(_VALID_BODY)}],
                    "usage": {"input_tokens": 1700, "output_tokens": 20},
                },
            )

        client = AnthropicCategoryClient(
            api_key=ANTHROPIC_API_KEY,
            model=ANTHROPIC_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )
        classification = await client.classify(IMAGE_BYTES, "image/jpeg", 7)

        assert classification.motif_strengths == _vector(landschaft=0.8)
        assert classification.usage == TokenUsage(input_tokens=1700, output_tokens=20)

    async def test_a_response_without_usage_still_yields_a_valid_classification(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _anthropic_success_response(_VALID_BODY)

        client = AnthropicCategoryClient(
            api_key=ANTHROPIC_API_KEY,
            model=ANTHROPIC_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )
        classification = await client.classify(IMAGE_BYTES, "image/jpeg", 7)

        assert classification.motif_strengths == _vector(landschaft=0.8)
        assert classification.usage is None


class TestMistralCategoryClientFillsUsage:
    async def test_classify_reports_the_token_usage_of_the_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": json.dumps(_VALID_BODY)}}],
                    "usage": {"prompt_tokens": 1300, "completion_tokens": 14},
                },
            )

        client = MistralCategoryClient(
            api_key=MISTRAL_API_KEY,
            model=MISTRAL_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )
        classification = await client.classify(IMAGE_BYTES, "image/jpeg", 7)

        assert classification.usage == TokenUsage(input_tokens=1300, output_tokens=14)

    async def test_a_response_without_usage_still_yields_a_valid_classification(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _mistral_success_response(_VALID_BODY)

        client = MistralCategoryClient(
            api_key=MISTRAL_API_KEY,
            model=MISTRAL_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )
        classification = await client.classify(IMAGE_BYTES, "image/jpeg", 7)

        assert classification.usage is None


class TestConfiguredModelReachesTheRequest:
    """specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 7: das Modell ist
    ein durchgereichter Konstruktor-Parameter statt einer im Client gelesenen Modulkonstante -
    und es ist DASSELBE Modell wie in der Landmark-Phase (Akzeptanzkriterium: "nicht zwei
    unterschiedliche Modelle nebeneinander")."""

    def test_the_anthropic_client_sends_the_model_it_was_built_with(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": '{"motifs": {}, "fine_labels": []}'}],
                },
            )

        client = AnthropicCategoryClient(
            api_key="test",
            model="ein-anderes-modell",
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )

        asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg", 1))

        assert captured["model"] == "ein-anderes-modell"

    def test_the_mistral_client_sends_the_model_it_was_built_with(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"motifs": {}, "fine_labels": []}'}}],
                },
            )

        client = MistralCategoryClient(
            api_key="test",
            model="ein-anderes-modell",
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )

        asyncio.run(client.classify(IMAGE_BYTES, "image/jpeg", 1))

        assert captured["model"] == "ein-anderes-modell"


# --- specs/features/0427-motive-mit-staerke.md, PR 2 ----------------------------------------


class TestStrengthValueBand:
    """Sicherheitsauflage S9: uebernommen wird ausschliesslich ein echter Zahlentyp im Band
    `0.0 <= v <= 1.0`. Alles andere wird VERWORFEN (Ersatzwert `0.0`), nie geklemmt."""

    @pytest.mark.parametrize("raw", [0.0, 1.0, 0.5, 0, 1, -0.0])
    def test_values_inside_the_band_are_kept(self, raw: float) -> None:
        result = _classification_from_json({"motifs": {"tiere": raw}}, photo_id=1)
        assert result.motif_strengths["tiere"] == float(raw)

    def test_zero_is_a_value_not_an_absence(self) -> None:
        """`0.0` heisst "nicht zu sehen" - es ist eine Aussage des Modells und unterscheidet sich
        nicht in der Darstellung, wohl aber in der Herkunft von einem verworfenen Wert."""
        result = _classification_from_json({"motifs": {"tiere": 0.0}}, photo_id=1)
        assert result.motif_strengths["tiere"] == 0.0

    @pytest.mark.parametrize("raw", [1.0000001, -0.1, 1.5, 2, 100, -1])
    def test_values_outside_the_band_become_zero_not_clamped(self, raw: float) -> None:
        """`1.4 -> 1.0` waere die staerkste Aussage, die das Produkt kennt, erfunden aus einer
        kaputten Antwort - und ein spaeteres Klemmen liesse `NaN` wieder durch."""
        result = _classification_from_json({"motifs": {"tiere": raw}}, photo_id=1)
        assert result.motif_strengths["tiere"] == 0.0

    @pytest.mark.parametrize("raw", [True, False])
    def test_booleans_are_rejected_even_though_bool_is_an_int(self, raw: bool) -> None:
        """`isinstance(True, int)` ist `True` - ohne expliziten Ausschluss erschiene
        `"menschen": true` als die staerkste Aussage, die das Produkt kennt."""
        result = _classification_from_json({"motifs": {"menschen": raw}}, photo_id=1)
        assert result.motif_strengths["menschen"] == 0.0

    @pytest.mark.parametrize("raw", ["0.7", None, ["0.7"], {"value": 0.7}, ""])
    def test_non_numeric_values_are_discarded_without_conversion(self, raw: object) -> None:
        result = _classification_from_json({"motifs": {"tiere": raw}}, photo_id=1)
        assert result.motif_strengths["tiere"] == 0.0

    @pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
    def test_json_float_literals_are_discarded_parsed_from_a_raw_body(self, literal: str) -> None:
        """S9, TESTFORM VERBINDLICH: Eingabe als ROH-Textkoerper (`json.loads` parst diese
        Literale standardmaessig), nicht als `json.dumps`-erzeugtes Dict. `strength` ist eine
        `double precision`-Spalte und Starlette rendert mit `allow_nan=False` - ein einziger
        durchgelassener Wert legte die GESAMTE Fotoliste des Projekts auf `500`. Die
        SQLite-Testdatenbank zeigt den Defekt strukturell nicht."""
        parsed = json.loads(f'{{"motifs":{{"tiere":{literal}}}}}')

        result = _classification_from_json(parsed, photo_id=1)

        assert result.motif_strengths["tiere"] == 0.0

    def test_a_discarded_value_does_not_affect_the_other_seven_motifs(self) -> None:
        result = _classification_from_json(
            {"motifs": {"tiere": "hoch", "menschen": 0.6}}, photo_id=1
        )
        assert result.motif_strengths == _vector(menschen=0.6)


class TestStrengthDiscardLogging:
    """Sicherheitsauflage S11: `photo_id` + festes Grund-Token, KEIN Rohwert."""

    @pytest.mark.parametrize(
        ("raw_literal", "expected_reason"),
        [
            ('"0.7"', "nicht_numerisch"),
            ("true", "nicht_numerisch"),
            ("null", "nicht_numerisch"),
            ("1.7", "ausserhalb_intervall"),
            ("-0.1", "ausserhalb_intervall"),
            ("NaN", "ausserhalb_intervall"),
        ],
    )
    def test_a_discarded_strength_logs_one_warning_with_a_fixed_reason_token(
        self, caplog: pytest.LogCaptureFixture, raw_literal: str, expected_reason: str
    ) -> None:
        parsed = json.loads(f'{{"motifs":{{"tiere":{raw_literal}}}}}')

        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            _classification_from_json(parsed, photo_id=42)

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "photo_id=42" in message
        assert expected_reason in message

    def test_the_warning_never_contains_the_raw_value(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Der Diagnosewert liegt in der FEHLERKLASSE - ein festes Grund-Token macht eine
        systematische Skalenverwechslung greppbar, der Rohwert sagt darueber hinaus nichts und
        waere Fremdtext im Log."""
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            _classification_from_json({"motifs": {"tiere": "SEHR-VIEL"}}, photo_id=1)

        assert "SEHR-VIEL" not in caplog.records[0].getMessage()

    def test_a_motif_the_answer_does_not_mention_logs_nothing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Nichts wurde verworfen: ein fehlender Schluessel ist keine entartete Aussage, sondern
        gar keine - er steht mit `0.0` im Vektor."""
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            result = _classification_from_json({"motifs": {"tiere": 0.4}}, photo_id=1)

        assert result.motif_strengths["menschen"] == 0.0
        assert caplog.records == []

    def test_each_discarded_value_logs_exactly_once(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            _classification_from_json(
                {
                    "motifs": {
                        "tiere": 1.7,
                        "menschen": "hoch",
                        "landschaft": 0.3,
                        "einhorn": 0.9,
                    }
                },
                photo_id=5,
            )

        assert len(caplog.records) == 3

    def test_an_unknown_key_with_an_unusable_number_logs_only_the_key(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Der Schluessel ist bereits verworfen - die Zahl wird gar nicht erst bewertet, es gibt
        also KEINE zweite Warnung fuer denselben Eintrag."""
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            result = _classification_from_json({"motifs": {"einhorn": 1.7}}, photo_id=7)

        assert result.motif_strengths == _vector()
        assert len(caplog.records) == 1
        assert "einhorn" in caplog.records[0].getMessage()

    def test_the_log_never_carries_the_whole_response(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """S11: geloggt wird ausschliesslich der einzelne verworfene Wert plus `photo_id` - nie
        die vollstaendige Antwort, nie der Request-Body, nie Base64-Bilddaten, nie der API-Key."""
        with caplog.at_level("WARNING", logger="photosort.remote_classification"):
            _classification_from_json(
                {
                    "motifs": {"tiere": 1.7},
                    "excluded": False,
                    "fine_labels": ["Geheimes-Feinlabel"],
                },
                photo_id=1,
            )

        message = caplog.records[0].getMessage()
        assert "Geheimes-Feinlabel" not in message
        assert "fine_labels" not in message


class TestResponseBudgetAfterTheMotifSchema:
    """Sicherheitsauflage S12: `_MAX_RESPONSE_TOKENS` ist eine SICHERHEITSschranke, nicht nur eine
    Kostenschranke - sie begrenzt zugleich die Menge an Fremdtext, die je Foto geparst und
    potenziell geloggt werden kann.

    Das Motiv-Antwortschema verlaengert die vollbesetzte Antwort von rund 185 auf rund 257
    Zeichen: acht Schluessel-Zahl-Paare (die laengsten Schluessel zerfallen in mehrere Tokens)
    plus das Ausschluss-Feld statt dreier Kategorie-Objekte. Ueberschlaegig sind das rund 110
    Ausgabe-Tokens kompakt und rund 145 bei einer eingerueckten Antwort. Beide Groessen stehen
    HIER als Literal und nicht nur im Kommentar."""

    def test_the_response_token_ceiling_is_pinned_to_the_new_value(self) -> None:
        """Von 256 auf 384 angehoben - wer den Wert weiter anhebt, soll an dieser Zeile auf die
        Begruendung und auf die drei zusammen nachzuziehenden Dinge stossen."""
        assert _MAX_RESPONSE_TOKENS == 384

    def test_the_assumed_output_tokens_still_cover_the_longer_response(self) -> None:
        """Die Schaetzung ist die einzige Absicherung VOR der kostenpflichtigen Aktion - sie darf
        die neue Antwortlaenge nicht unterschaetzen. `145` ist die gemessene obere Schranke der
        vollbesetzten, eingerueckten Achter-Antwort."""
        longest_plausible_response_tokens = 145

        for provider, assumed in ASSUMED_USAGE_BY_PROVIDER.items():
            assert assumed.output_tokens >= longest_plausible_response_tokens, provider

    def test_the_ceiling_keeps_clear_reserve_over_the_assumption(self) -> None:
        """Die Reserve-Invariante bleibt unveraendert `Schranke >= 2 x Annahme`. Sie ist NICHT an
        die Annahme anzupassen: reisst sie, ist das der Anlass fuer eine Meldung, nicht fuer eine
        neue Zahl an dieser Stelle."""
        for provider, assumed in ASSUMED_USAGE_BY_PROVIDER.items():
            assert _MAX_RESPONSE_TOKENS >= 2 * assumed.output_tokens, provider


# specs/features/0382-cloud-rate-limits-aussitzen.md, K1/K5/K6: beide Kategorie-Clients senden
# seitdem ueber cloud_vision.py::post_vision_request - dieselbe Funktion wie die beiden
# Landmark-Clients. Je Client ein PAAR, "429 dann 200" und "dauerhaft 429".


def _sequence_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[index]

    return httpx.MockTransport(handler)


class TestTheCategoryClientsSitOutARateLimit:
    async def test_anthropic_retries_a_429_and_returns_the_following_result(self) -> None:
        waits: list[float] = []
        client = AnthropicCategoryClient(
            api_key=ANTHROPIC_API_KEY,
            model=ANTHROPIC_VISION_MODEL,
            transport=_sequence_transport(
                [httpx.Response(429), _anthropic_success_response(_VALID_BODY)]
            ),
            throttle=_recording_throttle(waits),
        )

        classification = await client.classify(IMAGE_BYTES, "image/jpeg", 7)

        expected = _classification_from_json(_VALID_BODY, 7).motif_strengths
        assert classification.motif_strengths == expected
        assert waits == [2.0]

    async def test_anthropic_gives_up_after_five_attempts_on_a_permanent_429(self) -> None:
        waits: list[float] = []
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(429)

        client = AnthropicCategoryClient(
            api_key=ANTHROPIC_API_KEY,
            model=ANTHROPIC_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_recording_throttle(waits),
        )

        with pytest.raises(RemoteCategoryClassificationApiError) as excinfo:
            await client.classify(IMAGE_BYTES, "image/jpeg", 7)

        assert "429" in str(excinfo.value)
        assert len(requests) == 5
        assert waits == [2.0, 4.0, 8.0, 16.0]

    async def test_mistral_retries_a_429_and_returns_the_following_result(self) -> None:
        waits: list[float] = []
        client = MistralCategoryClient(
            api_key=MISTRAL_API_KEY,
            model=MISTRAL_VISION_MODEL,
            transport=_sequence_transport(
                [httpx.Response(429), _mistral_success_response(_VALID_BODY)]
            ),
            throttle=_recording_throttle(waits),
        )

        classification = await client.classify(IMAGE_BYTES, "image/jpeg", 7)

        expected = _classification_from_json(_VALID_BODY, 7).motif_strengths
        assert classification.motif_strengths == expected
        assert waits == [2.0]

    async def test_mistral_gives_up_after_five_attempts_on_a_permanent_429(self) -> None:
        waits: list[float] = []
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(429)

        client = MistralCategoryClient(
            api_key=MISTRAL_API_KEY,
            model=MISTRAL_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_recording_throttle(waits),
        )

        with pytest.raises(RemoteCategoryClassificationApiError) as excinfo:
            await client.classify(IMAGE_BYTES, "image/jpeg", 7)

        assert "429" in str(excinfo.value)
        assert len(requests) == 5
        assert waits == [2.0, 4.0, 8.0, 16.0]

    async def test_a_500_is_still_never_retried(self) -> None:
        """K5: `5xx` bleibt der unveraenderte best-effort-Skip - genau EIN HTTP-Versuch."""
        waits: list[float] = []
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(500)

        client = MistralCategoryClient(
            api_key=MISTRAL_API_KEY,
            model=MISTRAL_VISION_MODEL,
            transport=httpx.MockTransport(handler),
            throttle=_recording_throttle(waits),
        )

        with pytest.raises(RemoteCategoryClassificationApiError):
            await client.classify(IMAGE_BYTES, "image/jpeg", 7)

        assert len(requests) == 1
        assert waits == []
