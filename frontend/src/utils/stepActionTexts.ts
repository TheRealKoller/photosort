import type { StepId } from './pipelineSteps'

/*
 * Die Beschriftungen aller Aktionen der Schrittseiten - die einzige Quelle. Seiten, Sperrgründe
 * der Schrittleiste (`getBlockedReason`) und die Ablaufübersicht (`OVERVIEW_TEXTS`) lesen von
 * hier. Blattmodul ohne Laufzeit-Import: `pipelineSteps.ts` und `stepActions.ts` greifen beide
 * darauf zu, ein Import in eine der beiden Richtungen schlösse einen Zyklus.
 */

/** Die Schritte mit eigenem Lauf. */
export type RunStepId = Exclude<StepId, 'kuratierung'>

export interface RunStepTexts {
  /** Startknopf, zugleich Wiederholung nach einem Fehlschlag. */
  start: string
  /** Derselbe Knopf, gesperrt, solange der Lauf läuft. */
  running: string
  /** Der nachrangige Knopf nach einem erfolgreichen Lauf samt dauerhaft sichtbarem Erklärsatz. */
  rerun: { label: string; explanation: string }
}

export const RUN_STEP_TEXTS: Record<RunStepId, RunStepTexts> = {
  scan: {
    start: 'Fotos einlesen',
    running: 'Fotos werden eingelesen…',
    rerun: {
      label: 'Erneut einlesen',
      // Belegt am Backend: Ein Scan legt keinen Ausschuss-Lauf an und lässt `gate_confirmed_at`
      // unberührt; die Klassifizierung nimmt nur Fotos mit Ausschuss-Bewertung auf.
      explanation:
        'Erfasst neue, geänderte und entfernte Fotos im verknüpften Ordner. Ein bestätigter Ausschuss bleibt bestätigt; neu hinzugekommene Fotos prüft erst „Erneut erkennen“, vorher fließen sie nicht in die Klassifizierung ein.',
    },
  },
  ausschuss: {
    start: 'Vorschläge erkennen',
    running: 'Vorschläge werden erkannt…',
    rerun: {
      label: 'Erneut erkennen',
      explanation:
        'Bildet die Vorschläge neu. Ein bestehender Abschluss wird aufgehoben, die Klassifizierung ist bis zur erneuten Bestätigung gesperrt. Deine Einzelentscheidungen bleiben erhalten.',
    },
  },
  kriterien: {
    start: 'Klassifizierung starten',
    running: 'Klassifizierung läuft…',
    rerun: {
      label: 'Erneut klassifizieren',
      // Belegt am Backend: Der Album-Entwurf liest den Vorschlag des letzten erfolgreichen Laufs;
      // eigene Albumentscheidungen und die Endauswahl hängen an keinem Lauf.
      explanation:
        'Berechnet Kategorien und Bewertungen aller verbleibenden Fotos neu und bildet daraus einen neuen Album-Vorschlag. Eure Änderungen an den Album-Entwürfen und die Endauswahl bleiben erhalten.',
    },
  },
}

/** Ergänzung der Erklärzeile im Kopf des Ausschusses: Die Erkennung sortiert nichts aus. */
export const AUSSCHUSS_NOTHING_SORTED_TEXT =
  'Es wird noch nichts aussortiert — du entscheidest danach.'

/** Die Abschluss-Aktion ohne Anzahl - auch der Wortlaut im Sperrgrund der Schrittleiste. */
export const AUSSCHUSS_CONFIRM_LABEL = 'Ausschuss abschließen'

/** Die Weiterführung, nach dem ZIELschritt geschlüsselt. */
export const NEXT_STEP_LABELS: Record<Exclude<StepId, 'scan'>, string> = {
  ausschuss: 'Weiter zum Ausschuss',
  kriterien: 'Weiter zur Klassifizierung',
  kuratierung: 'Weiter zur Kuratierung',
}

/** Der neutrale Text, wenn der Folgeschritt abgeschaltet ist - kein Fehler, keine Aktion. */
export const NEXT_UNAVAILABLE_TEXT =
  'Die Klassifizierung ist derzeit ausgeschaltet — es gibt keinen nächsten Schritt.'

/** Die einzige Aktion der Kuratierung. */
export const ALBUM_OPEN_LABEL = 'Album-Entwurf öffnen'
