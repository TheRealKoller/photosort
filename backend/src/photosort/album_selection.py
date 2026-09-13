"""Die Endauswahl des Projekts: abgeleitet aus beiden Entwuerfen, ueberschrieben von der
gemeinsamen Entscheidung (ADR 0099 Punkte 1 und 2).

REIN und DB-FREI - dasselbe Muster wie `selection.py`/`events.py`/`quality.py`: keine Session, kein
Modell, kein SQL-Ausdruck, kein Enum-Import aus `models.py`. Die Regel lebt HIER und nur hier; die
Oberflaeche bildet sie nirgends nach.

Mit `n` = Zahl der Nutzer:

    im Entwurf(u,p) = (Albumentscheidung(u,p) = album_worthy) v (vorgeschlagen(p) ^ keine
                      Albumentscheidung(u,p))
    drin_zahl(p)    = #{u : im Entwurf(u,p)}
    Endauswahl(p)   = Entscheidung(p), falls vorhanden; sonst drin_zahl(p) == n
    strittig(p)     = keine Entscheidung(p) ^ 0 < drin_zahl(p) < n

Daraus folgen die beiden Zusagen, die miteinander in Spannung stehen, OHNE durchsetzenden Code:
Einigkeit ist eine VORBELEGUNG, weil sie nur im Zweig ohne Entscheidung wirkt; und eine getroffene
Entscheidung ueberlebt jede spaetere Entwurfsaenderung und jeden neuen Vorschlagslauf, weil beide
ausschliesslich in denselben Zweig hineinwirken. Ein strittiges, unentschiedenes Bild gehoert
NICHT zur Endauswahl - automatische Zugehoerigkeit gibt es allein bei Einigkeit.

Die Zahl ZWEI steht an keiner Stelle: "alle einig" / "nicht alle einig" ist fuer jede Nutzerzahl
definiert und faellt bei zwei Nutzern mit der Aussage der Story zusammen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SelectionState:
    """Die beiden abgeleiteten Aussagen ueber EIN Foto.

    `frozen`, weil beide Werte aus dieser einen Herleitung in den Lesepfad gehen und dort nie
    nachgerechnet werden - eine Zuweisung daran waere die zweite Herleitung."""

    included: bool
    contested: bool


def selection_state(
    *, taken: int, rejected: int, user_count: int, proposed: bool, decision: bool | None
) -> SelectionState:
    """Zugehoerigkeit und Strittigkeit eines Fotos aus den beiden Entwuerfen und der gemeinsamen
    Entscheidung.

    `taken`/`rejected` zaehlen die ALBUMENTSCHEIDUNGEN (`Rating.status`), nie das Vorhandensein
    einer Bewertungszeile: seit ADR 0098 kann eine Zeile allein den Favoriten tragen.

    DIE BEIDEN HERKUENFTE SIND NICHT SYMMETRISCH und das ist der Kern der Rechnung: Bei einem
    VORGESCHLAGENEN Foto ist jeder im Entwurf, der es nicht gestrichen hat (`user_count -
    rejected`); bei einem nicht vorgeschlagenen nur, wer es ausdruecklich aufgenommen hat
    (`taken`). Wer hier die jeweils andere Groesse liest, bekommt in der einen Haelfte der Faelle
    ein plausibles Falschergebnis, das keine Ausnahme wirft.

    KEIN CLAMP auf `[0, user_count]`: `taken + rejected <= user_count` gilt strukturell
    (`uq_rating_photo_user` plus Fremdschluessel auf `users`). Ein Clamp verbaerge den Bruch dieser
    Invariante, statt ihn zu zeigen.

    `user_count > 0` ist kein Randfallschutz, sondern Teil der Regel: Ohne ihn waere `0 == 0` wahr
    und jedes vorgeschlagene Foto Teil der Endauswahl einer nutzerlosen Instanz."""
    in_draft_count = (user_count - rejected) if proposed else taken
    if decision is not None:
        return SelectionState(included=decision, contested=False)
    return SelectionState(
        included=user_count > 0 and in_draft_count == user_count,
        contested=0 < in_draft_count < user_count,
    )
