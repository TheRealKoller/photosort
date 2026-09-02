"""Tests fuer scripts/gh-board.py (Spec 0262 / ADR 0043).

Kein Netzwerk, kein echtes `gh`: das Script bekommt sein `run`-Callable injiziert, ein FakeGh
beantwortet die Aufrufe aus einem In-Memory-Zustand und protokolliert dabei die tatsaechlich
konstruierten Argumentlisten (dieselbe Technik wie im abgeloesten test_gh_adapter.py).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

# Bindestrich im Dateinamen (analog zu seed-opencloud-demo.py, siehe conftest.py) - kein
# gueltiger Python-Modulname, daher per Pfad statt per "import" geladen.
_SCRIPT_PATH = Path(__file__).parent.parent / "gh-board.py"

OWNER = "TheRealKoller"
REPO = "photosort"
PROJECT_TITLE = "PhotoSort Roadmap"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gh_board", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def gh_board() -> ModuleType:
    return _load_module()


def _completed(
    stdout: str = "", *, returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


GH_VERSION_STDOUT = (
    "gh version 2.72.0 (2025-04-30)\nhttps://github.com/cli/cli/releases/tag/v2.72.0\n"
)

# So meldet `gh auth status`, wenn ueberhaupt keine Anmeldung vorliegt (Returncode 1).
NICHT_ANGEMELDET_AUSGABE = (
    "You are not logged into any GitHub hosts. To log in, run: gh auth login"
)

# `gh auth status` meldet pro Host MEHRERE Kontobloecke, sobald neben einem Umgebungstoken noch
# ein gespeichertes Konto existiert (lokal so beobachtet mit gh 2.98.0). Hier traegt das
# INAKTIVE Konto den `project`-Scope, das aktive nicht - wer die erste beste Scope-Zeile nimmt,
# meldet die Rechte eines Kontos, mit dem gar nicht gearbeitet wird.
ZWEI_KONTEN_AUSGABE = (
    "github.com\n"
    "  X Failed to log in to github.com account zweitkonto (keyring)\n"
    "  - Active account: false\n"
    "  - Token scopes: 'gist', 'project', 'read:org', 'repo'\n"
    "  \u2713 Logged in to github.com account TheRealKoller (GH_TOKEN)\n"
    "  - Active account: true\n"
    "  - Token scopes: 'repo'\n"
)


class FakeGh:
    """Minimaler, zustandsbehafteter Ersatz fuer echte `gh`-Aufrufe."""

    def __init__(
        self,
        *,
        auth_scopes: str | None = "- Token scopes: 'gist', 'project', 'read:org', 'repo'",
        auth_returncode: int = 0,
        auth_account: str = "TheRealKoller",
        auth_source: str = "keyring",
        auth_output: str | None = None,
        auth_stream: str = "stdout",
        missing_binary: bool = False,
        gh_version_stdout: str = GH_VERSION_STDOUT,
        viewer_permission: str | None = "ADMIN",
        project_list_stdout: str | None = None,
        issue_list: list[dict] | None = None,
        projects: list[dict] | None = None,
        fields: list[dict] | None = None,
        items: list[dict] | None = None,
        labels: list[str] | None = None,
        issue_create_stdout: str | None = None,
        pull_requests: dict[int, dict] | None = None,
        closing_prs: dict[int, list[dict]] | None = None,
        issue_states: dict[int, str] | None = None,
        done_schliesst_das_issue: bool = False,
        failing: set[tuple[str, ...]] | None = None,
        failure_stderr: dict[tuple[str, ...], str] | None = None,
    ) -> None:
        self.auth_scopes = auth_scopes
        self.auth_returncode = auth_returncode
        self.auth_account = auth_account
        self.auth_source = auth_source
        # Roh-Ueberschreibung der gesamten `gh auth status`-Ausgabe - nur fuer die Faelle, die
        # sich nicht aus Konto/Quelle/Scope-Zeile zusammensetzen lassen (mehrere Kontoblocks).
        self.auth_output = auth_output
        self.auth_stream = auth_stream
        # Opt-in, nie Default (Testkonzept zu ADR 0051): ein fehlendes `gh`-Binary laesst das
        # `run`-Callable mit FileNotFoundError scheitern statt mit Returncode != 0.
        self.missing_binary = missing_binary
        self.gh_version_stdout = gh_version_stdout
        self.viewer_permission = viewer_permission
        # Roh-Ueberschreibung der stdout von `gh project list` - fuer Antworten, die kein
        # oder strukturell unerwartetes JSON sind.
        self.project_list_stdout = project_list_stdout
        self.issue_list = issue_list if issue_list is not None else [{"number": 262}]
        self.projects = (
            projects
            if projects is not None
            else [{"number": 7, "id": "PVT_project", "title": PROJECT_TITLE}]
        )
        self.fields = (
            fields
            if fields is not None
            else [
                {
                    "id": "FIELD_status",
                    "name": "Status",
                    "options": [
                        {"id": f"OPT_{name}", "name": name}
                        for name in [
                            "Unrefined",
                            "Ready",
                            "Todo",
                            "In Progress",
                            "Review",
                            "Done",
                        ]
                    ],
                },
                {"id": "FIELD_prio", "name": "Priorität", "options": []},
            ]
        )
        self.items = (
            items
            if items is not None
            else [
                {
                    "id": "PVTI_262",
                    "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                    "status": "Ready",
                }
            ]
        )
        self.labels = labels if labels is not None else ["idee", "bug"]
        self.issue_create_stdout = (
            issue_create_stdout if issue_create_stdout is not None else _issue_url(311) + "\n"
        )
        self.pull_requests = pull_requests or {}
        self.closing_prs = closing_prs or {}
        # Zustandsbehaftet statt Antwort-Tabelle: `gh issue close` und `gh issue view --json
        # state` schauen auf denselben Zustand - genau darin besteht der Fall aus ADR 0048
        # (Testkonzept, Sektion "Erweiterung fuer ADR 0048"). Default: alle Issues offen.
        self.issue_states = dict(issue_states or {})
        # Opt-in-Modell des Board-Workflows `Auto-close issue` (ADR 0046, Abschnitt 5): ein
        # `item-edit` auf die `Done`-Options-Id schliesst das Issue. Bewusst KEIN Default -
        # sonst bekaemen alle unbeteiligten Tests ein Verhalten aufgepraegt, das ihr
        # Pruefgegenstand nicht ist.
        self.done_schliesst_das_issue = done_schliesst_das_issue
        self.failing = failing or set()
        # Je Aufruf-Praefix die stderr-Ausgabe, mit der er scheitern soll - die reale
        # Fehlermeldung entscheidet, wie `gh-board.py` sie einordnet.
        self.failure_stderr = failure_stderr or {}
        self.calls: list[list[str]] = []
        # Obergrenze, die `gh` selbst dann nicht ueberschreitet, wenn ein hoeheres `--limit`
        # angefordert wird. Default None = `gh` liefert die angeforderte Menge vollstaendig.
        self.item_list_hard_limit: int | None = None

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        if self.missing_binary:
            raise FileNotFoundError(2, "No such file or directory", args[0])
        for prefix in self.failing:
            if tuple(args[: len(prefix)]) == prefix:
                return _completed(
                    returncode=1, stderr=self.failure_stderr.get(prefix, "fake gh failure")
                )
        return self._dispatch(args)

    def _dispatch(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        head = tuple(args[:3])
        if tuple(args[:2]) == ("gh", "--version"):
            return _completed(self.gh_version_stdout)
        if head == ("gh", "auth", "status"):
            ausgabe = self.auth_status_ausgabe()
            if self.auth_stream == "stderr":
                return _completed(returncode=self.auth_returncode, stderr=ausgabe)
            return _completed(ausgabe, returncode=self.auth_returncode)
        if head == ("gh", "repo", "view"):
            return _completed(json.dumps({"viewerPermission": self.viewer_permission}))
        if head == ("gh", "issue", "list"):
            return _completed(json.dumps(self.issue_list))
        if head == ("gh", "project", "list"):
            if self.project_list_stdout is not None:
                return _completed(self.project_list_stdout)
            return _completed(json.dumps({"projects": self.projects}))
        if head == ("gh", "project", "field-list"):
            return _completed(json.dumps({"fields": self.fields}))
        if head == ("gh", "project", "item-list"):
            # Das echte `gh project item-list` schneidet bei `--limit` ab, meldet in
            # `totalCount` aber die volle Anzahl. Genau diese Diskrepanz ist der
            # Pruefgegenstand der Pagination-Tests - der Fake muss sie abbilden.
            limit = int(args[args.index("--limit") + 1])
            if self.item_list_hard_limit is not None:
                limit = min(limit, self.item_list_hard_limit)
            return _completed(
                json.dumps({"items": self.items[:limit], "totalCount": len(self.items)})
            )
        if head == ("gh", "project", "item-edit"):
            if self.done_schliesst_das_issue and "OPT_Done" in args:
                self.issue_states[self._issue_of_item(args[args.index("--id") + 1])] = "closed"
            return _completed("")
        if head == ("gh", "project", "item-add"):
            url = args[args.index("--url") + 1]
            number = int(url.rsplit("/", 1)[-1])
            item = {
                "id": f"PVTI_{number}",
                "content": {"type": "Issue", "number": number, "url": url},
            }
            self.items.append(item)
            return _completed(json.dumps({"id": item["id"]}))
        if head == ("gh", "issue", "create"):
            return _completed(self.issue_create_stdout)
        if head == ("gh", "issue", "close"):
            number = int(args[3])
            if self.issue_state(number) == "closed":
                # Real beobachtete Meldung (Spec 0278). Sie ist Kulisse, nie Pruefgegenstand:
                # keine Assertion darf auf ihr aufsetzen, sonst waere die in ADR 0048
                # verworfene Fehlertext-Heuristik durch die Hintertuer zurueck.
                return _completed(returncode=1, stderr=BEREITS_GESCHLOSSEN_STDERR)
            self.issue_states[number] = "closed"
            return _completed("")
        if head[:2] == ("gh", "issue") and head[2] in {"edit", "reopen"}:
            return _completed("")
        if head == ("gh", "issue", "view"):
            number = int(args[3])
            fields = args[args.index("--json") + 1]
            if fields == "state":
                return _completed(json.dumps({"state": self.issue_state(number).upper()}))
            if fields == "closedByPullRequestsReferences":
                referenzen = self.closing_prs.get(number, [])
                return _completed(json.dumps({"closedByPullRequestsReferences": referenzen}))
            raise AssertionError(f"unerwartete --json-Felder fuer 'gh issue view': {fields!r}")
        if head == ("gh", "pr", "view"):
            number = int(args[3])
            if number not in self.pull_requests:
                return _completed(returncode=1, stderr=f"no pull request #{number}")
            return _completed(json.dumps(self.pull_requests[number]))
        if head == ("gh", "label", "list"):
            return _completed(json.dumps([{"name": name} for name in self.labels]))
        if head == ("gh", "label", "create"):
            self.labels.append(args[3])
            return _completed("")
        raise AssertionError(f"unerwarteter gh-Aufruf im Test: {args}")

    # -- Zustand -----------------------------------------------------------------------------

    def auth_status_ausgabe(self) -> str:
        """Baut die Ausgabe von `gh auth status` in der realen Form nach: ein Kontoblock je
        Anmeldung, die Scope-Zeile optional (bei Token-Authentifizierung fehlt sie bzw. steht
        dort `none`)."""
        if self.auth_output is not None:
            return self.auth_output
        if self.auth_returncode != 0:
            return NICHT_ANGEMELDET_AUSGABE
        zeilen = [
            "github.com",
            f"  ✓ Logged in to github.com account {self.auth_account} ({self.auth_source})",
            "  - Active account: true",
            "  - Git operations protocol: https",
            "  - Token: gho_************************************",
        ]
        if self.auth_scopes is not None:
            zeilen.append(f"  {self.auth_scopes}")
        return "\n".join(zeilen) + "\n"

    def issue_state(self, number: int) -> str:
        return self.issue_states.get(number, "open")

    def _issue_of_item(self, item_id: str) -> int:
        for item in self.items:
            if item["id"] == item_id:
                return int((item.get("content") or {})["number"])
        raise AssertionError(f"unbekanntes Board-Item im Test: {item_id!r}")

    # -- Auswertungshilfen -------------------------------------------------------------------

    def calls_starting_with(self, *prefix: str) -> list[list[str]]:
        return [call for call in self.calls if tuple(call[: len(prefix)]) == prefix]

    def single_call(self, *prefix: str) -> list[str]:
        matches = self.calls_starting_with(*prefix)
        assert len(matches) == 1, f"erwartet genau ein {prefix!r}, gefunden: {matches}"
        return matches[0]


def _issue_url(number: int) -> str:
    return f"https://github.com/{OWNER}/{REPO}/issues/{number}"


def _pr_url(number: int) -> str:
    return f"https://github.com/{OWNER}/{REPO}/pull/{number}"


# So meldet `gh` ein `--json`-Feld, das die installierte Version nicht kennt - der Fall
# `closingIssuesReferences` mit gh < 2.72.0. Wortgetreue Form, Feldliste gekuerzt.
UNKNOWN_JSON_FIELD_STDERR = (
    'unknown JSON field: "closingIssuesReferences"\n'
    "Available fields:\n"
    "  additions\n"
    "  assignees\n"
    "  author\n"
    "  baseRefName\n"
    "  body\n"
    "  state\n"
    "  url"
)

# So scheitert `gh issue close` real auf einem bereits geschlossenen Issue (beobachtet bei der
# Finalisierung von Spec 0209, PR #277). Der Text ist Kulisse fuer den FakeGh - das
# Produktivverhalten haengt bewusst nicht an ihm (ADR 0048, Abschnitt 2).
BEREITS_GESCHLOSSEN_STDERR = "GraphQL: Could not close the issue. (closeIssue)"

# Ein Fehlschlag, der mit der `gh`-Version nichts zu tun hat.
ABGELAUFENES_TOKEN_STDERR = "gh: Bad credentials (HTTP 401)\nTry authenticating with: gh auth login"


def _closing_ref(number: int, *, owner: str = OWNER, repo: str = REPO) -> dict:
    """Ein Eintrag aus `closingIssuesReferences`, in der Feldform der echten `gh`-Antwort.

    Die Eintraege sind repo-qualifiziert - genau deshalb vergleicht `gh-board.py` das Tripel
    Owner/Repo/Nummer und nicht bloss die Nummer (ADR 0046, Abschnitt 3).
    """
    return {
        "number": number,
        "url": f"https://github.com/{owner}/{repo}/issues/{number}",
        "repository": {"name": repo, "owner": {"login": owner}},
    }


def _pull_request(
    number: int,
    *,
    state: str = "OPEN",
    base_ref_name: str = "main",
    closing_issues: list[dict] | None = None,
) -> dict:
    """PR-Antwort fuer den FakeGh - mit standardmaessig erfuellter Verknuepfungs-Vorbedingung.

    Die Default-Werte (`baseRefName` = Default-Branch, Referenz auf Issue 262) halten die
    Tests gruen, deren Pruefgegenstand ein ganz anderer ist; sonst faerbte eine vergessene
    Vorbedingung ein Dutzend Tests mit einer irrefuehrenden Meldung rot (Testkonzept,
    Abschnitt zu Spec 0251).
    """
    return {
        "state": state,
        "url": _pr_url(number),
        "baseRefName": base_ref_name,
        "closingIssuesReferences": (
            [_closing_ref(262)] if closing_issues is None else closing_issues
        ),
    }


def _board(gh_board: ModuleType, fake: FakeGh):
    return gh_board.GhBoard(owner=OWNER, project_title=PROJECT_TITLE, run=fake)


def _write_spec(
    repo_root: Path, number: str, *, status: str = "Accepted", title: str = "Beispiel-Spec"
) -> Path:
    features = repo_root / "specs" / "features"
    features.mkdir(parents=True, exist_ok=True)
    path = features / f"{number}-beispiel.md"
    path.write_text(
        f"# {number} - {title}\n"
        f"\n"
        f"**Status:** {status}\n"
        f"**Erstellt:** 2026-08-29\n"
        f"**Bezug:** [GitHub-Issue #262]({_issue_url(262)})\n"
        f"\n"
        f"## Ziel\n"
        f"\n"
        f"Irgendetwas. Auch hier steht ein **Status:** Beispieltext, der nicht getroffen "
        f"werden darf.\n",
        encoding="utf-8",
    )
    return path


# -- Redaktion (ADR 0051) -----------------------------------------------------------------------

# Realistische Formen echter GitHub-Token. Keiner davon ist ein gueltiges Geheimnis - die
# Zeichenfolgen sind hier frei erfunden, aber formgleich zu dem, was ein gespraechiges `gh`
# ausgeben koennte.
TOKEN_BEISPIELE = [
    "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
    "gho_" + "Z9y8X7w6V5u4T3s2R1q0P9o8N7m6L5k4J3i2",
    "ghu_" + "abcdefghijklmnopqrstuvwxyz0123456789",
    "ghs_" + "0123456789abcdefghijklmnopqrstuvwxyz",
    "ghr_" + "QWERTZUIOPasdfghjklyxcvbnm0123456789",
    "github_pat_" + "11ABCDEFG0abcdefghijklmn_" + "0123456789abcdefghijklmnopqrstuvwxyzAB",
]


@pytest.mark.parametrize("token", TOKEN_BEISPIELE)
def test_tokenfoermige_zeichenketten_werden_geschwaerzt(gh_board: ModuleType, token: str) -> None:
    """Zweite Verteidigungslinie hinter der Whitelist (Securitykonzept zu ADR 0051): Der Bericht
    ist dazu bestimmt, in ein Issue eines OEFFENTLICHEN Repositories zu wandern."""
    redigiert = gh_board.redact_for_report(f"failed to authenticate with {token} - aborting")

    assert token not in redigiert
    assert "failed to authenticate with" in redigiert


@pytest.mark.parametrize(
    "harmlos",
    [
        "github_pattern konnte nicht geladen werden",
        "ghost-Eintrag im Board",
        "gh project list --owner TheRealKoller --format json",
        "Token scopes: 'gist', 'project', 'read:org', 'repo'",
        "ghp_kurz",
    ],
)
def test_harmloser_text_bleibt_unveraendert(gh_board: ModuleType, harmlos: str) -> None:
    """Gegenrichtung: Ein Filter, der zu viel frisst, macht den Bericht unbrauchbar - und das
    faellt ohne Test niemandem auf, weil der Bericht dann ja "sauber" aussieht."""
    assert gh_board.redact_for_report(harmlos) == harmlos


def test_ansi_und_steuerzeichen_werden_entfernt(gh_board: ModuleType) -> None:
    """Fremdtext, der in ein Terminal, in Markdown und in einen Agenten-Kontext gerendert wird,
    darf keine Darstellung manipulieren koennen (Securitykonzept, Muss-Kriterium 5)."""
    roh = "\x1b[31mFehler\x1b[0m:\u202e thgilhgih \u200b\x07 zweite Zeile\nnaechste Zeile"

    redigiert = gh_board.redact_for_report(roh)

    assert "\x1b" not in redigiert
    assert "\u202e" not in redigiert
    assert "\u200b" not in redigiert
    assert "\x07" not in redigiert
    assert "Fehler" in redigiert
    # Zeilenumbrueche bleiben - sie tragen die Lesbarkeit einer mehrzeiligen gh-Meldung.
    assert "\nnaechste Zeile" in redigiert


def test_uebernommener_text_wird_sichtbar_gekuerzt(gh_board: ModuleType) -> None:
    """Ein unerwartet gespraechiges `gh` (GH_DEBUG=api, Stacktrace) darf nicht den halben
    Umgebungszustand in ein oeffentliches Issue schreiben."""
    redigiert = gh_board.redact_for_report("x" * 2000)

    assert len(redigiert) < 600
    assert redigiert.startswith("x" * 500)
    assert redigiert != "x" * 500


def test_credentials_in_url_form_werden_geschwaerzt(gh_board: ModuleType) -> None:
    """Der Tokenmuster-Filter kennt nur Tokenformen; eine Proxy-Konfiguration in URL-Form ist
    die naheliegendste Luecke daneben und kostet eine Zeile."""
    redigiert = gh_board.redact_for_report("proxy https://daniel:geheim@proxy.example:8080 refused")

    assert "geheim" not in redigiert
    assert "proxy.example:8080" in redigiert


# -- Board-Zugriff: probieren statt raten (ADR 0051) --------------------------------------------


# Je Board-Befehl der erste `gh`-Aufruf, der seine eigentliche Wirkung entfaltet. Frueher kam
# keiner von ihnen zustande, sobald das Wort "project" nicht in der `gh auth status`-Ausgabe
# stand - unabhaengig davon, ob der Zugriff tatsaechlich bestand.
WIRKSAMER_GH_AUFRUF_JE_BEFEHL = {
    "create-issue": ("gh", "issue", "create"),
    "set-body": ("gh", "issue", "edit"),
    "set-status": ("gh", "project", "item-edit"),
    "set-priority": ("gh", "project", "item-edit"),
    "show-status": ("gh", "project", "item-list"),
    "finalize": ("gh", "pr", "view"),
}


def _argv_fuer(befehl: str, tmp_path: Path) -> list[str]:
    body = tmp_path / "body.md"
    body.write_text("Beliebiger Text", encoding="utf-8")
    return {
        "create-issue": [
            "create-issue", "--type", "idee", "--title", "T", "--body-file", str(body)
        ],
        "set-body": ["set-body", "--issue", "262", "--body-file", str(body)],
        "set-status": ["set-status", "--issue", "262", "--status", "Todo"],
        "set-priority": ["set-priority", "--issue", "262", "--priority", "Hoch"],
        "show-status": ["show-status", "--issue", "262"],
        "finalize": ["finalize", "--spec", "0262", "--pr-number", "281"],
    }[befehl]


@pytest.mark.parametrize("befehl", sorted(WIRKSAMER_GH_AUFRUF_JE_BEFEHL))
@pytest.mark.parametrize(
    "auth_scopes",
    [
        pytest.param("- Token scopes: none", id="token-scopes-none"),
        pytest.param(None, id="gar-keine-scope-zeile"),
    ],
)
def test_eine_nichtssagende_scope_auskunft_blockiert_keinen_board_befehl(
    gh_board: ModuleType, tmp_path: Path, befehl: str, auth_scopes: str | None
) -> None:
    """Regressionsschutz fuer die Token-Authentifizierung (ADR 0051): `gh` meldet dort je nach
    Token-Art `Token scopes: none` oder gar keine Scope-Zeile - beides sagt nichts ueber den
    tatsaechlichen Zugriff aus. Nachgewiesen wird am protokollierten Aufruflog, nicht am
    Rueckgabewert: der Befehl muss seinen wirksamen `gh`-Aufruf ueberhaupt erreichen.
    """
    _write_spec(tmp_path, "0262")
    fake = FakeGh(
        auth_scopes=auth_scopes,
        auth_source="GH_TOKEN",
        fields=_fields_mit_prioritaets_optionen(),
        pull_requests={281: _pull_request(281)},
    )

    exit_code = gh_board.main(
        _argv_fuer(befehl, tmp_path), run=fake, repo_root=tmp_path, owner=OWNER
    )

    assert fake.calls_starting_with(*WIRKSAMER_GH_AUFRUF_JE_BEFEHL[befehl])
    assert exit_code == 0


def test_auf_dem_erfolgspfad_wird_gh_auth_status_nicht_mehr_aufgerufen(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Nachfolger von `test_vorhandener_project_scope_ist_still` (invertiert): Der Erfolgsfall
    kostet ab jetzt keinen Diagnoseaufruf mehr - die tokennaechste Ausgabe des Werkzeugs
    entsteht nur noch im Fehlerfall."""
    fake = FakeGh()

    exit_code = gh_board.main(
        ["set-status", "--issue", "262", "--status", "Todo"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 0
    assert fake.calls_starting_with("gh", "auth", "status") == []


def test_echter_scope_mangel_bleibt_am_gescheiterten_aufruf_deutbar(gh_board: ModuleType) -> None:
    """Nachfolger von `test_fehlender_project_scope_wird_als_eigener_fehler_gemeldet`: Die
    Zusicherung "ein fehlender `project`-Scope fuehrt zu einem Hinweis auf `gh auth refresh -s
    project`" bleibt bestehen - nur wird sie jetzt an einem tatsaechlich gescheiterten Zugriff
    gefaellt statt vor dem Versuch, und die urspruengliche `gh`-Meldung bleibt erhalten."""
    fake = FakeGh(
        auth_scopes="- Token scopes: 'gist', 'read:org', 'repo'",
        failing={("gh", "project", "list")},
        failure_stderr={("gh", "project", "list"): "your token has not been granted 'project'"},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).project()

    message = str(excinfo.value)
    assert "gh auth refresh -s project" in message
    assert "your token has not been granted 'project'" in message


def test_scheitert_die_deutung_selbst_ueberlebt_die_urspruengliche_meldung(
    gh_board: ModuleType,
) -> None:
    """Nachfolger von `test_auth_status_fehlschlag_wird_gemeldet`: Ein fehlgeschlagenes
    `gh auth status` ist ab jetzt kein eigener Abbruchgrund mehr, darf aber auch nicht die
    Meldung verschlucken, um die es eigentlich geht."""
    fake = FakeGh(
        auth_returncode=1,
        failing={("gh", "project", "list")},
        failure_stderr={("gh", "project", "list"): ABGELAUFENES_TOKEN_STDERR},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).project()

    message = str(excinfo.value)
    assert "Bad credentials" in message
    assert "gh auth refresh" not in message


def test_ein_vorhandener_project_scope_erzeugt_keinen_refresh_hinweis(
    gh_board: ModuleType,
) -> None:
    """Keine Uebererkennung: Enthaelt die Scope-Zeile `project` und scheitert der Aufruf
    trotzdem, schickt ein Refresh-Hinweis jede spaetere Fehlersuche auf die falsche Faehrte."""
    fake = FakeGh(
        failing={("gh", "project", "list")},
        failure_stderr={("gh", "project", "list"): ABGELAUFENES_TOKEN_STDERR},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).project()

    message = str(excinfo.value)
    assert "gh auth refresh" not in message
    assert "Bad credentials" in message


def test_die_deutung_bezieht_sich_auf_das_aktive_konto(gh_board: ModuleType) -> None:
    """`gh auth status` meldet pro Host mehrere Bloecke. Eine Auswertung, die die erste beste
    Scope-Zeile nimmt, meldet die Rechte eines Kontos, mit dem gar nicht gearbeitet wird -
    hier: das inaktive Keyring-Konto hat `project`, das aktive Umgebungstoken-Konto nicht."""
    fake = FakeGh(
        auth_output=ZWEI_KONTEN_AUSGABE,
        failing={("gh", "project", "list")},
        failure_stderr={("gh", "project", "list"): "GraphQL: Resource not accessible"},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).project()

    message = str(excinfo.value)
    assert "gh auth refresh -s project" in message
    assert "GH_TOKEN" in message


def test_die_deutung_liest_die_auskunft_auch_von_stderr(gh_board: ModuleType) -> None:
    """Aeltere `gh`-Versionen schreiben die Statusausgabe auf stderr statt auf stdout."""
    fake = FakeGh(
        auth_stream="stderr",
        auth_scopes="- Token scopes: 'gist', 'read:org', 'repo'",
        failing={("gh", "project", "list")},
        failure_stderr={("gh", "project", "list"): "GraphQL: Resource not accessible"},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).project()

    assert "gh auth refresh -s project" in str(excinfo.value)


def test_eine_unlesbare_projektliste_bekommt_nur_die_auth_quelle_als_kontext(
    gh_board: ModuleType,
) -> None:
    """Returncode 0, aber kein gueltiges JSON: ohne auswertbare Scope-Zeile bleibt es bei der
    urspruenglichen Meldung plus der Auth-Quelle als Kontext - kein geratener Scope-Hinweis."""
    fake = FakeGh(
        auth_scopes=None, auth_source="GITHUB_TOKEN", project_list_stdout="kein JSON, sondern Text"
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).project()

    message = str(excinfo.value)
    assert "GITHUB_TOKEN" in message
    assert "gh auth refresh" not in message


def test_die_angereicherte_meldung_ist_redigiert(gh_board: ModuleType) -> None:
    """Die Meldung geht ueber `{"error": ...}` an die Skills, die sie woertlich weiterreichen -
    und damit potenziell in ein oeffentliches Issue (Securitykonzept, Muss-Kriterium 2)."""
    token = TOKEN_BEISPIELE[0]
    fake = FakeGh(
        failing={("gh", "project", "list")},
        failure_stderr={("gh", "project", "list"): f"failed with token {token}"},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).project()

    assert token not in str(excinfo.value)


# -- Projekt-/Feld-Aufloesung -----------------------------------------------------------------


def test_unbekanntes_projekt_wird_nicht_angelegt_sondern_gemeldet(gh_board: ModuleType) -> None:
    """Ein erfolgreiches `gh project list` ohne Titeltreffer (umbenanntes Board) ist kein
    Berechtigungsproblem: Die Deutung aus ADR 0051 haengt am gescheiterten Aufruf, nicht an
    jedem Fehler dieser Funktion - sonst waere der ganze Rumpf in ein `try` gefasst und die
    Meldung fuehrte in die Irre."""
    fake = FakeGh(projects=[{"number": 1, "id": "PVT_other", "title": "Anderes Board"}])
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.project()

    message = str(excinfo.value)
    assert PROJECT_TITLE in message
    assert "gh auth refresh" not in message
    assert fake.calls_starting_with("gh", "project", "create") == []
    assert fake.calls_starting_with("gh", "auth", "status") == []


def test_fehlendes_statusfeld_wird_nicht_angelegt_sondern_gemeldet(gh_board: ModuleType) -> None:
    fake = FakeGh(fields=[{"id": "FIELD_prio", "name": "Priorität", "options": []}])
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.status_field()

    assert "Status" in str(excinfo.value)
    assert fake.calls_starting_with("gh", "project", "field-create") == []


def test_projekt_und_feld_werden_nur_einmal_aufgeloest(gh_board: ModuleType) -> None:
    fake = FakeGh()
    board = _board(gh_board, fake)

    board.status_field()
    board.status_field()

    assert len(fake.calls_starting_with("gh", "project", "list")) == 1
    assert len(fake.calls_starting_with("gh", "project", "field-list")) == 1


# -- Prioritaetsfeld-Aufloesung ----------------------------------------------------------------


def test_prioritaetsfeld_wird_aufgeloest(gh_board: ModuleType) -> None:
    fake = FakeGh()
    board = _board(gh_board, fake)

    field = board.priority_field()

    assert field["id"] == "FIELD_prio"
    assert field["name"] == "Priorität"


def test_fehlendes_prioritaetsfeld_wird_nicht_angelegt_sondern_gemeldet(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh(
        fields=[
            {
                "id": "FIELD_status",
                "name": "Status",
                "options": [{"id": "OPT_Ready", "name": "Ready"}],
            }
        ]
    )
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.priority_field()

    assert "Priorität" in str(excinfo.value)
    assert fake.calls_starting_with("gh", "project", "field-create") == []


# -- Item-Aufloesung ueber die Issue-Nummer ---------------------------------------------------


def test_item_wird_ueber_die_issue_nummer_aufgeloest(gh_board: ModuleType) -> None:
    fake = FakeGh()
    board = _board(gh_board, fake)

    assert board.find_item(262)["id"] == "PVTI_262"


def test_unbekanntes_issue_im_board_ist_ein_klarer_fehler(gh_board: ModuleType) -> None:
    fake = FakeGh()
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.find_item(999)

    assert "999" in str(excinfo.value)


def _viele_items(anzahl: int) -> list[dict]:
    """`anzahl` Board-Items mit aufsteigenden Issue-Nummern ab 200."""
    return [
        {
            "id": f"PVTI_{200 + i}",
            "content": {"type": "Issue", "number": 200 + i, "url": _issue_url(200 + i)},
            "status": "Unrefined",
        }
        for i in range(anzahl)
    ]


def test_item_jenseits_der_ersten_seite_wird_gefunden(gh_board: ModuleType) -> None:
    """Regression: bei 106 Board-Items lag #296 auf Position 101 und war damit fuer jede
    Schreiboperation unsichtbar - `set-priority`/`set-status` meldeten "kein Item des Boards"."""
    fake = FakeGh(items=_viele_items(106))
    board = _board(gh_board, fake)

    assert board.find_item(300)["id"] == "PVTI_300"
    assert board.find_item(305)["id"] == "PVTI_305"


def test_vollstaendig_gelieferte_erste_seite_wird_nicht_erneut_geholt(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh(items=_viele_items(42))
    board = _board(gh_board, fake)

    assert board.find_item(241)["id"] == "PVTI_241"
    assert len(fake.calls_starting_with("gh", "project", "item-list")) == 1


def test_abgeschnittene_liste_wird_genau_einmal_nachgeholt(gh_board: ModuleType) -> None:
    fake = FakeGh(items=_viele_items(250))
    board = _board(gh_board, fake)

    assert board.find_item(449)["id"] == "PVTI_449"
    aufrufe = fake.calls_starting_with("gh", "project", "item-list")
    assert len(aufrufe) == 2
    # Der zweite Aufruf fordert die per totalCount gemeldete volle Anzahl an, statt ein
    # weiteres Mal zu raten.
    assert aufrufe[1][aufrufe[1].index("--limit") + 1] == "250"


def test_unvollstaendige_liste_trotz_nachforderung_ist_ein_klarer_fehler(
    gh_board: ModuleType,
) -> None:
    """Kein stilles Abschneiden: meldet `gh` nach der Nachforderung weiterhin mehr Items als es
    liefert, ist "Issue nicht im Board" eine Luege - dann muss der Fehler das benennen."""
    fake = FakeGh(items=_viele_items(120))
    fake.item_list_hard_limit = 100
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError) as excinfo:
        board.find_item(300)

    meldung = str(excinfo.value)
    assert "120" in meldung
    assert "100" in meldung


def test_gleichnamige_pr_nummer_wird_nicht_mit_einem_issue_verwechselt(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_pr",
                "content": {"type": "PullRequest", "number": 262, "url": _pr_url(262)},
            }
        ]
    )
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError):
        board.find_item(262)


# -- set-status -------------------------------------------------------------------------------


def test_set_status_setzt_die_passende_options_id(gh_board: ModuleType) -> None:
    fake = FakeGh()

    result = gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="In Progress")

    assert result == {"issue_number": 262, "status": "In Progress"}
    assert fake.single_call("gh", "project", "item-edit") == [
        "gh",
        "project",
        "item-edit",
        "--id",
        "PVTI_262",
        "--project-id",
        "PVT_project",
        "--field-id",
        "FIELD_status",
        "--single-select-option-id",
        "OPT_In Progress",
    ]


def test_set_status_done_schliesst_das_issue_zusaetzlich(gh_board: ModuleType) -> None:
    fake = FakeGh()

    gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Done")

    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_set_status_ohne_done_laesst_den_issue_zustand_unangetastet(gh_board: ModuleType) -> None:
    fake = FakeGh()

    gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Review")

    assert fake.calls_starting_with("gh", "issue", "close") == []
    assert fake.calls_starting_with("gh", "issue", "reopen") == []


def test_unbekannter_statuswert_wird_abgelehnt(gh_board: ModuleType) -> None:
    fake = FakeGh()

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Erledigt")

    assert "Erledigt" in str(excinfo.value)
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_fehlende_options_id_im_board_bricht_ab(gh_board: ModuleType) -> None:
    fake = FakeGh(
        fields=[
            {
                "id": "FIELD_status",
                "name": "Status",
                "options": [{"id": "OPT_Todo", "name": "Todo"}],
            }
        ]
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Review")

    assert "Review" in str(excinfo.value)


# -- Prioritaet (get_priority/set_priority/set_priority_if_unset) -----------------------------


_PRIORITY_FIELD_WITH_OPTIONS = {
    "id": "FIELD_prio",
    "name": "Priorität",
    "options": [{"id": f"OPT_prio_{name}", "name": name} for name in ("Hoch", "Mittel", "Niedrig")],
}


def _fields_mit_prioritaets_optionen() -> list[dict]:
    return [
        {
            "id": "FIELD_status",
            "name": "Status",
            "options": [
                {"id": f"OPT_{name}", "name": name}
                for name in ["Unrefined", "Ready", "Todo", "In Progress", "Review", "Done"]
            ],
        },
        _PRIORITY_FIELD_WITH_OPTIONS,
    ]


def test_get_priority_liest_den_klartextwert(gh_board: ModuleType) -> None:
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "priorität": "Hoch",
            }
        ]
    )

    assert _board(gh_board, fake).get_priority(262) == "Hoch"


def test_get_priority_liefert_none_bei_leerem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "priorität": "",
            }
        ]
    )

    assert _board(gh_board, fake).get_priority(262) is None


def test_get_priority_liefert_none_wenn_feld_ganz_fehlt(gh_board: ModuleType) -> None:
    fake = FakeGh()  # Standard-Item hat gar kein "priorität"-Feld.

    assert _board(gh_board, fake).get_priority(262) is None


def test_set_priority_setzt_die_passende_options_id(gh_board: ModuleType) -> None:
    fake = FakeGh(fields=_fields_mit_prioritaets_optionen())

    _board(gh_board, fake).set_priority(262, "Mittel")

    assert fake.single_call("gh", "project", "item-edit") == [
        "gh",
        "project",
        "item-edit",
        "--id",
        "PVTI_262",
        "--project-id",
        "PVT_project",
        "--field-id",
        "FIELD_prio",
        "--single-select-option-id",
        "OPT_prio_Mittel",
    ]


def test_set_priority_fehlende_options_id_bricht_ab(gh_board: ModuleType) -> None:
    fake = FakeGh()  # Standard-Prioritaetsfeld hat keine Optionen.

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).set_priority(262, "Hoch")

    assert "Hoch" in str(excinfo.value)
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_set_priority_if_unset_schreibt_bei_leerem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(fields=_fields_mit_prioritaets_optionen())

    changed, priority = _board(gh_board, fake).set_priority_if_unset(262, "Hoch")

    assert (changed, priority) == (True, "Hoch")
    assert fake.single_call("gh", "project", "item-edit")


def test_set_priority_if_unset_ist_ein_no_op_bei_bereits_gesetztem_feld(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh(
        fields=_fields_mit_prioritaets_optionen(),
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "priorität": "Niedrig",
            }
        ],
    )

    changed, priority = _board(gh_board, fake).set_priority_if_unset(262, "Hoch")

    # Rueckgabe ist der VORHANDENE Wert (Niedrig), nicht der angefragte (Hoch).
    assert (changed, priority) == (False, "Niedrig")
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


# -- set-priority -----------------------------------------------------------------------------


def test_cmd_set_priority_schreibt_bei_leerem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(fields=_fields_mit_prioritaets_optionen())

    result = gh_board.cmd_set_priority(_board(gh_board, fake), issue_number=262, priority="Hoch")

    assert result == {"issue_number": 262, "priority": "Hoch", "changed": True}
    assert fake.single_call("gh", "project", "item-edit")


def test_cmd_set_priority_ist_no_op_bei_bereits_gesetztem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(
        fields=_fields_mit_prioritaets_optionen(),
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "priorität": "Niedrig",
            }
        ],
    )

    result = gh_board.cmd_set_priority(_board(gh_board, fake), issue_number=262, priority="Hoch")

    # Rueckgabe ist der vorhandene Wert (Niedrig), nicht der angefragte (Hoch).
    assert result == {"issue_number": 262, "priority": "Niedrig", "changed": False}
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_cmd_set_priority_unbekannter_wert_wird_vor_jedem_gh_aufruf_abgelehnt(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh()

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_set_priority(_board(gh_board, fake), issue_number=262, priority="Kritisch")

    assert "Kritisch" in str(excinfo.value)
    assert fake.calls == []


def test_cmd_set_priority_fehlende_options_id_fuer_gueltigen_wert_bricht_ab(
    gh_board: ModuleType,
) -> None:
    fake = FakeGh()  # Standard-Prioritaetsfeld ist vorhanden, hat aber keine Optionen.

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_set_priority(_board(gh_board, fake), issue_number=262, priority="Hoch")

    assert "Hoch" in str(excinfo.value)


# -- show-status ------------------------------------------------------------------------------


def test_show_status_liest_den_aktuellen_wert_ohne_schreibzugriff(gh_board: ModuleType) -> None:
    fake = FakeGh()

    result = gh_board.cmd_show_status(_board(gh_board, fake), issue_number=262)

    assert result == {"issue_number": 262, "status": "Ready"}
    assert fake.calls_starting_with("gh", "project", "item-edit") == []
    assert fake.calls_starting_with("gh", "issue", "edit") == []


def test_show_status_liefert_none_bei_leerem_feld(gh_board: ModuleType) -> None:
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_262",
                "content": {"type": "Issue", "number": 262, "url": _issue_url(262)},
                "status": "",
            }
        ]
    )

    assert gh_board.cmd_show_status(_board(gh_board, fake), issue_number=262)["status"] is None


# -- set-body ---------------------------------------------------------------------------------


def test_set_body_uebergibt_den_body_ueber_eine_datei(gh_board: ModuleType) -> None:
    fake = FakeGh()

    result = gh_board.cmd_set_body(_board(gh_board, fake), issue_number=262, body="Neuer Text")

    assert result == {"issue_number": 262}
    call = fake.single_call("gh", "issue", "edit")
    assert call[:4] == ["gh", "issue", "edit", "262"]
    assert call[4] == "--body-file"
    assert "Neuer Text" not in " ".join(call)


def test_temporaere_body_datei_wird_wieder_entfernt(gh_board: ModuleType) -> None:
    fake = FakeGh()
    gh_board.cmd_set_body(_board(gh_board, fake), issue_number=262, body="Neuer Text")

    body_path = Path(fake.single_call("gh", "issue", "edit")[5])
    assert not body_path.exists()


# -- create-issue -----------------------------------------------------------------------------


def test_create_issue_legt_label_projektitem_und_status_an(gh_board: ModuleType) -> None:
    fake = FakeGh()

    result = gh_board.cmd_create_issue(
        _board(gh_board, fake), typ="idee", title="Neue Idee", body="Rohtext"
    )

    assert result == {"issue_number": 311}
    create_call = fake.single_call("gh", "issue", "create")
    assert "--label" in create_call
    assert create_call[create_call.index("--label") + 1] == "idee"
    assert "Rohtext" not in " ".join(create_call)
    assert fake.single_call("gh", "project", "item-add") == [
        "gh",
        "project",
        "item-add",
        "7",
        "--owner",
        OWNER,
        "--url",
        _issue_url(311),
        "--format",
        "json",
    ]
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Unrefined"


def test_create_issue_legt_ein_fehlendes_label_vorher_an(gh_board: ModuleType) -> None:
    fake = FakeGh(labels=["bug"])

    gh_board.cmd_create_issue(_board(gh_board, fake), typ="idee", title="T", body="B")

    assert fake.single_call("gh", "label", "create")[3] == "idee"


def test_create_issue_legt_ein_vorhandenes_label_nicht_erneut_an(gh_board: ModuleType) -> None:
    fake = FakeGh(labels=["idee", "bug"])

    gh_board.cmd_create_issue(_board(gh_board, fake), typ="idee", title="T", body="B")

    assert fake.calls_starting_with("gh", "label", "create") == []


def test_unbekannter_typ_wird_abgelehnt(gh_board: ModuleType) -> None:
    fake = FakeGh()

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_create_issue(_board(gh_board, fake), typ="epic", title="T", body="B")

    assert fake.calls_starting_with("gh", "issue", "create") == []


def test_unparsbare_ausgabe_von_issue_create_bricht_ab(gh_board: ModuleType) -> None:
    fake = FakeGh(issue_create_stdout="irgendwas ohne URL\n")

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_create_issue(_board(gh_board, fake), typ="idee", title="T", body="B")


# -- get_pull_request ------------------------------------------------------------------------


def test_get_pull_request_holt_die_verknuepfungsfelder_und_niemals_den_body(
    gh_board: ModuleType,
) -> None:
    """Die Verknuepfungspruefung faehrt im ohnehin abgesetzten `gh pr view` mit (ADR 0046,
    Abschnitt 3). Dass **kein** `body` angefragt wird, ist keine Nebenwirkung, sondern eine
    zugesicherte Eigenschaft: von aussen befuellbarer Fremdtext wird gar nicht erst eingelesen.
    """
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    data = _board(gh_board, fake).get_pull_request(281)

    call = fake.single_call("gh", "pr", "view")
    assert call == [
        "gh",
        "pr",
        "view",
        "281",
        "--json",
        "state,url,baseRefName,closingIssuesReferences",
    ]
    assert not any("body" in arg for arg in call)
    assert data["state"] == "open"
    assert data["url"] == _pr_url(281)
    assert data["baseRefName"] == "main"
    assert data["closingIssuesReferences"] == [_closing_ref(262)]


# -- Zielzustands-Idempotenz beim Schliessen (Spec 0278 / ADR 0048) ---------------------------


def _zustandsabfragen(fake: FakeGh) -> list[list[str]]:
    """Nur die Zustands-Nachpruefungen aus dem Aufruflog - `gh issue view` gibt es auch mit
    anderen `--json`-Feldern (`closedByPullRequestsReferences`)."""
    return [
        call
        for call in fake.calls_starting_with("gh", "issue", "view")
        if call[call.index("--json") + 1] == "state"
    ]


def test_issue_state_fragt_genau_das_state_feld_ab_und_normalisiert(gh_board: ModuleType) -> None:
    """`gh` liefert den GraphQL-Enum gross (CLOSED); ohne Normalisierung griffe die Ausnahme nie.
    Abgefragt wird ausschliesslich `state` - nie Titel, Body, Labels oder Kommentare."""
    fake = FakeGh(issue_states={262: "closed"})

    assert _board(gh_board, fake).issue_state(262) == "closed"
    assert fake.single_call("gh", "issue", "view") == [
        "gh",
        "issue",
        "view",
        "262",
        "--json",
        "state",
    ]


@pytest.mark.parametrize("payload", ['{"state": null}', "{}", '{"state": ""}', "[]"])
def test_issue_state_meldet_ein_unbrauchbares_state_feld_als_boarderror(
    gh_board: ModuleType, payload: str
) -> None:
    """Ein KeyError/AttributeError wuerde die Ausgabekonvention des Werkzeugs
    ({"error": ...} plus Exit-Code 1) mit einem Traceback brechen."""

    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        if tuple(args[:3]) == ("gh", "issue", "view"):
            return _completed(payload)
        return FakeGh()(args)

    with pytest.raises(gh_board.BoardError):
        gh_board.GhBoard(owner=OWNER, project_title=PROJECT_TITLE, run=run).issue_state(262)


def test_close_issue_ist_still_wenn_das_issue_bereits_geschlossen_ist(
    gh_board: ModuleType,
) -> None:
    """Kern von AK 1/2: Zielzustand ist 'Issue geschlossen', nicht 'dieser Aufruf hat es
    geschlossen'."""
    fake = FakeGh(issue_states={262: "closed"})

    _board(gh_board, fake).close_issue(262)

    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_close_issue_meldet_den_urspruenglichen_fehler_wenn_das_issue_offen_ist(
    gh_board: ModuleType,
) -> None:
    """AK 5: ein echter Fehlschlag (z.B. abgelaufenes Token) bleibt ein Fehler - und zwar mit dem
    Originaltext von `gh issue close`, nicht mit dem der Nachpruefung."""
    fake = FakeGh(
        failing={("gh", "issue", "close")},
        failure_stderr={("gh", "issue", "close"): ABGELAUFENES_TOKEN_STDERR},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).close_issue(262)

    assert "Bad credentials" in str(excinfo.value)


def test_close_issue_meldet_den_close_fehler_wenn_die_nachpruefung_selbst_scheitert(
    gh_board: ModuleType,
) -> None:
    """AK 5: nicht existierendes Issue / fehlende Berechtigung / Dienst nicht erreichbar - der
    aussagekraeftigere `close`-Fehler wird gemeldet, der Lesefehler haengt als Ursache daran."""
    fake = FakeGh(
        failing={("gh", "issue", "close"), ("gh", "issue", "view")},
        failure_stderr={
            ("gh", "issue", "close"): ABGELAUFENES_TOKEN_STDERR,
            ("gh", "issue", "view"): "gh: Not Found (HTTP 404)",
        },
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        _board(gh_board, fake).close_issue(262)

    assert "Bad credentials" in str(excinfo.value)
    assert "Not Found" in str(excinfo.value.__cause__)


def test_close_issue_prueft_den_zustand_im_erfolgsfall_nicht_nach(gh_board: ModuleType) -> None:
    """AK 8 / Regressionsschutz: die Pruefung ist eine Nachpruefung, keine Vorabpruefung - sonst
    kostet sie in jedem `Done`-Pfad einen zusaetzlichen `gh`-Aufruf, ohne das Rennen mit der
    asynchronen Board-Automation zu beseitigen."""
    fake = FakeGh()

    _board(gh_board, fake).close_issue(262)

    assert _zustandsabfragen(fake) == []


def test_set_status_done_auf_bereits_geschlossenem_issue_meldet_erfolg(
    gh_board: ModuleType,
) -> None:
    """AK 2/4: regulaerer Payload, und der Zielzustand wird trotzdem vollstaendig hergestellt -
    die Board-Spalte wird gesetzt, das Schliessen versucht."""
    fake = FakeGh(issue_states={262: "closed"})

    result = gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Done")

    assert result == {"issue_number": 262, "status": "Done"}
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Done"
    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_set_status_done_ueberlebt_die_auto_close_automation_des_boards(
    gh_board: ModuleType,
) -> None:
    """Reproduktion des gemeldeten Falls im Zusammenhang: das `Done` schliesst das Issue ueber
    den Board-Workflow, das eigene `close` trifft es danach bereits geschlossen an."""
    fake = FakeGh(done_schliesst_das_issue=True)

    result = gh_board.cmd_set_status(_board(gh_board, fake), issue_number=262, status="Done")

    assert result == {"issue_number": 262, "status": "Done"}
    assert fake.issue_state(262) == "closed"


def test_set_status_done_ist_ununterscheidbar_vom_selbst_geschlossenen_fall(
    gh_board: ModuleType,
) -> None:
    """AK 3 als Gleichheit zweier real erzeugter Ergebnisse - nicht als Feldliste: nur diese Form
    faengt ein spaeter nachgeruestetes Feld ('war schon geschlossen') ab."""
    ergebnis_bereits_geschlossen = gh_board.cmd_set_status(
        _board(gh_board, FakeGh(issue_states={262: "closed"})), issue_number=262, status="Done"
    )
    ergebnis_frisch_geschlossen = gh_board.cmd_set_status(
        _board(gh_board, FakeGh()), issue_number=262, status="Done"
    )

    assert ergebnis_bereits_geschlossen == ergebnis_frisch_geschlossen


# -- finalize ---------------------------------------------------------------------------------


def test_finalize_schreibt_statuszeile_setzt_done_und_schliesst_das_issue(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result == {
        "spec_number": "0262",
        "issue_number": 262,
        "pr_number": 281,
        "status_line": f"Implemented ([PR #281]({_pr_url(281)}))",
        "status": "Done",
    }
    text = path.read_text(encoding="utf-8")
    assert f"**Status:** Implemented ([PR #281]({_pr_url(281)}))\n" in text
    # Der '**Status:**'-Vorkommen in der Inhaltszone darf nicht getroffen werden.
    assert "Auch hier steht ein **Status:** Beispieltext" in text
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Done"
    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_finalize_ueberlebt_die_auto_close_automation_des_boards(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """AK 1/4 als Reproduktion des gemeldeten Falls (Finalisierung von Spec 0209, PR #277): das
    `Done` schliesst das Issue ueber den Board-Workflow, das eigene `close` trifft es danach
    bereits geschlossen an - der Zielzustand entsteht trotzdem vollstaendig."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)}, done_schliesst_das_issue=True)

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result["status"] == "Done"
    assert f"**Status:** Implemented ([PR #281]({_pr_url(281)}))\n" in path.read_text(
        encoding="utf-8"
    )
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Done"
    assert fake.single_call("gh", "issue", "close") == ["gh", "issue", "close", "262"]


def test_finalize_ist_ununterscheidbar_vom_selbst_geschlossenen_fall(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """AK 3 als Gleichheit zweier real erzeugter Ergebnisse: der aufrufende Ablauf soll den
    Unterschied 'war schon geschlossen' gar nicht sehen koennen."""
    _write_spec(tmp_path / "bereits", "0262")
    _write_spec(tmp_path / "frisch", "0262")

    ergebnis_bereits_geschlossen = gh_board.cmd_finalize(
        _board(
            gh_board,
            FakeGh(pull_requests={281: _pull_request(281)}, issue_states={262: "closed"}),
        ),
        repo_root=tmp_path / "bereits",
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )
    ergebnis_frisch_geschlossen = gh_board.cmd_finalize(
        _board(gh_board, FakeGh(pull_requests={281: _pull_request(281)})),
        repo_root=tmp_path / "frisch",
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert ergebnis_bereits_geschlossen == ergebnis_frisch_geschlossen


def test_finalize_prueft_den_zustand_im_erfolgsfall_nicht_nach(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """AK 8: der ungestoerte Regelfall setzt weiterhin genau die bisherigen `gh`-Aufrufe ab."""
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert _zustandsabfragen(fake) == []


def test_finalize_akzeptiert_einen_bereits_gemergten_pr(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, state="MERGED")})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result["pr_number"] == 281


def test_finalize_lehnt_einen_ohne_merge_geschlossenen_pr_ab(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, state="CLOSED")})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert "closed" in str(excinfo.value).lower()
    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")


def test_finalize_lehnt_eine_nicht_akzeptierte_spec_ab(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Statusgate (c): jeder Status ausser `Accepted`/`Implemented` bricht unveraendert ab, und
    zwar vor jedem GitHub-Zugriff."""
    path = _write_spec(tmp_path, "0262", status="Proposed")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    meldung = str(excinfo.value)
    # Die Meldung muss beide zulaessigen Faelle nennen: eine unvollstaendige Aufzaehlung
    # widerspraeche der Regel, nach der eine bereits geschriebene identische Zielzeile
    # durchlaeuft - und dieses Werkzeug soll gerade ohne Handbeurteilung auswertbar sein.
    assert "'Proposed'" in meldung
    assert (
        "Status 'Accepted' oder eine, die bereits exakt die Zielzeile dieses Aufrufs traegt"
        in meldung
    )
    assert "**Status:** Proposed" in path.read_text(encoding="utf-8")
    assert fake.calls == []


def test_finalize_laeuft_bei_bereits_geschriebener_identischer_zielzeile_durch(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Statusgate (a) / AK 9 positiv: `Implemented` mit genau der Zeile, die dieser Lauf schreiben
    wuerde, ist ein bereits erreichter Zielzustand - kein Fehler. Geschrieben wird dabei exakt
    der Inhalt, der ohnehin schon in der Datei steht."""
    path = _write_spec(tmp_path, "0262", status=f"Implemented ([PR #281]({_pr_url(281)}))")
    vorher = path.read_text(encoding="utf-8")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result == {
        "spec_number": "0262",
        "issue_number": 262,
        "pr_number": 281,
        "status_line": f"Implemented ([PR #281]({_pr_url(281)}))",
        "status": "Done",
    }
    assert path.read_text(encoding="utf-8") == vorher
    item_edit = fake.single_call("gh", "project", "item-edit")
    assert item_edit[item_edit.index("--single-select-option-id") + 1] == "OPT_Done"


def test_finalize_lehnt_ein_implemented_mit_anderem_pr_ab(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Statusgate (b) / AK 9 negativ: das ist kein erreichter Zielzustand, sondern ein Hinweis auf
    die falsche Spec- oder PR-Nummer - Abbruch ohne Board-Schreibzugriff und ohne Dateiaenderung.
    """
    path = _write_spec(tmp_path, "0262", status=f"Implemented ([PR #1]({_pr_url(1)}))")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert f"**Status:** Implemented ([PR #1]({_pr_url(1)}))" in path.read_text(encoding="utf-8")
    assert fake.calls_starting_with("gh", "project", "item-edit") == []
    assert fake.calls_starting_with("gh", "issue", "close") == []


def test_finalize_lehnt_eine_zielzeile_mit_abweichendem_freitext_ab(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Statusgate (d): verglichen wird die vollstaendige Zeile, nicht das fuehrende Schluesselwort
    aus `read_spec_status()` - gleiche PR-Nummer bei abweichender URL gilt nicht als gleich."""
    path = _write_spec(
        tmp_path, "0262", status="Implemented ([PR #281](https://example.invalid/pull/281))"
    )
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert "https://example.invalid/pull/281" in path.read_text(encoding="utf-8")
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_finalize_vergleicht_die_zielzeile_nur_in_der_header_zone(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Ein in der Inhalts-Zone zitiertes `**Status:**` darf die Gleichheit nicht erfuellen, waehrend
    der Header auf etwas anderem steht - dieselbe `_split_header`-Trennung wie beim Schreiben."""
    path = _write_spec(tmp_path, "0262", status=f"Implemented ([PR #999]({_pr_url(999)}))")
    path.write_text(
        path.read_text(encoding="utf-8")
        + f"\n**Status:** Implemented ([PR #281]({_pr_url(281)}))\n",
        encoding="utf-8",
    )
    vorher = path.read_text(encoding="utf-8")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert path.read_text(encoding="utf-8") == vorher
    assert fake.calls_starting_with("gh", "project", "item-edit") == []


def test_finalize_ist_ohne_ruecknahme_wiederholbar(gh_board: ModuleType, tmp_path: Path) -> None:
    """AK 6, als ganzer Aufruf statt als Summe der Einzelschritte: zweimal derselbe Aufruf auf
    demselben zustandsbehafteten FakeGh, ohne dazwischen irgendetwas zurueckzunehmen."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)}, done_schliesst_das_issue=True)
    board = _board(gh_board, fake)

    def lauf() -> dict:
        return gh_board.cmd_finalize(
            board,
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    erster_lauf = lauf()
    datei_nach_lauf_1 = path.read_text(encoding="utf-8")
    zweiter_lauf = lauf()

    assert zweiter_lauf == erster_lauf
    assert path.read_text(encoding="utf-8") == datei_nach_lauf_1


def test_finalize_meldet_eine_fehlende_spec_datei(gh_board: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "specs" / "features").mkdir(parents=True)
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    assert "0262" in str(excinfo.value)


@pytest.mark.parametrize("number", ["../06", "26", "02620", "abcd", "02 2"])
def test_ungueltige_spec_nummer_wird_vor_jeder_pfadkonstruktion_abgelehnt(
    gh_board: ModuleType, tmp_path: Path, number: str
) -> None:
    fake = FakeGh()

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number=number,
            issue_number=262,
            pr_number=281,
        )


def test_finalize_ohne_pr_nummer_loest_den_schliessenden_gemergten_pr_auf(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(
        closing_prs={262: [{"number": 281, "url": _pr_url(281)}]},
        pull_requests={281: _pull_request(281, state="MERGED")},
    )

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=None,
    )

    assert result["pr_number"] == 281
    assert result["status_line"] == f"Implemented ([PR #281]({_pr_url(281)}))"


def test_finalize_ohne_gemergten_pr_ist_ein_fehler_statt_einer_stillen_aenderung(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(
        closing_prs={262: [{"number": 281, "url": _pr_url(281)}]},
        pull_requests={281: _pull_request(281)},
    )

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=None,
        )

    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")


def test_finalize_ohne_verknuepften_pr_ist_ein_klarer_fehler(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(closing_prs={262: []})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=None,
        )

    assert "262" in str(excinfo.value)


# -- finalize: PR<->Issue-Verknuepfung (Spec 0251 / ADR 0046) ---------------------------------


def test_finalize_akzeptiert_einen_pr_mit_passender_closing_referenz(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, closing_issues=[_closing_ref(262)])})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result["pr_number"] == 281
    assert "**Status:** Implemented" in path.read_text(encoding="utf-8")


def test_finalize_akzeptiert_ein_manuell_verknuepftes_issue_ohne_keyword(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Regressionsschutz fuer eine bewusste Entscheidung, kein zweiter Positivfall (ADR 0046,
    Abschnitt 3a): Vorgeschrieben ist die Zeile `Closes #NNN` im PR-Body, geprueft wird aber
    nur ihre **Wirkung** - die von GitHub gepflegte Verknuepfung. Weil `gh pr view --json` die
    Argumente `excludeUserLinked`/`userLinkedOnly` nicht uebergeben kann (beide Schema-Default
    `false`), enthaelt `closingIssuesReferences` auch per Development-Seitenleiste manuell
    verknuepfte Issues; die werden beim Merge genauso geschlossen.

    Aus Sicht des Test-Doubles ist dieser Fall vom Keyword-Fall **nicht unterscheidbar** - die
    Herkunft der Referenz taucht im Feld gar nicht auf. Genau das ist die Aussage: Der Test
    haelt fest, dass eine spaetere Verengung (Umstieg auf `gh api graphql` mit
    `excludeUserLinked: true`, Zusatzpruefung auf die Textzeile) auffallen soll, statt
    stillschweigend durchzugehen. Ohne diese Begruendung saehe er wie ein Duplikat des
    vorherigen Falls aus und waere der erste Kandidat beim Aufraeumen.
    """
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, closing_issues=[_closing_ref(262)])})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=281,
    )

    assert result["pr_number"] == 281


@pytest.mark.parametrize(
    ("pull_request", "erwartete_textbausteine"),
    [
        pytest.param(_pull_request(281, closing_issues=[]), ["2.72.0"], id="leere-liste"),
        pytest.param(
            _pull_request(281, closing_issues=[_closing_ref(999)]),
            ["2.72.0"],
            id="nur-fremdes-issue",
        ),
        pytest.param(
            _pull_request(281, closing_issues=[_closing_ref(262, owner="fremd", repo="anderes")]),
            ["2.72.0", "fremd/anderes"],
            id="gleiche-nummer-fremdes-repository",
        ),
        pytest.param(
            _pull_request(281, base_ref_name="release/0.24"),
            ["release/0.24", "main"],
            id="nicht-der-default-branch",
        ),
    ],
)
def test_finalize_lehnt_einen_pr_ohne_wirksame_verknuepfung_ab(
    gh_board: ModuleType,
    tmp_path: Path,
    pull_request: dict,
    erwartete_textbausteine: list[str],
) -> None:
    """Abbruch vor dem Umschreiben der Spec-Datei und vor **jedem** Board-Zugriff, auch dem
    lesenden - deshalb wird zusaetzlich das vollstaendige Aufruflog geprueft. Das beweist mehr
    als eine Aufzaehlung verbotener Aufrufe und altert nicht mit neuen Schreibbefehlen.
    """
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: pull_request})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    message = str(excinfo.value)
    assert "262" in message
    for baustein in erwartete_textbausteine:
        assert baustein in message
    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")
    assert {tuple(call[:3]) for call in fake.calls} == {("gh", "pr", "view")}


def test_ein_gh_ohne_das_verknuepfungsfeld_wird_als_versionsproblem_gemeldet(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Ein `gh` < 2.72.0 kennt `closingIssuesReferences` nicht und laesst den Aufruf mit
    'unknown JSON field' scheitern. Die Meldung muss die Mindestversion nennen, sonst wird ein
    Werkzeugproblem als fehlende Verknuepfung fehlgedeutet - und jemand traegt eine Zeile nach,
    die laengst da ist."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(
        failing={("gh", "pr", "view")},
        failure_stderr={("gh", "pr", "view"): UNKNOWN_JSON_FIELD_STDERR},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    message = str(excinfo.value)
    assert "2.72.0" in message
    assert "unknown JSON field" in message
    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")


def test_ein_unverwandter_gh_fehler_wird_nicht_zum_versionsproblem_umgedeutet(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Gegenstueck zum Versionsfall: Ein abgelaufenes Token, ein Netzwerkfehler oder ein nicht
    gefundener PR haben mit der `gh`-Version nichts zu tun. Wuerde der Hinweis unbedingt
    angehaengt, verschlechterte ausgerechnet diese Aenderung die Diagnostik - jemand
    aktualisiert `gh`, waehrend in Wahrheit die Anmeldung abgelaufen ist."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(
        failing={("gh", "pr", "view")},
        failure_stderr={("gh", "pr", "view"): ABGELAUFENES_TOKEN_STDERR},
    )

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    message = str(excinfo.value)
    assert "2.72.0" not in message
    assert "Bad credentials (HTTP 401)" in message
    assert "**Status:** Accepted" in path.read_text(encoding="utf-8")


def test_finalize_ist_nach_dem_nachtragen_der_verknuepfung_wiederholbar(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Der Abbruch ist folgenlos: Nach dem Nachtragen der Verknuepfung am offenen PR laeuft
    derselbe Aufruf durch, ohne dass vorher etwas zurueckgenommen werden muesste."""
    path = _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, closing_issues=[])})
    board = _board(gh_board, fake)

    with pytest.raises(gh_board.BoardError):
        gh_board.cmd_finalize(
            board, repo_root=tmp_path, spec_number="0262", issue_number=262, pr_number=281
        )

    fake.pull_requests[281] = _pull_request(281, closing_issues=[_closing_ref(262)])

    result = gh_board.cmd_finalize(
        board, repo_root=tmp_path, spec_number="0262", issue_number=262, pr_number=281
    )

    assert result["pr_number"] == 281
    assert "**Status:** Implemented" in path.read_text(encoding="utf-8")


def test_cli_meldet_die_fehlende_verknuepfung_als_json_fehler(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281, closing_issues=[])})

    exit_code = gh_board.main(
        ["finalize", "--spec", "0262", "--pr-number", "281"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 1
    assert "2.72.0" in json.loads(capsys.readouterr().out)["error"]


def test_finalize_ohne_pr_nummer_prueft_die_verknuepfung_bewusst_nicht_selbst(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Charakterisierungstest (ADR 0046, Abschnitt 3b): Der Ausnahmepfad findet den PR ueber
    `closedByPullRequestsReferences` am Issue - dieselbe von GitHub gepflegte Verknuepfung aus
    der Gegenrichtung, die ohne sie leer bliebe. Eine eigene Pruefung waere dort sinnlos.

    Festgehalten, damit niemand die Pruefung "sauberkeitshalber" nach `get_pull_request()`
    verschiebt und damit den Ausnahmepfad bricht: Dieser gemergte PR traegt weder eine
    passende Closing-Referenz noch den Default-Branch - und wird trotzdem akzeptiert.
    """
    _write_spec(tmp_path, "0262")
    fake = FakeGh(
        closing_prs={262: [{"number": 281, "url": _pr_url(281)}]},
        pull_requests={
            281: _pull_request(281, state="MERGED", base_ref_name="release/0.24", closing_issues=[])
        },
    )

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0262",
        issue_number=262,
        pr_number=None,
    )

    assert result["pr_number"] == 281


def test_mehrdeutige_spec_nummer_bricht_ab_statt_still_die_erste_datei_zu_waehlen(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    """Zwei Dateien mit derselben Nummer duerfen nie stillschweigend aufgeloest werden -
    `finalize` wuerde sonst die falsche Spec-Datei umschreiben (Copilot-Review-Finding auf
    PR #267)."""
    first = _write_spec(tmp_path, "0262")
    second = tmp_path / "specs" / "features" / "0262-zweite-datei.md"
    second.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    with pytest.raises(gh_board.BoardError) as excinfo:
        gh_board.cmd_finalize(
            _board(gh_board, fake),
            repo_root=tmp_path,
            spec_number="0262",
            issue_number=262,
            pr_number=281,
        )

    message = str(excinfo.value)
    assert "0262-beispiel.md" in message
    assert "0262-zweite-datei.md" in message
    assert "**Status:** Accepted" in first.read_text(encoding="utf-8")
    assert "**Status:** Accepted" in second.read_text(encoding="utf-8")


def test_finalize_findet_die_spec_ueber_die_nummer_nicht_ueber_den_titel(
    gh_board: ModuleType, tmp_path: Path
) -> None:
    _write_spec(tmp_path, "0262")
    _write_spec(tmp_path, "0065")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    result = gh_board.cmd_finalize(
        _board(gh_board, fake),
        repo_root=tmp_path,
        spec_number="0065",
        issue_number=262,
        pr_number=281,
    )

    assert result["spec_number"] == "0065"
    assert "Implemented" in (tmp_path / "specs" / "features" / "0065-beispiel.md").read_text(
        encoding="utf-8"
    )
    assert "**Status:** Accepted" in (
        tmp_path / "specs" / "features" / "0262-beispiel.md"
    ).read_text(encoding="utf-8")


# -- CLI --------------------------------------------------------------------------------------


def test_cli_gibt_ein_einzelnes_json_objekt_aus(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh()

    exit_code = gh_board.main(
        ["show-status", "--issue", "262"], run=fake, repo_root=tmp_path, owner=OWNER
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {"issue_number": 262, "status": "Ready"}


def test_cli_meldet_fehler_als_json_mit_exit_code_1(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh()

    exit_code = gh_board.main(
        ["set-status", "--issue", "262", "--status", "Erledigt"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert "Erledigt" in payload["error"]
    assert set(payload) == {"error"}


def test_cli_set_priority_gibt_das_erwartete_json_zurueck(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh(fields=_fields_mit_prioritaets_optionen())

    exit_code = gh_board.main(
        ["set-priority", "--issue", "262", "--priority", "Hoch"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "issue_number": 262,
        "priority": "Hoch",
        "changed": True,
    }


def test_cli_set_priority_lehnt_unbekannten_wert_mit_exit_code_1_ab(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh()

    exit_code = gh_board.main(
        ["set-priority", "--issue", "262", "--priority", "Kritisch"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert "Kritisch" in payload["error"]
    assert set(payload) == {"error"}


def test_cli_meldet_einen_fehlgeschlagenen_gh_aufruf_als_json(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGh(failing={("gh", "project", "item-list")})

    exit_code = gh_board.main(
        ["show-status", "--issue", "262"], run=fake, repo_root=tmp_path, owner=OWNER
    )

    assert exit_code == 1
    assert "error" in json.loads(capsys.readouterr().out)


def test_cli_finalize_nimmt_die_spec_nummer_als_issue_nummer(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    exit_code = gh_board.main(
        ["finalize", "--spec", "0262", "--pr-number", "281"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["issue_number"] == 262


def test_cli_finalize_ist_wiederholbar_und_meldet_zweimal_dasselbe(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AK 6/7 auf der Ebene, die `ship-feature` tatsaechlich auswertet: zweimal Exit-Code 0 und
    identisches JSON auf stdout - kein `{"error": ...}`, keine Handbeurteilung."""
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)}, done_schliesst_das_issue=True)
    argv = ["finalize", "--spec", "0262", "--pr-number", "281"]

    erster_code = gh_board.main(argv, run=fake, repo_root=tmp_path, owner=OWNER)
    erste_ausgabe = capsys.readouterr().out
    zweiter_code = gh_board.main(argv, run=fake, repo_root=tmp_path, owner=OWNER)
    zweite_ausgabe = capsys.readouterr().out

    assert (erster_code, zweiter_code) == (0, 0)
    assert json.loads(zweite_ausgabe) == json.loads(erste_ausgabe)


def test_cli_finalize_erlaubt_eine_abweichende_issue_nummer_fuer_altspecs(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_spec(tmp_path, "0065")
    fake = FakeGh(
        items=[
            {
                "id": "PVTI_240",
                "content": {"type": "Issue", "number": 240, "url": _issue_url(240)},
                "status": "Todo",
            }
        ],
        # Altspec: Issue-Nummer weicht von der Spec-Nummer ab, die Verknuepfung muss auf
        # genau dieses Issue zeigen (der Default der Hilfsfunktion referenziert 262).
        pull_requests={261: _pull_request(261, state="MERGED", closing_issues=[_closing_ref(240)])},
    )

    exit_code = gh_board.main(
        ["finalize", "--spec", "0065", "--issue", "240", "--pr-number", "261"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["issue_number"] == 240


@pytest.mark.parametrize(
    ("argv"),
    [
        ["create-issue", "--type", "idee", "--title", "T", "--body-file", "B"],
        ["set-body", "--issue", "262", "--body-file", "B"],
        ["set-status", "--issue", "262", "--status", "Todo"],
        ["set-priority", "--issue", "262", "--priority", "Hoch"],
        ["show-status", "--issue", "262"],
        ["finalize", "--spec", "0262"],
    ],
)
def test_cli_kennt_alle_in_den_skills_dokumentierten_befehle(
    gh_board: ModuleType, argv: list[str]
) -> None:
    """Die Aufrufformen aus .claude/skills/github-board/SKILL.md muessen parsebar bleiben."""
    assert gh_board.build_parser().parse_args(argv).command == argv[0]


def test_kein_gh_aufruf_verwendet_eine_shell(gh_board: ModuleType, tmp_path: Path) -> None:
    """Alle Aufrufe gehen als Argumentliste raus (ADR 0017, Abschnitt 5 - unveraendert gueltig)."""
    _write_spec(tmp_path, "0262")
    fake = FakeGh(pull_requests={281: _pull_request(281)})

    gh_board.main(
        ["finalize", "--spec", "0262", "--pr-number", "281"],
        run=fake,
        repo_root=tmp_path,
        owner=OWNER,
    )

    assert fake.calls
    for call in fake.calls:
        assert isinstance(call, list)
        assert call[0] == "gh"
        assert all(isinstance(arg, str) for arg in call)


# -- doctor: Versionsvergleich und Zuordnungstabelle -------------------------------------------


@pytest.mark.parametrize(
    ("ausgabe", "erwartet"),
    [
        pytest.param(GH_VERSION_STDOUT, (2, 72, 0), id="mehrzeilig-release-url-in-zeile-2"),
        pytest.param("gh version 2.72.0-1ubuntu0.1\n", (2, 72, 0), id="distributions-suffix"),
        pytest.param("gh version 2.9.0 (2023-01-01)\n", (2, 9, 0), id="aeltere-version"),
        pytest.param("", None, id="leere-ausgabe"),
        pytest.param("irgendetwas ohne Versionsangabe\n", None, id="nicht-auswertbar"),
    ],
)
def test_gh_version_wird_aus_der_ersten_zeile_gelesen(
    gh_board: ModuleType, ausgabe: str, erwartet: tuple[int, int, int] | None
) -> None:
    """`gh --version` ist mehrzeilig (die Release-URL steht in Zeile 2) und traegt in
    Distributionspaketen ein Suffix. Eine gar nicht auswertbare Zeichenkette ist ein Befund,
    kein Absturz."""
    assert gh_board.parse_gh_version(ausgabe) == erwartet


def test_der_versionsvergleich_ist_numerisch_nicht_lexikografisch(gh_board: ModuleType) -> None:
    """Ein lexikografischer Vergleich haelt `2.9.0` fuer neuer als die Mindestversion `2.72.0`
    und meldete ein echtes Werkzeugproblem als gruen."""
    assert "2.9.0" > "2.72.0"  # der Beleg, dass die naheliegende Form falsch waere
    assert gh_board.parse_gh_version("gh version 2.9.0") < gh_board.parse_gh_version(
        f"gh version {gh_board.MIN_GH_VERSION}"
    )


def test_die_zuordnungstabelle_deckt_jeden_lebenszyklus_schritt_ab(gh_board: ModuleType) -> None:
    """Eine statische Tabelle wird auf Totalitaet geprueft, nicht auf Beispiele: Ihr typischer
    Defekt ist kein falsches Verhalten, sondern ein Tippfehler, der still nie wieder auftaucht."""
    zugeordnet = {
        schritt
        for schritte in gh_board.PROBE_LIFECYCLE_STEPS.values()
        for schritt in schritte
    }

    assert zugeordnet == set(gh_board.LIFECYCLE_STEPS)
    assert len(gh_board.LIFECYCLE_STEPS) == len(set(gh_board.LIFECYCLE_STEPS))


# -- doctor: Bericht ---------------------------------------------------------------------------


# Alles, was Zustand hinterlaesst. `doctor` soll in einer noch nicht beurteilten Umgebung
# beliebig oft laufen koennen - deshalb ist das ein Sicherheits-Regressionstest ueber die
# protokollierten Argumentlisten, keine blosse Absichtserklaerung (ADR 0051, Abschnitt 5).
SCHREIBENDE_GH_AUFRUFE = [
    ("gh", "project", "item-edit"),
    ("gh", "project", "item-add"),
    ("gh", "project", "create"),
    ("gh", "issue", "create"),
    ("gh", "issue", "close"),
    ("gh", "issue", "edit"),
    ("gh", "pr", "edit"),
    ("gh", "label", "create"),
]


def _gesunder_fake(**kwargs) -> FakeGh:
    """Eine Umgebung, in der jede Pruefung durchgeht - inklusive der Board-Felder samt
    vollstaendiger Optionslisten (der FakeGh-Default laesst die Prioritaets-Optionen leer)."""
    kwargs.setdefault("fields", _fields_mit_prioritaets_optionen())
    return FakeGh(**kwargs)


def _doctor(gh_board: ModuleType, fake: FakeGh) -> dict:
    return gh_board.cmd_doctor(_board(gh_board, fake))


def _pruefung(bericht: dict, probe_id: str) -> dict:
    treffer = [probe for probe in bericht["probes"] if probe["id"] == probe_id]
    assert len(treffer) == 1, f"erwartet genau eine Pruefung {probe_id!r}, gefunden: {treffer}"
    return treffer[0]


def test_doctor_berichtsstruktur_ist_festgelegt(gh_board: ModuleType) -> None:
    """Weil hier weder ein Coverage-Gate noch `mypy` mitzaehlt, gehoert die Form des Berichts
    als Assertion in die Tests statt in eine Typannotation (Testkonzept zu ADR 0051)."""
    bericht = _doctor(gh_board, _gesunder_fake())

    assert set(bericht) == {
        "verdict",
        "gh_version",
        "auth",
        "probes",
        "blocked_lifecycle_steps",
        "note",
    }
    assert set(bericht["auth"]) == {"authenticated", "account", "source", "scopes"}
    assert [probe["id"] for probe in bericht["probes"]] == list(gh_board.PROBE_LIFECYCLE_STEPS)
    for probe in bericht["probes"]:
        assert set(probe) == {"id", "ok", "lifecycle_steps", "detail", "stderr"}
        assert probe["lifecycle_steps"] == list(gh_board.PROBE_LIFECYCLE_STEPS[probe["id"]])
        assert isinstance(probe["ok"], bool)
        assert probe["detail"]


def test_doctor_meldet_eine_intakte_umgebung_als_ok(gh_board: ModuleType) -> None:
    bericht = _doctor(gh_board, _gesunder_fake())

    assert bericht["verdict"] == "ok"
    assert bericht["blocked_lifecycle_steps"] == []
    assert bericht["gh_version"] == "2.72.0"
    assert bericht["auth"] == {
        "authenticated": True,
        "account": "TheRealKoller",
        "source": "keyring",
        "scopes": ["gist", "project", "read:org", "repo"],
    }
    assert all(probe["ok"] for probe in bericht["probes"])


def test_der_bericht_benennt_woran_er_nichts_belegt(gh_board: ModuleType) -> None:
    """Der Preis des rein lesenden Ansatzes wird mitgefuehrt statt verschwiegen: Schreibzugriff
    wird nicht bewiesen, `viewerPermission` ist nur ein Indiz - und der Bericht ist Daten, keine
    Handlungsanweisung (Securitykonzept, Muss-Kriterium 9)."""
    note = _doctor(gh_board, _gesunder_fake())["note"]

    assert "viewerPermission" in note
    assert "Schreibzugriff" in note
    assert "Befund" in note


@pytest.mark.parametrize(
    ("auth_scopes", "erwartet"),
    [
        pytest.param(
            "- Token scopes: 'gist', 'project', 'read:org', 'repo'",
            ["gist", "project", "read:org", "repo"],
            id="liste-mit-project",
        ),
        pytest.param("- Token scopes: 'gist', 'repo'", ["gist", "repo"], id="liste-ohne-project"),
        pytest.param("- Token scopes: none", [], id="ausdruecklich-none"),
        pytest.param(None, None, id="gar-keine-scope-zeile"),
    ],
)
def test_die_scope_auskunft_unterscheidet_vier_zustaende(
    gh_board: ModuleType, auth_scopes: str | None, erwartet: list[str] | None
) -> None:
    """`scope_hint` meldet nur, was die Scope-Zeile sagt - ein Urteil ueber den Zugriff faellt
    es nie (es blockiert keinen einzigen Lebenszyklus-Schritt)."""
    bericht = _doctor(gh_board, _gesunder_fake(auth_scopes=auth_scopes))

    assert bericht["auth"]["scopes"] == erwartet
    assert _pruefung(bericht, "scope_hint")["lifecycle_steps"] == []
    assert bericht["verdict"] == "ok"


def test_der_bericht_beschreibt_das_aktive_konto(gh_board: ModuleType) -> None:
    bericht = _doctor(gh_board, _gesunder_fake(auth_output=ZWEI_KONTEN_AUSGABE))

    assert bericht["auth"]["account"] == "TheRealKoller"
    assert bericht["auth"]["source"] == "GH_TOKEN"
    assert bericht["auth"]["scopes"] == ["repo"]


def test_doctor_laeuft_bei_gescheiterter_auth_vollstaendig_durch(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Die Umkehrung der Erfolgs-Konvention ist ein eigener Pruefgegenstand: Exit-Code 0, genau
    ein JSON-Objekt auf stdout, und die nachgelagerten Pruefungen sind nachweislich gelaufen -
    genau dafuer existiert das Kommando."""
    fake = FakeGh(auth_returncode=1, failing={("gh", "project", "list")})

    exit_code = gh_board.main(["doctor"], run=fake, repo_root=tmp_path, owner=OWNER)

    ausgabe = capsys.readouterr()
    bericht = json.loads(ausgabe.out)
    assert exit_code == 0
    assert ausgabe.out.strip().count("\n") == 0
    assert bericht["verdict"] == "blocked"
    assert bericht["auth"] == {
        "authenticated": False,
        "account": None,
        "source": None,
        "scopes": None,
    }
    assert sorted(bericht["blocked_lifecycle_steps"]) == sorted(gh_board.LIFECYCLE_STEPS)
    assert [probe["id"] for probe in bericht["probes"]] == list(gh_board.PROBE_LIFECYCLE_STEPS)
    assert fake.calls_starting_with("gh", "repo", "view")
    assert fake.calls_starting_with("gh", "issue", "list")
    assert fake.calls_starting_with("gh", "project", "list")


def test_doctor_ohne_gh_binary_meldet_einen_befund_statt_eines_tracebacks(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein fehlendes Binary laesst `subprocess.run` mit `FileNotFoundError` scheitern, nicht mit
    Returncode != 0 - und ein Kommando, das nur in einer kaputten Umgebung gebraucht wird,
    verliert seinen Wert vollstaendig, wenn es dort abstuerzt."""
    fake = FakeGh(missing_binary=True)

    exit_code = gh_board.main(["doctor"], run=fake, repo_root=tmp_path, owner=OWNER)

    bericht = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert bericht["verdict"] == "blocked"
    assert bericht["gh_version"] is None
    assert _pruefung(bericht, "gh_binary")["ok"] is False
    assert sorted(bericht["blocked_lifecycle_steps"]) == sorted(gh_board.LIFECYCLE_STEPS)
    assert [probe["id"] for probe in bericht["probes"]] == list(gh_board.PROBE_LIFECYCLE_STEPS)


def test_ein_unsichtbares_board_blockiert_genau_die_vier_board_schritte(
    gh_board: ModuleType,
) -> None:
    """Nicht `idee-erfassen`: Das Issue entsteht dort, bevor das Projekt aufgeloest wird."""
    fake = _gesunder_fake(
        failing={("gh", "project", "list")},
        failure_stderr={("gh", "project", "list"): "GraphQL: Resource not accessible"},
    )

    bericht = _doctor(gh_board, fake)

    assert bericht["blocked_lifecycle_steps"] == list(gh_board.BOARD_LIFECYCLE_STEPS)
    assert "idee-erfassen" not in bericht["blocked_lifecycle_steps"]
    projekt_pruefung = _pruefung(bericht, "project_visible")
    assert projekt_pruefung["ok"] is False
    assert "Resource not accessible" in projekt_pruefung["stderr"]


def test_ein_umbenanntes_board_ist_ein_befund_ohne_scope_deutung(gh_board: ModuleType) -> None:
    """Erfolgreicher Aufruf ohne Titeltreffer: kein Berechtigungsproblem, also auch kein
    Scope-Hinweis - und kein fremder Projekttitel im Bericht (das Repo ist oeffentlich)."""
    fake = _gesunder_fake(projects=[{"number": 1, "id": "PVT_other", "title": "Fremdes Board"}])

    bericht = _doctor(gh_board, fake)

    projekt_pruefung = _pruefung(bericht, "project_visible")
    assert projekt_pruefung["ok"] is False
    assert projekt_pruefung["stderr"] is None
    assert "Fremdes Board" not in json.dumps(bericht, ensure_ascii=False)
    assert "gh auth refresh" not in projekt_pruefung["detail"]


@pytest.mark.parametrize(
    "project_list_stdout",
    [
        pytest.param('{"projects": "nope"}', id="gueltiges-json-falsche-struktur"),
        pytest.param("kein JSON", id="kein-json"),
        pytest.param("", id="leere-ausgabe-bei-returncode-0"),
    ],
)
def test_doctor_ueberlebt_eine_unerwartete_antwortform(
    gh_board: ModuleType, project_list_stdout: str
) -> None:
    bericht = _doctor(gh_board, _gesunder_fake(project_list_stdout=project_list_stdout))

    assert _pruefung(bericht, "project_visible")["ok"] is False
    assert bericht["verdict"] == "blocked"


@pytest.mark.parametrize(
    ("permission", "erwartet_ok"),
    [
        pytest.param("ADMIN", True, id="admin"),
        pytest.param("WRITE", True, id="write"),
        pytest.param("MAINTAIN", True, id="maintain"),
        pytest.param("TRIAGE", False, id="triage-sieht-nach-schreibrecht-aus-und-ist-keins"),
        pytest.param("READ", False, id="read"),
        pytest.param("NONE", False, id="none"),
        pytest.param(None, False, id="kein-wert"),
    ],
)
def test_nur_echtes_schreibrecht_gilt_als_repo_zugriff(
    gh_board: ModuleType, permission: str | None, erwartet_ok: bool
) -> None:
    bericht = _doctor(gh_board, _gesunder_fake(viewer_permission=permission))

    assert _pruefung(bericht, "repo_access")["ok"] is erwartet_ok
    blockiert = set(bericht["blocked_lifecycle_steps"])
    assert ("idee-erfassen" in blockiert) is not erwartet_ok
    assert ("pr-eroeffnen" in blockiert) is not erwartet_ok


def test_eine_leere_issue_liste_ist_ein_erfolg(gh_board: ModuleType) -> None:
    """Wer `[]` als fehlgeschlagene Pruefung wertet, meldet in genau der Umgebung Alarm, die
    einwandfrei funktioniert."""
    bericht = _doctor(gh_board, _gesunder_fake(issue_list=[]))

    assert _pruefung(bericht, "issue_read")["ok"] is True
    assert bericht["verdict"] == "ok"


def test_doctor_fragt_von_den_issues_nur_die_nummer_ab(gh_board: ModuleType) -> None:
    """Kein von Dritten befuellbarer Inhalt im Bericht (Securitykonzept, Muss-Kriterium 6): Das
    Repository ist oeffentlich, jeder kann ein Issue mit beliebigem Titel anlegen."""
    fake = _gesunder_fake()

    _doctor(gh_board, fake)

    assert fake.single_call("gh", "issue", "list") == [
        "gh",
        "issue",
        "list",
        "--limit",
        "1",
        "--json",
        "number",
    ]


def test_ein_zu_altes_gh_blockiert_nur_die_finalisierung(gh_board: ModuleType) -> None:
    bericht = _doctor(gh_board, _gesunder_fake(gh_version_stdout="gh version 2.9.0 (2023-01-01)"))

    assert bericht["gh_version"] == "2.9.0"
    assert _pruefung(bericht, "gh_version")["ok"] is False
    assert bericht["blocked_lifecycle_steps"] == ["abschluss-finalisieren"]


def test_ein_fehlendes_board_feld_ist_ein_board_befund(gh_board: ModuleType) -> None:
    bericht = _doctor(
        gh_board,
        FakeGh(fields=[{"id": "FIELD_status", "name": "Status", "options": []}]),
    )

    assert _pruefung(bericht, "fields")["ok"] is False
    assert bericht["blocked_lifecycle_steps"] == list(gh_board.BOARD_LIFECYCLE_STEPS)


def test_fehlende_feld_optionen_sind_ein_board_befund(gh_board: ModuleType) -> None:
    """Der FakeGh-Default fuehrt das Prioritaetsfeld ohne Optionen - genau der Zustand, den ein
    manuell veraendertes Board erzeugt."""
    bericht = _doctor(gh_board, FakeGh())

    assert _pruefung(bericht, "fields")["ok"] is False
    assert "Priorität" in _pruefung(bericht, "fields")["detail"]


def test_die_item_pruefung_meldet_die_sichtbaren_board_items(gh_board: ModuleType) -> None:
    bericht = _doctor(gh_board, _gesunder_fake())

    assert _pruefung(bericht, "items")["ok"] is True
    assert "1" in _pruefung(bericht, "items")["detail"]


@pytest.mark.parametrize("kaputt", [False, True])
def test_verdict_ist_genau_dann_ok_wenn_kein_schritt_blockiert_ist(
    gh_board: ModuleType, kaputt: bool
) -> None:
    """`verdict` wird aus den blockierten Schritten abgeleitet, nicht separat gefuehrt."""
    fake = _gesunder_fake(failing={("gh", "project", "list")} if kaputt else set())

    bericht = _doctor(gh_board, fake)

    assert (bericht["verdict"] == "ok") is (bericht["blocked_lifecycle_steps"] == [])
    assert bericht["verdict"] == ("blocked" if kaputt else "ok")


@pytest.mark.parametrize("kaputt", [False, True])
def test_doctor_setzt_keinen_einzigen_schreibenden_gh_aufruf_ab(
    gh_board: ModuleType, tmp_path: Path, kaputt: bool
) -> None:
    fake = _gesunder_fake(
        failing={("gh", "project", "list"), ("gh", "repo", "view")} if kaputt else set()
    )

    gh_board.main(["doctor"], run=fake, repo_root=tmp_path, owner=OWNER)

    assert fake.calls
    for verboten in SCHREIBENDE_GH_AUFRUFE:
        assert fake.calls_starting_with(*verboten) == []


def test_doctor_redigiert_den_vollstaendigen_bericht(gh_board: ModuleType) -> None:
    """Geprueft ueber den vollstaendigen serialisierten Bericht, nicht ueber das Feld, an das
    man beim Schreiben gedacht hat - nur so ist ein spaeter ergaenztes Feld mitgedeckt."""
    token = TOKEN_BEISPIELE[0]
    gescheitert = {("gh", "project", "list"), ("gh", "repo", "view"), ("gh", "issue", "list")}
    fake = _gesunder_fake(
        failing=gescheitert,
        failure_stderr={prefix: f"boom mit {token} dabei" for prefix in gescheitert},
        # Auch die Ausgabe der gescheiterten `auth`-Pruefung geht (redigiert) in den Bericht.
        auth_returncode=1,
        auth_output=f"X Failed to log in to github.com using token {token} (GH_TOKEN)",
    )

    serialisiert = json.dumps(_doctor(gh_board, fake), ensure_ascii=False)

    assert token not in serialisiert
    assert "boom mit" in serialisiert


def test_doctor_kuerzt_ein_gespraechiges_stderr(gh_board: ModuleType) -> None:
    fake = _gesunder_fake(
        failing={("gh", "project", "list")},
        failure_stderr={("gh", "project", "list"): "A" * 5000},
    )

    stderr = _pruefung(_doctor(gh_board, fake), "project_visible")["stderr"]

    assert len(stderr) < 600


# -- doctor: CLI -------------------------------------------------------------------------------


def test_doctor_nimmt_keine_argumente_entgegen(gh_board: ModuleType) -> None:
    """Kein Argument heisst keine Eingabeflaeche (Securitykonzept, Muss-Kriterium 8)."""
    assert gh_board.build_parser().parse_args(["doctor"]).command == "doctor"
    with pytest.raises(SystemExit):
        gh_board.build_parser().parse_args(["doctor", "--issue", "262"])


def test_die_cli_kennt_genau_die_in_der_skill_tabelle_dokumentierten_befehle(
    gh_board: ModuleType,
) -> None:
    """'Befehl ergaenzt, Doku vergessen' ist damit ein roter Test statt einer stillen
    Abweichung (Testkonzept zu ADR 0051)."""
    skill_datei = Path(__file__).parents[2] / ".claude" / "skills" / "github-board" / "SKILL.md"
    dokumentiert = set(
        re.findall(r"^\|\s*`([a-z][a-z-]*)", skill_datei.read_text(encoding="utf-8"), re.MULTILINE)
    )
    subparser = next(
        aktion
        for aktion in gh_board.build_parser()._actions
        if isinstance(aktion, argparse._SubParsersAction)
    )

    assert set(subparser.choices) == dokumentiert


def test_ein_fehlendes_gh_binary_wird_zu_einer_fehlermeldung_statt_eines_tracebacks(
    gh_board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`subprocess.run` wirft bei fehlendem Binary `FileNotFoundError` statt Returncode != 0 -
    ungefangen faellt daraus ein Traceback heraus statt der ueblichen `{"error": ...}`-Ausgabe
    (dieselbe Lehre wie ADR 0048: BoardError, kein Durchgriff einer fremden Ausnahme)."""
    fake = FakeGh(missing_binary=True)

    exit_code = gh_board.main(
        ["show-status", "--issue", "262"], run=fake, repo_root=tmp_path, owner=OWNER
    )

    assert exit_code == 1
    assert "error" in json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("auth_stream", ["stdout", "stderr"])
def test_der_bericht_nennt_die_ausgabe_einer_gescheiterten_auth_pruefung(
    gh_board: ModuleType, auth_stream: str
) -> None:
    """Genau der Fall, fuer den `doctor` gebaut wurde: Remote-Session mit ungueltigem oder
    abgelaufenem Umgebungstoken. Die `auth`-Pruefung blockiert dann ALLE Lebenszyklus-Schritte -
    dann muss der Bericht auch sagen, woran es lag und welche Token-Quelle betroffen war, sonst
    ist ausgerechnet der wichtigste Bericht der unbrauchbarste. Auf welchem Stream `gh` den
    Fehlschlag meldet, haengt an seiner Version und darf keinen Unterschied machen.
    """
    fake = _gesunder_fake(
        auth_returncode=1,
        auth_stream=auth_stream,
        auth_output="X Failed to log in to github.com using token (GH_TOKEN)",
    )

    bericht = _doctor(gh_board, fake)

    pruefung = _pruefung(bericht, "auth")
    assert pruefung["ok"] is False
    assert "GH_TOKEN" in pruefung["stderr"]
    assert sorted(bericht["blocked_lifecycle_steps"]) == sorted(gh_board.LIFECYCLE_STEPS)


def test_im_erfolgsfall_wird_die_auth_ausgabe_nicht_uebernommen(gh_board: ModuleType) -> None:
    """Gegenstueck: Im Erfolgsfall ist die Ausgabe von `gh auth status` ein vollstaendiger
    Status-Dump - dort tragen ausschliesslich die vier Whitelist-Felder die Auskunft, und nichts
    wird verbatim durchgereicht (Securitykonzept, Muss-Kriterium 4). Blockiert ist in diesem
    Fall ohnehin nichts, es gibt also auch nichts zu erklaeren."""
    bericht = _doctor(gh_board, _gesunder_fake())

    assert _pruefung(bericht, "auth")["ok"] is True
    assert _pruefung(bericht, "auth")["stderr"] is None
    assert "Git operations protocol" not in json.dumps(bericht, ensure_ascii=False)
