"""Die feste Entscheidungsregel "sicher erkannt".

Die Grenzfaelle laufen auf Aehnlichkeitsebene unter einer `autouse`-Parametrierung mit binaer
exakten Schwellen:
Mit `0.1` waere `s_andere + ABSTAND` nicht exakt, und ein Fall genau auf der Schwelle waere je nach
Rechenform rot oder gruen. Die Faelle lesen die Schwellen deshalb als MODULATTRIBUT. Die
kalibrierten Werte stehen genau einmal als Literal (`TestTheCalibratedConstants`).
"""

from __future__ import annotations

import ast
import math

import pytest

from photosort import person_matching
from photosort.person_matching import (
    EMBEDDING_DIMENSION,
    StoredReference,
    centroid,
    conflicts_with_other_person,
    decide_assignments,
    is_usable,
    similarities_to,
    validated_embedding,
)
from tests.import_closure import SRC_DIR

MODEL = "aktuelles-modell"
P = 1
Q = 2


@pytest.fixture(autouse=True, params=[(0.5, 0.125), (0.625, 0.25)], ids=["0.5/0.125", "0.625/0.25"])
def _dyadic_thresholds(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    accept, margin = request.param
    monkeypatch.setattr(person_matching, "ACCEPT_SIMILARITY", accept)
    monkeypatch.setattr(person_matching, "DISTINCT_MARGIN", margin)


def _accept() -> float:
    return person_matching.ACCEPT_SIMILARITY


def _margin() -> float:
    return person_matching.DISTINCT_MARGIN


def _basis(index: int, *, scale: float = 1.0) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[index] = scale
    return vector


def _reference(vector: list[float], model_key: str = MODEL) -> StoredReference:
    return StoredReference(model_key=model_key, embedding=vector)


class TestTheCentroid:
    def test_the_centroid_not_the_closest_single_reference_decides(self) -> None:
        """Eine Referenz gleich dem Gesicht, zwei orthogonal: der naechste Einzelwert waere 1,
        der Schwerpunkt liegt fern - kein Kandidat."""
        references = [_reference(_basis(0)), _reference(_basis(1)), _reference(_basis(1))]
        person = centroid(references, model_key=MODEL)
        assert person is not None

        [similarity] = similarities_to(_basis(0), {P: person}).values()

        assert similarity < _accept()
        assert decide_assignments([{P: similarity}]) == frozenset()

    def test_the_result_does_not_depend_on_the_length_of_the_vectors(self) -> None:
        short = centroid([_reference(_basis(0, scale=0.5)), _reference(_basis(1))], model_key=MODEL)
        long = centroid([_reference(_basis(0, scale=3.0)), _reference(_basis(1))], model_key=MODEL)

        assert short is not None and long is not None
        assert short == pytest.approx(long)
        assert math.fsum(value * value for value in short) == pytest.approx(1.0)

    def test_a_single_reference_is_its_own_centroid(self) -> None:
        vector = [0.0] * EMBEDDING_DIMENSION
        vector[3], vector[4] = 0.6, 0.8

        assert centroid([_reference(vector)], model_key=MODEL) == pytest.approx(tuple(vector))

    def test_references_of_another_model_key_do_not_flow_in(self) -> None:
        mixed = centroid(
            [_reference(_basis(0)), _reference(_basis(1), model_key="altes-modell")],
            model_key=MODEL,
        )

        assert mixed == pytest.approx(tuple(_basis(0)))

    def test_a_person_without_a_valid_reference_is_never_a_candidate(self) -> None:
        only_foreign = centroid([_reference(_basis(0), model_key="altes-modell")], model_key=MODEL)
        only_broken = centroid([_reference([math.nan] * EMBEDDING_DIMENSION)], model_key=MODEL)

        assert only_foreign is None
        assert only_broken is None
        assert similarities_to(_basis(0), {}) == {}
        assert decide_assignments([{}]) == frozenset()


class TestAcceptanceAndMargin:
    def test_exactly_on_the_acceptance_threshold_counts_as_reached(self) -> None:
        assert decide_assignments([{P: _accept()}]) == frozenset({P})

    def test_just_below_the_acceptance_threshold_is_not_reached(self) -> None:
        below = math.nextafter(_accept(), 0.0)

        assert decide_assignments([{P: below}]) == frozenset()

    def test_exactly_the_margin_above_the_other_person_counts_as_reached(self) -> None:
        other = _accept() - _margin()

        assert decide_assignments([{P: _accept(), Q: other}]) == frozenset({P})

    def test_less_than_the_margin_above_the_other_person_is_not_reached(self) -> None:
        other = math.nextafter(_accept() - _margin(), 1.0)

        assert decide_assignments([{P: _accept(), Q: other}]) == frozenset()

    def test_a_face_equally_similar_to_both_gets_neither(self) -> None:
        assert decide_assignments([{P: 1.0, Q: 1.0}]) == frozenset()

    def test_with_one_person_only_the_acceptance_threshold_applies(self) -> None:
        """Festgehaltenes Verhalten: ohne zweite Person gibt es keinen Abstand zu pruefen."""
        assert decide_assignments([{P: _accept()}]) == frozenset({P})

    def test_a_nan_similarity_never_names(self) -> None:
        assert decide_assignments([{P: math.nan}]) == frozenset()
        assert decide_assignments([{P: 1.0, Q: math.nan}]) == frozenset()
        assert decide_assignments([{P: math.nan, Q: 0.0}]) == frozenset()


class TestOneToOne:
    def test_two_candidates_for_p_name_nobody_p_but_q_through_a_third_face(self) -> None:
        faces = [{P: 1.0, Q: 0.0}, {P: 1.0, Q: 0.0}, {P: 0.0, Q: 1.0}]

        assert decide_assignments(faces) == frozenset({Q})

    def test_a_face_is_never_assigned_to_both_persons(self) -> None:
        assert decide_assignments([{P: 1.0, Q: 1.0 - _margin() / 2}]) == frozenset()

    def test_one_candidate_each_names_both(self) -> None:
        assert decide_assignments([{P: 1.0, Q: 0.0}, {P: 0.0, Q: 1.0}]) == frozenset({P, Q})

    def test_no_faces_name_nobody(self) -> None:
        assert decide_assignments([]) == frozenset()

    def test_the_order_of_faces_and_references_does_not_matter(self) -> None:
        faces = [{P: 1.0, Q: 0.0}, {P: 0.0, Q: 1.0}, {P: 0.2, Q: 0.1}]
        forward = decide_assignments(faces)
        backward = decide_assignments([dict(reversed(face.items())) for face in reversed(faces)])

        references = [_reference(_basis(0)), _reference(_basis(1))]
        assert centroid(references, model_key=MODEL) == pytest.approx(
            centroid(list(reversed(references)), model_key=MODEL)
        )
        assert forward == backward == frozenset({P, Q})


class TestTighteningIsNotMonotone:
    def test_a_higher_acceptance_threshold_can_create_a_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Zwei Kandidaten heissen "nicht benennen"; eine strengere Schwelle streicht einen davon,
        und das Foto traegt danach einen Namen, den es vorher nicht trug. Nach jeder Verschaerfung
        ist die Durchsicht deshalb vollstaendig zu wiederholen."""
        faces = [{P: 0.75}, {P: 1.0}]
        assert decide_assignments(faces) == frozenset()

        monkeypatch.setattr(person_matching, "ACCEPT_SIMILARITY", 0.875)

        assert decide_assignments(faces) == frozenset({P})


class TestARejectedReference:
    """Ein gezeigtes Gesicht, das der ANDEREN Person gleicht, wird abgelehnt."""

    def test_exactly_on_the_acceptance_threshold_is_rejected(self) -> None:
        assert conflicts_with_other_person(_accept()) is True

    def test_just_below_is_accepted(self) -> None:
        assert conflicts_with_other_person(math.nextafter(_accept(), 0.0)) is False

    def test_nan_is_rejected(self) -> None:
        assert conflicts_with_other_person(math.nan) is True


class TestTheEmbeddingCheck:
    def test_a_unit_vector_passes(self) -> None:
        assert validated_embedding(_basis(5)) == tuple(_basis(5))

    @pytest.mark.parametrize(
        "broken",
        [
            [math.nan] + [0.0] * (EMBEDDING_DIMENSION - 1),
            [math.inf] + [0.0] * (EMBEDDING_DIMENSION - 1),
            [0.0] * EMBEDDING_DIMENSION,
            _basis(0, scale=1.5),
            _basis(0, scale=0.5),
            [1.0] * 127,
            [1.0 / math.sqrt(129)] * 129,
        ],
        ids=["nan", "inf", "nullvektor", "norm-zu-gross", "norm-zu-klein", "127", "129"],
    )
    def test_a_broken_embedding_is_refused(self, broken: list[float]) -> None:
        assert validated_embedding(broken) is None

    def test_the_norm_band_is_inclusive(self) -> None:
        edge = _basis(0, scale=1.0 + person_matching.NORM_TOLERANCE)
        beyond = _basis(0, scale=1.0 + 2 * person_matching.NORM_TOLERANCE)

        assert validated_embedding(edge) is not None
        assert validated_embedding(beyond) is None


class TestUsability:
    def test_exactly_the_minimum_score_and_side_is_usable(self) -> None:
        side = person_matching.MIN_FACE_SIDE_PX
        score = person_matching.MIN_DETECTION_SCORE

        assert is_usable(score=score, width=side, height=side) is True

    def test_just_below_either_is_not_usable(self) -> None:
        side = person_matching.MIN_FACE_SIDE_PX
        score = person_matching.MIN_DETECTION_SCORE

        assert is_usable(score=math.nextafter(score, 0.0), width=side, height=side) is False
        assert is_usable(score=score, width=side - 0.5, height=side) is False
        assert is_usable(score=score, width=side, height=side - 0.5) is False

    def test_a_nan_score_is_not_usable(self) -> None:
        side = person_matching.MIN_FACE_SIDE_PX

        assert is_usable(score=math.nan, width=side, height=side) is False


_RULE_CONSTANTS = (
    "MIN_DETECTION_SCORE",
    "MIN_FACE_SIDE_PX",
    "ACCEPT_SIMILARITY",
    "DISTINCT_MARGIN",
    "MAX_FACES_PER_PHOTO",
    "MAX_REFERENCES_PER_PERSON",
)


class TestTheCalibratedConstants:
    def test_the_start_values(self) -> None:
        """Der EINE Literalfall. Eine Lockerung wird hier laut und verlangt eine neue, fehlerfreie
        Abnahme im laufenden Betrieb."""
        source = (SRC_DIR / "photosort" / "person_matching.py").read_text(encoding="utf-8")
        assigned = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in ast.parse(source).body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in _RULE_CONSTANTS
        }

        assert assigned == {
            "MIN_DETECTION_SCORE": 0.90,
            "MIN_FACE_SIDE_PX": 100,
            "ACCEPT_SIMILARITY": 0.50,
            "DISTINCT_MARGIN": 0.10,
            "MAX_FACES_PER_PHOTO": 20,
            "MAX_REFERENCES_PER_PERSON": 20,
        }

    def test_the_constants_are_assigned_only_in_person_matching(self) -> None:
        assigning = sorted(
            {
                path.name
                for path in SRC_DIR.rglob("*.py")
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(node, ast.Assign | ast.AnnAssign)
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
                if isinstance(target, ast.Name) and target.id in _RULE_CONSTANTS
            }
        )

        assert assigning == ["person_matching.py"]

    def test_the_module_reads_neither_environment_nor_settings(self) -> None:
        tree = ast.parse((SRC_DIR / "photosort" / "person_matching.py").read_text("utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {(node.module or "") for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}

        assert imported <= {"__future__", "math", "collections.abc", "dataclasses"}
