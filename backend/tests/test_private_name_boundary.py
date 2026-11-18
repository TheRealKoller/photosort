"""Die Sichtbarkeitsgrenze (Spec 0648, ADR 0150).

Ein Name mit genau einem fuehrenden Unterstrich ist in der Datei benutzbar, die ihn definiert.
Jede andere Datei - Produktion wie Test - bezieht ihn nicht: nicht per `from ... import _name`,
nicht ueber `alias._name` eines `photosort`-Moduls, nicht ueber `setattr`/`getattr`/
`monkeypatch.setattr`/`patch.object` und nicht als Patch-Zeichenkette `photosort.a.b._name`.

Ein Unterstrich am MODULSEGMENT (`photosort.worker._runs`) ist ausgenommen: das ist eine
Ablage-Adresse im eigenen Paket, kein Name (ADR 0150 Punkt 2). Der Waechter misst gebundene
Namen, keine Verzeichnisse.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.import_closure import SRC_DIR, module_file

TESTS_DIR = Path(__file__).resolve().parent
PRODUCTION_DIR = SRC_DIR / "photosort"

_PATCH_ZIEL = re.compile(r"^photosort(?:\.[A-Za-z_]\w*)+$")


def _ismodulpfad(teile: list[str]) -> bool:
    """`True`, wenn die Teilefolge ein Modul des Quellbaums adressiert - nicht einen Namen darin."""
    return module_file(".".join(teile)) is not None


def _resolviertes_modul(teile: list[str]) -> tuple[str, list[str]] | None:
    """Laengstes Modulpraefix der Teilefolge plus die Namen dahinter."""
    for schnitt in range(len(teile), 0, -1):
        if _ismodulpfad(teile[:schnitt]):
            return ".".join(teile[:schnitt]), teile[schnitt:]
    return None


def _privater_name(teile: list[str]) -> str | None:
    """Der erste gebundene private Name der Teilefolge, `None` wenn keiner."""
    for teil in teile:
        if teil.startswith("_") and not teil.startswith("__"):
            return teil
    return None


def _privater_string(ausdruck: ast.expr) -> str | None:
    if isinstance(ausdruck, ast.Constant) and isinstance(ausdruck.value, str):
        wert = ausdruck.value
        if wert.startswith("_") and not wert.startswith("__"):
            return wert
    return None


class _Dateipruefung(ast.NodeVisitor):
    """Alle Verstossstellen EINER Datei."""

    def __init__(self, pfad: Path) -> None:
        self.pfad = pfad
        self.verstoesse: list[tuple[int, str, str]] = []
        self._modulaliase: dict[str, str] = {}

    def binde_aliase(self) -> None:
        """Aliase, die an ein `photosort`-Modul gebunden sind - Grundlage der Attributform."""
        for knoten in ast.walk(ast.parse(self.pfad.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.Import):
                for alias in knoten.names:
                    if alias.asname is not None:
                        self._modulaliase[alias.asname] = alias.name
                    else:
                        wurzel = alias.name.split(".")[0]
                        self._modulaliase[wurzel] = wurzel
            elif isinstance(knoten, ast.ImportFrom) and knoten.module is not None:
                if not knoten.module.startswith("photosort"):
                    continue
                for alias in knoten.names:
                    untermodul = f"{knoten.module}.{alias.name}"
                    gebunden = alias.asname or alias.name
                    if _ismodulpfad(untermodul.split(".")):
                        self._modulaliase[gebunden] = untermodul

    def _modul_von(self, ausdruck: ast.expr) -> str | None:
        """Das `photosort`-Modul, an das ein Ausdruck gebunden ist - Alias plus Attributkette."""
        teile: list[str] = []
        while isinstance(ausdruck, ast.Attribute):
            teile.insert(0, ausdruck.attr)
            ausdruck = ausdruck.value
        if not isinstance(ausdruck, ast.Name):
            return None
        wurzel = self._modulaliase.get(ausdruck.id)
        if wurzel is None:
            return None
        aufgeloest = _resolviertes_modul([*wurzel.split("."), *teile])
        return aufgeloest[0] if aufgeloest is not None else None

    def _melde(self, zeile: int, name: str, modul: str) -> None:
        self.verstoesse.append((zeile, name, modul))

    def visit_ImportFrom(self, knoten: ast.ImportFrom) -> None:
        if knoten.module is not None and knoten.module.startswith("photosort"):
            for alias in knoten.names:
                if _ismodulpfad(f"{knoten.module}.{alias.name}".split(".")):
                    continue
                name = alias.name
                if name.startswith("_") and not name.startswith("__"):
                    quelldatei = module_file(knoten.module)
                    if quelldatei is not None and quelldatei != self.pfad:
                        self._melde(knoten.lineno, name, knoten.module)
        self.generic_visit(knoten)

    def visit_Attribute(self, knoten: ast.Attribute) -> None:
        if knoten.attr.startswith("_") and not knoten.attr.startswith("__"):
            modul = self._modul_von(knoten.value)
            if modul is not None:
                self._melde(knoten.lineno, knoten.attr, modul)
        self.generic_visit(knoten)

    def visit_Call(self, knoten: ast.Call) -> None:
        if isinstance(knoten.func, ast.Attribute):
            func = knoten.func.attr
        elif isinstance(knoten.func, ast.Name):
            func = knoten.func.id
        else:
            func = None
        if func in {"setattr", "getattr", "object"} and len(knoten.args) >= 2:
            name = _privater_string(knoten.args[1])
            if name is not None:
                self._melde(knoten.lineno, name, self._modul_von(knoten.args[0]) or "?")
        for argument in [*knoten.args, *(kw.value for kw in knoten.keywords)]:
            if not (isinstance(argument, ast.Constant) and isinstance(argument.value, str)):
                continue
            text = argument.value
            if not _PATCH_ZIEL.match(text):
                continue
            aufgeloest = _resolviertes_modul(text.split("."))
            if aufgeloest is None:
                continue
            modul, reste = aufgeloest
            name = _privater_name(reste)
            if name is not None:
                self._melde(knoten.lineno, name, modul)
        self.generic_visit(knoten)


def _relativ(pfad: Path) -> str:
    """Adresse der Datei in der Arbeitsliste: `src`- bzw. `tests`-relativ."""
    if PRODUCTION_DIR in pfad.parents:
        return pfad.relative_to(PRODUCTION_DIR).as_posix()
    if TESTS_DIR in pfad.parents:
        return "tests/" + pfad.relative_to(TESTS_DIR).as_posix()
    return pfad.name


def finde_verstoesse(pfad: Path) -> list[tuple[int, str, str]]:
    """`(zeile, privater Name, Modul)` je Verstoss einer Datei."""
    pruefung = _Dateipruefung(pfad)
    pruefung.binde_aliase()
    pruefung.visit(ast.parse(pfad.read_text(encoding="utf-8")))
    if pfad.resolve() == Path(__file__).resolve():
        # Die eigene Datei fuehrt die Verstoss-Beispiele ihres Selbstschutzes als Text; sie sind
        # Pruefmaterial, keine Benutzung. Alles ausserhalb der Beispieldefinitionen wird gemessen.
        return [fund for fund in pruefung.verstoesse if not _ist_beispiel(fund[0])]
    return pruefung.verstoesse


def _dateien(wurzel: Path) -> list[Path]:
    return sorted(wurzel.rglob("*.py"))


# Arbeitsliste waehrend der Abarbeitung (Spec 0648): Datei -> Namen. Geprueft wird GLEICHHEIT in
# beide Richtungen - ein neuer Verstoss wird rot, ein abgearbeiteter Eintrag ebenfalls.
_BEKANNTE_FUNDE_TEXT = """
album_suitability.py: _sanitize_label_text
api/model_choice.py: _reject_while_a_criterion_run_is_active
api/photos/__init__.py: _suggestion_reason
api/photos/_reads.py: _event_out _location_out
api/photos/album_draft.py: _album_level_source _event_and_location_by_photo_id _event_ids_from_rankings
    _filtered_photo_ids _final_selection_decisions _get_project_or_404
    _latest_successful_criterion_scoring_run_id _partition_sizes _photos_by_id _place_in_events
    _ranking_by_photo_id _run_events _to_photo_out _user_count
api/photos/album_selection.py: _album_level_source _event_and_location_by_photo_id
    _final_selection_decisions _get_project_or_404 _latest_successful_criterion_scoring_run_id
    _partition_sizes _photos_by_id _place_in_events _ranking_by_photo_id _run_events _to_photo_out
api/photos/ausschuss.py: _album_level_source _auto_decided_ids _event_and_location_by_photo_id
    _event_ids_from_rankings _final_selection_decisions _get_project_or_404
    _latest_successful_criterion_scoring_run_id _partition_sizes _photos_by_id _ranking_by_photo_id
    _suggestion_reason _to_photo_out _user_count
api/photos/draft_exchange.py: _album_level_source _event_and_location_by_photo_id
    _event_ids_from_rankings _final_selection_decisions _get_project_or_404
    _latest_successful_criterion_scoring_run_id _partition_sizes _photos_by_id _ranking_by_photo_id
    _to_photo_out _user_count
api/photos/duplicate_groups.py: _album_level_source _auto_decided_ids _event_and_location_by_photo_id
    _event_ids_from_rankings _final_selection_decisions _get_project_or_404
    _latest_successful_criterion_scoring_run_id _partition_sizes _photos_by_id _ranking_by_photo_id
    _to_photo_out _user_count
classification_review.py: _compute_content_criteria _finish_cancelled _raise_if_cancel_requested
    _take_over_queued_run _try_build
criterion_probe.py: _count_landmark_candidates
landmark.py: _sanitize_label_text
places.py: _sanitize_label_text
remote_classification.py: _sanitize_label_text
tests/test_aesthetics.py: _ASSET_PATH
tests/test_album_suitability.py: _sanitize_label_text
tests/test_api_classification_reviews.py: _guard_export_shape
tests/test_api_opencloud_folder_counts.py: _count_images_up_to_limit
tests/test_api_persons.py: _criterion_scoring_run_summary _name_taken _person_write_lock _phase_progress
    _phase_remaining_seconds _taken_slots _wait_for_the_second
tests/test_api_stats.py: _DATABASE_SIZE_SQL _local_database_bytes_estimate
tests/test_api_unnamed_faces.py: _embedding_at _on_model_thread
tests/test_classification.py: _FACE_DETECTOR_MODEL_PATH _FACE_LANDMARKER_MODEL_PATH
    _OBJECT_DETECTOR_MODEL_PATH _SCENE_CLASSIFIER_MODEL_PATH _laplace_edges_without_border_artifact
    _yaw_degrees_from_rotation_matrix
tests/test_classification_review_isolation.py: _build_classification_estimate
tests/test_criteria.py: _OBJECT_DETECTOR_MODEL_PATH _SCENE_CLASSIFIER_MODEL_PATH
tests/test_criterion_probe.py: _number _report_head
tests/test_demo_state.py: _DEMO_AUTO_DECIDED_GROUP_SIZE _DEMO_CORRECTED_INDEX _DEMO_DUPLICATE_GROUP_SIZES
    _DEMO_EXCLUDED_INDEX _DEMO_EYE_ALBUM_LEVEL _DEMO_EYE_MODEL_REVISION _DEMO_LOCAL_BASIS_INDEX
    _DEMO_UNASSESSED_INDEX
tests/test_duplicate_probe.py: _distribution _groups_of _summarise
tests/test_duplikat_anzeigezustand.py: _suggestion_reason
tests/test_event_probe.py: _quota_lines _report_head _tally
tests/test_events.py: _EARTH_RADIUS_METERS _landmark_name_is_plausible _round_limit _usable_name
tests/test_final_selection.py: _selection_state_of
tests/test_horizon.py: _score_from_angle_deviation _select_dominant_candidate_angle
tests/test_label_embedding.py: _mean_pool_and_normalize
tests/test_landmark.py: _build_prompt _landmark_detection_from_json
tests/test_opencloud_client.py: _join
tests/test_persons.py: _correction_row _delete_reference _has_correction_face
    _unlink_references_of_other_models
tests/test_place_dataset.py: _build_parser _download_archive
tests/test_remote_classification.py: _MAX_RESPONSE_TOKENS _classification_from_json _sanitize_label_text
    _slugify
tests/test_worker_classification.py: _now_utc
tests/test_worker_criterion_scoring.py: _IMAGE_ANALYSIS_CRITERION_KEYS _IMAGE_ANALYSIS_CRITERION_SOURCES
    _compute_content_criteria _count_landmark_candidates _log_cloud_vision_throttling _now_utc
    _recognize_persons _select_landmark_candidates _start_criterion_scoring_run
tests/test_worker_export.py: _join
tests/test_worker_eye_phase.py: _set_phase
tests/test_worker_fail_run.py: _commit_phase_costs _fail_run
tests/test_worker_finish_cancelled.py: _fail _fail_export_run _fail_run _finish_cancelled
tests/test_worker_persons.py: _build_grouping_and_rankings
tests/test_worker_place_names.py: _build_grouping_and_rankings _landmark_points_by_name _place_infos
tests/test_worker_reap_stalled_runs.py: _fail_run _now_utc
tests/test_worker_remote_category_classification.py: _count_remote_category_candidates
tests/test_worker_scan_classification.py: _classify_scan_entries
tests/test_worker_scan_project.py: _catch_up_aspect_ratios _now_utc
tests/test_worker_score_cancel.py: _raise_if_cancel_requested
tests/test_worker_score_project.py: _now_utc
worker/__init__.py: _CLOUD_VISION_IMAGE_MIME_TYPE _IMAGE_ANALYSIS_CRITERION_SOURCES _append_cloud_error
    _apply_run_selection _build_grouping_and_rankings _classify_scan_entries _clear_cloud_vision_error
    _commit_phase_costs _compute_content_criteria _detect_landmark_for_photo _fail_export_run _fail_run
    _finish_cancelled _finish_if_cancel_requested _landmark_place_cells _landmark_place_hints
    _landmark_points_by_name _log_cloud_vision_failure _log_cloud_vision_throttling _now_utc _place_infos
    _raise_if_cancel_requested _recognize_persons _record_cloud_vision_error _run_eye_phase
    _select_landmark_candidates _set_phase _start_criterion_scoring_run _take_over_queued_run _try_build
    _upsert_landmark_detection
worker/_criterion/eye.py: _now_utc _sanitize_label_text _set_phase
worker/_criterion/landmark.py: _CLOUD_VISION_IMAGE_MIME_TYPE _append_cloud_error
    _clear_cloud_vision_error _commit_phase_costs _log_cloud_vision_failure _log_cloud_vision_throttling
    _now_utc _raise_if_cancel_requested _record_cloud_vision_error _try_build
worker/_criterion/local.py: _now_utc _raise_if_cancel_requested _try_build
worker/_criterion/persons.py: _now_utc _set_phase _try_build
worker/_criterion/ranking.py: _now_utc
worker/classification.py: _append_cloud_error _fail_run _finish_cancelled _finish_if_cancel_requested
    _run_eye_phase _set_phase _start_criterion_scoring_run _take_over_queued_run
worker/criterion_scoring.py: _apply_run_selection _build_grouping_and_rankings _fail_run
    _finish_cancelled _landmark_place_cells _landmark_place_hints _now_utc _place_infos
    _raise_if_cancel_requested _recognize_persons _run_landmark_phase _run_local_phase
    _select_landmark_candidates _set_phase _write_local_motif_header
worker/export.py: _fail_export_run _finish_cancelled _join _now_utc _take_over_queued_run
worker/remote_categories.py: _CLOUD_VISION_IMAGE_MIME_TYPE _clear_cloud_vision_error _commit_phase_costs
    _fail_run _finish_cancelled _log_cloud_vision_failure _log_cloud_vision_throttling _now_utc
    _raise_if_cancel_requested _record_cloud_vision_error _try_build
worker/scan.py: _fail_run _finish_cancelled _now_utc _raise_if_cancel_requested _take_over_queued_run
worker/scoring.py: _fail_run _finish_cancelled _now_utc _raise_if_cancel_requested _take_over_queued_run
worker/stall_reaper.py: _fail_export_run _fail_run _now_utc
"""


def _bekannte_funde() -> dict[str, set[str]]:
    """Arbeitsliste: Datei -> Namen, gelesen aus dem Blocktext."""
    eintraege: list[str] = []
    for zeile in _BEKANNTE_FUNDE_TEXT.splitlines():
        if eintraege and zeile.startswith("   ") and not zeile.startswith(": "):
            eintraege[-1] += " " + zeile.strip()
        else:
            eintraege.append(zeile)
    funde: dict[str, set[str]] = {}
    for eintrag in filter(None, eintraege):
        datei, _, namen = eintrag.partition(":")
        funde[datei] = set(namen.split())
    return funde


def test_kein_privater_name_ueberschreitet_eine_dateigrenze() -> None:
    gefunden: dict[str, set[str]] = {}
    for wurzel in (PRODUCTION_DIR, TESTS_DIR):
        for pfad in _dateien(wurzel):
            for _, name, _ in finde_verstoesse(pfad):
                gefunden.setdefault(_relativ(pfad), set()).add(name)
    erwartet = _bekannte_funde()
    neu = sorted(set(gefunden) - set(erwartet))
    abgearbeitet = sorted(set(erwartet) - set(gefunden))
    geaendert = sorted(
        datei for datei in set(gefunden) & set(erwartet) if gefunden[datei] != erwartet[datei]
    )
    assert not (neu or abgearbeitet or geaendert), (
        "Sichtbarkeitsgrenze verletzt (ADR 0150): "
        f"neu={neu} abgearbeitet={abgearbeitet} geaendert={geaendert}"
    )


def test_die_messung_ist_nicht_leer_und_deckt_den_baum() -> None:
    geprueft = {
        _relativ(pfad) for wurzel in (PRODUCTION_DIR, TESTS_DIR) for pfad in _dateien(wurzel)
    }
    assert len(geprueft) > 100
    assert "api/model_choice.py" in geprueft


def _meldung(pfad: Path) -> list[str]:
    return [
        f"{pfad.name}:{zeile}: {name} aus {modul}" for zeile, name, modul in finde_verstoesse(pfad)
    ]


_KEIN_VERSTOSS = [
    "from photosort.worker._runs import set_phase, now_utc\n",
    "from photosort.opencloud.client import join_remote_path\n",
]

_VERSTOSS_BEISPIELE = [
    ("from photosort.opencloud.client import _join\n", "_join", "from-import", 1),
    (
        "import photosort.worker._runs as runs\n\nx = runs._set_phase\n",
        "_set_phase",
        "attribut",
        3,
    ),
    (
        "import photosort.worker._runs as runs\n\nsetattr(runs, '_set_phase', None)\n",
        "_set_phase",
        "setattr",
        3,
    ),
    (
        "from unittest import mock\n\nmock.patch('photosort.worker._runs._fail_run')\n",
        "_fail_run",
        "patch-ziel",
        3,
    ),
]
# Grenzen der Beispieldefinitionen - der Detektor liest die eigene Datei und ueberspringt sie.
_BEISPIEL_ZEILEN = (0, 0)
_QUELLEN_ZEILEN: frozenset[int] = frozenset()


def _ist_beispiel(zeile: int) -> bool:
    return _BEISPIEL_ZEILEN[0] <= zeile <= _BEISPIEL_ZEILEN[1] or zeile in _QUELLEN_ZEILEN


def _snippet(tmp_path: Path, quelle: str) -> Path:
    pfad = tmp_path / "fall.py"
    pfad.write_text(quelle, encoding="utf-8")
    return pfad


@pytest.mark.parametrize("quelle", _KEIN_VERSTOSS, ids=["unbekannt", "oeffentlich"])
def test_ein_snippet_ohne_verstoss_bleibt_leer(tmp_path: Path, quelle: str) -> None:
    assert finde_verstoesse(_snippet(tmp_path, quelle)) == []


@pytest.mark.parametrize(
    ("quelle", "erwarteter_name", "zeile"),
    [
        pytest.param(quelle, name, zeile, id=ident)
        for quelle, name, ident, zeile in _VERSTOSS_BEISPIELE
    ],
)
def test_jede_erfassungsform_meldet_genau_einen_fund(
    tmp_path: Path, quelle: str, erwarteter_name: str, zeile: int
) -> None:
    meldungen = _meldung(_snippet(tmp_path, quelle))
    assert len(meldungen) == 1, meldungen
    assert meldungen[0].startswith(f"fall.py:{zeile}: {erwarteter_name} aus ")


def test_die_eigene_datei_darf_ihren_eigenen_privaten_namen_lesen() -> None:
    assert finde_verstoesse(Path(__file__)) == []


def test_ein_unterstrich_modulsegment_ist_kein_verstoss() -> None:
    verstoesse = {
        name for _, name, _ in finde_verstoesse(TESTS_DIR / "test_worker_import_graph.py")
    }
    assert "_runs" not in verstoesse


def _beispielgrenzen() -> tuple[int, int]:
    """Zeilenbereich der Beispieldefinitionen in dieser Datei (Start- und Endzeile)."""
    quellzeilen = Path(__file__).read_text(encoding="utf-8").splitlines()
    start = next(i for i, zeile in enumerate(quellzeilen, 1) if zeile.startswith("_KEIN_VERSTOSS"))
    ende = next(i for i, zeile in enumerate(quellzeilen, 1) if zeile.startswith("_QUELLEN_ZEILEN"))
    return start, ende


_BEISPIEL_ZEILEN = _beispielgrenzen()
_QUELLEN_ZEILEN = frozenset({_BEISPIEL_ZEILEN[0], _BEISPIEL_ZEILEN[1]})
