from __future__ import annotations

from photosort.album_suitability import build_album_suitability_prompt_lines
from photosort.motifs import MOTIF_REGISTRY

# Der EINE Klassifizierungs-Prompt: Motivstaerken, Ausschluss-Flag, Feinlabels und
# Albumtauglichkeit in einer Frage. Bewusst ein eigenes Modul zwischen den beiden reinen
# Registermodulen (`motifs.py`, `album_suitability.py`) und dem Client
# (`remote_classification.py`): `motifs.py` bleibt reines Registermodul und weiss nichts ueber die
# Antwortform des Anbieters.


def build_classification_prompt(*, max_fine_labels: int) -> str:
    """Erzeugt den Klassifizierungs-Prompt AUSSCHLIESSLICH aus `MOTIF_REGISTRY` und den festen
    Stufenankern der Albumtauglichkeit - Prompt, Motivset und Stufenband koennen damit nicht
    auseinanderlaufen, eine zweite gepflegte Liste im Prompt-Literal gibt es nicht.

    `max_fine_labels` kommt als Parameter vom Aufrufer statt aus einem Import: die
    Feinlabel-Grenze gehoert weder zum Motivset noch zum Stufenband.

    SICHERHEIT (S4): der Prompt entsteht nie aus einem Literal daneben, nie aus Datenbankinhalten
    und nie aus einer frueheren Modellantwort - es gibt keinen Rueckkopplungspfad, ueber den eine
    Antwort den naechsten Prompt beeinflussen koennte. Bricht in
    tests/test_classification_prompt.py, Faelle
    `test_the_prompt_is_generated_from_the_registry_not_a_literal` und
    `test_the_album_block_is_generated_from_the_anchors_not_from_a_literal`."""
    lines = [
        "Analysiere dieses Foto und bewerte, wie deutlich jedes der folgenden Motive darauf zu "
        "sehen ist.",
        "",
        # Ausdruecklich OHNE das Wort "Hauptkategorie" und ohne das Wort "Vorrang", auch nicht
        # verneint: der Prompt soll den abgeschafften Mechanismus nicht erst einfuehren, um ihn
        # dann auszuschliessen. Ein Waechtertest haelt beide Woerter aus dem Prompt heraus.
        "Leitfrage je Motiv: Wie stark ist dieses Motiv im Bild vertreten? Bewerte jedes Motiv "
        "FUER SICH - ein Foto kann mehrere Motive zugleich stark zeigen. Waehle kein einzelnes "
        "Motiv aus und ordne die Motive nicht.",
        "",
        "Die Motive (verwende ausschliesslich den jeweiligen Schluessel):",
    ]
    for definition in MOTIF_REGISTRY.values():
        lines.append(
            f'- "{definition.key}" ({definition.display_name}): {definition.definition} '
            f"Abgrenzung: {definition.delimitation}"
        )
    motif_example = ", ".join(f'"{key}": <Zahl>' for key in MOTIF_REGISTRY)
    lines.extend(
        [
            "",
            "Nenne zu JEDEM der oben genannten Schluessel eine Zahl zwischen 0 und 1 "
            "(0 = nicht zu sehen, 1 = bildbestimmend). Lasse keinen Schluessel weg und erfinde "
            "keinen weiteren.",
            "",
            "Anlass- und Ereignisbegriffe (Geburtstag, Urlaub, Weihnachten, Hochzeit) sind KEIN "
            "Motiv - vergib sie ausschliesslich als Feinlabel.",
            "",
            # Ein Wahrheitswert und bewusst KEINE Staerke mit Schwelle: das Modell beantwortet die
            # Frage selbst, und eine Schwelle waere genau die Zugehoerigkeitsgrenze, die dieses
            # Motivset abschafft.
            'Gib zusaetzlich im Feld "excluded" an, ob das Foto eine Text-, Bildschirm- oder '
            "Dokumentabbildung ist (Screenshot, abfotografiertes Dokument, Formular, Beleg, "
            "Ticket, QR-Code, Schild, dessen Text der Bildzweck ist) - als echten Wahrheitswert "
            "true oder false, nicht als Zahl und nicht als Text.",
            "",
            f"Nenne zusaetzlich hoechstens {max_fine_labels} kurze, frei formulierte deutsche "
            "Feinlabels, die das Foto naeher beschreiben (Anlass, Ort, konkretes Motiv).",
            "",
        ]
    )
    # Die Albumtauglichkeit steht NACH dem Motivblock und ausserhalb von ihm: sie ist eine Aussage
    # ueber die Bildguete, keine Motivstaerke.
    lines.extend(build_album_suitability_prompt_lines())
    lines.extend(
        [
            "",
            "Antworte AUSSCHLIESSLICH mit einem einzigen validen JSON-Objekt, ohne "
            "Markdown-Codeblock, ohne weiteren Text, exakt in dieser Form: "
            '{"motifs": {' + motif_example + '}, "excluded": <true|false>, '
            '"fine_labels": ["<Feinlabel>", ...], '
            '"album_suitability": {"level": <Zahl>, "reason": "<Begruendung>"}}',
        ]
    )
    return "\n".join(lines)
