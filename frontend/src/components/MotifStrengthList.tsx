import type { MotifAssessmentOut, MotifKey, MotifSetOut, MotifStrengthOut } from '../api/types'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Progress } from './ui/progress'
import { Skeleton } from './ui/skeleton'
import {
  formatCriterionPercent,
  formatDateTime,
  formatProviderLabel,
} from '../utils/formatStats'
import { formatMotifKey, isLocallyAssessable } from '../utils/motifLabels'
import type { MotifCorrectionError } from '../hooks/useMotifCorrection'

/**
 * Die acht Motive eines Fotos samt ihrer wirksamen Staerke - Design-System-Muster "Mehrwertige
 * Eigenschaft als Staerkeliste, nicht als Zuordnung".
 *
 * EIN Baustein mit Prop `editable`: bedienbar in der Einzelbildansicht, schreibgeschuetzt im
 * Info-Popover der Kachel. Vier Festlegungen tragen die Darstellung:
 *
 * 1. Die Zeilenreihenfolge ist die REGISTRY-Reihenfolge aus `GET /motifs`, auf jedem Foto
 *    dieselbe, und wird NIE nach Staerke sortiert. Die Staerke wird je Schluessel aus `motifs`
 *    nachgeschlagen, nie ueber den Index der Antwortliste. Acht gleichnamige Korrekturschalter,
 *    die von Foto zu Foto die Position wechseln, laden zum Fehlklick ein - und ein Fehlklick
 *    schreibt hier einen Datenwert.
 * 2. FEHLT DIE KOPFZEILE, gibt es KEINE LISTE, sondern einen Satz. Acht Nullzeilen sind von
 *    "nichts erkannt" nicht zu unterscheiden; der Unterschied ist damit strukturell und nicht
 *    farblich.
 * 3. Es gibt KEIN berechnetes Urteil "nichts erkannt" - dafuer braeuchte die Oberflaeche eine
 *    Schwelle, und die schafft diese Story ab. Ebenso erscheint hier KEIN Bandwort: es lehrte den
 *    Nutzer genau die Zugehoerigkeitsschwelle, die es im Auswahlpfad nicht gibt.
 * 4. Die Staerke wird NIE allein ueber Farbe getragen: der Balken ist `aria-hidden` und neutral
 *    gefuellt (kein Bewertungston), der eigentliche Text ist die Prozentzahl bzw. das
 *    Korrekturwort. Der Korrekturzustand steht dreifach - `aria-pressed`, Wortwechsel in der
 *    Wertspalte, `data-motif-corrected`.
 *
 * Bei 360px: Name und Wert in einer Zeile, Balken darunter ueber die volle Breite, Schaltflaechen
 * in einer eigenen `flex-wrap`-Zeile - EIN DOM-Baum, kein breitenabhaengiger Zweig.
 */
interface MotifStrengthListProps {
  /** Das geladene Set. `undefined` waehrend des Ladens bzw. nach einem Fehlschlag. */
  motifSet: MotifSetOut | undefined
  motifSetLoading?: boolean
  /** Der Fehlertext des fehlgeschlagenen `GET /motifs`. */
  motifSetError?: string
  onMotifSetRetry?: () => void
  /** `null` heisst "noch nicht klassifiziert" - dann erscheint der Satz statt der Liste. */
  assessment: MotifAssessmentOut | null | undefined
  motifs: readonly MotifStrengthOut[] | undefined
  editable: boolean
  onCorrect?: (motifKey: MotifKey, applies: boolean) => void
  onWithdraw?: (motifKey: MotifKey) => void
  /** Das Motiv mit laufender Korrektur - nur DIESE Zeile wird gesperrt, die uebrige Liste bleibt
   * bedienbar. */
  pendingMotifKey?: MotifKey | null
  error?: MotifCorrectionError | null
}

const UNASSESSED_TEXT =
  'Noch nicht klassifiziert — dieses Foto hat noch keinen Klassifizierungslauf gesehen.'

const EXCLUDED_TEXT =
  'Als Dokument oder Bildschirmabbildung erkannt — dieses Foto erscheint in keiner ' +
  'Motivauswahl. Diese Einstufung lässt sich nicht von Hand ändern; ein neuer ' +
  'Klassifizierungslauf beurteilt das Foto erneut.'

const LOCAL_BASIS_TEXT = 'Grundlage: lokale Erkennung — sie kann nicht jedes Motiv beurteilen.'

const NOT_LOCALLY_ASSESSABLE_TEXT = 'lokal nicht beurteilbar'

/** Acht Platzhalterzeilen statt eines Spinners - dieselbe Zeilenzahl wie die spaetere Liste, damit
 * der Bereich beim Eintrudeln nicht springt. `rounded-lg` wie eine Listenzeile. */
function SkeletonRows() {
  return (
    <div className="flex flex-col gap-3" role="status" aria-label="Motive werden geladen">
      {Array.from({ length: 8 }, (_, index) => (
        <Skeleton key={index} className="h-8 rounded-lg" data-testid="motif-skeleton-row" />
      ))}
    </div>
  )
}

function BasisLine({ assessment }: { assessment: MotifAssessmentOut }) {
  // `text-xs text-text`, KEIN `Alert`: die Grundlage ist eine Auskunft, kein Fehler.
  return (
    <p className="text-xs text-text">
      {assessment.source === 'local'
        ? LOCAL_BASIS_TEXT
        : `Grundlage: Cloud-Klassifizierung (${formatProviderLabel(assessment.provider ?? '')}), ` +
          formatDateTime(assessment.computed_at)}
    </p>
  )
}

/**
 * Das Glossar: EIN einziges `<details>` am Listenende.
 *
 * Kein Info-Ausloeser je Zeile (acht zusaetzliche Trefferflaechen fuer Nachschlagetext) und kein
 * Popover - die Liste wird ihrerseits in einem Popover gerendert, und ein zweites Panel darin ist
 * nicht zulaessig.
 *
 * SICHERHEIT (S19): Registry-Text ausschliesslich als React-TEXTKNOTEN - nie ueber
 * `dangerouslySetInnerHTML`, nie als HTML-String-Prop, und er fliesst in kein `href`, `src`,
 * `style` und keinen `url()`-Kontext.
 */
function Glossary({ motifSet }: { motifSet: MotifSetOut }) {
  return (
    <details className="text-xs text-text">
      <summary className="cursor-pointer underline decoration-dotted">
        Was die acht Motive bedeuten
      </summary>
      <dl className="mt-2 flex flex-col gap-2">
        {motifSet.items.map((item) => (
          <div key={item.key} className="flex flex-col gap-1">
            <dt className="font-semibold text-text-h">{item.display_name}</dt>
            <dd className="flex flex-col gap-1">
              <span>{item.definition}</span>
              <span className="text-text-muted">{`Abgrenzung: ${item.delimitation}`}</span>
            </dd>
          </div>
        ))}
      </dl>
    </details>
  )
}

function correctionState(correction: boolean | null): 'applies' | 'rejected' | undefined {
  // Auf `=== null` geprueft, nie auf Falsyness: `false` ist eine Aussage, keine Abwesenheit.
  if (correction === null) {
    return undefined
  }
  return correction ? 'applies' : 'rejected'
}

interface RowProps {
  motifKey: MotifKey
  displayName: string
  strength: MotifStrengthOut | undefined
  showLocalGap: boolean
  editable: boolean
  busy: boolean
  onCorrect?: (motifKey: MotifKey, applies: boolean) => void
  onWithdraw?: (motifKey: MotifKey) => void
}

function MotifRow({
  motifKey,
  displayName,
  strength,
  showLocalGap,
  editable,
  busy,
  onCorrect,
  onWithdraw,
}: RowProps) {
  const value = strength?.strength ?? 0
  const correction = strength?.correction ?? null
  const state = correctionState(correction)

  return (
    <li
      className="flex flex-col gap-2 border-b border-separator pb-3 last:border-b-0 last:pb-0"
      data-motif-key={motifKey}
      data-motif-corrected={state}
    >
      <div className="flex items-baseline justify-between gap-3">
        {/* Die laengsten Namen muessen umbrechen duerfen. */}
        <span className="break-words text-text-h">{displayName}</span>
        {state !== undefined ? (
          // STATT der Prozentzahl - die ueberstimmte Modellzahl steht nicht daneben.
          <span className="shrink-0 text-xs text-text-h">
            {state === 'applies' ? 'Trifft zu (korrigiert)' : 'Trifft nicht zu (korrigiert)'}
          </span>
        ) : showLocalGap ? (
          // Weder Balken noch Zahl: ein `0 %` waere hier die Aussage "nicht zu sehen" statt
          // "nicht angesehen".
          <span className="shrink-0 text-xs text-text-muted">{NOT_LOCALLY_ASSESSABLE_TEXT}</span>
        ) : (
          <span className="shrink-0 font-mono text-xs">{formatCriterionPercent(value)}</span>
        )}
      </div>
      {!(showLocalGap && state === undefined) && (
        // Das Verhaeltnis traegt `value`/`max` - nie ein Inline-Style und nie ein willkuerlicher
        // Wert. Bei einer Korrektur ist der Balken voll bzw. leer, weil die wirksame Staerke
        // bereits 1 bzw. 0 ist.
        <Progress tone="neutral" value={value} max={1} aria-hidden="true" className="h-2" />
      )}
      {editable && (
        // `gap-3` ist die Pflichtgrenze zwischen aufgespannten Trefferflaechen. `h-8` + `tap-target`
        // statt `h-11`: die Korrektur ist nicht der heisse Pfad.
        <div className="flex flex-wrap gap-3">
          <Button
            type="button"
            size="sm"
            variant={state === 'applies' ? 'default' : 'outline'}
            aria-pressed={state === 'applies'}
            aria-label={`Trifft zu: ${displayName}`}
            busy={busy}
            onClick={() => onCorrect?.(motifKey, true)}
          >
            Trifft zu
          </Button>
          <Button
            type="button"
            size="sm"
            variant={state === 'rejected' ? 'default' : 'outline'}
            aria-pressed={state === 'rejected'}
            aria-label={`Trifft nicht zu: ${displayName}`}
            busy={busy}
            onClick={() => onCorrect?.(motifKey, false)}
          >
            Trifft nicht zu
          </Button>
          {state !== undefined && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label={`Zurücknehmen: ${displayName}`}
              busy={busy}
              onClick={() => onWithdraw?.(motifKey)}
            >
              Zurücknehmen
            </Button>
          )}
        </div>
      )}
    </li>
  )
}

export function MotifStrengthList({
  motifSet,
  motifSetLoading = false,
  motifSetError,
  onMotifSetRetry,
  assessment,
  motifs,
  editable,
  onCorrect,
  onWithdraw,
  pendingMotifKey = null,
  error = null,
}: MotifStrengthListProps) {
  if (motifSetError !== undefined) {
    // Keine Liste mit Rohschluesseln - lieber gar keine Liste.
    return <Alert onRetry={onMotifSetRetry}>{motifSetError}</Alert>
  }
  if (motifSetLoading || motifSet === undefined) {
    return <SkeletonRows />
  }

  // DER STRUKTURELLE Unterschied: Satz statt Liste, nicht acht Nullzeilen.
  if (assessment === null || assessment === undefined) {
    return <p className="text-sm text-text">{UNASSESSED_TEXT}</p>
  }

  const excluded = assessment.excluded_document
  // Eine ausgeschlossene Einstufung ist nicht von Hand korrigierbar: die Liste bleibt EINSEHBAR,
  // aber ohne Bedienelemente. Kein deaktivierter Schalter, nach dem niemand suchen soll.
  const rowsEditable = editable && !excluded
  const byKey = new Map((motifs ?? []).map((entry) => [entry.key, entry]))

  return (
    <div className="flex flex-col gap-3">
      {excluded && <p className="text-sm text-text">{EXCLUDED_TEXT}</p>}
      <BasisLine assessment={assessment} />
      <ul aria-label="Motive" className="flex flex-col gap-3">
        {motifSet.items.map((item) => (
          <MotifRow
            key={item.key}
            motifKey={item.key}
            displayName={formatMotifKey(item.key, motifSet.items)}
            strength={byKey.get(item.key)}
            showLocalGap={
              assessment.source === 'local' && !isLocallyAssessable(item.key, motifSet.items)
            }
            editable={rowsEditable}
            busy={pendingMotifKey === item.key}
            onCorrect={onCorrect}
            onWithdraw={onWithdraw}
          />
        ))}
      </ul>
      {error !== null && (
        // Kein "Erneut versuchen": die Schaltflaeche der Zeile IST die Wiederholung. Der `detail`
        // des Backends steht woertlich als Textknoten, der Motivname sagt, welche Zeile es war.
        <Alert
          title={`Korrektur fehlgeschlagen: ${formatMotifKey(error.motifKey, motifSet.items)}`}
        >
          {error.detail}
        </Alert>
      )}
      <Glossary motifSet={motifSet} />
    </div>
  )
}
