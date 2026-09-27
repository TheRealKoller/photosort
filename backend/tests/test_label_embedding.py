from __future__ import annotations

import ast
import hashlib
import math
import os
import socket
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from photosort.label_embedding import (
    EMBEDDING_DIMENSION,
    LABEL_EMBEDDER_ONNX_PATH,
    LABEL_EMBEDDER_TOKENIZER_PATH,
    LABEL_EMBEDDER_TOKENIZER_SHA256,
    LabelEmbedderLike,
    _mean_pool_and_normalize,
    cosine_similarity,
    normalize_label_text,
)
from photosort.model_assets import LABEL_EMBEDDER_ONNX
from tests.import_closure import SRC_DIR

# specs/decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 4,
# specs/architecture/0002-testkonzept.md ("label_embedding.py"): analog test_aesthetics.py/
# test_classification.py - ein eigener Integritaets-Test je gepinntem Modell-Asset.


class TestLabelEmbedderAssets:
    def test_committed_onnx_file_matches_the_documented_sha256(self) -> None:
        digest = hashlib.sha256(LABEL_EMBEDDER_ONNX_PATH.read_bytes()).hexdigest()
        assert digest == LABEL_EMBEDDER_ONNX.sha256

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


# specs/features/0469, Teil 2 Schritt 1: Die beiden generischen Helfer sind aus
# `remote_classification.py` hierher gezogen, damit der Sehenswuerdigkeits-Pfad sie nicht aus dem
# Kategorie-Pfad importieren muss. VERHALTENSERHALTEND - die Faelle stehen unveraendert hier, mit
# denselben Namen und denselben Assertions, nur gegen den neuen Importpfad.


class TestNormalizeLabelText:
    def test_casefolds_and_strips(self) -> None:
        assert normalize_label_text("  HUND  ") == "hund"

    def test_nfkc_normalizes_equivalent_unicode_forms(self) -> None:
        # "ﬁsch" (Ligatur U+FB01) normalisiert NFKC zu "fisch".
        assert normalize_label_text("ﬁsch") == "fisch"


class TestCosineSimilarity:
    def test_identical_vectors_have_similarity_one(self) -> None:
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_have_similarity_zero(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def _closed_local_port() -> int:
    """Ein Port, auf dem niemand lauscht: gebunden, sofort wieder freigegeben. Ein Upload, der
    trotz Abschaltung versucht wird, laeuft dort in eine Ablehnung statt ins Netz."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


class TestTelemetryIsOff:
    """S15: `onnxruntime` uebertraegt keine Telemetrie, auch ausserhalb der CI.

    Rot-Beleg (kein Testfall, weil er gegen einen fremden Dienst liefe): Ohne Abschaltung
    entstehen unter `onnxruntime` 1.29.0 schon beim blossen `import onnxruntime`
    `…/Microsoft/DeveloperTools/.onnxruntime/deviceid` und `onnxruntime.db`, gemessen lokal am
    2026-09-27.

    Der Unterprozess bekommt eine VON GRUND AUF gebaute Umgebung: kein `CI`/`GITHUB_ACTIONS`
    (sonst schaltet sich das SDK selbst ab), kein geerbtes `ORT_DISABLE_TELEMETRY` aus
    `conftest.py` oder dem Image (sonst bestuende der Fall auch ohne die Zeile im Code)."""

    def test_building_the_embedder_leaves_home_cache_and_working_directory_empty(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        cache = tmp_path / "cache"
        work = tmp_path / "work"
        for directory in (home, cache, work):
            directory.mkdir()
        proxy = f"http://127.0.0.1:{_closed_local_port()}"
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(home),
            "XDG_CACHE_HOME": str(cache),
            "https_proxy": proxy,
            "HTTPS_PROXY": proxy,
        }
        program = (
            "from photosort.label_embedding import build_label_embedder\n"
            "vector = build_label_embedder().embed('Hund')\n"
            "assert len(vector) == 384\n"
        )

        completed = subprocess.run(
            [sys.executable, "-c", program],
            cwd=work,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        for directory in (home, cache, work):
            assert sorted(path.name for path in directory.rglob("*")) == [], directory.name


def _onnxruntime_imports() -> list[tuple[Path, ast.AST, list[ast.stmt]]]:
    """Jede Importstelle von `onnxruntime` im Quellbaum, samt des Koerpers, in dem sie steht."""
    found: list[tuple[Path, ast.AST, list[ast.stmt]]] = []
    for path in sorted(SRC_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for parent in ast.walk(tree):
            body = getattr(parent, "body", None)
            if not isinstance(body, list):
                continue
            for statement in body:
                names: list[str] = []
                if isinstance(statement, ast.Import):
                    names = [alias.name for alias in statement.names]
                elif isinstance(statement, ast.ImportFrom):
                    names = [statement.module or ""]
                if any(name.split(".")[0] == "onnxruntime" for name in names):
                    found.append((path, statement, body))
    return found


def _is_the_disabling_assignment(statement: ast.stmt) -> bool:
    """`os.environ["ORT_DISABLE_TELEMETRY"] = "1"` - zuweisend, nie `setdefault`."""
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
        return False
    target = statement.targets[0]
    return (
        isinstance(target, ast.Subscript)
        and ast.unparse(target.value) == "os.environ"
        and isinstance(target.slice, ast.Constant)
        and target.slice.value == "ORT_DISABLE_TELEMETRY"
        and isinstance(statement.value, ast.Constant)
        and statement.value.value == "1"
    )


class TestTheOnlyImportOfOnnxruntimeIsPrecededByTheSwitch:
    """Eine zweite Importstelle umginge die Abschaltung, ohne dass der Unterprozessfall rot wird."""

    def test_onnxruntime_is_imported_at_exactly_one_place(self) -> None:
        imports = _onnxruntime_imports()

        assert [path.name for path, _statement, _body in imports] == ["label_embedding.py"]

    def test_the_assignment_stands_before_it_in_the_same_body(self) -> None:
        [(_path, statement, body)] = _onnxruntime_imports()
        before = body[: body.index(statement)]  # type: ignore[arg-type]

        assert any(_is_the_disabling_assignment(earlier) for earlier in before)

    def test_the_guard_recognises_the_assignment_and_not_setdefault(self) -> None:
        """Gegenprobe gegen Vakuum-Gruen des Waechters."""
        assignment = ast.parse('os.environ["ORT_DISABLE_TELEMETRY"] = "1"').body[0]
        setdefault = ast.parse('os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")').body[0]

        assert _is_the_disabling_assignment(assignment)
        assert not _is_the_disabling_assignment(setdefault)
