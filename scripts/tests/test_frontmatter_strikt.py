"""Waechter: jeder `description:`-Skalar, den ein strenger YAML-Leser liest, bleibt gueltig.

**Zusicherung.** Fuer jede `SKILL.md` unter `.claude/skills/`, jede Rollendatei unter
`.claude/agents/` und jede Agentendatei unter `.opencode/agents/` und `.omp/agents/` ist der
Wert der `description:`-Zeile ein gueltiger YAML-Skalar: gequotet, ein Block-Skalar (`>-`, `|`)
oder ein Klartext **ohne** `: `.

**Wofuer.** OpenCode und omp lesen denselben Frontmatter-Kopf wie Claude Code, parsen ihn aber
streng. Ein `: ` im unquotierten Klartext - etwa in einem woertlich zitierten Anker - ist kein
gueltiger YAML-Skalar, und der betroffene Skill oder Agent faellt **still** aus dem Register,
waehrend Claude Code ihn unveraendert weiter laedt.

**Was bei Verletzung passiert.** Kein Werkzeug meldet etwas. Der Skill oder Agent ist in der
OpenCode- bzw. omp-Sitzung schlicht nicht vorhanden, und jeder Ablauf, der ihn aufruft, greift
ins Leere. Deshalb steht die Regel hier als Test und nicht als Konvention.

Die Pruefung kommt ohne zusaetzliche Abhaengigkeit aus: PyYAML gehoert bewusst nicht zu den
`scripts`-Abhaengigkeiten (siehe `scripts/pyproject.toml`), und geprueft wird genau die Regel,
an der die Dateien tatsaechlich gescheitert sind.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

REPO_WURZEL = Path(__file__).resolve().parent.parent.parent

# Untergrenze weit unter dem Ist-Stand (2026-09-20: 20 Skills, 7 Rollendateien, 7 Agentendateien).
# Ein leer oder halb gelesener Suchraum darf nie als "kein Befund" durchgehen.
MINDESTZAHL_DATEIEN = 20

SKILL_MUSTER = ".claude/skills/*/SKILL.md"
AGENT_MUSTER = (".claude/agents/*.md", ".opencode/agents/*.md", ".omp/agents/*.md")

_FRONTMATTER = re.compile(r"\A---\n(?P<kopf>.*?)\n---\n", re.DOTALL)
_BESCHREIBUNG = re.compile(r"^description:(?P<wert>.*)$", re.MULTILINE)

# Ein `: ` beendet einen Klartext-Skalar vorzeitig: der Leser sieht dort einen neuen Schluessel.
VERBOTEN_IM_KLARTEXT = ": "

# YAML-Anzeiger, die den Wert als gequotet, als Block-Skalar oder als Sammlung beginnen lassen.
_ANZEICHEN = ("'", '"', "|", ">", "[", "{", "&", "*", "!", "%", "@", "`")


def frontmatter(text: str) -> str | None:
    """Reine Funktion: der YAML-Kopf am Dateianfang, oder `None` ohne `---`-Block."""
    treffer = _FRONTMATTER.search(text)
    if treffer is None:
        return None
    return treffer.group("kopf")


def ist_klartext_mit_doppelpunkt(rohwert: str) -> bool:
    """Reine Funktion: ist der `description:`-Wert ein Klartext, den `: ` vorzeitig beendet?

    `rohwert` ist der Text hinter dem Doppelpunkt der Schluesselzeile. Ein leerer Wert ist kein
    Klartext, sondern der Anfang eines Block-Skalars auf den Folgezeilen.
    """
    wert = rohwert.strip()
    if not wert:
        return False
    if wert.startswith(_ANZEICHEN):
        return False
    return VERBOTEN_IM_KLARTEXT in rohwert


def befunde(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: jede Datei ohne Frontmatter, ohne `description:` oder mit dem verbotenen Wert."""
    ergebnis: list[str] = []
    for pfad in sorted(abbild):
        kopf = frontmatter(abbild[pfad])
        if kopf is None:
            ergebnis.append(f"{pfad}: kein YAML-Frontmatter")
            continue
        treffer = _BESCHREIBUNG.search(kopf)
        if treffer is None:
            ergebnis.append(f"{pfad}: keine `description:`-Zeile im Frontmatter")
            continue
        if ist_klartext_mit_doppelpunkt(treffer.group("wert")):
            ergebnis.append(f"{pfad}: `: ` im unquotierten `description:`-Klartext")
    return ergebnis


def bestand() -> dict[str, str]:
    """Die geprueften Dateien als Abbild Pfad -> Inhalt."""
    muster = [SKILL_MUSTER, *AGENT_MUSTER]
    pfade = sorted({p for m in muster for p in REPO_WURZEL.glob(m)})
    if len(pfade) < MINDESTZAHL_DATEIEN:
        raise ValueError(
            f"Nur {len(pfade)} Dateien gefunden (erwartet mindestens {MINDESTZAHL_DATEIEN}). "
            "Der Suchraum ist kaputt; eine Nullmeldung waere dann bedeutungslos."
        )
    return {str(p.relative_to(REPO_WURZEL)): p.read_text(encoding="utf-8") for p in pfade}


# --- Tests -----------------------------------------------------------------------------------


def test_der_bestand_hat_keine_befunde() -> None:
    assert befunde(bestand()) == []


def test_jede_datei_traegt_eine_beschreibung() -> None:
    ohne = [
        pfad
        for pfad, text in bestand().items()
        if (kopf := frontmatter(text)) is None or _BESCHREIBUNG.search(kopf) is None
    ]
    assert ohne == []


def test_waechter_faengt_den_historischen_fall() -> None:
    """Die vier Skills, an denen der Fehler auftrat, in ihrer urspruenglichen Form."""
    kaputt = {
        ".claude/skills/refinement/SKILL.md": (
            "---\n"
            "name: refinement\n"
            'description: ... z.B. "neue Anforderung: ...", oder wenn er auf ein Issue verweist.\n'
            "---\n\nText\n"
        ),
        ".claude/skills/produktentscheidung/SKILL.md": (
            "---\n"
            "name: produktentscheidung\n"
            "description: Definiert den Anker `## Blockiert: Produktentscheidung noetig`.\n"
            "---\n\nText\n"
        ),
        ".claude/skills/ship-feature/SKILL.md": (
            "---\n"
            "name: ship-feature\n"
            "description: Antwort mit dem Anker `## Blockiert: Architektur-Konsultation noetig`.\n"
            "---\n\nText\n"
        ),
        ".claude/skills/ship-entwurf/SKILL.md": (
            "---\n"
            "name: ship-entwurf\n"
            "description: Endet mit `## Entwurfslauf abgeschlossen: Pull Request erwünscht`.\n"
            "---\n\nText\n"
        ),
    }
    assert len(befunde(kaputt)) == len(kaputt)


def test_waechter_akzeptiert_gequotet_und_als_blockskalar() -> None:
    heil = {
        "a/SKILL.md": "---\nname: a\ndescription: 'Anker `## Blockiert: X noetig`'\n---\n",
        "b/SKILL.md": '---\nname: b\ndescription: "Anker `## Blockiert: X noetig`"\n---\n',
        "c/SKILL.md": "---\nname: c\ndescription: >-\n  Anker `## Blockiert: X noetig`\n---\n",
        "d/SKILL.md": "---\nname: d\ndescription: Ohne Doppelpunkt im Klartext\n---\n",
    }
    assert befunde(heil) == []


def test_datei_ohne_frontmatter_scheitert_laut() -> None:
    assert befunde({"x/SKILL.md": "# Ueberschrift\n\nText ohne Kopf.\n"}) == [
        "x/SKILL.md: kein YAML-Frontmatter"
    ]


def test_funktion_urteilt_ueber_den_objektiven_zustand() -> None:
    assert ist_klartext_mit_doppelpunkt(" Anker `## Blockiert: X`") is True
    assert ist_klartext_mit_doppelpunkt(" 'Anker `## Blockiert: X`'") is False
    assert ist_klartext_mit_doppelpunkt(" Ohne Doppelpunkt") is False
    assert ist_klartext_mit_doppelpunkt("") is False
