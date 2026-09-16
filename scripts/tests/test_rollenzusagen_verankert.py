r"""Haelt fest, dass eine Rollenzusage nur Zugeteiltes nennt und die Produktentscheidung abgibt.

Gegenstand ist Markdown, das ein Modell zur Laufzeit interpretiert: die sieben Rollendateien unter
`.claude/agents/`, die fuenf Aufrufstellen unter `.claude/skills/` und die Definitionsstelle des
Ankers `## Blockiert: Produktentscheidung nötig`. Kein Mechanismus dieses Repositoriums fuehrt
diese Texte aus. Zugesichert wird hier deshalb ausschliesslich **Nachweisbares**: dass die
Anweisung dasteht, an welcher Stelle sie dasteht, und dass sie nur an einer Stelle steht.

Der Waechter kodiert **keine Filterliste der Laufzeit**. Er vergleicht ausschliesslich zwei Dinge,
die beide im Repositorium liegen: `werkzeugzuteilung.json` und die Rollen-/Aufrufdateien. Eine hart
kodierte Filterliste veraltete mit der naechsten Version der Laufzeit und erzwaenge dann etwas
Falsches, das im Repositorium nicht behebbar ist. `claude_code_version` und `gemessen_am` werden
auf Form geprueft, **nie** gegen einen Sollwert oder ein Hoechstalter: Eine Frist wuerde an einem
Tag rot, an dem nichts falsch ist und niemand im Repositorium etwas beheben kann.

Zehn Zusicherungen, je Kriterium getrennt, damit ein Ausfall benennt, *welche* Zusage verschwunden
ist:

1. **Vorzusicherung `tools:`** - jede Rollendatei fuehrt genau eine, nicht leere `tools:`-Zeile.
2. **Deckung** - die Rollenmenge des Artefakts ist gleich der Menge der `.claude/agents/*.md`.
3. **Zone statt Verbot** - genau ein Block `**Werkzeugabweichung:**` je Rollendatei, Ort plus
   Mengengleichheit.
4. **Ankermenge** - die Dateien unter `.claude/**` mit der Ankerzeile sind gleich der abgeleiteten
   Menge.
5. **Ankerort** - jedes Vorkommen liegt im Abschnitt, der die Entscheidungslage bzw. die
   Auswertung beschreibt.
6. **Der Rechercheur fuehrt den Anker nicht** - null Vorkommen, als Gleichheit geprueft.
7. **Ein Format, eine Stelle** - der Feldblock kommt im Suchraum genau einmal vor.
8. **Die drei bestehenden Anker** bleiben wortgleich, je einmal, an ihrer Definitionsstelle.
9. **Vorlegefaehigkeit** - Ankerzeile, `AskUserQuestion` und `SendMessage` in **einem** Abschnitt
   je Aufrufstelle.
10. **Messartefakt-Form** - je Rolle eigene Felder, und die sieben `angeboten`-Mengen sind nicht
    durchweg identisch.

**Zusicherung 1 ist eine Vorzusicherung, und das ist ihr ganzer Zweck.** Eine Rollendatei **ohne**
`tools:`-Zeile erbt die **weiteste** Zuteilung der Laufzeit. Das Entfernen der Zeile waere damit
der billigste Weg, jede Abwesenheitszusage dieses Moduls leer wahr zu machen: Wo nichts mehr
aufgezaehlt ist, steht auch kein strukturell abwesendes Token mehr da. Die Zeile wird deshalb
zuerst und unabhaengig gefordert, statt nur ihren Inhalt zu pruefen.

**Was hier bewusst NICHT gebaut wird:** ein Pruefer, der aus Prosa herausliest, ob eine Stelle
*inhaltlich* noch eine Rueckfrage verlangt, und eine Heuristik ueber Sitzungsprotokolle. Beide
waeren gruen, ohne etwas zu wissen - schaedlicher als kein Test, weil sie die benannte offene
Flanke zudeckten. Dass ein Lauf am Anker tatsaechlich anhaelt und die Sitzung die Frage vorlegt,
ist in CI nicht feststellbar (`specs/architecture/0002-testkonzept.md`).

**Die meisten Zusicherungen haben konstruktionsbedingt keinen Rot-Schritt** (die `tools:`-Zeilen
standen immer da, eine zweite Definitionsstelle gab es nie). Ihr Nachweis laeuft ueber die
Gegenproben an synthetischem Text in **beide** Richtungen.

Kein Netzwerk, kein GitHub, kein echtes git ausser `git ls-files`: gelesen werden ausschliesslich
Dateien dieses Repositoriums.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

ARTEFAKT_PFAD = "scripts/tests/werkzeugzuteilung.json"

AGENTEN_VERZEICHNIS = ".claude/agents"
RECHERCHEUR = ".claude/agents/research-engineer.md"

# --- Selbstschutz ----------------------------------------------------------------------------

# Untergrenzen weit unter dem Ist-Stand (2026-09-16: 7 Rollendateien, 5 Aufrufstellen). Sie fangen
# den Totalausfall der Aufzaehlung, nicht jede geloeschte Datei: Ein leer oder halb gelesener
# Suchraum darf nie als "genau einmal gefunden" oder "nirgends gefunden" durchgehen.
MINDESTZAHL_ROLLENDATEIEN = 7

# --- Reine Funktionen ------------------------------------------------------------------------

_FRONTMATTER = re.compile(r"\A---\n(?P<kopf>.*?)\n---\n", re.DOTALL)
_TOOLS_ZEILE = re.compile(r"^tools:(?P<wert>.*)$", re.MULTILINE)
_NAME_ZEILE = re.compile(r"^name:(?P<wert>.*)$", re.MULTILINE)


def frontmatter(text: str) -> str:
    """Reine Funktion: der YAML-Kopf einer Rollendatei.

    Wirft, wenn keiner da ist: Ohne Kopf gibt es weder `name:` noch `tools:`, und ein Nullbefund
    ueber beide waere dann eine Aussage ueber die falsche Datei.
    """
    treffer = _FRONTMATTER.search(text)
    if treffer is None:
        raise ValueError(
            "Kein YAML-Frontmatter (`---`-Block am Dateianfang) gefunden. Ohne ihn hat die Datei "
            "weder `name:` noch `tools:`, und jede Aussage darueber waere leer wahr."
        )
    return treffer.group("kopf")


def tools_zeilen(text: str) -> list[str]:
    """Reine Funktion: die Werte aller `tools:`-Zeilen des Frontmatters, in Fundreihenfolge."""
    return [treffer.group("wert").strip() for treffer in _TOOLS_ZEILE.finditer(frontmatter(text))]


def rollenname(text: str) -> str:
    """Reine Funktion: der Wert der `name:`-Zeile des Frontmatters."""
    treffer = _NAME_ZEILE.search(frontmatter(text))
    if treffer is None:
        raise ValueError("Keine `name:`-Zeile im Frontmatter - die Rolle hat damit keinen Namen.")
    return treffer.group("wert").strip()


def tools_befunde(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: jede Rollendatei ohne genau eine, nicht leere `tools:`-Zeile.

    **Warum diese Zusicherung vor allen anderen steht:** Fehlt die Zeile, erbt die Rolle die
    **weiteste** Zuteilung der Laufzeit - und jede Abwesenheitszusage dieses Moduls wuerde leer
    wahr, weil in einer nicht vorhandenen Aufzaehlung auch kein verbotenes Token steht. Das
    Entfernen der Zeile waere damit der billigste Weg zu Gruen.
    """
    if len(abbild) < MINDESTZAHL_ROLLENDATEIEN:
        raise ValueError(
            f"Nur {len(abbild)} Rollendateien gefunden (erwartet mindestens "
            f"{MINDESTZAHL_ROLLENDATEIEN}). Die Aufzaehlung ist kaputt; eine Nullmeldung waere "
            "dann bedeutungslos."
        )
    befunde: list[str] = []
    for pfad in sorted(abbild):
        zeilen = tools_zeilen(abbild[pfad])
        if len(zeilen) != 1:
            befunde.append(
                f"{pfad}: {len(zeilen)} `tools:`-Zeilen, erwartet genau eine. Ohne sie erbt die "
                "Rolle die weiteste Zuteilung der Laufzeit; zwei Zeilen sind ein Widerspruch."
            )
            continue
        if not zeilen[0]:
            befunde.append(
                f"{pfad}: Die `tools:`-Zeile ist leer. Eine leere Allowlist ist keine Allowlist - "
                "die Laufzeit faellt dann auf ihre Vorgabemenge zurueck."
            )
    return befunde


def deckungsbefunde(artefakt: Mapping[str, object], abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: die beidseitige Gleichung Artefaktrollen <-> Rollendateien.

    Geprueft wird **Gleichheit**, nicht Teilmenge, und in beide Richtungen: eine neue Rollendatei
    ohne Messung ist ebenso ein Befund wie eine gemessene Rolle, deren Datei verschwunden ist.
    Zusaetzlich wird der `name:`-Wert gegen den Dateinamen gehalten - sonst traegt eine Datei den
    Namen einer anderen Rolle und jede Aussage ueber "diese Rolle" zeigt auf den falschen Text.
    """
    rollen = artefakt.get("rollen")
    if not isinstance(rollen, dict) or not rollen:
        raise ValueError(
            "Der Messartefakt fuehrt keinen nicht leeren `rollen`-Block. Ohne ihn ist jede "
            "Deckungsaussage bedeutungslos."
        )
    befunde: list[str] = []

    aus_dateien = {Path(pfad).stem for pfad in abbild}
    if aus_dateien != set(rollen):
        befunde.append(
            f"Der Artefakt fuehrt {sorted(rollen)}, die Dateien {sorted(aus_dateien)}. Geprueft "
            "wird Gleichheit in beide Richtungen: Eine neue Rollendatei ohne Messung ist ebenso "
            "ein Befund wie eine gemessene Rolle ohne Datei."
        )
    for pfad in sorted(abbild):
        name = rollenname(abbild[pfad])
        if name != Path(pfad).stem:
            befunde.append(
                f"{pfad}: `name:` ist {name!r}, der Dateiname sagt {Path(pfad).stem!r}. Ohne "
                "Gleichheit zeigt jede Aussage ueber 'diese Rolle' auf den falschen Text."
            )
    return befunde


def artefakt_befunde(artefakt: Mapping[str, object]) -> list[str]:
    """Reine Funktion: die Formpruefung des Messartefakts (Zusicherung 10).

    Je Rolle sind `aufrufparameter`, `angeboten` und `bemerkung` nicht leer; die sieben
    `angeboten`-Mengen sind **nicht durchweg identisch**, und die des `research-engineer` weicht
    von den uebrigen ab. Das falsifiziert die Uebertragung **einer** Messung auf alle sieben -
    beweisen laesst sich nicht, dass sieben Proben liefen, widerlegen schon.

    `claude_code_version` und `gemessen_am` werden auf **Form** geprueft, nie gegen einen Sollwert
    und nie gegen ein Hoechstalter.
    """
    befunde: list[str] = []

    version = artefakt.get("claude_code_version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        befunde.append(
            f"`claude_code_version` ist {version!r}, erwartet eine Zeichenkette der Form "
            "`<zahl>.<zahl>.<zahl>`. Geprueft wird die Form, nie ein Sollwert."
        )
    gemessen = artefakt.get("gemessen_am")
    if not isinstance(gemessen, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", gemessen):
        befunde.append(
            f"`gemessen_am` ist {gemessen!r}, erwartet ein Datum der Form `JJJJ-MM-TT`. Ein "
            "Hoechstalter wird ausdruecklich **nicht** geprueft."
        )
    abwesend = artefakt.get("strukturell_abwesend")
    if (
        not isinstance(abwesend, list)
        or not abwesend
        or not all(isinstance(eintrag, str) and eintrag for eintrag in abwesend)
    ):
        befunde.append(
            f"`strukturell_abwesend` ist {abwesend!r}, erwartet eine nicht leere Liste nicht "
            "leerer Namen. Eine leere Liste liesse jede Ortszusicherung leer wahr werden."
        )

    rollen = artefakt.get("rollen")
    if not isinstance(rollen, dict) or not rollen:
        befunde.append("`rollen` fehlt oder ist leer.")
        return befunde

    angeboten_je_rolle: dict[str, frozenset[str]] = {}
    for name in sorted(rollen):
        eintrag = rollen[name]
        if not isinstance(eintrag, dict):
            befunde.append(f"{name}: kein Objekt.")
            continue
        for feld in ("aufrufparameter", "bemerkung"):
            wert = eintrag.get(feld)
            if not isinstance(wert, str) or not wert.strip():
                befunde.append(
                    f"{name}: `{feld}` ist {wert!r}, erwartet eine nicht leere Zeichenkette. Ein "
                    "leeres Feld macht aus 'je Rolle festgestellt' eine Behauptung."
                )
        angeboten = eintrag.get("angeboten")
        if (
            not isinstance(angeboten, list)
            or not angeboten
            or not all(isinstance(werkzeug, str) and werkzeug for werkzeug in angeboten)
        ):
            befunde.append(
                f"{name}: `angeboten` ist {angeboten!r}, erwartet eine nicht leere Liste nicht "
                "leerer Werkzeugnamen."
            )
            continue
        angeboten_je_rolle[name] = frozenset(angeboten)

    if len(set(angeboten_je_rolle.values())) < 2:
        befunde.append(
            "Alle `angeboten`-Mengen sind identisch. Genau das waere das Bild, das entstuende, "
            "wenn **eine** Messung auf alle Rollen uebertragen worden waere, statt je Rolle zu "
            "messen."
        )
    rechercheur = angeboten_je_rolle.get("research-engineer")
    uebrige = {menge for name, menge in angeboten_je_rolle.items() if name != "research-engineer"}
    if rechercheur is not None and rechercheur in uebrige:
        befunde.append(
            "Die `angeboten`-Menge des `research-engineer` ist gleich der einer anderen Rolle. "
            "Er laeuft unter anderen Parametern und hat als einzige Rolle Web-Werkzeuge statt "
            "Schreibwerkzeugen; Gleichheit ist hier ein Hinweis auf eine uebertragene Messung."
        )
    return befunde


# --- Duenne Leser ----------------------------------------------------------------------------


def rollendateien(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: die Rollendateien, per **Glob ueber das Arbeitsverzeichnis**.

    Ausdruecklich **nicht** ueber `git ls-files`: Eine neu angelegte, noch nicht per `git add`
    hinzugefuegte Rollendatei waere dort unsichtbar - und damit genau der Fall, gegen den die
    Deckungszusicherung steht, lokal nicht rot. Der Glob ist flach (`*.md`) und sieht deshalb
    auch dann nur echte Rollendateien, wenn unterhalb von `.claude/` ein Arbeitsbaum liegt.
    """
    verzeichnis = wurzel / AGENTEN_VERZEICHNIS
    return {
        f"{AGENTEN_VERZEICHNIS}/{pfad.name}": pfad.read_text(encoding="utf-8")
        for pfad in sorted(verzeichnis.glob("*.md"))
    }


def artefakt(wurzel: Path = REPO_WURZEL) -> dict[str, object]:
    """Duenner Leser: der Messartefakt `scripts/tests/werkzeugzuteilung.json`."""
    inhalt = json.loads((wurzel / ARTEFAKT_PFAD).read_text(encoding="utf-8"))
    if not isinstance(inhalt, dict):
        raise ValueError(f"{ARTEFAKT_PFAD} enthaelt kein JSON-Objekt.")
    return inhalt


def git_dateien(*orte: str, wurzel: Path = REPO_WURZEL) -> list[str]:
    """Duenner Leser: die von Git verwalteten Pfade unter `orte`.

    Ueber `git ls-files` statt `rglob`: Unterhalb von `.claude/worktrees/` liegen ausgecheckte
    Arbeitsbaeume dieses Repositoriums. Ein Verzeichnislauf faende jede Definition dort noch
    einmal je Arbeitsbaum und machte die Einmaligkeitspruefungen aus einem Grund rot, der mit
    ihrem Gegenstand nichts zu tun hat. Der Preis ist benannt: Eine noch nicht hinzugefuegte
    Datei liegt ausserhalb - wer hier lokal gruen misst, hat eine Aussage ueber den Stand, der
    committet wird. Die Rollenmenge selbst wird deshalb per Glob gebildet (siehe oben).
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", *orte],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    return [roh.decode("utf-8") for roh in ergebnis.stdout.split(b"\0") if roh]


# --- Selbstschutz ----------------------------------------------------------------------------


def test_die_rollendateien_werden_ueberhaupt_gefunden() -> None:
    """Ein leerer Glob liesse jede Abwesenheitszusage dieses Moduls leer wahr werden."""
    dateien = rollendateien()

    assert len(dateien) >= MINDESTZAHL_ROLLENDATEIEN, (
        f"Nur {len(dateien)} Rollendateien unter {AGENTEN_VERZEICHNIS}/ (erwartet mindestens "
        f"{MINDESTZAHL_ROLLENDATEIEN}). Entweder ist der Glob kaputt oder das Verzeichnis - in "
        "beiden Faellen sagt ein Nullbefund dieses Moduls nichts."
    )


def test_eine_leere_rollenmenge_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Rollendateien gefunden"):
        tools_befunde({})


def test_eine_datei_ohne_frontmatter_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Kein YAML-Frontmatter"):
        frontmatter("# Ueberschrift\n\nText ohne Kopf.\n")


# --- Zusicherung 1: die Vorzusicherung ---------------------------------------------------------


def test_jede_rollendatei_fuehrt_genau_eine_nicht_leere_tools_zeile() -> None:
    """Ohne sie erbt die Rolle die weiteste Zuteilung - der billigste Weg zu falschem Gruen."""
    befunde = tools_befunde(rollendateien())

    assert not befunde, "; ".join(befunde)


def test_eine_fehlende_tools_zeile_wird_gemeldet() -> None:
    abbild = {f".claude/agents/r{nummer}.md": "---\nname: r\n---\n" for nummer in range(7)}

    befunde = tools_befunde(abbild)

    assert len(befunde) == 7
    assert "0 `tools:`-Zeilen" in befunde[0]


def test_eine_leere_tools_zeile_wird_gemeldet() -> None:
    abbild = {f".claude/agents/r{nummer}.md": "---\nname: r\ntools:\n---\n" for nummer in range(7)}

    befunde = tools_befunde(abbild)

    assert len(befunde) == 7
    assert "leer" in befunde[0]


def test_eine_gefuellte_tools_zeile_gilt_nicht_als_verstoss() -> None:
    abbild = {
        f".claude/agents/r{nummer}.md": "---\nname: r\ntools: Read, Bash\n---\n"
        for nummer in range(7)
    }

    assert tools_befunde(abbild) == []


# --- Zusicherung 2: Deckung --------------------------------------------------------------------


def test_der_messartefakt_deckt_genau_die_vorhandenen_rollendateien() -> None:
    """Gleichheit in beide Richtungen, gebildet per Glob ueber das Arbeitsverzeichnis."""
    befunde = deckungsbefunde(artefakt(), rollendateien())

    assert not befunde, "; ".join(befunde)


def test_eine_ungemessene_rollendatei_wird_gemeldet() -> None:
    """Gegenprobe zur Gleichheit: Eine Teilmengenpruefung liesse genau das durch."""
    befunde = deckungsbefunde(
        {"rollen": {"alt": {}}},
        {
            ".claude/agents/alt.md": "---\nname: alt\n---\n",
            ".claude/agents/neu.md": "---\nname: neu\n---\n",
        },
    )

    assert any("neu" in befund for befund in befunde)


def test_eine_gemessene_rolle_ohne_datei_wird_gemeldet() -> None:
    befunde = deckungsbefunde(
        {"rollen": {"alt": {}, "weg": {}}},
        {".claude/agents/alt.md": "---\nname: alt\n---\n"},
    )

    assert any("weg" in befund for befund in befunde)


def test_ein_abweichender_rollenname_wird_gemeldet() -> None:
    befunde = deckungsbefunde(
        {"rollen": {"alt": {}}},
        {".claude/agents/alt.md": "---\nname: jemand-anders\n---\n"},
    )

    assert any("jemand-anders" in befund for befund in befunde)


def test_ein_leerer_rollenblock_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"rollen`-Block"):
        deckungsbefunde({"rollen": {}}, {".claude/agents/alt.md": "---\nname: alt\n---\n"})


# --- Zusicherung 10: die Form des Messartefakts -----------------------------------------------


def test_der_messartefakt_traegt_je_rolle_eine_eigene_feststellung() -> None:
    """AK2: eigene Felder je Rolle, und die sieben Mengen sind nicht durchweg identisch."""
    befunde = artefakt_befunde(artefakt())

    assert not befunde, "; ".join(befunde)


def _artefakt_probe(**abweichung: object) -> dict[str, object]:
    rollen: dict[str, object] = {
        "architect": {
            "aufrufparameter": "subagent_type: architect",
            "angeboten": ["Read", "Bash"],
            "bemerkung": "Befund.",
        },
        "research-engineer": {
            "aufrufparameter": "subagent_type: research-engineer",
            "angeboten": ["Read", "WebSearch"],
            "bemerkung": "Befund.",
        },
    }
    probe: dict[str, object] = {
        "claude_code_version": "2.1.273",
        "gemessen_am": "2026-09-16",
        "strukturell_abwesend": ["AskUserQuestion"],
        "rollen": rollen,
    }
    probe.update(abweichung)
    return probe


def test_die_erwartete_artefaktform_gilt_nicht_als_verstoss() -> None:
    assert artefakt_befunde(_artefakt_probe()) == []


def test_eine_fehlende_version_wird_gemeldet() -> None:
    befunde = artefakt_befunde(_artefakt_probe(claude_code_version="jung"))

    assert len(befunde) == 1
    assert "claude_code_version" in befunde[0]


def test_ein_hoechstalter_wird_ausdruecklich_nicht_geprueft() -> None:
    """Die Gegenrichtung: Ein altes Messdatum ist kein Befund - nur eine kaputte Form ist einer."""
    assert artefakt_befunde(_artefakt_probe(gemessen_am="1999-01-01")) == []


def test_eine_leere_bemerkung_wird_gemeldet() -> None:
    rollen = {
        "architect": {"aufrufparameter": "p", "angeboten": ["Read"], "bemerkung": "  "},
        "research-engineer": {"aufrufparameter": "p", "angeboten": ["WebSearch"], "bemerkung": "b"},
    }

    befunde = artefakt_befunde(_artefakt_probe(rollen=rollen))

    assert len(befunde) == 1
    assert "bemerkung" in befunde[0]


def test_durchweg_identische_werkzeugmengen_werden_gemeldet() -> None:
    """Genau das Bild, das eine auf alle Rollen uebertragene Einzelmessung erzeugte."""
    rollen = {
        "architect": {"aufrufparameter": "p", "angeboten": ["Read"], "bemerkung": "b"},
        "research-engineer": {"aufrufparameter": "p", "angeboten": ["Read"], "bemerkung": "b"},
    }

    befunde = artefakt_befunde(_artefakt_probe(rollen=rollen))

    assert any("identisch" in befund for befund in befunde)
