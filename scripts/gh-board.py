#!/usr/bin/env python3
"""Duenner Helfer fuer die GitHub-Projects-(V2)-Operationen des PhotoSort-Workflows.

Loest `scripts/github-project-sync/` ab (Spec 0262 / ADR 0043): Es wird nichts mehr
"synchronisiert" - es gibt keine Zustandsdatei, kein Nummern-Mapping und keinen Content-Push des
Spec-Inhalts in den Issue-Body mehr. Uebrig bleiben einzelne, zustandslose Board-Operationen, die
die Skills unter `.claude/skills/` aufrufen (siehe `.claude/skills/github-board/SKILL.md`).

Die fehleranfaellige Projects-V2-Logik (Projekt-/Feld-/Options-/Item-ID-Aufloesung, Setzen eines
Single-Select-Werts) liegt bewusst nur hier und nicht verstreut in den Skill-Dateien.

Ausgabe ist immer ein einzelnes JSON-Objekt auf stdout, im Fehlerfall `{"error": "..."}` mit
Exit-Code 1 - dieselbe Aufrufkonvention wie beim abgeloesten Tool.

Haertung unveraendert aus ADR 0017, Abschnitt 5: kein `shell=True`, Argumente ausschliesslich in
Listenform, Bodies ueber temporaere Dateien statt ueber die Kommandozeile, Spec-Nummern vor jeder
Pfadkonstruktion validiert.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

RunFunc = Callable[[list[str]], "subprocess.CompletedProcess[str]"]

DEFAULT_OWNER = "TheRealKoller"
DEFAULT_PROJECT_TITLE = "PhotoSort Roadmap"

STATUS_FIELD_NAME = "Status"
# Die sechs Board-Werte aus ADR 0037, Abschnitt 1 - unveraendert. Anders als frueher gibt es
# keine Projektion aus dem Datei-Status mehr (Baseline/Override, ADR 0037 Abschnitt 2): der Wert
# wird direkt gesetzt, weil kein voller Lauf ihn mehr neu berechnen koennen muss (ADR 0043,
# Abschnitt 4).
STATUS_VALUES = ("Unrefined", "Ready", "Todo", "In Progress", "Review", "Done")

PRIORITY_FIELD_NAME = "Priorität"
# First-write-wins-Feld (ADR 0044): Startwert einer Empfehlung, danach ausschliesslich manuell
# von Daniel im Board gepflegt - kein Wert wird von hier aus je wieder ueberschrieben.
PRIORITY_VALUES = ("Hoch", "Mittel", "Niedrig")

STORY_TYPE_LABELS = {"idee": "idee", "bug": "bug"}
LABEL_PROVISIONING = {
    "idee": {
        "description": "Story-Issue: neue Idee, noch ungeschaerft/in Verfeinerung.",
        "color": "0e8a16",
    },
    "bug": {"description": "Something isn't working", "color": "d73a4a"},
}

_SPEC_NUMBER_RE = re.compile(r"^\d{4}$")
_STATUS_LINE_RE = re.compile(r"^\*\*Status:\*\*.*$", re.MULTILINE)
_STATUS_KEYWORD_RE = re.compile(r"^\*\*Status:\*\*\s*([A-Za-z]+)", re.MULTILINE)
_CONTENT_ZONE_START_RE = re.compile(r"^## ", re.MULTILINE)
# "gh issue create" hat kein --json-Flag und gibt bei Erfolg nur die Issue-URL auf stdout aus.
_ISSUE_URL_NUMBER_RE = re.compile(r"/issues/(\d+)/?\s*$")


class BoardError(RuntimeError):
    """Ein `gh`-Aufruf ist fehlgeschlagen oder der Aufruf war nicht zulaessig."""


def _default_run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603


# -- Spec-Datei ---------------------------------------------------------------------------------


def validate_spec_number(value: str) -> str:
    """Verteidigung in der Tiefe gegen Pfad-Traversal ueber die Spec-Nummer (ADR 0017,
    Abschnitt 5) - vor jeder Pfadkonstruktion aus einer uebergebenen Nummer."""
    if not _SPEC_NUMBER_RE.match(value):
        raise BoardError(f"Ungueltige Spec-Nummer: {value!r} (erwartet genau 4 Ziffern).")
    return value


def find_spec_path(repo_root: Path, spec_number: str) -> Path:
    """Genau ein Treffer, sonst Abbruch. Bei mehreren Dateien mit derselben Nummer stillschweigend
    die erste zu waehlen wuerde beim Finalisieren die falsche Spec-Datei umschreiben, ohne dass der
    Fehler sichtbar wird (Copilot-Review-Finding auf PR #267)."""
    features_dir = repo_root / "specs" / "features"
    candidates = sorted(features_dir.glob(f"{validate_spec_number(spec_number)}-*.md"))
    if not candidates:
        raise BoardError(f"Spec {spec_number} nicht unter {features_dir} gefunden.")
    if len(candidates) > 1:
        raise BoardError(
            f"Spec-Nummer {spec_number} ist mehrdeutig - {len(candidates)} Dateien unter "
            f"{features_dir}: {', '.join(path.name for path in candidates)}. Die doppelte "
            "Nummer erst aufloesen, bevor eine dieser Dateien geschrieben wird."
        )
    return candidates[0]


def _split_header(text: str) -> tuple[str, str]:
    content_match = _CONTENT_ZONE_START_RE.search(text)
    if content_match is None:
        raise BoardError("Spec-Datei hat keine Inhalts-Zone (erste '## '-Ueberschrift).")
    return text[: content_match.start()], text[content_match.start() :]


def read_spec_status(text: str) -> str:
    """Nur das fuehrende Schluesselwort der Status-Zeile (Freitext danach wird ignoriert, z.B.
    'Implemented ([PR #1](url))')."""
    header, _ = _split_header(text)
    match = _STATUS_KEYWORD_RE.search(header)
    if match is None:
        raise BoardError("Spec-Datei hat kein '**Status:**'-Metadaten-Feld im Header.")
    return match.group(1)


def set_status_line(text: str, new_status: str) -> str:
    """Ersetzt ausschliesslich die '**Status:**'-Zeile im Header - ein gleichlautendes Vorkommen
    in der Inhalts-Zone (z.B. ein zitierter Metadaten-Block) bleibt unangetastet."""
    header, rest = _split_header(text)
    if _STATUS_LINE_RE.search(header) is None:
        raise BoardError("Spec-Datei hat kein '**Status:**'-Metadaten-Feld im Header.")
    new_header = _STATUS_LINE_RE.sub(lambda _m: f"**Status:** {new_status}", header, count=1)
    return new_header + rest


# -- gh-Zugriff ---------------------------------------------------------------------------------


class GhBoard:
    """Alle `gh`-Aufrufe des Workflows an einer Stelle. `run` ist injizierbar (Tests)."""

    def __init__(
        self,
        *,
        owner: str = DEFAULT_OWNER,
        project_title: str = DEFAULT_PROJECT_TITLE,
        run: RunFunc = _default_run,
    ) -> None:
        self._owner = owner
        self._project_title = project_title
        self._run = run
        self._project: dict[str, Any] | None = None
        self._status_field: dict[str, Any] | None = None
        self._priority_field: dict[str, Any] | None = None
        self._items: list[dict[str, Any]] | None = None

    # -- Primitive ------------------------------------------------------------------------

    def _run_text(self, args: list[str]) -> str:
        result = self._run(args)
        if result.returncode != 0:
            raise BoardError(
                f"gh-Aufruf fehlgeschlagen ({' '.join(args)}): {(result.stderr or '').strip()}"
            )
        return result.stdout

    def _run_json(self, args: list[str]) -> Any:
        stdout = self._run_text(args)
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise BoardError(
                f"gh-Ausgabe fuer '{' '.join(args)}' war kein gueltiges JSON: {exc}"
            ) from exc

    def _with_body_file(self, body: str, build_args: Callable[[str], list[str]]) -> str:
        """Bodies gehen nie ueber die Kommandozeile (ADR 0017, Abschnitt 5)."""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(body)
            body_path = handle.name
        try:
            return self._run_text(build_args(body_path))
        finally:
            Path(body_path).unlink(missing_ok=True)

    # -- Projekt/Feld/Item ----------------------------------------------------------------

    def check_auth_scope(self) -> None:
        result = self._run(["gh", "auth", "status"])
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            raise BoardError(f"'gh auth status' fehlgeschlagen: {output.strip()}")
        if "project" not in output:
            raise BoardError(
                "Der lokalen gh-Session fehlt der Scope 'project' fuer GitHub Projects (V2). "
                "Bitte einmalig 'gh auth refresh -s project' ausfuehren."
            )

    def project(self) -> dict[str, Any]:
        """Loest das bestehende Board ueber seinen Titel auf. Es wird bewusst KEIN Projekt
        angelegt (ADR 0043, Abschnitt 4) - ein versehentlich erzeugtes zweites Board waere
        deutlich schaedlicher als ein klarer Fehler."""
        if self._project is None:
            data = self._run_json(
                ["gh", "project", "list", "--owner", self._owner, "--format", "json"]
            )
            for project in data.get("projects", []):
                if project.get("title") == self._project_title:
                    self._project = project
                    break
            else:
                raise BoardError(
                    f"Kein GitHub Project mit dem Titel {self._project_title!r} fuer Owner "
                    f"{self._owner!r} gefunden."
                )
        return self._project

    def _resolve_field(self, field_name: str) -> dict[str, Any]:
        """Loest ein Board-Feld samt Options-IDs ueber `gh project field-list` auf. Legt es
        bewusst NICHT an - eine geaenderte Optionsliste ist seit ADR 0030, Abschnitt 3, ein
        einmaliger manueller Schritt (fuer die Prioritaet ebenso, ADR 0044 Abschnitt 3)."""
        project = self.project()
        data = self._run_json(
            [
                "gh",
                "project",
                "field-list",
                str(project["number"]),
                "--owner",
                self._owner,
                "--format",
                "json",
            ]
        )
        for field in data.get("fields", []):
            if field.get("name") == field_name:
                return field
        raise BoardError(f"Das Board {self._project_title!r} hat kein Feld {field_name!r}.")

    def status_field(self) -> dict[str, Any]:
        if self._status_field is None:
            self._status_field = self._resolve_field(STATUS_FIELD_NAME)
        return self._status_field

    def priority_field(self) -> dict[str, Any]:
        if self._priority_field is None:
            self._priority_field = self._resolve_field(PRIORITY_FIELD_NAME)
        return self._priority_field

    def _option_id(self, status: str) -> str:
        return self._option_id_for(self.status_field(), STATUS_FIELD_NAME, status)

    def _option_id_for(self, field: dict[str, Any], field_name: str, value: str) -> str:
        options = {o["name"]: o["id"] for o in field.get("options", [])}
        option_id = options.get(value)
        if option_id is None:
            raise BoardError(
                f"Das Board-Feld {field_name!r} hat keine Option fuer {value!r} "
                f"(vorhanden: {sorted(options)}). Die Feld-Optionen wurden vermutlich manuell "
                "veraendert."
            )
        return option_id

    def _item_list(self) -> list[dict[str, Any]]:
        # "--limit 100" ist nicht paginiert (aktuell ~70 Items) - dieselbe bereits in ADR 0017
        # dokumentierte und akzeptierte Grenze wie beim abgeloesten Tool.
        if self._items is None:
            project = self.project()
            data = self._run_json(
                [
                    "gh",
                    "project",
                    "item-list",
                    str(project["number"]),
                    "--owner",
                    self._owner,
                    "--format",
                    "json",
                    "--limit",
                    "100",
                ]
            )
            self._items = list(data.get("items", []))
        return self._items

    def find_item(self, issue_number: int) -> dict[str, Any]:
        """Loest das Board-Item ueber die Issue-Nummer auf - der Ersatz fuer die frueher in
        specs/.github-sync-state.json zwischengespeicherte item_id (ADR 0043, Abschnitt 2)."""
        for item in self._item_list():
            content = item.get("content") or {}
            if content.get("type") == "Issue" and content.get("number") == issue_number:
                return item
        raise BoardError(
            f"Issue #{issue_number} ist kein Item des Boards {self._project_title!r} "
            "(oder liegt jenseits der ersten 100 Items)."
        )

    # -- Operationen ----------------------------------------------------------------------

    def set_status(self, issue_number: int, status: str) -> None:
        item = self.find_item(issue_number)
        self._run_text(
            [
                "gh",
                "project",
                "item-edit",
                "--id",
                str(item["id"]),
                "--project-id",
                str(self.project()["id"]),
                "--field-id",
                str(self.status_field()["id"]),
                "--single-select-option-id",
                self._option_id(status),
            ]
        )

    def get_status(self, issue_number: int) -> str | None:
        # "gh project item-list" liefert die Feldwerte als Klartext unter dem klein
        # geschriebenen Feldnamen (z.B. {"status": "Ready"}), nicht unter der Options-Id.
        value = self.find_item(issue_number).get(STATUS_FIELD_NAME.lower())
        return str(value) if value not in (None, "") else None

    def set_priority(self, issue_number: int, priority: str) -> None:
        """Unbedingtes Schreiben, analog `set_status`. Der first-write-wins-Vertrag lebt in
        `set_priority_if_unset`, nicht hier - diese Methode schreibt immer."""
        item = self.find_item(issue_number)
        self._run_text(
            [
                "gh",
                "project",
                "item-edit",
                "--id",
                str(item["id"]),
                "--project-id",
                str(self.project()["id"]),
                "--field-id",
                str(self.priority_field()["id"]),
                "--single-select-option-id",
                self._option_id_for(self.priority_field(), PRIORITY_FIELD_NAME, priority),
            ]
        )

    def get_priority(self, issue_number: int) -> str | None:
        value = self.find_item(issue_number).get(PRIORITY_FIELD_NAME.lower())
        return str(value) if value not in (None, "") else None

    def set_priority_if_unset(self, issue_number: int, priority: str) -> tuple[bool, str]:
        """First-write-wins-Kern (ADR 0044, Abschnitt 2): ist das Feld bereits gesetzt - gleich ob
        durch einen frueheren `refinement`-Lauf oder eine manuelle Board-Aenderung Daniels - wird
        NICHT geschrieben, und der VORHANDENE (nicht der angefragte) Wert wird zurueckgegeben."""
        existing = self.get_priority(issue_number)
        if existing is not None:
            return False, existing
        self.set_priority(issue_number, priority)
        return True, priority

    def close_issue(self, issue_number: int) -> None:
        self._run_text(["gh", "issue", "close", str(issue_number)])

    def set_issue_body(self, issue_number: int, body: str) -> None:
        self._with_body_file(
            body,
            lambda body_path: ["gh", "issue", "edit", str(issue_number), "--body-file", body_path],
        )

    def ensure_label(self, name: str) -> None:
        data = self._run_json(["gh", "label", "list", "--json", "name", "--limit", "100"])
        if name in {item["name"] for item in data}:
            return
        meta = LABEL_PROVISIONING[name]
        self._run_text(
            [
                "gh",
                "label",
                "create",
                name,
                "--description",
                meta["description"],
                "--color",
                meta["color"],
            ]
        )

    def create_issue(self, *, title: str, body: str, label: str) -> tuple[int, str]:
        stdout = self._with_body_file(
            body,
            lambda body_path: [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--label",
                label,
                "--body-file",
                body_path,
            ],
        )
        lines = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
        match = _ISSUE_URL_NUMBER_RE.search(lines[-1]) if lines else None
        if match is None:
            raise BoardError(
                "Konnte keine Issue-Nummer aus der Ausgabe von 'gh issue create' extrahieren "
                f"(erwartet eine Issue-URL, z.B. '.../issues/123'): {stdout.strip()!r}"
            )
        return int(match.group(1)), lines[-1]

    def add_item(self, issue_url: str) -> str:
        data = self._run_json(
            [
                "gh",
                "project",
                "item-add",
                str(self.project()["number"]),
                "--owner",
                self._owner,
                "--url",
                issue_url,
                "--format",
                "json",
            ]
        )
        self._items = None  # Cache invalidieren: das neue Item fehlt in einer bereits geholten
        return str(data["id"])  # Liste.

    def get_pull_request(self, pr_number: int) -> dict[str, str]:
        data = self._run_json(["gh", "pr", "view", str(pr_number), "--json", "state,url"])
        return {"state": str(data["state"]).lower(), "url": str(data.get("url", ""))}

    def closing_pull_requests(self, issue_number: int) -> list[int]:
        data = self._run_json(
            [
                "gh",
                "issue",
                "view",
                str(issue_number),
                "--json",
                "closedByPullRequestsReferences",
            ]
        )
        return [int(ref["number"]) for ref in data.get("closedByPullRequestsReferences") or []]


# -- Befehle ------------------------------------------------------------------------------------


def cmd_create_issue(board: GhBoard, *, typ: str, title: str, body: str) -> dict[str, Any]:
    label = STORY_TYPE_LABELS.get(typ)
    if label is None:
        raise BoardError(
            f"Unbekannter Typ {typ!r} (erwartet einen von {sorted(STORY_TYPE_LABELS)})."
        )
    board.ensure_label(label)
    issue_number, issue_url = board.create_issue(title=title, body=body, label=label)
    board.add_item(issue_url)
    board.set_status(issue_number, "Unrefined")
    return {"issue_number": issue_number}


def cmd_set_body(board: GhBoard, *, issue_number: int, body: str) -> dict[str, Any]:
    board.set_issue_body(issue_number, body)
    return {"issue_number": issue_number}


def cmd_set_status(board: GhBoard, *, issue_number: int, status: str) -> dict[str, Any]:
    if status not in STATUS_VALUES:
        raise BoardError(
            f"Unbekannter Status {status!r} (erwartet einen von {list(STATUS_VALUES)})."
        )
    board.set_status(issue_number, status)
    if status == "Done":
        # Ein erledigtes oder verworfenes Issue wird zusaetzlich nativ geschlossen (ADR 0037,
        # Abschnitt 6). Alle anderen Werte fassen den Issue-Zustand bewusst nicht an - ein
        # Wiedereroeffnen passiert nativ auf GitHub.
        board.close_issue(issue_number)
    return {"issue_number": issue_number, "status": status}


def cmd_show_status(board: GhBoard, *, issue_number: int) -> dict[str, Any]:
    return {"issue_number": issue_number, "status": board.get_status(issue_number)}


def cmd_finalize(
    board: GhBoard,
    *,
    repo_root: Path,
    spec_number: str,
    issue_number: int,
    pr_number: int | None,
) -> dict[str, Any]:
    """Pre-Merge-Finalisierung (Regelweg, ADR 0042) bzw. nachtraegliche Erkennung eines bereits
    gemergten PRs (Ausnahmepfad, ADR 0037 Abschnitt 5 - hier ohne --pr-number).

    Bewusste Reihenfolge: erst die Spec-Datei umschreiben, dann das Board setzen. Scheitert der
    Board-Zugriff danach, bleibt die umgeschriebene Datei als sichtbare Arbeitskopie-Aenderung
    stehen; ein erneuter Versuch braucht dann erst deren Revert (die Statuspruefung unten
    verlangt 'Accepted').
    """
    spec_path = find_spec_path(repo_root, spec_number)
    text = spec_path.read_text(encoding="utf-8")
    status = read_spec_status(text)
    if status != "Accepted":
        raise BoardError(
            f"Spec {spec_number} hat Datei-Status {status!r} - finalisiert wird nur eine Spec im "
            "Status 'Accepted'."
        )

    resolved_pr, pull_request = _resolve_pull_request(board, issue_number, pr_number)
    status_line = f"Implemented ([PR #{resolved_pr}]({pull_request['url']}))"
    spec_path.write_text(set_status_line(text, status_line), encoding="utf-8")

    board.set_status(issue_number, "Done")
    board.close_issue(issue_number)

    return {
        "spec_number": spec_number,
        "issue_number": issue_number,
        "pr_number": resolved_pr,
        "status_line": status_line,
        "status": "Done",
    }


def _resolve_pull_request(
    board: GhBoard, issue_number: int, pr_number: int | None
) -> tuple[int, dict[str, str]]:
    if pr_number is not None:
        pull_request = board.get_pull_request(pr_number)
        # "open" ist der Regelfall (kurz vor dem Merge), "merged" der nachgezogene Ausnahmefall.
        # "closed" heisst geschlossen OHNE Merge - daraus darf nie "Implemented" werden.
        if pull_request["state"] not in {"open", "merged"}:
            raise BoardError(
                f"PR #{pr_number} hat den Zustand {pull_request['state']!r} (erwartet 'open' "
                "oder 'merged') - ein ohne Merge geschlossener PR darf nicht zu 'Implemented' "
                "fuehren."
            )
        return pr_number, pull_request

    # Ohne --pr-number: den gemergten, das Issue schliessenden PR auflaesen (Ersatz fuer die
    # frueher aus der Zustandsdatei gelesene pr_number).
    candidates = board.closing_pull_requests(issue_number)
    for candidate in candidates:
        pull_request = board.get_pull_request(candidate)
        if pull_request["state"] == "merged":
            return candidate, pull_request
    raise BoardError(
        f"Zu Issue #{issue_number} ist kein gemergter, schliessender Pull Request gefunden "
        f"worden (geprueft: {candidates or 'keine Verknuepfung'}). Fuer die Finalisierung vor "
        "dem Merge die PR-Nummer mit --pr-number angeben."
    )


# -- CLI ----------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gh-board",
        description=(
            "Einzelne GitHub-Projects-(V2)-Operationen fuer den PhotoSort-Workflow. Siehe "
            ".claude/skills/github-board/SKILL.md sowie specs/features/"
            "0262-github-project-sync-tool-entfernen.md."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-issue", help="Neues Story-Issue anlegen (Unrefined).")
    create.add_argument("--type", dest="typ", required=True, choices=sorted(STORY_TYPE_LABELS))
    create.add_argument("--title", required=True)
    create.add_argument("--body-file", required=True)

    set_body = subparsers.add_parser("set-body", help="Issue-Body ueberschreiben.")
    set_body.add_argument("--issue", type=int, required=True)
    set_body.add_argument("--body-file", required=True)

    set_status = subparsers.add_parser("set-status", help="Board-Status setzen.")
    set_status.add_argument("--issue", type=int, required=True)
    set_status.add_argument("--status", required=True)

    show_status = subparsers.add_parser("show-status", help="Board-Status lesen (rein lesend).")
    show_status.add_argument("--issue", type=int, required=True)

    finalize = subparsers.add_parser(
        "finalize", help="Spec auf 'Implemented' setzen, Board 'Done', Issue schliessen."
    )
    finalize.add_argument("--spec", required=True, metavar="NNNN")
    finalize.add_argument(
        "--issue",
        type=int,
        default=None,
        help="Nur noetig fuer Altspecs, deren Nummer nicht der Issue-Nummer entspricht.",
    )
    finalize.add_argument("--pr-number", type=int, default=None)

    return parser


def _discover_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (candidate / "specs").is_dir() and (candidate / ".git").exists():
            return candidate
    raise BoardError(f"Kein Repo-Root (specs/ + .git) ausgehend von {start} gefunden.")


def _read_body_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise BoardError(f"Body-Datei {path!r} nicht lesbar: {exc}") from exc


def _dispatch(args: argparse.Namespace, board: GhBoard, repo_root: Path) -> dict[str, Any]:
    if args.command == "create-issue":
        return cmd_create_issue(
            board, typ=args.typ, title=args.title, body=_read_body_file(args.body_file)
        )
    if args.command == "set-body":
        return cmd_set_body(board, issue_number=args.issue, body=_read_body_file(args.body_file))
    if args.command == "set-status":
        return cmd_set_status(board, issue_number=args.issue, status=args.status)
    if args.command == "show-status":
        return cmd_show_status(board, issue_number=args.issue)
    if args.command == "finalize":
        spec_number = validate_spec_number(args.spec)
        return cmd_finalize(
            board,
            repo_root=repo_root,
            spec_number=spec_number,
            issue_number=args.issue if args.issue is not None else int(spec_number),
            pr_number=args.pr_number,
        )
    raise BoardError(f"Unbekannter Befehl: {args.command!r}")


def main(
    argv: Sequence[str] | None = None,
    *,
    run: RunFunc = _default_run,
    repo_root: Path | None = None,
    owner: str = DEFAULT_OWNER,
) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        root = repo_root if repo_root is not None else _discover_repo_root(Path.cwd())
        board = GhBoard(owner=owner, run=run)
        board.check_auth_scope()
        payload = _dispatch(args, board, root)
    except BoardError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
