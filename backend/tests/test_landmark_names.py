"""Das projektgebundene Namensregister der Sehenswuerdigkeiten - REIN und DB-FREI
(specs/features/0469-verlaessliche-sehenswuerdigkeitsnamen.md,
decisions/0107-sehenswuerdigkeitsname-eine-grenze-und-ein-projektgebundenes-namensregister.md).

Ohne DB, ohne Netz, ohne Modell: Der Einbetter ist durchgaengig ein Test-Double mit injizierten
Vektoren. Ob ein echtes Einbettungsmodell zwei Schreibweisen derselben Sehenswuerdigkeit als
aehnlich bewertet, ist hier AUSDRUECKLICH NICHT der Gegenstand - dafuer gibt es keinen Namenskorpus
im Repository, und `LANDMARK_NAME_SIMILARITY_THRESHOLD` ist dokumentiert-unkalibriert.
"""

from __future__ import annotations

import ast

import pytest

from photosort.landmark_names import (
    LANDMARK_NAME_SIMILARITY_THRESHOLD,
    LandmarkNameEntry,
    resolve_canonical_landmark,
)
from tests.import_closure import import_closure, imported_root_packages, module_file


class FakeLabelEmbedder:
    """Spy-faehiges Test-Double - liefert feste, injizierte Vektoren je Text und zaehlt jeden
    Aufruf. Der Aufrufnachweis ist an mehreren Stellen der eigentliche Gegenstand ("der
    Schnellweg fragt das Modell gar nicht")."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return self._vectors[text]


def _entry(display_name: str, locality: str | None, embedding: list[float]) -> LandmarkNameEntry:
    return LandmarkNameEntry(
        normalized_name=display_name.casefold(),
        display_name=display_name,
        embedding=embedding,
        locality=locality,
    )


class TestTheSameNormalisedNameAlwaysHits:
    """ADR 0107 Punkt 4 Schritt 1: Der Schnellweg trifft IMMER - ohne Ortspruefung und ohne
    Modellaufruf."""

    def test_a_differently_cased_name_hits_the_existing_entry(self) -> None:
        existing = [_entry("Zugspitze", "Grainau", [1.0, 0.0])]
        embedder = FakeLabelEmbedder({})

        result = resolve_canonical_landmark("ZUGSPITZE", "Grainau", existing, embedder)

        assert result is existing[0]
        assert embedder.calls == []

    def test_the_same_name_hits_even_with_different_localities(self) -> None:
        """EIN EIGENER FALL, und er hat einen Grund: Die Ortsnamen-Sperre gilt ausdruecklich NICHT
        fuer den Schnellweg. Zwei zeichengleiche Namen gelten schon vor dieser Entscheidung als
        dieselbe Sehenswuerdigkeit; wer das spaeter als Bug "repariert", zerlegt eine
        Sehenswuerdigkeit, die zwei benachbarte Gemeinden beruehrt, wieder in zwei."""
        existing = [_entry("Zugspitze", "Grainau", [1.0, 0.0])]
        embedder = FakeLabelEmbedder({})

        result = resolve_canonical_landmark("zugspitze", "Ehrwald", existing, embedder)

        assert result is existing[0]
        assert embedder.calls == []

    def test_the_hit_keeps_the_display_name_first_seen(self) -> None:
        """Die Anzeigeform ist die ZUERST gesehene, keine kuratierte Fassung."""
        existing = [_entry("Zugspitze", None, [1.0, 0.0])]

        result = resolve_canonical_landmark("ZUGSPITZE", None, existing, FakeLabelEmbedder({}))

        assert result.display_name == "Zugspitze"


class TestSimilarityIsTheBridge:
    """ADR 0107 Punkt 4 Schritt 2: Aehnlichkeit oberhalb der eigenen Schwelle traegt zusammen, was
    verschieden geschrieben ist."""

    def test_a_similar_name_at_the_same_locality_hits(self) -> None:
        existing = [_entry("Zugspitze", "Grainau", [1.0, 0.0])]
        vector = _vector_with_similarity(LANDMARK_NAME_SIMILARITY_THRESHOLD)
        embedder = FakeLabelEmbedder({"zugspitzgipfel": vector})

        result = resolve_canonical_landmark("Zugspitzgipfel", "Grainau", existing, embedder)

        assert result is existing[0]

    def test_exactly_on_the_similarity_threshold_hits_inclusive(self) -> None:
        existing = [_entry("Zugspitze", None, [1.0, 0.0])]
        vector = _vector_with_similarity(LANDMARK_NAME_SIMILARITY_THRESHOLD)
        embedder = FakeLabelEmbedder({"zugspitzgipfel": vector})

        result = resolve_canonical_landmark("Zugspitzgipfel", None, existing, embedder)

        assert result is existing[0]

    def test_just_below_the_similarity_threshold_becomes_a_new_entry(self) -> None:
        existing = [_entry("Zugspitze", None, [1.0, 0.0])]
        vector = _vector_with_similarity(LANDMARK_NAME_SIMILARITY_THRESHOLD - 0.05)
        embedder = FakeLabelEmbedder({"watzmann": vector})

        result = resolve_canonical_landmark("Watzmann", None, existing, embedder)

        assert result is not existing[0]
        assert result.display_name == "Watzmann"

    @pytest.mark.parametrize(
        ("candidate_locality", "entry_locality"),
        [(None, "Grainau"), ("Grainau", None), (None, None)],
        ids=["kandidat-ohne-ort", "eintrag-ohne-ort", "beide-ohne-ort"],
    )
    def test_similarity_decides_alone_when_one_side_has_no_resolved_locality(
        self, candidate_locality: str | None, entry_locality: str | None
    ) -> None:
        """Das BEWUSST GETRAGENE Restrisiko (Daniel, 2026-09-14): Traegt eine Seite keinen
        aufgeloesten Ortsnamen - bevorzugt in duenn besiedelter Gegend -, entscheidet die
        Aehnlichkeit allein, und zwei verschiedene Sehenswuerdigkeiten koennen verschmelzen. Die
        Gegenmassnahme waere gewesen, den Aehnlichkeitspfad ohne beidseitigen Ortsnamen zu sperren
        - was in genau diesen Gegenden gar nicht mehr vereinheitlicht haette."""
        existing = [_entry("Zugspitze", entry_locality, [1.0, 0.0])]
        embedder = FakeLabelEmbedder({"zugspitzgipfel": [1.0, 0.0]})

        result = resolve_canonical_landmark(
            "Zugspitzgipfel", candidate_locality, existing, embedder
        )

        assert result is existing[0]


class TestTheLocalityIsTheLock:
    """Die Sperre traegt die Zusicherung gegen die gefaehrlichste Klasse: Ein mehrsprachiges
    Satz-Einbettungsmodell haelt "Koelner Dom" und "Ulmer Dom" fuer nahe verwandt, weil es die
    Bauform vergleicht und nicht den Eigennamen."""

    def test_two_different_resolved_localities_are_never_merged(self) -> None:
        """Geprueft bei AEHNLICHKEIT 1.0 - maximale Gegenkraft. Bei einem Wert knapp oberhalb der
        Schwelle koennte die Trennung auch an der Schwelle gelegen haben; hier kann allein der
        verschiedene Ortsname die Ursache sein."""
        existing = [_entry("Koelner Dom", "Koeln", [1.0, 0.0])]
        embedder = FakeLabelEmbedder({"ulmer dom": [1.0, 0.0]})

        result = resolve_canonical_landmark("Ulmer Dom", "Ulm", existing, embedder)

        assert result is not existing[0]
        assert result.display_name == "Ulmer Dom"

    def test_the_counter_probe_the_very_same_vectors_merge_at_the_same_locality(self) -> None:
        """Die Gegenprobe zum Fall darueber, mit denselben Vektoren: ohne sie bewiese er nur, dass
        irgendetwas trennt."""
        existing = [_entry("Koelner Dom", "Koeln", [1.0, 0.0])]
        embedder = FakeLabelEmbedder({"dom zu koeln": [1.0, 0.0]})

        result = resolve_canonical_landmark("Dom zu Koeln", "Koeln", existing, embedder)

        assert result is existing[0]

    def test_a_locked_entry_does_not_block_a_second_matching_entry(self) -> None:
        """Die Sperre gilt je EINTRAG, nicht fuer den ganzen Durchgang: Ein gesperrter Eintrag
        darf einen passenden dahinter nicht verdecken."""
        koeln = _entry("Koelner Dom", "Koeln", [1.0, 0.0])
        ulm = _entry("Ulmer Dom", "Ulm", [1.0, 0.0])
        embedder = FakeLabelEmbedder({"dom von ulm": [1.0, 0.0]})

        result = resolve_canonical_landmark("Dom von Ulm", "Ulm", [koeln, ulm], embedder)

        assert result is ulm


class TestANewEntryJoinsTheListImmediately:
    def test_an_unknown_name_becomes_a_new_entry_without_an_id(self) -> None:
        """Die `id` wird erst nach dem Einfuegen nachgesetzt (Muster `FineLabelSnapshotEntry`) -
        `None` heisst "noch nicht in der Datenbank"."""
        existing: list[LandmarkNameEntry] = []
        embedder = FakeLabelEmbedder({"zugspitze": [1.0, 0.0]})

        result = resolve_canonical_landmark("Zugspitze", "Grainau", existing, embedder)

        assert result.id is None
        assert result.display_name == "Zugspitze"
        assert result.normalized_name == "zugspitze"
        assert result.locality == "Grainau"
        assert result.embedding == [1.0, 0.0]

    def test_the_new_entry_extends_the_list_in_place(self) -> None:
        existing: list[LandmarkNameEntry] = []

        result = resolve_canonical_landmark(
            "Zugspitze", None, existing, FakeLabelEmbedder({"zugspitze": [1.0, 0.0]})
        )

        assert existing == [result]

    def test_a_second_similar_new_name_in_the_same_run_hits_the_first(self) -> None:
        """Ohne die In-place-Ergaenzung entstuenden zwei Zeilen fuer dieselbe Sehenswuerdigkeit im
        SELBEN Lauf - und die zweite koennte am projektweiten Eindeutigkeits-Constraint
        scheitern."""
        existing: list[LandmarkNameEntry] = []
        embedder = FakeLabelEmbedder({"zugspitze": [1.0, 0.0], "zugspitzgipfel": [1.0, 0.0]})

        first = resolve_canonical_landmark("Zugspitze", "Grainau", existing, embedder)
        second = resolve_canonical_landmark("Zugspitzgipfel", "Grainau", existing, embedder)

        assert second is first
        assert len(existing) == 1

    def test_a_second_identical_new_name_takes_the_fast_path(self) -> None:
        existing: list[LandmarkNameEntry] = []
        embedder = FakeLabelEmbedder({"zugspitze": [1.0, 0.0]})

        first = resolve_canonical_landmark("Zugspitze", None, existing, embedder)
        second = resolve_canonical_landmark("zugspitze", None, existing, embedder)

        assert second is first
        assert embedder.calls == ["zugspitze"]


class TestTheSimilarityThresholdIsItsOwn:
    def test_it_is_not_the_one_of_the_fine_labels(self) -> None:
        """Eigennamen verlangen einen strengeren Massstab als Sachbegriffe, und beide muessen sich
        unabhaengig bewegen koennen (ADR 0107 Punkt 4)."""
        from photosort.remote_classification import CATEGORY_LABEL_SIMILARITY_THRESHOLD

        assert LANDMARK_NAME_SIMILARITY_THRESHOLD > CATEGORY_LABEL_SIMILARITY_THRESHOLD

    def test_the_landmark_module_does_not_import_the_category_path(self) -> None:
        """Der Grund, aus dem die beiden generischen Helfer nach `label_embedding.py` gezogen sind:
        Feinlabels und Sehenswuerdigkeitsnamen sind fachlich unverbunden."""
        assert "photosort.remote_classification" not in import_closure("photosort.landmark_names")


class TestTheModuleBoundary:
    """Muster `places.py`: die reine Aufloesungslogik ist DB-frei, der Datenbankzugriff bleibt in
    `worker.py`."""

    def test_the_module_imports_neither_sqlalchemy_nor_the_models(self) -> None:
        closure = import_closure("photosort.landmark_names")

        assert "photosort.models" not in closure
        assert "sqlalchemy" not in imported_root_packages("photosort.landmark_names")

    def test_the_import_graph_walker_actually_finds_something(self) -> None:
        # Gegenprobe: ohne sie bestuende der Fall oben auch dann, wenn der Walker nichts findet.
        assert "photosort.label_embedding" in import_closure("photosort.landmark_names")
        assert "photosort" in imported_root_packages("photosort.landmark_names")

    def test_the_module_never_reaches_for_a_session(self) -> None:
        path = module_file("photosort.landmark_names")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))

        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

        assert "session" not in names


def _vector_with_similarity(similarity: float) -> list[float]:
    """Ein Einheitsvektor mit exakt dieser Kosinus-Aehnlichkeit zu `[1.0, 0.0]` - dieselbe
    Konstruktion wie in tests/test_remote_classification.py."""
    return [similarity, (1.0 - similarity**2) ** 0.5]
