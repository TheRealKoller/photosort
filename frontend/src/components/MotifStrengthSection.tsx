import { useId, useState } from 'react'

import type { MotifAssessmentOut, MotifKey, MotifSetOut, MotifStrengthOut } from '../api/types'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'
import { MotifStrengthSymbol } from './MotifStrengthSymbol'
import {
  criterionPercentValue,
  formatCriterionPercent,
  formatDateTime,
  formatProviderLabel,
} from '../utils/formatStats'
import { motifIconName } from '../utils/motifIcons'
import { formatMotifKey, isLocallyAssessable } from '../utils/motifLabels'
import { motifFillStep } from '../utils/motifStrength'
import type { MotifCorrectionError } from '../hooks/useMotifCorrection'

/**
 * Die acht Motive eines Fotos samt ihrer wirksamen Staerke - Design-System-Muster "Mehrwertige
 * Eigenschaft als Fuellstandsreihe".
 *
 * EIN Baustein mit Prop `editable`: bedienbar in der Einzelbildansicht, schreibgeschuetzt im
 * Info-Popover der Kachel. Fuenf Festlegungen tragen die Darstellung:
 *
 * 1. Die Reihenfolge ist die REGISTRY-Reihenfolge aus `GET /motifs`, auf jedem Foto dieselbe, und
 *    wird NIE nach Staerke sortiert. Die Staerke wird je Schluessel aus `motifs` nachgeschlagen,
 *    nie ueber den Index der Antwortliste. Acht gleichartige Schaltflaechen, die von Foto zu Foto
 *    die Position wechseln, laden zum Fehlklick ein - und ein Fehlklick oeffnet hier die Zeile,
 *    in der ein Datenwert geschrieben wird.
 * 2. FEHLT DIE KOPFZEILE, gibt es KEINE REIHE, sondern einen Satz. Acht ungefuellte Symbole sind
 *    von "nichts erkannt" nicht zu unterscheiden; der Unterschied ist damit strukturell und nicht
 *    farblich.
 * 3. Es gibt KEIN berechnetes Urteil "nichts erkannt" - dafuer braeuchte die Oberflaeche eine
 *    Schwelle. Ebenso erscheint hier KEIN Bandwort: es lehrte den Nutzer genau die
 *    Zugehoerigkeitsschwelle, die es im Auswahlpfad nicht gibt.
 * 4. Die Staerke wird NIE allein ueber Farbe getragen: die FUELLHOEHE zeigt dieselbe Information,
 *    und der zugaengliche Name jeder Schaltflaeche nennt den Wert als Text. Damit ist jede Angabe
 *    ohne Zeigen und ohne Aufklappen erreichbar.
 * 5. ANGEHEFTET SCHLAEGT ZEIGEN: Sobald etwas angeheftet ist, ueberschreibt Zeigen nichts mehr -
 *    sonst wechselte die Zeile unter dem Zeiger auf dem Weg zu den Korrekturschaltern.
 *    `aria-expanded` folgt NUR dem Anheften.
 *
 * KEIN POPOVER und kein `title`-Attribut: Die Reihe steht im Kachel-Popover bereits in einem
 * Panel, und ein zweites darin ist nicht zulaessig.
 */
interface MotifStrengthSectionProps {
  /** Das geladene Set. `undefined` waehrend des Ladens bzw. nach einem Fehlschlag. */
  motifSet: MotifSetOut | undefined
  motifSetLoading?: boolean
  /** Der Fehlertext des fehlgeschlagenen `GET /motifs`. */
  motifSetError?: string
  onMotifSetRetry?: () => void
  /** `null` heisst "noch nicht klassifiziert" - dann erscheint der Satz statt der Reihe. */
  assessment: MotifAssessmentOut | null | undefined
  motifs: readonly MotifStrengthOut[] | undefined
  editable: boolean
  onCorrect?: (motifKey: MotifKey, applies: boolean) => void
  onWithdraw?: (motifKey: MotifKey) => void
  /** Das Motiv mit laufender Korrektur - nur DESSEN Schaltflaechen werden gesperrt, die Reihe
   * bleibt bedienbar. */
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

const DETAIL_PROMPT_TEXT = 'Symbol antippen für Details'

/**
 * Platzhalter statt eines Spinners, in der FORM DER SPAETEREN DARSTELLUNG: eine Reihe aus acht
 * Platzhaltern NEBENEINANDER, darunter einer fuer die Detailzeile.
 *
 * Die Form ist keine Kosmetik. Acht Platzhalter untereinander (die Form der abgeloesten
 * Balkenliste) beanspruchen rund 340 px gegen die rund 60 px der geladenen Reihe; der Bereich
 * zoege beim Eintrudeln der Antwort alles darunter um rund 280 px hoch - die "Bewegung von Layout
 * oder Position", die das Design-System ausschliesst.
 */
function SkeletonRows() {
  return (
    <div className="flex flex-col gap-3" role="status" aria-label="Motive werden geladen">
      {/* Die Grundlagenzeile, die nach dem Laden an dieser Stelle steht. */}
      <Skeleton className="h-4 w-2/3 rounded-sm" data-testid="motif-skeleton-basis" />
      <div className="flex items-stretch" data-testid="motif-skeleton-row">
        {Array.from({ length: 8 }, (_, index) => (
          <div key={index} className="flex-1 px-1">
            <Skeleton className="h-8 rounded-sm" data-testid="motif-skeleton-symbol" />
          </div>
        ))}
      </div>
      <Skeleton className="h-4 w-1/2 rounded-sm" data-testid="motif-skeleton-detail" />
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
 * Das Glossar: EIN einziges `<details>` am Ende des Bausteins.
 *
 * Kein Info-Ausloeser je Motiv (acht zusaetzliche Trefferflaechen fuer Nachschlagetext) und kein
 * Popover - der Baustein wird seinerseits in einem Popover gerendert, und ein zweites Panel darin
 * ist nicht zulaessig.
 *
 * SICHERHEIT (S19): Registry-Text ausschliesslich als React-TEXTKNOTEN - nie ueber
 * `dangerouslySetInnerHTML`, nie als HTML-String-Prop, und er fliesst in kein `href`, `src`,
 * `style` und keinen `url()`-Kontext. Dasselbe gilt fuer die Detailzeile und fuer den
 * zugaenglichen Namen der Symbole, in die derselbe Text seit dem Umbau ebenfalls austritt.
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

/**
 * Was an der Stelle des Werts steht - EINE Quelle fuer den zugaenglichen Namen des Symbols UND
 * fuer die Detailzeile. Zwei getrennte Ableitungen liefen auseinander, und die eine von beiden,
 * die niemand sieht, ist der zugaengliche Name.
 */
function valueText(
  strength: MotifStrengthOut | undefined,
  showLocalGap: boolean,
): { text: string; mono: boolean } {
  const state = correctionState(strength?.correction ?? null)
  if (state !== undefined) {
    // STATT der Prozentzahl - die ueberstimmte Modellzahl steht nicht daneben.
    return {
      text: state === 'applies' ? 'Trifft zu (korrigiert)' : 'Trifft nicht zu (korrigiert)',
      mono: false,
    }
  }
  if (showLocalGap) {
    // Ein `0 %` waere hier die Aussage "nicht zu sehen" statt "nicht angesehen".
    return { text: NOT_LOCALLY_ASSESSABLE_TEXT, mono: false }
  }
  return { text: formatCriterionPercent(strength?.strength ?? 0), mono: true }
}

interface DetailRowProps {
  id: string
  displayName: string | undefined
  value: { text: string; mono: boolean } | undefined
  motifKey: MotifKey | undefined
  correctionState: 'applies' | 'rejected' | undefined
  editable: boolean
  busy: boolean
  onCorrect?: (motifKey: MotifKey, applies: boolean) => void
  onWithdraw?: (motifKey: MotifKey) => void
}

/**
 * Die Zeile unter der Reihe: voller Motivname, genauer Wert und - nur an der bedienbaren Stelle -
 * die drei Korrekturschaltflaechen.
 *
 * SIE EXISTIERT AUCH UNGEWAEHLT, mit dem Aufforderungssatz statt einer leeren Flaeche: `aria-
 * controls` der Symbole zeigt nie ins Leere, und die Reihe springt beim ersten Klick nicht.
 */
function DetailRow({
  id,
  displayName,
  value,
  motifKey,
  correctionState: state,
  editable,
  busy,
  onCorrect,
  onWithdraw,
}: DetailRowProps) {
  if (displayName === undefined || value === undefined || motifKey === undefined) {
    return (
      <div id={id} className="flex flex-col gap-2 text-xs text-text-muted">
        <p>{DETAIL_PROMPT_TEXT}</p>
      </div>
    )
  }

  return (
    <div id={id} className="flex flex-col gap-2 text-xs">
      <div className="flex items-baseline justify-between gap-3">
        {/* Die laengsten Namen muessen umbrechen duerfen. */}
        <span className="break-words text-text-h">{displayName}</span>
        <span className={value.mono ? 'shrink-0 font-mono' : 'shrink-0 text-text-h'}>
          {value.text}
        </span>
      </div>
      {editable && (
        // `gap-3` ist die Pflichtgrenze zwischen aufgespannten Trefferflaechen. `size="sm"` statt
        // `h-11`: die Korrektur ist nicht der heisse Pfad.
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
    </div>
  )
}

export function MotifStrengthSection({
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
}: MotifStrengthSectionProps) {
  const detailId = useId()
  // Zwei Zustaende, bewusst getrennt: der Klick HEFTET AN, Zeigen und Tastaturfokus zeigen nur
  // eine VORSCHAU. Ein gemeinsamer Zustand koennte den Unterschied nicht tragen, an dem
  // `aria-expanded` und die sichtbare Markierung haengen - beide folgen ausschliesslich dem
  // Anheften. Folgte `aria-expanded` der Vorschau, saehe assistive Technik beim blossen
  // Durchtabben acht aufklappende Bereiche, von denen keiner offen ist.
  const [pinnedKey, setPinnedKey] = useState<MotifKey | null>(null)
  const [previewKey, setPreviewKey] = useState<MotifKey | null>(null)

  if (motifSetError !== undefined) {
    // Keine Reihe mit Rohschluesseln - lieber gar keine Reihe.
    return <Alert onRetry={onMotifSetRetry}>{motifSetError}</Alert>
  }
  if (motifSetLoading || motifSet === undefined) {
    return <SkeletonRows />
  }

  // DER STRUKTURELLE Unterschied: Satz statt Reihe, nicht acht ungefuellte Symbole.
  if (assessment === null || assessment === undefined) {
    return <p className="text-sm text-text">{UNASSESSED_TEXT}</p>
  }

  const excluded = assessment.excluded_document
  // Eine ausgeschlossene Einstufung ist nicht von Hand korrigierbar: die Reihe bleibt EINSEHBAR,
  // aber ohne Bedienelemente. Kein deaktivierter Schalter, nach dem niemand suchen soll.
  const rowsEditable = editable && !excluded
  const byKey = new Map((motifs ?? []).map((entry) => [entry.key, entry]))

  const activeKey = pinnedKey ?? previewKey
  const activeItem = motifSet.items.find((item) => item.key === activeKey)
  const activeLocalGap =
    activeItem !== undefined &&
    assessment.source === 'local' &&
    !isLocallyAssessable(activeItem.key, motifSet.items)

  return (
    <div className="flex flex-col gap-3">
      {excluded && <p className="text-sm text-text">{EXCLUDED_TEXT}</p>}
      <BasisLine assessment={assessment} />
      <ul aria-label="Motive" className="flex items-stretch">
        {motifSet.items.map((item) => {
          const strength = byKey.get(item.key)
          const displayName = formatMotifKey(item.key, motifSet.items)
          const showLocalGap =
            assessment.source === 'local' && !isLocallyAssessable(item.key, motifSet.items)
          const step = motifFillStep(
            strength?.strength ?? 0,
            motifSet.strength_bands,
            !showLocalGap,
          )
          return (
            <li key={item.key} className="flex-1">
              <button
                type="button"
                // `tap-target` spannt NUR die kurze (senkrechte) Achse auf: acht waagerechte
                // 44px-Flaechen brauchten 352px und vertrugen sich nicht mit der Zusage "alle
                // acht in einer Zeile ohne waagerechtes Scrollen". WCAG 2.5.8 (24x24px) bleibt
                // auf beiden Achsen deutlich ueberschritten (ADR 0113 Punkt 5).
                //
                // Das ANGEHEFTETE Symbol traegt zusaetzlich die Board-Flaeche `bg-overlay`: ohne
                // ein sichtbares Merkmal ist am Bildschirm nicht zu sehen, welches der acht
                // Symbole zu der Zeile darunter gehoert - `aria-expanded` traegt das nur fuer
                // assistive Technik. Das blosse Zeigen markiert NICHT: es heftet nichts an.
                className={`tap-target flex w-full items-center justify-center rounded-sm py-1 ${
                  pinnedKey === item.key ? 'bg-overlay' : ''
                }`}
                aria-label={`${displayName}: ${valueText(strength, showLocalGap).text}`}
                aria-expanded={pinnedKey === item.key}
                aria-controls={detailId}
                data-motif-key={item.key}
                data-motif-corrected={correctionState(strength?.correction ?? null)}
                onClick={() => setPinnedKey((current) => (current === item.key ? null : item.key))}
                // Zeigen UND Tastaturfokus speisen dieselbe Vorschau: Ohne `onFocus` bekaeme ein
                // sehender Tastaturnutzer beim Durchtabben nichts zu sehen - der zugaengliche
                // Name traegt zwar alle Angaben, ist aber genau fuer ihn unsichtbar.
                onMouseEnter={() => setPreviewKey(item.key)}
                onMouseLeave={() =>
                  setPreviewKey((current) => (current === item.key ? null : current))
                }
                onFocus={() => setPreviewKey(item.key)}
                onBlur={() => setPreviewKey((current) => (current === item.key ? null : current))}
              >
                <MotifStrengthSymbol
                  iconName={motifIconName(item.key)}
                  step={step}
                  // Fuellhoehe und angezeigte Zahl stammen aus DERSELBEN Rundung. Bei `none`
                  // (Staerke 0 oder lokal nicht beurteilbar) bleibt die Fuellebene leer - eine
                  // ungefaerbte Fuellung erbte sonst die Textfarbe und behauptete eine Staerke.
                  fillPercent={step === 'none' ? 0 : criterionPercentValue(strength?.strength ?? 0)}
                />
              </button>
            </li>
          )
        })}
      </ul>
      <DetailRow
        id={detailId}
        displayName={
          activeItem === undefined ? undefined : formatMotifKey(activeItem.key, motifSet.items)
        }
        value={
          activeItem === undefined
            ? undefined
            : valueText(byKey.get(activeItem.key), activeLocalGap)
        }
        motifKey={activeItem?.key}
        correctionState={
          activeItem === undefined
            ? undefined
            : correctionState(byKey.get(activeItem.key)?.correction ?? null)
        }
        editable={rowsEditable}
        busy={activeItem !== undefined && pendingMotifKey === activeItem.key}
        onCorrect={onCorrect}
        onWithdraw={onWithdraw}
      />
      {error !== null && (
        // Kein "Erneut versuchen": die Schaltflaeche der Zeile IST die Wiederholung. Der `detail`
        // des Backends steht woertlich als Textknoten, der Motivname sagt, welches Motiv es war -
        // auch wenn dieses Motiv gerade nicht aufgeklappt ist.
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
