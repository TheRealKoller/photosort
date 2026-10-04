import type { OverviewEntryId, OverviewEntryState, StepId } from './pipelineSteps'
import { PIPELINE_STEPS } from './pipelineSteps'
import { STATION_LABELS } from './projectRoutes'
import { AUSSCHUSS_CONFIRM_LABEL, RUN_STEP_TEXTS } from './stepActionTexts'

/*
 * Die festen Erklärtexte der Ablaufübersicht. Sie verwenden keinen Begriff, der nicht schon in der
 * Oberfläche steht; jede in „…" zitierte Bezeichnung steht wörtlich an ihrer Bedienstelle
 * (geprüft in `workflowOverview.structure.test.ts`). Als `Record<OverviewEntryId, …>` typisiert,
 * damit ein Eintrag ohne Text ein Typfehler ist.
 */

export type WorkerKind = 'beides' | 'läuft von selbst' | 'braucht dich'

export interface OverviewEntryText {
  /** Wozu es den Schritt gibt - höchstens zwei Sätze. */
  purpose: string
  /** Die Kennzeichnung „Wer arbeitet" als Wort, dahinter ihre Erläuterung. */
  worker: { kind: WorkerKind; detail: string }
  /** Wer ihn erledigt - nur bei Schritten mit Handlung. */
  responsibility: string | null
  /** Was vorher erledigt sein muss und warum - nennt den Schritt `step` mit seinem Namen. */
  prerequisite: { step: StepId; text: string } | null
}

export const OVERVIEW_TEXTS: Record<OverviewEntryId, OverviewEntryText> = {
  scan: {
    purpose:
      'PhotoSort durchsucht den verknüpften OpenCloud-Ordner und nimmt die Fotos ins Projekt auf; die Original-Fotos bleiben auf OpenCloud unverändert. Ein neuer Scan übernimmt später neue, geänderte und entfernte Fotos.',
    worker: {
      kind: 'beides',
      detail: `du startest ihn mit „${RUN_STEP_TEXTS.scan.start}“, den Rest erledigt PhotoSort.`,
    },
    responsibility: 'einer von euch, einmal für das ganze Projekt',
    prerequisite: null,
  },
  ausschuss: {
    purpose: `PhotoSort schlägt unscharfe, überbelichtete oder doppelte Fotos als Ausschuss vor. Du gehst die Vorschläge durch, korrigierst, wo nötig, und bestätigst mit „${AUSSCHUSS_CONFIRM_LABEL}“.`,
    worker: {
      kind: 'beides',
      detail: `du startest mit „${RUN_STEP_TEXTS.ausschuss.start}“, PhotoSort erkennt, du prüfst und bestätigst.`,
    },
    responsibility: 'einer von euch, einmal für das ganze Projekt',
    prerequisite: {
      step: 'scan',
      text: 'der Scan – geprüft werden nur Fotos, die der Scan ins Projekt aufgenommen hat.',
    },
  },
  kriterien: {
    purpose:
      'PhotoSort bewertet jedes Foto, das nach dem Ausschuss übrig ist, nach Qualität und Bildinhalt und bildet daraus eine Rangfolge je Foto-Moment. Darauf bauen Kuratierung, Album-Entwurf und Endauswahl auf.',
    worker: {
      kind: 'beides',
      detail: `du startest mit „${RUN_STEP_TEXTS.kriterien.start}“ und wählst, ob die Cloud-Bilderkennung mitläuft; den Rest erledigt PhotoSort.`,
    },
    responsibility: 'einer von euch, einmal für das ganze Projekt',
    prerequisite: {
      step: 'ausschuss',
      text: 'der bestätigte Ausschuss – damit aussortierte Fotos weder bewertet noch an den Cloud-Anbieter geschickt werden.',
    },
  },
  kuratierung: {
    purpose:
      'Aus der Klassifizierung stellt PhotoSort einen Vorschlag zusammen, der alle Foto-Momente abdeckt und in jedem die vorkommenden Motive mischt. Wie groß er ungefähr wird, legst du bei Bedarf mit dem Richtwert fest.',
    worker: {
      kind: 'läuft von selbst',
      detail: 'den Richtwert kannst du ändern, musst du aber nicht.',
    },
    responsibility: null,
    prerequisite: {
      step: 'kriterien',
      text: 'die abgeschlossene Klassifizierung – der Vorschlag baut auf ihrer Rangfolge auf.',
    },
  },
  album: {
    purpose:
      'Hier steht der Vorschlag als dein eigener Entwurf. Du greifst nur ein, wo dich etwas stört – streichen, tauschen oder ein Foto hinzufügen –, und bestätigen musst du nichts.',
    worker: { kind: 'beides', detail: 'PhotoSort schlägt vor, du greifst ein.' },
    responsibility: 'jeder für sich – jeder von euch hat seinen eigenen Entwurf',
    prerequisite: {
      step: 'kriterien',
      text: 'die abgeschlossene Klassifizierung, denn aus ihr entsteht der Vorschlag.',
    },
  },
  selection: {
    purpose:
      'PhotoSort vergleicht eure beiden Album-Entwürfe und zeigt unter „Unterschiede“ die Fotos, bei denen ihr uneins seid. Darüber entscheidet ihr gemeinsam; die ganze Auswahl steht unter „Endauswahl“.',
    worker: {
      kind: 'braucht dich',
      detail: 'PhotoSort zeigt die Unterschiede, entscheiden müsst ihr.',
    },
    responsibility: 'ihr beide gemeinsam',
    prerequisite: {
      step: 'kriterien',
      text: 'die abgeschlossene Klassifizierung, denn ohne Vorschlag gibt es nichts zu vergleichen. Am meisten bringt sie, wenn ihr beide euren Album-Entwurf durchgesehen habt.',
    },
  },
}

/** Der sichtbare Name eines Eintrags: Schritte aus `PIPELINE_STEPS`, Stationen aus
 * `STATION_LABELS` - keine zweite Kopie. */
export function overviewEntryLabel(id: OverviewEntryId): string {
  if (id === 'album' || id === 'selection') {
    return STATION_LABELS[id]
  }
  return PIPELINE_STEPS.find((step) => step.id === id)?.label ?? id
}

/** Das Zustandswort in der Kopfzeile eines Eintrags - immer als Wort, nie nur als Farbe. */
export const OVERVIEW_STATE_WORDS: Record<OverviewEntryState, string> = {
  erledigt: 'erledigt',
  aktuell: 'aktuell',
  offen: 'offen',
  gesperrt: 'gesperrt',
  abgeschaltet: 'abgeschaltet',
  jederzeit: 'jederzeit möglich',
}
