#!/usr/bin/env python3
"""Duenner Helfer fuer die GitHub-Projects-(V2)-Operationen des PhotoSort-Workflows.

Loest `scripts/github-project-sync/` ab (Spec 0262 / ADR 0043): Es wird nichts mehr
"synchronisiert" - es gibt keine Zustandsdatei, kein Nummern-Mapping und keinen Content-Push des
Spec-Inhalts in den Issue-Body mehr. Uebrig bleiben einzelne, zustandslose Board-Operationen, die
die Skills unter `.claude/skills/` aufrufen (siehe `.claude/skills/github-board/SKILL.md`).

Die fehleranfaellige Projects-V2-Logik (Projekt-/Feld-/Options-/Item-ID-Aufloesung, Setzen eines
Single-Select-Werts) liegt bewusst nur hier und nicht verstreut in den Skill-Dateien.

Ausgabe ist immer ein einzelnes JSON-Objekt auf stdout, im Fehlerfall `{"error": "..."}` mit
Exit-Code 1 - dieselbe Aufrufkonvention wie beim abgeloesten Tool. Einzige, bewusst
dokumentierte Ausnahme ist `doctor` (ADR 0052): Es beendet sich mit Exit-Code 0, sobald ein
Bericht entsteht, weil fehlgeschlagene Pruefungen dort der Inhalt sind und nicht das Scheitern.

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
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

RunFunc = Callable[[list[str]], "subprocess.CompletedProcess[str]"]

DEFAULT_OWNER = "TheRealKoller"
DEFAULT_REPO = "photosort"
DEFAULT_PROJECT_TITLE = "PhotoSort Roadmap"

# Der Branch, aus dem heraus GitHub ein per Closing-Keyword verknuepftes Issue beim Merge
# schliesst - ein PR gegen einen Nebenbranch tut das nicht (ADR 0046, Abschnitt 3).
DEFAULT_BRANCH = "main"
# `gh pr view --json` kennt `closingIssuesReferences` erst ab dieser Version (30.04.2025).
MIN_GH_VERSION = "2.72.0"

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

# Startlimit fuer `gh project item-list`. Bewusst kein Deckel, sondern nur der erste Versuch:
# meldet `gh` mehr Items als es geliefert hat, wird mit der gemeldeten Anzahl nachgefordert
# (siehe Board._item_list). Der Wert haelt den Normalfall bei genau einem Aufruf.
ITEM_LIST_START_LIMIT = 200

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
# So meldet `gh` ein `--json`-Feld, das die installierte Version nicht kennt. Nur dieser
# Fall bekommt den Versionshinweis - der Feldname selbst taugt nicht als Merkmal, er steht
# als Teil der Argumentliste ohnehin in jeder gescheiterten Meldung.
_UNKNOWN_JSON_FIELD_RE = re.compile(r"unknown\s+JSON\s+field", re.IGNORECASE)
_CONTENT_ZONE_START_RE = re.compile(r"^## ", re.MULTILINE)
# "gh issue create" hat kein --json-Flag und gibt bei Erfolg nur die Issue-URL auf stdout aus.
_ISSUE_URL_NUMBER_RE = re.compile(r"/issues/(\d+)/?\s*$")


class BoardError(RuntimeError):
    """Ein `gh`-Aufruf ist fehlgeschlagen oder der Aufruf war nicht zulaessig."""


def _default_run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603


# -- Redaktion ----------------------------------------------------------------------------------

# Jede Zeichenkette, die aus einem fremden Werkzeug in eine weitergereichte Ausgabe gelangt,
# laeuft durch GENAU diese eine Funktion (ADR 0052, Securitykonzept): der `doctor`-Bericht ist
# dazu bestimmt, in ein Issue eines OEFFENTLICHEN Repositories zu wandern, und die angereicherte
# Fehlermeldung aus `project()` reicht der `github-board`-Skill woertlich weiter. Ein Fehlgriff
# ist an dieser Stelle nicht zurueckzunehmen (Edit-Historie, Mail-Benachrichtigungen).
#
# Tragende Schicht ist die Whitelist (nur benannte Felder werden uebernommen, nie eine ganze
# `gh`-Ausgabe); diese Funktion ist die zweite Reihe plus die Sanitisierung/Kuerzung.
REPORT_TEXT_LIMIT = 500
REDACTED = "[redigiert]"
TRUNCATION_MARKER = " [... gekuerzt]"

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")
# Die heute von GitHub ausgegebenen Tokenformen. Bewusst KEIN 40-Hex-Muster (Alt-PATs): es
# traefe jede Commit-SHA und machte den Bericht unbrauchbar - deshalb traegt die Whitelist die
# Last, nicht dieser Filter.
_TOKEN_RE = re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,}")
_URL_CREDENTIALS_RE = re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)")


def redact_for_report(text: str, *, limit: int = REPORT_TEXT_LIMIT) -> str:
    """Sanitisiert, redigiert und kuerzt einen Text, bevor er weitergereicht wird.

    Reihenfolge: erst ANSI-/Steuer-/Format-/Bidi-/Zero-Width-Zeichen entfernen (sonst koennte
    Fremdtext seine eigene Darstellung in Terminal, Markdown oder Agenten-Kontext manipulieren),
    dann tokenfoermige Zeichenketten schwaerzen, zuletzt kuerzen - so kann kein Geheimnis durch
    das Kuerzen "aufgeteilt" der Schwaerzung entgehen.
    """
    cleaned = _ANSI_ESCAPE_RE.sub("", text)
    cleaned = "".join(
        char
        for char in cleaned
        if char == "\n" or unicodedata.category(char) not in {"Cc", "Cf"}
    )
    cleaned = _TOKEN_RE.sub(REDACTED, cleaned)
    cleaned = _URL_CREDENTIALS_RE.sub(REDACTED, cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > limit:
        cleaned = cleaned[:limit] + TRUNCATION_MARKER
    return cleaned


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


# -- Diagnose: Lebenszyklus-Schritte und ihre Voraussetzungen -----------------------------------

# Die Schritte, die eine Story vom Erfassen bis zum abgeschlossenen Pull Request durchlaeuft
# (ADR 0052, Abschnitt 4). Der Bericht sagt damit nicht "Pruefung X ist rot", sondern welche
# Schritte in dieser Umgebung nicht gehen. Die drei Status-Schreibschritte stehen einzeln, weil
# das Akzeptanzkriterium der Spec fuer jeden von ihnen ein Urteil verlangt.
LIFECYCLE_STEPS = (
    "idee-erfassen",
    "issue-body-schreiben",
    "status-ready",
    "spec-anlegen",
    "status-in-progress",
    "pr-eroeffnen",
    "status-review",
    "abschluss-finalisieren",
)

# Die Schritte, die ueber das Board laufen (Status schreiben bzw. lesen). Bewusst OHNE
# `idee-erfassen`: `cmd_create_issue` legt das Issue an, bevor es das Projekt aufloest - bei
# unsichtbarem Board scheitert es erst an der Board-Aufnahme, das Issue entsteht trotzdem.
BOARD_LIFECYCLE_STEPS = (
    "status-ready",
    "status-in-progress",
    "status-review",
    "abschluss-finalisieren",
)

# Statische Zuordnung Pruefung -> blockierte Lebenszyklus-Schritte. Reiner Datenbestand; ein
# Test prueft ihre Vollstaendigkeit gegen LIFECYCLE_STEPS.
PROBE_LIFECYCLE_STEPS: dict[str, tuple[str, ...]] = {
    "gh_binary": LIFECYCLE_STEPS,
    "gh_version": ("abschluss-finalisieren",),
    "auth": LIFECYCLE_STEPS,
    # Reine Information ohne Urteil: Die Scope-Zeile sagt, was sie sagt - den Zugriff misst
    # `project_visible` tatsaechlich.
    "scope_hint": (),
    "repo_access": ("idee-erfassen", "issue-body-schreiben", "pr-eroeffnen"),
    "issue_read": ("issue-body-schreiben", "abschluss-finalisieren"),
    "project_visible": BOARD_LIFECYCLE_STEPS,
    "fields": BOARD_LIFECYCLE_STEPS,
    "items": BOARD_LIFECYCLE_STEPS,
}

# Nur diese drei Werte bedeuten Schreibrecht am Repository. `TRIAGE` sieht danach aus und ist
# keins (Issues verwalten, aber kein Push, kein Issue-Body schreiben).
REPO_WRITE_PERMISSIONS = ("ADMIN", "MAINTAIN", "WRITE")

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def parse_gh_version(output: str) -> tuple[int, int, int] | None:
    """Liest die Version aus der ersten nicht-leeren Zeile von `gh --version`.

    Numerisch, nicht lexikografisch: `2.9.0` ist aelter als `2.72.0`, ein String-Vergleich sagt
    das Gegenteil. Ein Distributions-Suffix (`2.72.0-1ubuntu0.1`) stoert nicht, eine gar nicht
    auswertbare Ausgabe ergibt `None` - ein Befund, kein Absturz.
    """
    line = next((line for line in output.splitlines() if line.strip()), "")
    match = _VERSION_RE.search(line)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


# -- Auth-Auskunft (Whitelist) ------------------------------------------------------------------

# Die von `gh` gemeldete Token-Quelle. Uebernommen wird ausschliesslich diese geschlossene Menge
# von Literalen - jede andere Angabe wird zu "unbekannt", damit kein Fremdtext in eine
# weitergereichte Meldung oder in den `doctor`-Bericht geraet (Securitykonzept zu ADR 0052).
AUTH_SOURCES = ("keyring", "oauth_token", "GH_TOKEN", "GITHUB_TOKEN")
UNKNOWN_AUTH_SOURCE = "unbekannt"

_AUTH_ACCOUNT_RE = re.compile(r"account\s+(\S+)\s+\(([^)]+)\)")
_AUTH_ACTIVE_RE = re.compile(r"Active account:\s*true", re.IGNORECASE)
_AUTH_SCOPES_RE = re.compile(r"Token scopes:\s*(.*)$")
_QUOTED_SCOPE_RE = re.compile(r"'([^']*)'")


def _parse_scopes(value: str) -> list[str]:
    text = value.strip()
    if not text or text.lower() == "none":
        return []
    quoted = _QUOTED_SCOPE_RE.findall(text)
    if quoted:
        return quoted
    return [part.strip() for part in text.split(",") if part.strip()]


def parse_auth_status(output: str) -> dict[str, Any]:
    """Extrahiert `account`, `source` und `scopes` aus der Ausgabe von `gh auth status`.

    Massgeblich ist der Block mit `Active account: true` (Securitykonzept zu ADR 0052): `gh`
    meldet pro Host MEHRERE Kontobloecke, sobald neben einem Umgebungstoken noch ein
    gespeichertes Konto existiert. Wer die erste beste Scope-Zeile nimmt, meldet die Rechte
    eines Kontos, mit dem gar nicht gearbeitet wird.

    `scopes` unterscheidet vier Zustaende: Liste mit `project`, Liste ohne `project`, leere
    Liste (`Token scopes: none`) und `None` (gar keine Scope-Zeile, typisch fuer
    Token-Authentifizierung). Nur die zweite Form rechtfertigt einen Refresh-Hinweis.
    """
    blocks: list[dict[str, Any]] = []
    for line in output.splitlines():
        account_match = _AUTH_ACCOUNT_RE.search(line)
        if account_match is not None:
            source = account_match.group(2)
            blocks.append(
                {
                    "account": account_match.group(1),
                    "source": source if source in AUTH_SOURCES else UNKNOWN_AUTH_SOURCE,
                    "active": False,
                    "scopes": None,
                }
            )
            continue
        if not blocks:
            continue
        block = blocks[-1]
        if _AUTH_ACTIVE_RE.search(line):
            block["active"] = True
        scopes_match = _AUTH_SCOPES_RE.search(line)
        if scopes_match is not None:
            block["scopes"] = _parse_scopes(scopes_match.group(1))

    active = next((block for block in blocks if block["active"]), None)
    if active is None and len(blocks) == 1:
        # Aeltere `gh`-Versionen melden keine 'Active account'-Zeile. Bei genau einem Block gibt
        # es nichts zu unterscheiden; bei mehreren wird bewusst nicht geraten.
        active = blocks[0]
    if active is None:
        return {"account": None, "source": None, "scopes": None}
    return {"account": active["account"], "source": active["source"], "scopes": active["scopes"]}


# -- gh-Zugriff ---------------------------------------------------------------------------------


def _unexpected_shape(call: str, erwartung: str) -> BoardError:
    return BoardError(
        f"Die Antwort von '{call}' hatte eine unerwartete Form ({erwartung}). Sie war gueltiges "
        "JSON, aber nicht die erwartete Struktur - vermutlich hat sich das Ausgabeformat von "
        "`gh` geaendert."
    )


def _json_objects(data: Any, *, key: str | None, call: str) -> list[dict[str, Any]]:
    """Die EINE Stelle, an der die Strukturerwartung an eine `--json`/`--format json`-Antwort von
    `gh` steht: entweder direkt eine Liste von Objekten (`key=None`) oder ein Objekt, unter dessen
    Schluessel eine Liste von Objekten liegt.

    Alles andere endet hier als sprechender `BoardError` statt weiter unten als `AttributeError`,
    `TypeError` oder `KeyError`. `gh` ist ein fremdes Werkzeug mit eigenem Ausgabeformat; aus
    gueltigem JSON auf die erwartete Struktur zu schliessen, ist dieselbe Fehlerklasse wie aus
    Fremdtext auf einen Zustand zu schliessen (ADR 0048). Der heimtueckischste Fall ist ein
    String, wo eine Liste erwartet wird: Eine Schleife darueber laeuft klaglos - ueber die
    einzelnen Zeichen.

    Gebuendelt statt je Aufloesung wiederholt, damit die naechste hinzukommende sie nicht erneut
    vergisst (Copilot-Finding auf dem Umsetzungs-PR zu Spec 0309: `project()` war defensiv,
    `_resolve_field()`/`_fetch_items()` waren es nicht).
    """
    entries: Any = data
    if key is not None:
        if not isinstance(data, dict):
            raise _unexpected_shape(call, f"erwartet wurde ein JSON-Objekt mit {key!r}")
        entries = data.get(key, [])
    if not isinstance(entries, list):
        erwartung = "erwartet wurde eine Liste"
        raise _unexpected_shape(call, erwartung if key is None else f"{erwartung} unter {key!r}")
    if any(not isinstance(entry, dict) for entry in entries):
        raise _unexpected_shape(call, "die Liste enthaelt Eintraege, die keine JSON-Objekte sind")
    return entries


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

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def project_title(self) -> str:
        return self._project_title

    # -- Primitive ------------------------------------------------------------------------

    def _run_text(self, args: list[str]) -> str:
        try:
            result = self._run(args)
        except FileNotFoundError as exc:
            # Ein fehlendes Binary laesst `subprocess.run` mit FileNotFoundError scheitern, nicht
            # mit Returncode != 0 - ungefangen faellt daraus ein Traceback statt der ueblichen
            # `{"error": ...}`-Ausgabe heraus.
            raise BoardError(f"gh-Aufruf nicht moeglich ({' '.join(args)}): {exc}") from exc
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

    def probe(self, args: list[str]) -> tuple[bool, str, str]:
        """Fuehrt einen Aufruf aus, OHNE bei einem Fehlschlag abzubrechen - er ist hier der
        Befund, nicht das Scheitern (ADR 0052). Ein fehlendes Binary (`FileNotFoundError`, den
        sonst niemand faengt) wird ebenso zum Befund statt zum Traceback."""
        try:
            result = self._run(args)
        except FileNotFoundError as exc:
            return False, "", str(exc)
        return result.returncode == 0, result.stdout or "", result.stderr or ""

    def auth_info(self) -> dict[str, Any]:
        """Die vier Whitelist-Felder aus `gh auth status` (ADR 0052): `authenticated`,
        `account`, `source`, `scopes` - im Erfolgsfall nie die Ausgabe selbst.

        Wird ausschliesslich im Fehlerfall (zur Deutung) und von `doctor` aufgerufen, nie vor
        einem Zugriff: Ein Urteil vor dem Versuch ist genau das, was ADR 0052 abschafft.

        `error_output` traegt AUSSCHLIESSLICH die Ausgabe eines FEHLGESCHLAGENEN Aufrufs und ist
        sonst leer. Der Unterschied ist der Kern von Muss-Kriterium 4 des Securitykonzepts: Im
        Erfolgsfall ist die Ausgabe ein vollstaendiger Status-Dump, den die Whitelist ersetzt und
        der nie verbatim weitergereicht wird. Im Fehlerfall gibt es keine parsebaren Felder, und
        der Text ist eine Fehlermeldung - ohne ihn nennte ein Bericht, der daraufhin JEDEN
        Lebenszyklus-Schritt blockiert, keinerlei Ursache. Er laeuft beim Einbau in den Bericht
        durch dieselbe Redaktion wie jede andere uebernommene Zeichenkette.
        """
        ok, stdout, stderr = self.probe(["gh", "auth", "status"])
        # Je nach `gh`-Version steht die Ausgabe (Status wie Fehlschlag) auf stdout oder stderr.
        output = f"{stdout}\n{stderr}".strip()
        if not ok:
            return {
                "authenticated": False,
                "account": None,
                "source": None,
                "scopes": None,
                "error_output": output,
            }
        return {"authenticated": True, "error_output": "", **parse_auth_status(output)}

    def _explain_project_failure(self, error: BoardError) -> BoardError:
        """Deutet einen BEREITS gescheiterten Zugriff (ADR 0052, Abschnitt 3). Die Textauswertung
        ist damit nicht abgeschafft, sondern entmachtet: Sie kann keinen Aufruf mehr verhindern,
        nur einen gescheiterten erklaeren. Die urspruengliche `gh`-Meldung wird nie ersetzt,
        immer nur ergaenzt - und laeuft dabei durch die Redaktion, weil die Skills sie woertlich
        weiterreichen (Securitykonzept, Muss-Kriterium 2).
        """
        message = redact_for_report(str(error))
        auth = self.auth_info()
        if not auth["authenticated"]:
            # Scheitert die Deutung selbst, bleibt es bei dem, was `gh` gesagt hat.
            return BoardError(message)
        quelle = auth["source"] or UNKNOWN_AUTH_SOURCE
        scopes = auth["scopes"]
        if scopes is not None and "project" not in scopes:
            return BoardError(
                f"{message} Hinweis: Der aktiven gh-Anmeldung ({quelle}) fehlt der Scope "
                "'project' fuer GitHub Projects (V2) - einmalig 'gh auth refresh -s project' "
                "ausfuehren."
            )
        return BoardError(f"{message} (Auth-Quelle der aktiven gh-Anmeldung: {quelle}.)")

    def project(self) -> dict[str, Any]:
        """Loest das bestehende Board ueber seinen Titel auf. Es wird bewusst KEIN Projekt
        angelegt (ADR 0043, Abschnitt 4) - ein versehentlich erzeugtes zweites Board waere
        deutlich schaedlicher als ein klarer Fehler.

        Dieser Aufruf IST die Zugriffsprobe (ADR 0052, Abschnitt 2): Gedeutet wird ausschliesslich
        der fehlgeschlagene Aufruf, nicht der erfolgreiche ohne Titeltreffer - ein umbenanntes
        Board ist kein Berechtigungsproblem und darf keinen Scope-Hinweis nach sich ziehen.
        """
        if self._project is None:
            args = ["gh", "project", "list", "--owner", self._owner, "--format", "json"]
            try:
                data = self._run_json(args)
            except BoardError as exc:
                raise self._explain_project_failure(exc) from exc
            for project in _json_objects(data, key="projects", call=" ".join(args)):
                if project.get("title") == self._project_title:
                    self._project = project
                    break
            else:
                raise BoardError(
                    f"Kein GitHub Project mit dem Titel {self._project_title!r} fuer Owner "
                    f"{self._owner!r} gefunden."
                )
        return self._project

    def _project_value(self, key: str) -> str:
        """Ein Pflichtfeld des aufgeloesten Projekts, das in eine Folge-Argumentliste
        interpoliert wird. Fehlt es, ist das ein `BoardError` statt eines `KeyError`."""
        value = self.project().get(key)
        if value is None or value == "":
            raise BoardError(
                f"Die Antwort von 'gh project list' fuer das Board {self._project_title!r} "
                f"traegt kein Feld {key!r} - die Ausgabeform von `gh` hat sich vermutlich "
                "geaendert."
            )
        return str(value)

    def _resolve_field(self, field_name: str) -> dict[str, Any]:
        """Loest ein Board-Feld samt Options-IDs ueber `gh project field-list` auf. Legt es
        bewusst NICHT an - eine geaenderte Optionsliste ist seit ADR 0030, Abschnitt 3, ein
        einmaliger manueller Schritt (fuer die Prioritaet ebenso, ADR 0044 Abschnitt 3)."""
        args = [
            "gh",
            "project",
            "field-list",
            self._project_value("number"),
            "--owner",
            self._owner,
            "--format",
            "json",
        ]
        data = self._run_json(args)
        for field in _json_objects(data, key="fields", call=" ".join(args)):
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
        raw_options = field.get("options")
        options = {
            option["name"]: option["id"]
            for option in (raw_options if isinstance(raw_options, list) else [])
            if isinstance(option, dict) and "name" in option and "id" in option
        }
        option_id = options.get(value)
        if option_id is None:
            raise BoardError(
                f"Das Board-Feld {field_name!r} hat keine Option fuer {value!r} "
                f"(vorhanden: {sorted(options)}). Die Feld-Optionen wurden vermutlich manuell "
                "veraendert."
            )
        return option_id

    def _fetch_items(self, limit: int) -> tuple[list[dict[str, Any]], int]:
        """Holt bis zu `limit` Board-Items und gibt sie zusammen mit der von `gh` gemeldeten
        Gesamtzahl zurueck. `totalCount` zaehlt immer das ganze Board, unabhaengig davon, wie
        viele Items `--limit` durchgelassen hat - daran erkennen wir ein Abschneiden."""
        args = [
            "gh",
            "project",
            "item-list",
            self._project_value("number"),
            "--owner",
            self._owner,
            "--format",
            "json",
            "--limit",
            str(limit),
        ]
        data = self._run_json(args)
        items = _json_objects(data, key="items", call=" ".join(args))
        # `data` ist nach `_json_objects` nachweislich ein Objekt.
        total = data.get("totalCount")
        return list(items), total if isinstance(total, int) else len(items)

    def _item_list(self) -> list[dict[str, Any]]:
        """Laedt die Board-Items vollstaendig - erst mit einem Startlimit, und falls `gh`
        daraufhin mehr Items meldet als es geliefert hat, ein zweites Mal mit genau dieser
        gemeldeten Anzahl. Ein festes Limit hatte hier zuvor still abgeschnitten: sobald das
        Board ueber die Grenze wuchs, waren die zuletzt angelegten Issues fuer jede
        Schreiboperation unsichtbar und wurden als "kein Item des Boards" gemeldet."""
        if self._items is None:
            items, total = self._fetch_items(ITEM_LIST_START_LIMIT)
            if total > len(items):
                items, total = self._fetch_items(total)
            if total > len(items):
                raise BoardError(
                    f"Das Board {self._project_title!r} meldet {total} Items, "
                    f"'gh project item-list' liefert aber nur {len(items)}. Die Item-Liste ist "
                    "unvollstaendig - eine Suche darin wuerde vorhandene Issues faelschlich als "
                    "nicht im Board melden."
                )
            self._items = items
        return self._items

    def find_item(self, issue_number: int) -> dict[str, Any]:
        """Loest das Board-Item ueber die Issue-Nummer auf - der Ersatz fuer die frueher in
        specs/.github-sync-state.json zwischengespeicherte item_id (ADR 0043, Abschnitt 2)."""
        for item in self._item_list():
            content = item.get("content")
            if not isinstance(content, dict):
                continue
            if content.get("type") == "Issue" and content.get("number") == issue_number:
                return item
        raise BoardError(
            f"Issue #{issue_number} ist kein Item des Boards {self._project_title!r}."
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
                self._project_value("id"),
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
                self._project_value("id"),
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

    def issue_state(self, issue_number: int) -> str:
        """Rein lesend, ausschliesslich `--json state`: nie Titel, Body, Labels oder Kommentare
        (ADR 0046, Abschnitt 3 - verarbeitet werden nur strukturierte, von GitHub selbst erzeugte
        Metadaten, kein von Dritten befuellbarer Freitext). `gh` liefert den GraphQL-Enum in
        Grossschreibung; normalisiert wird wie in `get_pull_request()`."""
        data = self._run_json(["gh", "issue", "view", str(issue_number), "--json", "state"])
        state = data.get("state") if isinstance(data, dict) else None
        if not isinstance(state, str) or not state.strip():
            raise BoardError(
                f"'gh issue view {issue_number} --json state' hat keinen brauchbaren Zustand "
                f"geliefert: {data!r}."
            )
        return state.strip().lower()

    def close_issue(self, issue_number: int) -> None:
        """Zielzustand ist 'Issue geschlossen', nicht 'dieser Aufruf hat es geschlossen': Der
        Board-Workflow 'Auto-close issue' schliesst das Issue schon beim Setzen der Spalte auf
        'Done' (ADR 0046, Abschnitt 5) und ist dabei schneller als dieser Aufruf; ebenso ein
        Closing-Keyword beim Merge oder ein Schliessen von Hand. Ein Fehlschlag wird deshalb
        gegen den tatsaechlichen Zustand geprueft statt gegen den Fehlertext von `gh` - der ist
        undokumentiert, aenderbar und nicht trennscharf (ADR 0048, Abschnitt 2).

        Erfolg gilt nur bei positiver Gleichheit auf 'closed': jeder andere Wert - 'open', ein
        kuenftiger Enum-Wert, ein unbrauchbares Feld - fuehrt auf den Fehlerpfad. Die Pruefung
        laeuft bewusst NACH dem Fehlschlag: eine Vorabpruefung kostete in jedem 'Done'-Pfad
        einen zusaetzlichen Aufruf und beseitigte das Rennen mit der asynchronen
        Board-Automation trotzdem nicht."""
        try:
            self._run_text(["gh", "issue", "close", str(issue_number)])
        except BoardError as close_error:
            try:
                already_closed = self.issue_state(issue_number) == "closed"
            except BoardError as probe_error:
                # Ist die Pruefung selbst nicht moeglich (Issue existiert nicht, fehlende
                # Berechtigung, Dienst nicht erreichbar), bleibt der urspruengliche Fehlschlag
                # die gemeldete Ursache - er ist der aussagekraeftigere.
                raise close_error from probe_error
            if not already_closed:
                raise

    def set_issue_body(self, issue_number: int, body: str) -> None:
        self._with_body_file(
            body,
            lambda body_path: ["gh", "issue", "edit", str(issue_number), "--body-file", body_path],
        )

    def ensure_label(self, name: str) -> None:
        args = ["gh", "label", "list", "--json", "name", "--limit", "100"]
        data = self._run_json(args)
        vorhanden = {
            label["name"] for label in _json_objects(data, key=None, call=" ".join(args))
            if "name" in label
        }
        if name in vorhanden:
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
                self._project_value("number"),
                "--owner",
                self._owner,
                "--url",
                issue_url,
                "--format",
                "json",
            ]
        )
        # Cache invalidieren: das neue Item fehlt in einer bereits geholten Liste.
        self._items = None
        item_id = data.get("id") if isinstance(data, dict) else None
        if not item_id:
            raise BoardError(
                "Die Antwort von 'gh project item-add' traegt keine Item-Id: "
                f"{str(data)[:200]!r}."
            )
        return str(item_id)

    def get_pull_request(self, pr_number: int) -> dict[str, Any]:
        """Der PR-**Body** wird bewusst nicht angefragt (ADR 0046, Abschnitt 3): Geprueft wird
        GitHubs eigenes Parse-Ergebnis der Closing-Keywords, nicht ein von aussen befuellbarer
        Freitext. `closingIssuesReferences` setzt `gh` >= 2.72.0 voraus."""
        try:
            data = self._run_json(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "--json",
                    "state,url,baseRefName,closingIssuesReferences",
                ]
            )
        except BoardError as exc:
            # Nur der Fall, den der Hinweis erklaert, bekommt ihn auch: ein abgelaufenes Token,
            # ein Netzwerkfehler oder ein nicht gefundener PR wuerde sonst in Richtung eines
            # Werkzeug-Updates gelenkt, das gar nichts behebt.
            if not _UNKNOWN_JSON_FIELD_RE.search(str(exc)):
                raise
            raise BoardError(
                f"{exc} (Hinweis: 'closingIssuesReferences' kennt `gh pr view --json` erst ab "
                f"gh {MIN_GH_VERSION} - ein unbekanntes JSON-Feld ist kein Beleg dafuer, dass "
                "die Verknuepfung zum Issue fehlt.)"
            ) from exc
        return {
            "state": str(data["state"]).lower(),
            "url": str(data.get("url", "")),
            "baseRefName": str(data.get("baseRefName", "")),
            "closingIssuesReferences": list(data.get("closingIssuesReferences") or []),
        }

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


def cmd_set_priority(board: GhBoard, *, issue_number: int, priority: str) -> dict[str, Any]:
    """First-write-wins (ADR 0044) - Gegenstueck zu `cmd_set_status`, das unbedingt ueberschreibt.
    Die Validierung laeuft bewusst vor jedem Board-Zugriff (auch vor dem lesenden)."""
    if priority not in PRIORITY_VALUES:
        raise BoardError(
            f"Unbekannte Prioritaet {priority!r} (erwartet einen von {list(PRIORITY_VALUES)})."
        )
    changed, resolved_priority = board.set_priority_if_unset(issue_number, priority)
    return {"issue_number": issue_number, "priority": resolved_priority, "changed": changed}


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
    stehen; ein erneuter Versuch laeuft trotzdem durch, weil die bereits geschriebene Zielzeile
    als erreichter Zustand gilt (ADR 0048, Abschnitt 3) - zurueckgenommen werden muss nichts.
    """
    spec_path = find_spec_path(repo_root, spec_number)
    text = spec_path.read_text(encoding="utf-8")
    status = read_spec_status(text)
    # 'Implemented' darf die Entscheidung bis nach der PR-Aufloesung verschieben (ohne
    # aufgeloesten PR ist die Zielzeile nicht bildbar); jeder andere Status bricht weiterhin ab,
    # BEVOR ein GitHub-Zugriff stattfindet.
    if status not in {"Accepted", "Implemented"}:
        raise BoardError(
            f"Spec {spec_number} hat Datei-Status {status!r} - finalisiert wird nur eine Spec im "
            "Status 'Accepted' oder eine, die bereits exakt die Zielzeile dieses Aufrufs traegt."
        )

    resolved_pr, pull_request = _resolve_pull_request(board, issue_number, pr_number)
    status_line = f"Implemented ([PR #{resolved_pr}]({pull_request['url']}))"
    if status == "Implemented":
        _require_identical_status_line(text, status_line, spec_number=spec_number)
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


def _require_identical_status_line(text: str, status_line: str, *, spec_number: str) -> None:
    """Eng gefasste Zielzustands-Regel fuer das Datei-Status-Gate (ADR 0048, Abschnitt 3): Nur
    exakt die Zeile, die dieser Lauf schreiben wuerde - gleiche PR-Nummer UND gleiche URL -, gilt
    als bereits erreichter Zustand. Ein 'Implemented' mit einem anderen PR ist kein erreichter
    Zustand, sondern ein Hinweis auf die falsche Spec- oder PR-Nummer.

    Verglichen wird ausschliesslich in der Header-Zone (dieselbe Trennung wie beim Schreiben in
    `set_status_line()`): ein in der Inhalts-Zone zitiertes '**Status:**' darf die Gleichheit
    nicht erfuellen, waehrend der Header auf etwas anderem steht.
    """
    header, _ = _split_header(text)
    match = _STATUS_LINE_RE.search(header)
    if match is None:
        raise BoardError("Spec-Datei hat kein '**Status:**'-Metadaten-Feld im Header.")
    vorhanden = match.group(0)
    ziel = f"**Status:** {status_line}"
    if vorhanden != ziel:
        raise BoardError(
            f"Spec {spec_number} steht bereits auf {vorhanden!r}, dieser Aufruf wuerde {ziel!r} "
            "schreiben - finalisiert wird nur eine Spec im Status 'Accepted' oder eine, die "
            "bereits exakt diese Zielzeile traegt. Eine abweichende 'Implemented'-Zeile deutet "
            "auf die falsche Spec- oder PR-Nummer hin."
        )


def _closing_issue_matches(reference: dict[str, Any], issue_number: int) -> bool:
    """Repo-qualifizierter Vergleich (ADR 0046, Abschnitt 3): GitHub kennt repo-uebergreifende
    Closing-Referenzen, `number` allein ist also nicht eindeutig. Verglichen wird das Tripel
    Owner/Repo/Nummer."""
    repository = reference.get("repository") or {}
    owner = (repository.get("owner") or {}).get("login")
    return (
        reference.get("number") == issue_number
        and repository.get("name") == DEFAULT_REPO
        and owner == DEFAULT_OWNER
    )


def _describe_closing_references(references: list[dict[str, Any]]) -> str:
    if not references:
        return "keine"
    parts = []
    for reference in references:
        repository = reference.get("repository") or {}
        owner = (repository.get("owner") or {}).get("login", "?")
        parts.append(f"{owner}/{repository.get('name', '?')}#{reference.get('number', '?')}")
    return ", ".join(parts)


def _require_linked_issue(
    pull_request: dict[str, Any], *, pr_number: int, issue_number: int
) -> None:
    """Prueft GitHubs eigenes Parse-Ergebnis der Closing-Keywords, nicht den PR-Body (ADR 0046,
    Abschnitt 3). Zugesichert werden soll genau eine Eigenschaft: 'GitHub schliesst dieses Issue
    beim Merge'. Ein manuell ueber die Development-Seitenleiste verknuepftes Issue erfuellt sie
    ebenso und wird bewusst mit akzeptiert (Abschnitt 3a).

    Laeuft vor dem Umschreiben der Spec-Datei und vor jedem Board-Zugriff: Der Aufruf ist nach
    einem `gh pr edit --body-file` folgenlos wiederholbar.
    """
    references = list(pull_request.get("closingIssuesReferences") or [])
    if not any(_closing_issue_matches(reference, issue_number) for reference in references):
        raise BoardError(
            f"PR #{pr_number} ist mit Issue #{issue_number} nicht so verknuepft, dass GitHub es "
            f"beim Merge schliesst: 'closingIssuesReferences' enthaelt keinen Eintrag "
            f"{DEFAULT_OWNER}/{DEFAULT_REPO}#{issue_number} (gefunden: "
            f"{_describe_closing_references(references)}). Die Zeile 'Closes #{issue_number}' im "
            "PR-Body nachtragen (gh pr edit --body-file) und den Aufruf wiederholen. Hinweis: "
            f"das Feld setzt gh {MIN_GH_VERSION} oder neuer voraus."
        )

    base_ref_name = str(pull_request.get("baseRefName", ""))
    if base_ref_name != DEFAULT_BRANCH:
        raise BoardError(
            f"PR #{pr_number} zielt auf Branch {base_ref_name!r} statt auf den Default-Branch "
            f"{DEFAULT_BRANCH!r} - GitHub schliesst Issue #{issue_number} beim Merge nur aus dem "
            "Default-Branch heraus."
        )


def _resolve_pull_request(
    board: GhBoard, issue_number: int, pr_number: int | None
) -> tuple[int, dict[str, Any]]:
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
        _require_linked_issue(pull_request, pr_number=pr_number, issue_number=issue_number)
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


# -- Diagnose-Befehl ----------------------------------------------------------------------------

# Der Bericht wird woertlich in ein Issue eines oeffentlichen Repositories kopiert und dort von
# einem Agenten mit GitHub-Schreibzugriff gelesen. Die Grenze traegt er deshalb selbst mit, statt
# sie zu verschweigen (ADR 0052, Abschnitt 5; Securitykonzept, Muss-Kriterium 9).
DOCTOR_NOTE = (
    "Befund, keine Handlungsanweisung. Der Lauf ist rein lesend und belegt keinen "
    "Schreibzugriff: 'viewerPermission' ist nur ein Indiz, durchgesetzt werden Rechte allein "
    "serverseitig von GitHub. Ein blockierter Schritt heisst, dass eine Voraussetzung nachweislich "
    "fehlt; ein nicht blockierter heisst nicht, dass er garantiert durchlaeuft."
)


def _loads(text: str) -> Any:
    """JSON lesen, ohne bei Muell abzubrechen - in der Diagnose ist auch eine unerwartete
    Antwortform ein Befund."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _probe_result(
    probe_id: str, ok: bool, detail: str, stderr: str = ""
) -> dict[str, Any]:
    """Eine einzelne Pruefung als Berichtseintrag. Jede Zeichenkette laeuft hier durch die eine
    Redaktionsfunktion - eine Redaktion, die an einem einzigen Feld vorbeigeht, ist keine."""
    return {
        "id": probe_id,
        "ok": bool(ok),
        "lifecycle_steps": list(PROBE_LIFECYCLE_STEPS[probe_id]),
        "detail": redact_for_report(detail),
        "stderr": redact_for_report(stderr) if stderr.strip() else None,
    }


def _missing_field_options(board: GhBoard) -> list[str]:
    """Fehlende Optionen der beiden Board-Felder - nur die eigenen, in diesem Modul definierten
    Werte, nie fremd befuellbarer Text."""
    luecken: list[str] = []
    for field_name, expected, field in (
        (STATUS_FIELD_NAME, STATUS_VALUES, board.status_field()),
        (PRIORITY_FIELD_NAME, PRIORITY_VALUES, board.priority_field()),
    ):
        vorhanden = {
            option.get("name") for option in field.get("options", []) if isinstance(option, dict)
        }
        fehlend = [value for value in expected if value not in vorhanden]
        if fehlend:
            luecken.append(f"{field_name} ohne {', '.join(fehlend)}")
    return luecken


def cmd_doctor(board: GhBoard) -> dict[str, Any]:
    """Stellt die Faehigkeiten der Umgebung entlang der Lebenszyklus-Schritte fest (ADR 0052,
    Abschnitt 4).

    Zwei Eigenschaften, die kein anderer Befehl hat: Jede Pruefung ist unabhaengig - eine
    fehlgeschlagene beendet den Lauf nicht -, und jeder Befund ist ueber eine statische Tabelle
    einem Lebenszyklus-Schritt zugeordnet. Der Bericht sagt damit nicht "Pruefung X ist rot",
    sondern welche Schritte in dieser Umgebung nicht gehen.

    Rein lesend (Abschnitt 5) und mit Exit-Code 0, sobald ein Bericht entsteht - eine bewusste,
    dokumentierte Ausnahme von der `{"error": ...}`/Exit-1-Konvention der uebrigen Befehle:
    Fehlgeschlagene Pruefungen sind der Inhalt, nicht das Scheitern.
    """
    probes: list[dict[str, Any]] = []

    # 1) Binary. Faellt es aus, faellt alles aus.
    binary_ok, version_stdout, version_stderr = board.probe(["gh", "--version"])
    probes.append(
        _probe_result(
            "gh_binary",
            binary_ok,
            "Das gh-Binary ist ausfuehrbar."
            if binary_ok
            else "Das gh-Binary ist nicht ausfuehrbar.",
            version_stderr,
        )
    )

    # 2) Version - numerisch verglichen, aus derselben Ausgabe.
    version = parse_gh_version(version_stdout) if binary_ok else None
    version_text = ".".join(str(part) for part in version) if version is not None else None
    if version is None:
        probes.append(
            _probe_result(
                "gh_version",
                False,
                "Keine auswertbare Versionsangabe aus 'gh --version' (erwartet mindestens "
                f"gh {MIN_GH_VERSION}).",
            )
        )
    else:
        minimum = parse_gh_version(MIN_GH_VERSION) or (0, 0, 0)
        probes.append(
            _probe_result(
                "gh_version",
                version >= minimum,
                f"gh {version_text}, Mindestversion {MIN_GH_VERSION} (erst ab dort kennt "
                "'gh pr view --json' das Feld 'closingIssuesReferences').",
            )
        )

    # 3) Anmeldung - nur die vier Whitelist-Felder, nie die Ausgabe selbst.
    auth = board.auth_info()
    if not auth["authenticated"]:
        auth_detail = "'gh auth status' meldet keine nutzbare Anmeldung."
    elif auth["account"]:
        auth_detail = f"Angemeldet als {auth['account']}, Token-Quelle {auth['source']}."
    else:
        auth_detail = "Angemeldet, aber ohne auswertbaren Kontoblock in 'gh auth status'."
    probes.append(
        _probe_result("auth", auth["authenticated"], auth_detail, auth["error_output"])
    )

    # 4) Scope-Auskunft - reine Information, ausdruecklich ohne Urteil ueber den Zugriff.
    #
    #    `scopes is None` allein taugt hier nicht als Verzweigung: Der Wert traegt zwei
    #    Bedeutungen - "angemeldet, aber ohne Scope-Zeile" (Token-Auth) und "konnte gar nicht
    #    gefragt werden" (Anmeldung fehlgeschlagen, `gh` nicht installiert). Aus dem fehlenden
    #    Wert auf die erste Ursache zu schliessen, waere genau der Defekt, den diese Spec
    #    behebt - und im Remote-Lauf zu Spec 0309 ist er eingetreten: `gh` fehlte dort
    #    vollstaendig, gemeldet wurde "typisch bei Token-Authentifizierung".
    #
    #    `ok` heisst bei DIESER Pruefung "die Auskunft liegt vor", nicht "der Zugriff besteht"
    #    (sie blockiert bewusst keinen Lebenszyklus-Schritt, kann also kein `verdict`
    #    verfaelschen). Deshalb `False`, wenn nichts festgestellt werden konnte: Ein gruener
    #    Haken neben der Aussage "nicht feststellbar" liest sich als Entwarnung, die niemand
    #    gegeben hat.
    scopes = auth["scopes"]
    scope_ok = True
    if not auth["authenticated"]:
        scope_ok = False
        scope_detail = (
            "Die Scope-Auskunft war nicht feststellbar - es konnte keine Anmeldung abgefragt "
            "werden (siehe die Pruefungen 'gh_binary' und 'auth'). Das ist keine Aussage "
            "darueber, welche Scopes ein Token traegt."
        )
    elif scopes is None:
        scope_detail = (
            "Die Auskunft des aktiven Kontos enthaelt keine Scope-Zeile (typisch bei "
            "Token-Authentifizierung). Daraus folgt kein Urteil ueber den Zugriff."
        )
    elif not scopes:
        scope_detail = (
            "Die Scope-Zeile des aktiven Kontos meldet 'none'. Daraus folgt kein Urteil ueber "
            "den Zugriff."
        )
    elif "project" in scopes:
        scope_detail = "Die Scope-Zeile des aktiven Kontos nennt 'project'."
    else:
        scope_detail = (
            "Die Scope-Zeile des aktiven Kontos nennt 'project' nicht. Gemessen wird der "
            "Zugriff trotzdem von der Pruefung 'project_visible'."
        )
    probes.append(_probe_result("scope_hint", scope_ok, scope_detail))

    # 5) Repository-Berechtigung - Indiz, kein Beweis fuer Schreibzugriff.
    repository = f"{board.owner}/{DEFAULT_REPO}"
    repo_ok, repo_stdout, repo_stderr = board.probe(
        ["gh", "repo", "view", repository, "--json", "viewerPermission"]
    )
    repo_data = _loads(repo_stdout) if repo_ok else None
    permission = None
    if isinstance(repo_data, dict) and isinstance(repo_data.get("viewerPermission"), str):
        permission = repo_data["viewerPermission"]
    probes.append(
        _probe_result(
            "repo_access",
            permission in REPO_WRITE_PERMISSIONS,
            f"viewerPermission fuer {repository}: {permission or 'nicht ermittelbar'} "
            f"(als Schreibrecht gelten {', '.join(REPO_WRITE_PERMISSIONS)}; TRIAGE gehoert "
            "ausdruecklich nicht dazu).",
            repo_stderr,
        )
    )

    # 6) Issues lesbar - ausschliesslich '--json number', nie Titel/Body/Labels (das Repository
    #    ist oeffentlich, jeder kann ein Issue mit beliebigem Titel anlegen).
    issue_ok, issue_stdout, issue_stderr = board.probe(
        ["gh", "issue", "list", "--limit", "1", "--json", "number"]
    )
    issue_data = _loads(issue_stdout) if issue_ok else None
    issues_lesbar = issue_ok and isinstance(issue_data, list)
    probes.append(
        _probe_result(
            "issue_read",
            issues_lesbar,
            f"{len(issue_data) if isinstance(issue_data, list) else 0} Issue(s) gelesen (eine "
            "leere Liste ist ein gueltiges Ergebnis)."
            if issues_lesbar
            else "Die Issue-Liste war nicht lesbar oder hatte eine unerwartete Form.",
            issue_stderr,
        )
    )

    # 7) Board sichtbar - der Aufruf, der bei jedem schreibenden Board-Pfad ohnehin stattfindet.
    project_ok, project_stdout, project_stderr = board.probe(
        ["gh", "project", "list", "--owner", board.owner, "--format", "json"]
    )
    project_data = _loads(project_stdout) if project_ok else None
    projekte = project_data.get("projects") if isinstance(project_data, dict) else None
    if not project_ok:
        board_sichtbar = False
        project_detail = "Die Projektliste konnte nicht abgerufen werden."
    elif not isinstance(projekte, list):
        board_sichtbar = False
        project_detail = "Die Antwort auf 'gh project list' hatte eine unerwartete Form."
    else:
        board_sichtbar = any(
            isinstance(eintrag, dict) and eintrag.get("title") == board.project_title
            for eintrag in projekte
        )
        project_detail = (
            f"Das Board {board.project_title!r} ist sichtbar ({len(projekte)} Projekte "
            "insgesamt)."
            if board_sichtbar
            else f"Das Board {board.project_title!r} ist unter {len(projekte)} sichtbaren "
            "Projekten nicht dabei (umbenannt oder nicht sichtbar)."
        )
    probes.append(_probe_result("project_visible", board_sichtbar, project_detail, project_stderr))

    # 8) Board-Felder samt Optionen - bewusst ueber dieselben Methoden, die jeder Schreibpfad
    #    benutzt: Die Pruefung soll den echten Aufloesungsweg gehen, nicht einen nachgebauten.
    #    Preis ist ein zweiter (rein lesender) 'gh project list'-Aufruf, weil der Cache nach der
    #    Roh-Probe oben leer ist - in einer Diagnose ist Unabhaengigkeit der Pruefungen mehr wert
    #    als ein gesparter Aufruf.
    try:
        luecken = _missing_field_options(board)
    except BoardError as exc:
        probes.append(_probe_result("fields", False, str(exc)))
    else:
        probes.append(
            _probe_result(
                "fields",
                not luecken,
                f"Die Board-Felder {STATUS_FIELD_NAME!r} und {PRIORITY_FIELD_NAME!r} tragen alle "
                "erwarteten Optionen."
                if not luecken
                else f"Unvollstaendige Board-Felder: {'; '.join(luecken)}.",
            )
        )

    # 9) Board-Items - nur die Anzahl, kein Inhalt.
    try:
        items = board._item_list()
    except BoardError as exc:
        probes.append(_probe_result("items", False, str(exc)))
    else:
        probes.append(_probe_result("items", True, f"{len(items)} Board-Item(s) sichtbar."))

    blockiert = [
        schritt
        for schritt in LIFECYCLE_STEPS
        if any(schritt in probe["lifecycle_steps"] for probe in probes if not probe["ok"])
    ]
    return {
        "verdict": "blocked" if blockiert else "ok",
        "gh_version": version_text,
        "auth": {
            "authenticated": auth["authenticated"],
            "account": redact_for_report(auth["account"]) if auth["account"] else None,
            "source": auth["source"],
            "scopes": (
                [redact_for_report(scope) for scope in scopes] if scopes is not None else None
            ),
        },
        "probes": probes,
        "blocked_lifecycle_steps": blockiert,
        "note": redact_for_report(DOCTOR_NOTE),
    }


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

    set_priority = subparsers.add_parser(
        "set-priority", help="Board-Prioritaet first-write-wins setzen."
    )
    set_priority.add_argument("--issue", type=int, required=True)
    set_priority.add_argument("--priority", required=True)

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

    # Bewusst ohne jedes Argument: keine Eingabeflaeche, keine Interpolation fremder Werte in
    # eine Argumentliste (ADR 0017, Abschnitt 5).
    subparsers.add_parser(
        "doctor",
        help=(
            "Umgebungsdiagnose entlang der Lebenszyklus-Schritte. Rein lesend; Exit-Code 0, "
            "sobald ein Bericht entsteht."
        ),
    )

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
    if args.command == "set-priority":
        return cmd_set_priority(board, issue_number=args.issue, priority=args.priority)
    if args.command == "show-status":
        return cmd_show_status(board, issue_number=args.issue)
    if args.command == "doctor":
        return cmd_doctor(board)
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
        payload = _dispatch(args, board, root)
    except BoardError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
