"""Haelt fest, dass die Spec-Statuszeile vor dem Copilot-Review steht (ADR 0128, Spec 0414).

Zugesichert wird an zwei Dateien, Reihenfolgen jeweils ueber Zeichenoffsets:

1. `.claude/skills/ship-feature/SKILL.md`: `**Status:** Implemented` steht genau einmal, und zwar
   in `## Schritt 6`. In Schritt 6 gilt `pr-erstellen` < `pr-verknuepfung-lesen` < Statuszeile <
   ein folgendes `git push`. Das erste `copilot-review-anfordern` der Datei liegt hinter der
   Statuszeile. Die Einmaligkeit faengt eine zurueckgelassene alte Setz-Anweisung, der Ort das
   Zurueckwandern. Die Ruecknahme in Schritt 8 fuehrt `**Status:** Accepted` und zaehlt nicht.
2. `.github/workflows/ci.yml`: genau ein `concurrency:`, auf oberster Ebene, mit der Gruppe samt
   Rueckfall auf `github.run_id` und `cancel-in-progress: true`. Fehlt der Rueckfall, teilen sich
   alle `main`-Laeufe eine Gruppe, und ein zweiter Merge bricht den Lauf des ersten ab; unter
   einem Job eingerueckt bricht der Block nur diesen Job ab, nicht den Lauf.

Nicht zugesichert und deshalb Dokumentdurchsicht: die Ruecknahme bei einem PR ohne Merge und dass
GitHub den Lauf der Eroeffnung tatsaechlich abbricht (Beobachtung am Umsetzungs-PR).

**Mutationsnachweis (2026-10-01, nach Gruen gefuehrt).** Am Text der echten `ship-feature`-Datei
je einzeln gesetzt und rot bekommen: der Codeblock mit der Statuszeile aus Schritt 6 zurueck in
Schritt 8 verschoben; eine zweite Setz-Anweisung `**Status:** Implemented` in Schritt 8 ergaenzt;
`copilot-review-anfordern` in Schritt 6 vor die Statuszeile gezogen; das `git push` hinter der
Statuszeile entfernt. Die drei `ci.yml`-Mutationen laufen als Gegenproben unten mit. Die geforderte
Nicht-Reaktion blieb gruen: die Ruecknahme mit `**Status:** Accepted` in Schritt 8. Wer ein Muster
aendert, wiederholt diese Probe, statt sie zu glauben.

Eigene duenne Leser, kein Import aus Nachbarmodulen; kein Netzwerk, gelesen werden ausschliesslich
Dateien dieses Repositoriums.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]
SHIP_FEATURE_PFAD = REPO_WURZEL / ".claude" / "skills" / "ship-feature" / "SKILL.md"
CI_PFAD = REPO_WURZEL / ".github" / "workflows" / "ci.yml"

STATUSZEILE = "**Status:** Implemented"
SCHRITT_SECHS = "## Schritt 6:"
PR_ERSTELLEN = "`pr-erstellen`"
VERKNUEPFUNG = "`pr-verknuepfung-lesen`"
COPILOT_ANFORDERN = "`copilot-review-anfordern`"
PUSH = "git push"

GRUPPE = "${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}"
GROUP_ZEILE = f"group: {GRUPPE}"
CANCEL_ZEILE = "cancel-in-progress: true"

_UEBERSCHRIFT = re.compile(r"^## ", re.MULTILINE)
_CONCURRENCY = re.compile(r"^(?P<einzug> *)concurrency:")


# --- Leser --------------------------------------------------------------------------------------


def dateitext(pfad: Path) -> str:
    """Eine fehlende Datei scheitert mit `FileNotFoundError`, eine leere mit `ValueError`."""
    text = pfad.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"{pfad.name}: leer - die Zusicherung waere ungeprueft.")
    return text


def abschnittsgrenzen(text: str, ueberschrift: str) -> tuple[int, int]:
    """Start- und Endoffset des `##`-Abschnitts, der mit `ueberschrift` beginnt."""
    treffer = re.search(rf"^{re.escape(ueberschrift)}", text, re.MULTILINE)
    if treffer is None:
        raise ValueError(f"Ueberschrift {ueberschrift!r} fehlt - kein Abschnitt zum Pruefen.")
    folgende = _UEBERSCHRIFT.search(text, treffer.end())
    return treffer.start(), folgende.start() if folgende else len(text)


def wirksame_zeilen(text: str) -> list[str]:
    """Ganzzeilige YAML-Kommentare werden zu Leerzeilen; der Regelkommentar nennt den Schluessel."""
    zeilen = ["" if zeile.lstrip().startswith("#") else zeile for zeile in text.splitlines()]
    if not any(zeile.strip() for zeile in zeilen):
        raise ValueError("0 wirksame Zeilen - die Zusicherung waere ungeprueft.")
    return zeilen


# --- Pruefer ------------------------------------------------------------------------------------


def statuszeilen_befunde(text: str) -> list[str]:
    anzahl = text.count(STATUSZEILE)
    if anzahl != 1:
        return [f"{STATUSZEILE!r} steht {anzahl}x in ship-feature, erwartet genau einmal."]
    beginn, ende = abschnittsgrenzen(text, SCHRITT_SECHS)
    if not beginn <= text.index(STATUSZEILE) < ende:
        return [f"{STATUSZEILE!r} steht nicht in {SCHRITT_SECHS!r}."]
    return []


def reihenfolge_befunde(text: str) -> list[str]:
    beginn, ende = abschnittsgrenzen(text, SCHRITT_SECHS)
    schritt = text[beginn:ende]
    marken = [(marke, schritt.find(marke)) for marke in (PR_ERSTELLEN, VERKNUEPFUNG, STATUSZEILE)]
    befunde = [f"{marke} fehlt in Schritt 6." for marke, ort in marken if ort < 0]
    if befunde:
        return befunde
    for (frueher, ort_frueher), (spaeter, ort_spaeter) in zip(marken, marken[1:], strict=False):
        if ort_spaeter < ort_frueher:
            befunde.append(f"{spaeter} steht in Schritt 6 vor {frueher}.")
    if schritt.find(PUSH, marken[-1][1]) < 0:
        befunde.append(f"Hinter der Statuszeile steht in Schritt 6 kein {PUSH!r}.")
    return befunde


def copilot_befunde(text: str) -> list[str]:
    status, copilot = text.find(STATUSZEILE), text.find(COPILOT_ANFORDERN)
    if status < 0 or copilot < 0:
        return [f"{STATUSZEILE!r} oder {COPILOT_ANFORDERN} fehlt in ship-feature."]
    if copilot < status:
        return [f"{COPILOT_ANFORDERN} steht vor der Statuszeile."]
    return []


def concurrency_befunde(text: str) -> list[str]:
    zeilen = wirksame_zeilen(text)
    fundstellen = [
        (nummer, len(treffer.group("einzug")))
        for nummer, zeile in enumerate(zeilen)
        if (treffer := _CONCURRENCY.match(zeile))
    ]
    if len(fundstellen) != 1:
        return [f"{len(fundstellen)} 'concurrency:'-Bloecke in ci.yml, erwartet genau einer."]
    nummer, einzug = fundstellen[0]
    befunde = []
    if einzug:
        befunde.append(f"Zeile {nummer + 1}: 'concurrency:' steht nicht auf oberster Ebene.")
    block = []
    for zeile in zeilen[nummer + 1 :]:
        if zeile.strip() and len(zeile) - len(zeile.lstrip(" ")) <= einzug:
            break
        block.append(zeile.strip())
    if GROUP_ZEILE not in block:
        befunde.append(f"Im concurrency-Block fehlt {GROUP_ZEILE!r}.")
    if CANCEL_ZEILE not in block:
        befunde.append(f"Im concurrency-Block fehlt {CANCEL_ZEILE!r}.")
    return befunde


# --- Am echten Bestand --------------------------------------------------------------------------


def test_die_statuszeile_steht_in_ship_feature_genau_einmal_und_in_schritt_sechs() -> None:
    assert not statuszeilen_befunde(dateitext(SHIP_FEATURE_PFAD))


def test_in_schritt_sechs_folgt_die_statuszeile_der_verknuepfungspruefung_und_wird_gepusht() -> (
    None
):
    assert not reihenfolge_befunde(dateitext(SHIP_FEATURE_PFAD))


def test_das_copilot_review_wird_erst_hinter_der_statuszeile_angefordert() -> None:
    assert not copilot_befunde(dateitext(SHIP_FEATURE_PFAD))


def test_ci_bricht_den_ueberholten_lauf_je_pr_ab() -> None:
    befunde = concurrency_befunde(dateitext(CI_PFAD))

    assert not befunde, " ".join(befunde)


# --- Gegenproben an synthetischem Text ----------------------------------------------------------

SYNTHETISCH = (
    "## Schritt 6: PR\n"
    "4. `pr-erstellen`\n"
    "5. `pr-verknuepfung-lesen`\n"
    "6. setzen:\n"
    "   **Status:** Implemented (PR)\n"
    "   committen, `git push`.\n"
    "## Schritt 7: Copilot\n"
    "1. `copilot-review-anfordern`\n"
    "## Schritt 8: Abgleich\n"
    "1. Skript, dann git push.\n"
    "Ruecknahme: **Status:** Accepted\n"
)


def test_der_synthetische_regelfall_samt_ruecknahme_ist_gruen() -> None:
    assert statuszeilen_befunde(SYNTHETISCH) == []
    assert reihenfolge_befunde(SYNTHETISCH) == []
    assert copilot_befunde(SYNTHETISCH) == []


@pytest.mark.parametrize(
    "mutiert",
    [
        SYNTHETISCH.replace(
            "4. `pr-erstellen`\n5. `pr-verknuepfung-lesen`",
            "4. `pr-verknuepfung-lesen`\n5. `pr-erstellen`",
        ),
        SYNTHETISCH.replace(
            "5. `pr-verknuepfung-lesen`\n6. setzen:\n   **Status:** Implemented (PR)\n",
            "6. setzen:\n   **Status:** Implemented (PR)\n5. `pr-verknuepfung-lesen`\n",
        ),
        SYNTHETISCH.replace("   committen, `git push`.\n", "   committen.\n"),
    ],
    ids=["verknuepfung-vor-eroeffnung", "statuszeile-vor-verknuepfung", "kein-push-dahinter"],
)
def test_eine_vertauschte_oder_unvollstaendige_reihenfolge_wird_gemeldet(mutiert: str) -> None:
    assert mutiert != SYNTHETISCH
    assert reihenfolge_befunde(mutiert)


def test_eine_zurueckgewanderte_statuszeile_wird_gemeldet() -> None:
    mutiert = SYNTHETISCH.replace("   **Status:** Implemented (PR)\n", "").replace(
        "Ruecknahme:", "**Status:** Implemented (PR)\nRuecknahme:"
    )

    assert statuszeilen_befunde(mutiert)


def test_eine_zweite_setz_anweisung_wird_gemeldet() -> None:
    mutiert = SYNTHETISCH + "3. **Status:** Implemented (PR) setzen.\n"

    assert statuszeilen_befunde(mutiert)


def test_eine_vorgezogene_copilot_anforderung_wird_gemeldet() -> None:
    mutiert = SYNTHETISCH.replace(
        "4. `pr-erstellen`\n", "4. `pr-erstellen`, `copilot-review-anfordern`\n"
    )

    assert copilot_befunde(mutiert)


# --- Gegenproben am mutierten echten ci.yml -----------------------------------------------------


def _ersetzt(text: str, alt: str, neu: str) -> str:
    """Ersetzt genau ein Vorkommen - sonst waere die Gegenprobe still wirkungslos."""
    if text.count(alt) != 1:
        raise ValueError(f"Mutationsvorlage {alt!r} steht {text.count(alt)}x im Text, erwartet 1x.")
    return text.replace(alt, neu)


def ohne_rueckfall(text: str) -> str:
    return _ersetzt(text, " || github.run_id", "")


def mit_abbruch_aus(text: str) -> str:
    return _ersetzt(text, CANCEL_ZEILE, "cancel-in-progress: false")


def unter_einen_job_eingerueckt(text: str) -> str:
    block = f"concurrency:\n  {GROUP_ZEILE}\n  {CANCEL_ZEILE}\n"
    eingerueckt = f"    concurrency:\n      {GROUP_ZEILE}\n      {CANCEL_ZEILE}\n"
    return _ersetzt(_ersetzt(text, block, ""), "\n  backend:\n", f"\n  backend:\n{eingerueckt}")


@pytest.mark.parametrize("mutation", [ohne_rueckfall, mit_abbruch_aus, unter_einen_job_eingerueckt])
def test_jede_abschwaechung_des_concurrency_blocks_wird_gemeldet(
    mutation: Callable[[str], str],
) -> None:
    assert concurrency_befunde(mutation(dateitext(CI_PFAD)))


def test_eine_kommentarzeile_mit_dem_schluessel_bleibt_gruen() -> None:
    text = "# concurrency: je PR ein Lauf\n" + dateitext(CI_PFAD).replace(
        "\n  backend:\n", "\n  backend:\n    # concurrency: nicht hier\n", 1
    )

    assert concurrency_befunde(text) == []


# --- Lautes Scheitern ---------------------------------------------------------------------------


def test_eine_fehlende_datei_scheitert_laut(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        dateitext(tmp_path / "gibt-es-nicht.md")


def test_eine_leere_datei_scheitert_laut(tmp_path: Path) -> None:
    leer = tmp_path / "leer.yml"
    leer.write_text("  \n\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"leer"):
        dateitext(leer)


def test_ein_workflow_nur_aus_kommentaren_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"0 wirksame Zeilen"):
        concurrency_befunde("# concurrency:\n\n")


def test_ein_fehlender_schritt_sechs_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"fehlt"):
        statuszeilen_befunde("## Schritt 7: X\n**Status:** Implemented\n")
