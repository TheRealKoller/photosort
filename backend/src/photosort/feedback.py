"""Die Auswertung des Ereignis-Logs der Nacharbeit: Modellfehler, Tauscharten, Gewichte.

REIN und DB-FREI - dasselbe Muster wie `quality.py`/`selection.py`/`album_selection.py`: keine
Sitzung, kein Modell, kein SQL-Ausdruck. Die Ladeabfragen liegen daneben in `feedback_log.py` und
reichen hierher nur Zahlen und Zuordnungen.

DAS VERFAHREN IST EINE AUSZAEHLUNG, kein Training und kein Modellaufruf. Fuer jedes Paar ("der
Nutzer zog `B` dem `A` vor") und jedes Kriterium `k`, dessen Wert auf BEIDEN Fotos vorliegt, stimmt
`k` mit dem Ereignisgewicht ab - zustimmend bei `v_k(B) > v_k(A)`, ablehnend bei `<`, gar nicht bei
Gleichstand:

    zustimmung_k = (Summe zustimmend - Summe ablehnend) / (Summe zustimmend + Summe ablehnend)
    w_k          = startwert_k * (1 + FEEDBACK_WEIGHT_SPAN * zustimmung_k * n_k / (n_k + PRIOR_STRENGTH))

Der letzte Faktor ist eine SCHRUMPFUNG GEGEN DIE NEUTRALLAGE: Bei `n_k = 0` ergibt sich exakt der
Startwert, der Nullzustand faellt ohne Sonderfall heraus. Die Division wird trotzdem JE KRITERIUM
vor ihrer Ausfuehrung abgefangen und nicht je Ableitung - ein Kriterium ohne Stimmen kann neben
einem mit Stimmen stehen, und ein `NaN` aus `0/0` vergiftete danach jeden Qualitaetswert aller
Projekte, ohne einen Fehler zu erzeugen (S12).

NUR VORZEICHEN werden verglichen, nie Betraege: Sonst waere ein Kriterium mit gestauchtem
Wertebereich strukturell benachteiligt.

ITERIERT WIRD UEBER DEN UEBERGEBENEN SCHLUESSELSATZ, nie ueber die vorliegenden Messwerte:
`photo_criterion_scores` traegt Kriterien mit Inhaltsaussage, die `quality.py` bewusst nicht
gewichtet, und der umgekehrte Weg braechte eines davon in den Qualitaetswert (G2).

DIE FALLZAHL IST UNGEWICHTET, die Stimmenzahl gewichtet. Eine gewichtete Zahl als Fallzahl
behauptete Korrekturen, die niemand vorgenommen hat.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from itertools import product

from photosort.selection import motif_is_present

# Unterhalb dieser gespeicherten Staerke gilt ein Motiv als GAR NICHT GENANNT, darueber (und
# unterhalb der Praesenzgrenze) als genannt, aber zu schwach. INKLUSIV nach oben: Der Wert an der
# Grenze ist genannt.
#
# Eigene Konstante und ausdruecklich KEIN Anzeigeband aus `motifs.py`: Die Anzeigebaender teilen
# die Skala fuer das Auge, und eine spaetere Verschiebung dort duerfte die Fehlerklassifizierung
# der Diagnose nicht mitverschieben. Dokumentiert-unkalibrierter Startwert in der Klasse von
# `LOCAL_CORRECTION_SPAN`: Ab welcher Staerke ein Modell ein Motiv "erwaehnt" hat, ist gegen einen
# Fotokorpus zu kalibrieren, den das Repository nach der Bilddaten-Regel nicht hat.
MOTIF_ABSENT_THRESHOLD = 0.2

# Die halbe Breite des Bandes, in dem sich ein abgeleitetes Gewicht um seinen Startwert bewegen
# darf. STRIKT KLEINER ALS 1, und das ist die eigentliche Aussage: Bei `>= 1` erreichte ein
# durchgaengig widersprochenes Kriterium das Gewicht null oder ein negatives - es waere
# ausgeschaltet bzw. invertiert statt abgewertet, und ein Gewicht null liesse es aus der
# Renormierung in `quality.py::local_correction` ganz herausfallen.
FEEDBACK_WEIGHT_SPAN = 0.3

# Die Stimmenzahl, bei der die Schrumpfung genau die Haelfte der Bandbreite freigibt
# (`n / (n + PRIOR_STRENGTH) = 0,5`). STRIKT POSITIV: Bei `0` entfiele die Schrumpfung und die
# erste einzelne Stimme schluege mit der vollen Bandbreite durch. Ebenfalls ein
# dokumentiert-unkalibrierter Startwert.
PRIOR_STRENGTH = 10.0

# Die beiden `kind`-Werte, auf die die Motivfehler-Klassifizierung ueberhaupt reagiert. Sie stehen
# hier als Zeichenketten, weil dieses Modul `photosort.models` nicht importiert (Reinheit); dass
# sie mit `FeedbackEventKind` uebereinstimmen, haelt ein Waechterfall in
# `tests/test_feedback_diagnosis.py` fest.
MOTIF_ADDED_KIND = "motif_added"
MOTIF_DROPPED_KIND = "motif_dropped"


class MotifErrorCase(enum.StrEnum):
    """Die drei Arten, auf die das Modell bei einem Motiv danebenlag.

    `TOO_WEAK` und `MISSING` sind BEIDE "das Motiv ist da, das Modell sieht es nicht" und trotzdem
    verschiedene Befunde: Das eine ist eine Schwellenfrage, das andere eine Erkennungsluecke."""

    TOO_WEAK = "too_weak"
    MISSING = "missing"
    OVERCALLED = "overcalled"


def classify_motif_error(kind: str, model_strength: float | None) -> MotifErrorCase | None:
    """Welchen Modellfehler eine Motivkorrektur anzeigt - oder `None`, wenn sie keinen anzeigt.

    NICHT JEDE KORREKTUR IST EIN MODELLFEHLER, und das ist der Kern dieser Funktion: Ein
    hinzugefuegtes Motiv, das das Modell ohnehin bereits traegt, ein weggenommenes, das es nie
    behauptet hat, und jede Ruecknahme einer Korrektur sagen ueber das Modell nichts aus. Sie als
    Fehler zu zaehlen bliesse die drei Fehlerzahlen um genau die Faelle auf, in denen das Modell
    recht hatte.

    Die Praesenzgrenze kommt ueber `selection.py::motif_is_present`, NIE als Zahl: Geteilt wird
    das Praedikat, sonst stuende die Zahl zwar an einer Stelle, der Vergleichsoperator aber an
    zweien.

    `model_strength` ist die EINGEFRORENE gespeicherte Staerke aus dem Ereignis; `None` heisst
    "das Modell hat dieses Motiv nie genannt"."""
    if kind == MOTIF_ADDED_KIND:
        if model_strength is None:
            return MotifErrorCase.MISSING
        if motif_is_present(model_strength):
            return None
        if model_strength < MOTIF_ABSENT_THRESHOLD:
            return MotifErrorCase.MISSING
        return MotifErrorCase.TOO_WEAK
    if kind == MOTIF_DROPPED_KIND:
        if model_strength is None or not motif_is_present(model_strength):
            return None
        return MotifErrorCase.OVERCALLED
    return None


@dataclass(frozen=True)
class MotifCorrectionRecord:
    """Eine Motivkorrektur, so weit die Fehlerklassifizierung sie braucht: ihre Art und die
    EINGEFRORENE gespeicherte Modellstaerke."""

    kind: str
    model_strength: float | None


def count_motif_errors(corrections: Iterable[MotifCorrectionRecord]) -> dict[MotifErrorCase, int]:
    """Die drei Fehlerzahlen - mit einem Eintrag JE FALL, auch fuer den mit null Vorkommen.

    Eine Korrektur ohne Modellfehler zaehlt NIRGENDS mit; es gibt keine vierte Klasse, in der sie
    landete. Die Bezugsgroesse der drei Zahlen ist die Gesamtzahl der Korrekturen und nicht ihre
    eigene Summe - sie sind ausdruecklich nicht erschoepfend."""
    tally = dict.fromkeys(MotifErrorCase, 0)
    for correction in corrections:
        case = classify_motif_error(correction.kind, correction.model_strength)
        if case is not None:
            tally[case] += 1
    return tally


class ExchangeKind(enum.StrEnum):
    """Die drei Tauschklassen. Sie sind DISJUNKT und ERSCHOEPFEND und werden nirgends summiert:
    `UNDETERMINED` ist kein Restposten, sondern eine eigene ausgewiesene Klasse (D3)."""

    WITHIN_LEVEL = "within_level"
    ACROSS_LEVEL = "across_level"
    UNDETERMINED = "undetermined"


def classify_exchange(level: int | None, replaced_level: int | None) -> ExchangeKind:
    """In welcher Klasse ein Austausch steht - gelesen aus den beiden EINGEFROREN Modellstufen.

    Ein Paar mit fehlender Stufe ist `UNDETERMINED` und wird keiner der beiden anderen Klassen
    zugeschlagen: Ob der Nutzer innerhalb der Modellmeinung oder gegen sie getauscht hat, ist
    ohne beide Stufen nicht entscheidbar, und "keine Aussage" ist etwas anderes als "keine
    Abweichung"."""
    if level is None or replaced_level is None:
        return ExchangeKind.UNDETERMINED
    return ExchangeKind.WITHIN_LEVEL if level == replaced_level else ExchangeKind.ACROSS_LEVEL


def preferred_lower_rated(quality: float | None, replaced_quality: float | None) -> bool | None:
    """Wurde beim Austausch das SCHLECHTER bewertete Bild vorgezogen? `None` heisst "nicht
    vergleichbar" - Gleichstand oder ein fehlender Wert.

    Der Gleichstand wird keiner der beiden Seiten zugeschlagen (D4): `False` hiesse hier "ein
    besser bewertetes Bild vorgezogen", und das ist eine Aussage, die ein Gleichstand nicht
    traegt."""
    if quality is None or replaced_quality is None or quality == replaced_quality:
        return None
    return quality < replaced_quality


@dataclass(frozen=True)
class ExchangeRecord:
    """Ein Austausch, so weit die Auszaehlung ihn braucht: beide eingefrorenen Modellstufen und
    beide eingefrorenen Qualitaetswerte."""

    level: int | None
    replaced_level: int | None
    quality: float | None
    replaced_quality: float | None


@dataclass(frozen=True)
class ExchangeStats:
    """Die Bilanz EINER Tauschklasse.

    `quality_incomparable_count` haelt die Paare mit gleichem und die mit fehlendem
    Qualitaetswert. Sie gehen in `preferred_lower_rated_count` NICHT ein und werden auch nicht
    seinem Gegenstueck zugeschlagen (D4): Ohne diese eigene Zahl laese sich ein gestiegener
    Anteil "schlechteres Bild vorgezogen" nicht von einem gewachsenen Anteil unvergleichbarer
    Paare unterscheiden."""

    count: int = 0
    preferred_lower_rated_count: int = 0
    quality_incomparable_count: int = 0


def summarize_exchanges(records: Iterable[ExchangeRecord]) -> dict[ExchangeKind, ExchangeStats]:
    """Die Austausche je Klasse - mit einem Eintrag je Klasse, auch fuer die ohne Vorkommen.

    DIE DREI KLASSEN WERDEN HIER NICHT SUMMIERT und tauchen auch als Summe nirgends auf (D3). Sie
    sind disjunkt und erschoepfend, ihre Summe waere also die Gesamtzahl der Austausche - eine
    Zahl, die die Aussage ueber die lokalen Kriterien mit der ueber die Modellstufe mischte."""
    counts = dict.fromkeys(ExchangeKind, 0)
    lower_rated = dict.fromkeys(ExchangeKind, 0)
    incomparable = dict.fromkeys(ExchangeKind, 0)
    for record in records:
        kind = classify_exchange(record.level, record.replaced_level)
        counts[kind] += 1
        preference = preferred_lower_rated(record.quality, record.replaced_quality)
        if preference is None:
            incomparable[kind] += 1
        elif preference:
            lower_rated[kind] += 1
    return {
        kind: ExchangeStats(
            count=counts[kind],
            preferred_lower_rated_count=lower_rated[kind],
            quality_incomparable_count=incomparable[kind],
        )
        for kind in ExchangeKind
    }


@dataclass(frozen=True)
class PreferencePair:
    """EIN "der Nutzer zog `preferred` dem `rejected` vor" samt seinem Gewicht.

    Die beiden Abbildungen tragen die LOKALEN Kriterienwerte der beiden Fotos - live gelesen und
    nicht eingefroren: Sie sind eine deterministische Messung an denselben Pixeln, keine je Lauf
    neu erfragte Fremdaussage."""

    preferred: Mapping[str, float] = field(default_factory=dict)
    rejected: Mapping[str, float] = field(default_factory=dict)
    weight: float = 1.0


@dataclass(frozen=True)
class FinalDecisionRecord:
    """Ein Ereignis der gemeinsamen Endauswahl, so weit die Paarbildung es braucht."""

    criterion_scoring_run_id: int | None
    event_id: int | None
    level: int | None
    included: bool
    weight: float
    values: Mapping[str, float] = field(default_factory=dict)


def final_decision_pairs(records: Iterable[FinalDecisionRecord]) -> list[PreferencePair]:
    """Die Paare aus der gemeinsamen Endauswahl: je `(Lauf, Ereignis, Stufe)` jedes aufgenommene
    gegen jedes herausgenommene Foto (G5).

    DIE GRUPPIERUNG UEBER DAS EINGEFRORENE EREIGNIS HAELT DIE GEGENUEBERSTELLUNG LOKAL - ohne sie
    verglichen wir einen Sonnenuntergang von Tag 1 gegen ein Abendessen von Tag 5, und die
    Zustimmungsrate eines Kriteriums saehe genauso aus.

    Ein Ereignis ohne Lauf-, Event- oder Stufenbezug bildet KEIN Paar. Bei den ersten beiden ist
    die Gruppe unbestimmt; bei der Stufe ist "derselben Stufe" fuer `None` nicht erfuellbar -
    dieselbe Entscheidung, die einen Austausch ohne Stufe `undetermined` macht.

    Das Paar traegt das Gewicht des AUFGENOMMENEN Ereignisses. Beide Seiten tragen es gleich
    (`FINAL_DECISION_WEIGHT`, gesetzt an der einen Schreibstelle); ein Produkt beider quadrierte
    es."""
    groups: dict[tuple[int, int, int], tuple[list[FinalDecisionRecord], list[FinalDecisionRecord]]]
    groups = {}
    for record in records:
        if (
            record.criterion_scoring_run_id is None
            or record.event_id is None
            or record.level is None
        ):
            continue
        key = (record.criterion_scoring_run_id, record.event_id, record.level)
        taken, removed = groups.setdefault(key, ([], []))
        (taken if record.included else removed).append(record)

    return [
        PreferencePair(preferred=taken.values, rejected=removed.values, weight=taken.weight)
        for taken_records, removed_records in groups.values()
        for taken, removed in product(taken_records, removed_records)
    ]


@dataclass(frozen=True)
class CriterionAgreement:
    """Die Bilanz EINES Kriteriums ueber alle Paare.

    `case_count` ist die UNGEWICHTETE Zahl der auswertbaren Paare - beide Fotos tragen den
    Messwert, Gleichstand eingeschlossen (D5). `votes` ist die GEWICHTETE Stimmenzahl `n_k` und
    zaehlt den Gleichstand ausdruecklich NICHT mit: Ein Paar kann auswertbar sein und trotzdem
    nicht abstimmen, und genau dieser Unterschied ist der zweite entartete Weg des Verfahrens.

    `agreement` ist bei `votes == 0` exakt `0.0` und damit die Neutrallage - nie ein `NaN` aus
    einer Division durch null (S12)."""

    case_count: int
    votes: float
    agreement: float


def criterion_agreement(
    pairs: Iterable[PreferencePair], keys: Iterable[str]
) -> dict[str, CriterionAgreement]:
    """Die Bilanz je Kriterium aus `keys` - ein Eintrag fuer JEDEN Schluessel, auch fuer den ohne
    ein einziges Paar.

    Iteriert wird ueber `keys` und nicht ueber die vorliegenden Messwerte (siehe Modulkopf); ein
    gemessenes Kriterium ausserhalb von `keys` erscheint nicht im Ergebnis."""
    requested = list(dict.fromkeys(keys))
    cases = dict.fromkeys(requested, 0)
    approving = dict.fromkeys(requested, 0.0)
    rejecting = dict.fromkeys(requested, 0.0)

    for pair in pairs:
        for key in requested:
            if key not in pair.preferred or key not in pair.rejected:
                continue
            cases[key] += 1
            preferred_value, rejected_value = pair.preferred[key], pair.rejected[key]
            if preferred_value > rejected_value:
                approving[key] += pair.weight
            elif preferred_value < rejected_value:
                rejecting[key] += pair.weight

    result: dict[str, CriterionAgreement] = {}
    for key in requested:
        votes = approving[key] + rejecting[key]
        # DIE DIVISION JE KRITERIUM ABGEFANGEN, vor ihrer Ausfuehrung.
        agreement = 0.0 if votes <= 0.0 else (approving[key] - rejecting[key]) / votes
        result[key] = CriterionAgreement(case_count=cases[key], votes=votes, agreement=agreement)
    return result


def derive_weights(
    agreements: Mapping[str, CriterionAgreement], baseline: Mapping[str, float]
) -> dict[str, float]:
    """Die abgeleiteten Gewichte - der Startwert, um die geschrumpfte Zustimmung verschoben.

    DER SCHLUESSELSATZ DES ERGEBNISSES IST EXAKT DER DES STARTWERTS, in beide Richtungen: Ein
    Startwertschluessel ohne Bilanz behaelt seinen Wert, ein der Startwerttabelle unbekannter
    Bilanzschluessel wird verworfen (G2). Ein `{**baseline, **derived}` besaesse nur die erste
    Haelfte - und genau das ist der Weg, auf dem ein Kriterium mit Inhaltsaussage in den
    Qualitaetswert geriete.

    Bei `votes == 0` steht der Startwert IDENTISCH im Ergebnis, nicht sein Produkt mit `1.0`: Der
    Nullzustand ist der Startwert und nicht etwas, das ihm bis auf Rundung gleicht."""
    derived: dict[str, float] = {}
    for key, start in baseline.items():
        entry = agreements.get(key)
        if entry is None or entry.votes <= 0.0:
            derived[key] = start
            continue
        shrinkage = entry.votes / (entry.votes + PRIOR_STRENGTH)
        derived[key] = start * (1.0 + FEEDBACK_WEIGHT_SPAN * entry.agreement * shrinkage)
    return derived
