import { useId } from 'react'

import type {
  CategoryCandidateOut,
  CategoryKey,
  CriterionScoreOut,
  FineLabelOut,
  RankingOut,
  SuggestionOut,
} from '../api/types'
import { cn } from '../lib/utils'
import { formatCategoryKey, formatProviderLabel, type CategorySet } from '../utils/categoryLabels'
import { CONFIDENCE_EXPLANATION, CONFIDENCE_EXPLANATION_LABEL } from '../utils/confidenceLabels'
import { formatCriterionPercent } from '../utils/formatStats'
import { formatSuggestionReason, formatSuggestionStatusLabel } from '../utils/suggestionLabels'
import { CategorySelect } from './CategorySelect'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

interface CriterionDetailsListProps {
  criterionScores: CriterionScoreOut[]
  /** Die Zugehoerigkeit, um die es an dieser Anzeigestelle geht - in der Kuratierung die der
   * gerenderten Kachel, sonst die Hauptzugehoerigkeit. Traegt "Kategorie" und "Rang". */
  ranking: RankingOut | null
  /** ALLE Zugehoerigkeiten des Fotos (specs/features/0300-nebenkategorien.md). Grundlage der
   * Sektion "Kategorien dieses Fotos", die nur bei mehr als einer Zugehoerigkeit erscheint -
   * ohne Nebenkategorien ist die Oberflaeche von heute nicht zu unterscheiden. Default `[]`,
   * damit bestehende Aufrufer unveraendert weiterlaufen. */
  rankings?: RankingOut[]
  suggestion: SuggestionOut | null
  // Blendet die Ausschuss-Gruppe unbedingt aus, unabhaengig von `suggestion` (Akzeptanzkriterium
  // 6, specs/features/0041-bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md) -
  // die permanente Sektion in PhotoDetailPage.tsx reicht `suggestion` zwar ohnehin nicht durch,
  // dieses Flag ist trotzdem die alleinige, direkt getestete Absicherung gegen ein versehentliches
  // kuenftiges Durchreichen.
  showSuggestion: boolean
  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt
  // "Mehrfachkandidaten-Vergleich mit Override-Aktion" - alle sechs Props sind optional mit
  // neutralen Defaults, damit bestehende Aufrufer (die diese Props noch nicht kennen) unveraendert
  // weiterlaufen (Regressionspflicht): mit dem Default `categoryCandidates=[]` bleibt die neue
  // Gruppe immer ausgeblendet (0 <= 1 Kandidat), die bisherige einzeilige "Kategorie"-Anzeige
  // bleibt unveraendert sichtbar.
  categoryCandidates?: CategoryCandidateOut[]
  /** Bis zu zwei frei formulierte Feinlabels (specs/features/0289-feste-kategorien.md) - reine
   * Zusatzinformation am Foto, keine Kategorie. Ohne Feinlabels wird KEIN Platzhalter gerendert.
   *
   * SICHERHEITSHINWEIS: freier, extern erzeugter LLM-Text - ausschliesslich als regulaerer
   * React-Textknoten rendern (nie dangerouslySetInnerHTML, nie als HTML-String-Prop, nie in
   * href/src/style). Das ist keine blosse Konvention, sondern die tragende Voraussetzung der
   * localStorage-Token-Entscheidung (ADR 0005). */
  fineLabels?: FineLabelOut[]
  /** Das ueber `GET /categories` geladene feste Set - Grundlage von Anzeigenamen, Reihenfolge und
   * der "Alle Kategorien"-Auswahl. Leer, solange es laedt (generischer Fallback greift). */
  categories?: CategorySet
  /** Ladezustand des Sets - deaktiviert die Auswahl statt sie leer anzubieten (kein Bypass). */
  categoriesLoading?: boolean
  /** Fehlerzustand des Sets - Inline-Alert mit "Erneut versuchen" statt einer leeren Auswahl. */
  categoriesError?: boolean
  onRetryCategories?: () => void
  categoryOverride?: CategoryKey | null
  onOverrideCategory?: (categoryKey: CategoryKey) => void
  onResetOverride?: () => void
  /** Der `category_key`, dessen "Übernehmen"-Button gerade eine laufende Anfrage hat - nur DIESER
   * eine Button wird disabled, der Rest der Liste bleibt bedienbar (Design-System: "blockiert
   * nicht die uebrige Liste"). */
  pendingOverrideKey?: CategoryKey | null
  /** Ob die "Zuruecksetzen"-Anfrage fuer den aktuellen Override-Ziel-Kandidaten laeuft - es gibt
   * nur genau ein Override-Ziel gleichzeitig, deshalb reicht ein einzelnes Flag statt eines Keys. */
  resetPending?: boolean
  /** Welcher Teil der Aufschluesselung gerendert wird (specs/features/0370-bedienelemente-
   * zuerst.md). `'all'` (Vorgabe) ist die unveraenderte, verschraenkte Gesamtdarstellung des
   * Popovers; `'controls'` und `'info'` rendern die beiden Teilmengen, aus denen die
   * Einzelbildansicht ihre neue Reihenfolge zusammensetzt (Bedienelemente vor Information).
   *
   * Der Vorgabewert ist die tragende Regressionszusage: `CriterionDetailsPopover.tsx` reicht das
   * Prop nicht durch und bleibt damit buchstaeblich unveraendert (Akzeptanzkriterium 8). */
  part?: CriterionDetailsPart
}

/** specs/features/0370-bedienelemente-zuerst.md: Bedienteil, Informationsteil oder beides. */
export type CriterionDetailsPart = 'all' | 'controls' | 'info'

/**
 * Vorbedingung des Bedienteils, als EINZIGE Quelle der Wahrheit exportiert
 * (specs/features/0370-bedienelemente-zuerst.md): Ohne sie rendert `part='controls'` `null`, und
 * die Seite laesst ihren Wrapper weg. Zwei getrennte Bedingungen an zwei Stellen ergaeben sonst
 * einen leeren Flex-Container, der im `gap-4` der Seite eine sichtbare Luecke erzeugt.
 *
 * Beide Faktoren sind Bestandsverhalten und keine neue Regel: ohne Kriterien bindet die
 * Einzelbildansicht die Sektion schon heute gar nicht erst ein, ohne Ranking enthaelt der
 * Kategorien-Block heute weder Kandidaten noch Auswahl.
 */
export function hasCategoryControls(
  criterionScores: CriterionScoreOut[],
  ranking: RankingOut | null,
): boolean {
  return criterionScores.length > 0 && ranking !== null
}

// specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
// Architektur-Entscheidung 1: die Block-Zuordnung folgt AUSSCHLIESSLICH dem Registry-Flag
// `category_eligible` aus der API-Antwort - hier wird bewusst KEINE Key-Liste gepflegt, sonst
// liefen Backend-Registry und Frontend beim naechsten neuen Kriterium auseinander. Bewusst
// ordnungserhaltend (zweimal `filter`, kein Sortieren): die Reihenfolge innerhalb eines Blocks
// bleibt die vom Backend gelieferte Registry-Reihenfolge (Akzeptanzkriterium 5). Nicht
// exportiert - die Aufteilung ist ein Implementierungsdetail dieser Komponente.
function partitionByCategoryEligibility(criterionScores: CriterionScoreOut[]): {
  quality: CriterionScoreOut[]
  categories: CriterionScoreOut[]
} {
  return {
    quality: criterionScores.filter((score) => !score.category_eligible),
    categories: criterionScores.filter((score) => score.category_eligible),
  }
}

/**
 * Die Modell-Selbsteinschaetzung als sekundaerer Text unmittelbar rechts neben dem
 * Kategorienamen (specs/features/0299-kategorie-konfidenz-anzeigen.md, UI/UX-Abschnitt).
 *
 * `null` rendert NICHTS - kein Platzhalter, kein Strich, kein `0%`. Die Luecke ist das korrekte
 * Signal: sie zeigt, dass es zu diesem Schluessel gar keine Modellaussage gibt, und ein
 * Platzhalter machte daraus eine Aussage. Deshalb die Pruefung auf `=== null` und nicht auf
 * Falsyness - `0` ist ein gueltiger Wert und heisst "das Modell war sich zu 0 % sicher".
 *
 * Die 60-%-Schwelle des Kuratierungsfilters wird hier bewusst NICHT visuell kodiert (keine Farbe,
 * kein Symbol): eine niedrige Selbsteinschaetzung ist kein Fehler, und eine Warnfarbe
 * suggerierte eine Bewertung, die die Zahl nicht hergibt.
 */
function CandidateConfidence({ confidence }: { confidence: number | null }) {
  if (confidence === null) {
    return null
  }
  return <span className="font-normal text-text-muted">{formatCriterionPercent(confidence)}</span>
}

/**
 * Der feste Hinweis, der die Zahl als Selbsteinschaetzung ausweist (Akzeptanzkriterium 7).
 *
 * Natives `<details>/<summary>` statt des Info-Popovers der Statistikseite: diese Komponente wird
 * ihrerseits INNERHALB eines Radix-Popovers gerendert (CriterionDetailsPopover in Raster und
 * Kuratierung), das seinen Schliess-Zeitpunkt ueber einen eigenen Ref-basierten Grace-Bereich
 * steuert. Ein zweites, portaliertes Popover darin brauchte genau diesen Mechanismus ein zweites
 * Mal. `<details>` ist nativ tastatur-, touch- und screenreaderbedienbar und braucht keine freie
 * Positionierung. Der Wortlaut ist an beiden Anzeigestellen dieselbe Konstante - nur der
 * Aufklapp-Mechanismus unterscheidet sich.
 */
function ConfidenceExplanation() {
  return (
    <details className="text-xs text-text">
      <summary className="cursor-pointer underline decoration-dotted">
        {CONFIDENCE_EXPLANATION_LABEL}
      </summary>
      <p className="mt-2 text-text-muted">{CONFIDENCE_EXPLANATION}</p>
    </details>
  )
}

/* specs/features/0300-nebenkategorien.md: die Rolle einer Zugehoerigkeit als TEXT. Die Begriffe
 * folgen der Story ("Haupt"/"Neben", nicht "Primaer"/"Sekundaer") und stehen hier einmal, damit
 * Rollenzeile und Sektion nicht auseinanderlaufen koennen. */
const PRIMARY_ROLE_LABEL = 'Haupt'
const SECONDARY_ROLE_LABEL = 'Neben'
const MEMBERSHIP_SECTION_LABEL = 'Kategorien dieses Fotos'

function CriterionRow({ score }: { score: CriterionScoreOut }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-text">{score.display_name}</dt>
      <dd className="font-medium text-text-h">{formatCriterionPercent(score.value)}</dd>
    </div>
  )
}

interface CategoryCandidateRow extends CategoryCandidateOut {
  /** Ein aktiver Override, dessen Ziel-Kandidat in der aktuellen Kandidatenliste nicht (mehr)
   * auftaucht (z.B. nach einem neuen Scoring-Lauf mit geaenderten lokalen Werten) - wird als
   * zusaetzliche Zeile am Ende angehaengt statt zu verschwinden (Design-System: "Verlaesslichkeit
   * statt Onboarding"). Hat keinen sinnvollen Score/keine Herkunft, beides wird fuer diese Zeile
   * nicht angezeigt. */
  isOrphan?: boolean
}

function buildCategoryCandidateRows(
  categoryCandidates: CategoryCandidateOut[],
  categoryOverride: CategoryKey | null,
): CategoryCandidateRow[] {
  // specs/features/0289-feste-kategorien.md: die Reihenfolge kommt seit dieser Spec bereits vom
  // Server (Registry-Anzeigereihenfolge) - hier wird bewusst NICHT mehr umsortiert. Das frueher
  // hier verwendete Score-Sortierkriterium ist mit dem `score`-Feld entfallen: die Auswahl
  // entscheidet die feste Vorrangreihenfolge im Backend, ein Zahlenvergleich in der Oberflaeche
  // haette keine Entsprechung mehr in der Logik.
  const rows: CategoryCandidateRow[] = [...categoryCandidates]
  const overrideIsOrphan =
    categoryOverride !== null &&
    !categoryCandidates.some((c) => c.category_key === categoryOverride)
  if (overrideIsOrphan) {
    // `confidence: null` ist hier die inhaltlich richtige Aussage, kein Fuellwert: eine verwaiste
    // Zeile hat gerade KEINEN Kandidaten mehr in der aktuellen Liste und damit keine Modellzahl.
    rows.push({
      category_key: categoryOverride,
      origin: 'local',
      provider: null,
      confidence: null,
      isOrphan: true,
    })
  }
  return rows
}

/**
 * Reine Praesentationskomponente mit den Bewertungsdetails eines Fotos - extrahiert aus dem
 * bisher inline in CriterionDetailsPopover.tsx liegenden `<dl>`-Markup
 * (specs/features/0041-bewertungsdetails-permanent-in-detailansicht-hover-auto-close.md,
 * Architektur-Abschnitt), damit sowohl das Popover (Grid/Kuratierung) als auch die permanente
 * Sektion in PhotoDetailPage.tsx dieselbe Darstellung/Formatierungslogik teilen (DRY,
 * Akzeptanzkriterium 5/13). Prueft selbst NICHT, ob `criterionScores` leer ist - die Entscheidung,
 * den Bereich bei leerer Liste gar nicht erst einzubinden, bleibt bewusst bei den jeweiligen
 * Aufrufern (Popover-Sichtbarkeit vs. permanente Sektion), da beide Stellen die gleiche Bedingung
 * ohnehin schon selbst pruefen muessen (Popover fuer den Trigger, PhotoDetailPage.tsx fuer den
 * Abschnitts-Rahmen).
 *
 * Gliedert die Kriterien in zwei beschriftete Bloecke "Qualitaet"/"Kategorien"
 * (specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md): ein Block ohne Inhalt
 * wird komplett weggelassen (keine Ueberschrift, kein leeres `<dl>`), bei komplett leerer Eingabe
 * rendert die Komponente nur noch den aeusseren Container ohne jedes `dt`/`dd` - der bis Spec 0209
 * hier dokumentierte Sonderfall "leeres `<dl>`" gilt nicht mehr. Der Ausschuss-Vorschlag bleibt
 * ein dritter, eigener Bereich ausserhalb beider Bloecke und ohne eigene Ueberschrift.
 */
export function CriterionDetailsList({
  criterionScores,
  ranking,
  rankings = [],
  suggestion,
  showSuggestion,
  categoryCandidates = [],
  fineLabels = [],
  categories = [],
  categoriesLoading = false,
  categoriesError = false,
  onRetryCategories,
  categoryOverride = null,
  onOverrideCategory,
  onResetOverride,
  pendingOverrideKey = null,
  resetPending = false,
  part = 'all',
}: CriterionDetailsListProps) {
  // specs/features/0370-bedienelemente-zuerst.md: JEDES bestehende Sichtbarkeitsgate bleibt
  // woertlich erhalten und bekommt nur den passenden Teil-Faktor dazu. Fuer `part='all'` ergibt
  // damit jedes Gate wieder genau die heutige Bedingung - das Popover ist nachweislich unberuehrt.
  const showControlsPart = part !== 'info'
  const showInfoPart = part !== 'controls'
  const candidateRows = buildCategoryCandidateRows(categoryCandidates, categoryOverride)
  // specs/features/0300-nebenkategorien.md, Akzeptanzkriterium 24: bei genau einer Zugehoerigkeit
  // (und ohne jede) sieht die Oberflaeche exakt wie heute aus - weder Rollenzeile noch Sektion.
  const showMembershipRoles = rankings.length > 1
  const showCandidateGroup = candidateRows.length > 1
  // specs/features/0299-kategorie-konfidenz-anzeigen.md: die Zahl der einzeiligen Anzeige haengt
  // am angezeigten Schluessel (`ranking.category_key`), nicht am einzigen Kandidaten - beide
  // koennen auseinanderfallen, z.B. wenn die Rangfolge aus einem aelteren Lauf stammt.
  const singleLineConfidence =
    categoryCandidates.find((c) => c.category_key === ranking?.category_key)?.confidence ?? null
  // Der Hinweis erscheint genau dann, wenn tatsaechlich mindestens eine Zahl dargestellt wird -
  // eine Erklaerung zu einer nicht vorhandenen Zahl waere reines Rauschen, und der Altbestand
  // ohne jede Angabe ist auf absehbare Zeit der haeufigste Fall (Akzeptanzkriterium 9).
  const showsAnyConfidence = showCandidateGroup
    ? candidateRows.some((row) => row.confidence !== null)
    : singleLineConfidence !== null
  const { quality: qualityScores, categories: categoryScores } =
    partitionByCategoryEligibility(criterionScores)
  // Die Kandidatenliste bzw. die einzeilige "Kategorie"-Anzeige und "Rang" gehoeren fachlich in
  // den Kategorien-Block - er erscheint deshalb auch ohne kategoriefaehiges Kriterium, sobald ein
  // Ranking vorliegt.
  const showCategoriesBlock =
    (showControlsPart && ranking !== null) ||
    (showInfoPart && (categoryScores.length > 0 || ranking !== null))
  const showQualityBlock = showInfoPart && qualityScores.length > 0
  const showSuggestionGroup = showInfoPart && showSuggestion && suggestion !== null
  // Ein einzelnes useId() mit Suffixen statt zweier Aufrufe (React-Doku-Muster fuer mehrere
  // zusammengehoerige Ids) - noetig, weil zwei Instanzen gleichzeitig im DOM stehen koennen
  // (Popover ueber der permanenten Sektion, seit Spec 0370 zusaetzlich Bedien- und
  // Informationsteil derselben Seite) und feste Ids dann kollidieren wuerden.
  const blockId = useId()
  const qualityHeadingId = `${blockId}-quality`
  const categoriesHeadingId = `${blockId}-categories`

  // Ein Teil ohne Inhalt gibt `null` zurueck statt eines leeren `flex flex-col gap-4`-Containers:
  // im `gap-4` der Einzelbildansicht verbrauchte eine leere Instanz einen sichtbaren Abstand.
  // `part='all'` behaelt bewusst das Bestandsverhalten (aeusserer Container auch ohne Inhalt).
  if (part === 'controls' && !hasCategoryControls(criterionScores, ranking)) {
    return null
  }
  if (part !== 'all' && !showQualityBlock && !showCategoriesBlock && !showSuggestionGroup) {
    return null
  }

  /* Die Kandidaten-/Rang-Gruppe ist die Stelle, an der Bedienung und Information verschraenkt
   * sind - sie wird EINMAL gebildet und von beiden Teilen benutzt, damit die Reihenfolge
   * innerhalb der Gruppe fuer `part='all'` woertlich die heutige bleibt. */
  const categoryRankGroup = ranking !== null && (
    // Der groessere Abstand vor der Kandidaten-/Rang-Gruppe sitzt als Margin an der
    // Gruppe selbst statt als `gap-3` am <dl>: so haengen die Kriterienzeilen in beiden
    // Bloecken auf derselben Ebene (<dl> > Zeilen-<div> > dt/dd) statt im
    // Kategorien-Block eine Wrapper-<div>-Ebene tiefer (Copilot-Review-Fund auf PR
    // #277). `mt-2` (0.375rem) addiert sich zum `gap-2` des <dl> auf exakt die
    // 0.75rem des vorherigen `gap-3` - und entfaellt, wenn keine Kriterienzeile
    // vorausgeht, weil dann auch vorher kein Abstand gerendert wurde (im Bedienteil also
    // immer, dort steht nie eine Kriterienzeile davor). Die Darstellung bleibt damit in jedem
    // Fall pixelgleich (Spec 0209, Akzeptanzkriterium 6: reine Umgruppierung, keine visuelle
    // Aenderung).
    <div className={cn('flex flex-col gap-2', showInfoPart && categoryScores.length > 0 && 'mt-2')}>
      {showControlsPart &&
        (showCandidateGroup ? (
          <div className="flex flex-col gap-2">
            <dt className="text-text">Kategorie-Kandidaten</dt>
            <dd>
              <ul className="flex flex-col gap-2">
                {candidateRows.map((row) => {
                  const isEffective = !row.isOrphan && ranking.category_key === row.category_key
                  const isOverrideTarget = categoryOverride === row.category_key
                  const isPending = pendingOverrideKey === row.category_key
                  return (
                    <li
                      key={row.category_key}
                      data-testid={`category-candidate-row-${row.category_key}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2"
                    >
                      <div className="flex flex-wrap items-baseline gap-2">
                        <span className="font-medium text-text-h">
                          {formatCategoryKey(row.category_key, categories)}
                        </span>
                        <CandidateConfidence confidence={row.confidence} />
                        {!row.isOrphan && (
                          <Badge tone="neutral">
                            {row.origin === 'remote' && row.provider
                              ? formatProviderLabel(row.provider)
                              : 'Lokal erkannt'}
                          </Badge>
                        )}
                      </div>
                      {isOverrideTarget ? (
                        <div className="flex items-center gap-2">
                          <Badge tone="neutral">Manuell übernommen</Badge>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            busy={resetPending}
                            disabled={resetPending}
                            onClick={() => onResetOverride?.()}
                          >
                            Zurücksetzen
                          </Button>
                        </div>
                      ) : isEffective ? (
                        <Badge tone="neutral">Aktuell</Badge>
                      ) : (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          busy={isPending}
                          disabled={isPending}
                          onClick={() => onOverrideCategory?.(row.category_key)}
                        >
                          Übernehmen
                        </Button>
                      )}
                    </li>
                  )
                })}
              </ul>
            </dd>
          </div>
        ) : (
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Kategorie</dt>
            <dd className="font-medium text-text-h">
              {/* Ohne Zahl bleibt die Zeile EXAKT wie bisher (nur der Textknoten, kein
                  zusaetzliches Element) - der haeufigste Fall soll unveraendert
                  aussehen. Die Zahl folgt dem ANGEZEIGTEN Schluessel: sie kommt aus der
                  Kandidatenliste, nicht aus dem einen vorhandenen Kandidaten, denn die
                  Rangfolge kann eine andere Kategorie zeigen. */}
              {singleLineConfidence === null ? (
                formatCategoryKey(ranking.category_key, categories)
              ) : (
                <>
                  <span>{formatCategoryKey(ranking.category_key, categories)}</span>{' '}
                  <CandidateConfidence confidence={singleLineConfidence} />
                </>
              )}
            </dd>
          </div>
        ))}
      {/* specs/features/0300-nebenkategorien.md, Akzeptanzkriterium 13: die Rolle AN
          DIESER STELLE - in der Kuratierung die der gerenderten Kachel. Sie kommt
          ausschliesslich aus `is_primary`, nie aus einem Zahlenvergleich, und steht als
          TEXT da, nicht als Farbe. Ohne Nebenkategorien (genau eine Zugehoerigkeit)
          erscheint die Zeile gar nicht - die Oberflaeche sieht dann exakt wie bisher
          aus (Akzeptanzkriterium 24). */}
      {showInfoPart && showMembershipRoles && (
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-text">Rolle</dt>
          <dd>
            <Badge tone="neutral">
              {ranking.is_primary ? PRIMARY_ROLE_LABEL : SECONDARY_ROLE_LABEL}
            </Badge>
          </dd>
        </div>
      )}
      {showInfoPart && (
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-text">Rang</dt>
          <dd className="font-medium text-text-h">
            Rang {ranking.rank_position} von {ranking.partition_size}
          </dd>
        </div>
      )}
      {/* specs/features/0289-feste-kategorien.md, UI/UX-Abschnitt: die
          "Alle Kategorien"-Auswahl ERGAENZT die Kandidatenliste, sie ersetzt sie nicht -
          der Nutzer sieht weiterhin, was das System erkannt hat, bevor er es
          uebersteuert. Nur eingebunden, wenn ein Uebersteuern ueberhaupt vorgesehen ist
          (Aufrufer reicht `onOverrideCategory` durch). */}
      {showControlsPart && showsAnyConfidence && <ConfidenceExplanation />}
      {showControlsPart && onOverrideCategory && (
        <div className="mt-2">
          <CategorySelect
            categories={categories}
            value={categoryOverride ?? ranking.category_key}
            onSelect={onOverrideCategory}
            pending={pendingOverrideKey !== null}
            isLoading={categoriesLoading}
            isError={categoriesError}
            onRetry={onRetryCategories}
          />
        </div>
      )}
    </div>
  )

  /* Innenleben des Kategorien-Blocks - identisch fuer alle drei Teile; nur der Rahmen darum
   * unterscheidet sich (Ueberschrift + beschriftete Gruppe vs. schlichter <div>, siehe unten). */
  const categoriesBlockContent = (
    <>
      <dl className="flex flex-col gap-2">
        {showInfoPart &&
          categoryScores.map((score) => <CriterionRow key={score.criterion_key} score={score} />)}
        {categoryRankGroup}
      </dl>
      {/* Feinlabel-Chips (specs/features/0289-feste-kategorien.md, UI/UX-Abschnitt): raeumlich
          deutlich von der Kategorie getrennt, kompakter und in einem anderen Ton
          (`suggested`-Variante des Akzent-Chips) - sie sind Zusatzinformation, keine
          kategoriale Einordnung. Bewusst OHNE Icon/Symbol, damit sie nicht mit den
          Bewertungs-Chips verwechselt werden. Ohne Feinlabels wird KEIN Platzhalter
          gerendert - der Bereich entfaellt ersatzlos. Sichtbar auch bei "Nicht erkannt". */}
      {/* specs/features/0300-nebenkategorien.md, UI/UX-Abschnitt: die Kategorien DES FOTOS
          mit ihrer jeweiligen Rolle - sichtbar nur, wenn es tatsaechlich mehr als eine gibt.
          Die Konfidenzzahlen aus Spec 0299 werden hier NICHT wiederholt; sie stehen
          unveraendert in der Kandidatenliste darueber. */}
      {showInfoPart && showMembershipRoles && (
        <div className="mt-2 flex flex-col gap-2">
          <h4 className="text-xs text-text">{MEMBERSHIP_SECTION_LABEL}</h4>
          <ul aria-label={MEMBERSHIP_SECTION_LABEL} className="flex flex-col gap-2">
            {rankings.map((membership) => (
              <li
                key={membership.category_key}
                data-category-key={membership.category_key}
                className="flex flex-wrap items-baseline justify-between gap-2"
              >
                <span className="font-medium text-text-h">
                  {formatCategoryKey(membership.category_key, categories)}
                </span>
                <Badge tone="neutral">
                  {membership.is_primary ? PRIMARY_ROLE_LABEL : SECONDARY_ROLE_LABEL}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
      {showInfoPart && fineLabels.length > 0 && (
        <div className="mt-2 flex flex-col gap-2">
          <h4 className="text-xs text-text">Feinlabels</h4>
          <ul aria-label="Feinlabels" className="flex flex-wrap gap-2">
            {fineLabels.map((label) => (
              <li key={label.canonical_key}>
                {/* Reiner React-Textknoten - freier LLM-Text, nie als HTML. */}
                <Badge tone="accent" suggested className="max-w-full truncate">
                  {label.display_name}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )

  return (
    <div className="flex flex-col gap-4">
      {showQualityBlock && (
        // role="group" + aria-labelledby am Wrapper, NICHT am <dl>: ein <dl> hat in dieser
        // Toolchain keine namensfaehige Rolle, die Beschriftung kaeme dort weder im
        // Accessibility-Tree noch in einer Rollenabfrage an (Spec 0209,
        // Architektur-Entscheidung 3).
        <div role="group" aria-labelledby={qualityHeadingId} className="flex flex-col gap-2">
          <h3 id={qualityHeadingId} className="text-xs font-medium text-text-h">
            Qualität
          </h3>
          <dl className="flex flex-col gap-2">
            {qualityScores.map((score) => (
              <CriterionRow key={score.criterion_key} score={score} />
            ))}
          </dl>
        </div>
      )}
      {showCategoriesBlock &&
        (showInfoPart ? (
          <div role="group" aria-labelledby={categoriesHeadingId} className="flex flex-col gap-2">
            <h3 id={categoriesHeadingId} className="text-xs font-medium text-text-h">
              Kategorien
            </h3>
            {categoriesBlockContent}
          </div>
        ) : (
          /* Der Bedienteil (`part='controls'`) rendert denselben Inhalt OHNE <h3> und ohne
             role="group"/aria-labelledby (specs/features/0370-bedienelemente-zuerst.md): zwei
             gleichlautende "Kategorien"-Ueberschriften auf einer Seite waeren mehrdeutig, eine neu
             erfundene Ueberschrift eine von Akzeptanzkriterium 4 ausgeschlossene
             Beschriftungsaenderung, und eine unbeschriftete Gruppe ist im Accessibility-Tree
             wertlos. Seine Elemente sind einzeln beschriftet ("Kategorie-Kandidaten"/"Kategorie"
             als <dt>, "Alle Kategorien" als <label>). Das <dl> steckt in
             `categoriesBlockContent` - ohne es stuenden dt/dd hier ohne <dl>-Vorfahren. */
          <div className="flex flex-col gap-2">{categoriesBlockContent}</div>
        ))}
      {/* Dritter, eigener Bereich ausserhalb beider Bloecke und bewusst OHNE eigene Ueberschrift
          (Spec 0209, Akzeptanzkriterium 8) - erscheint auch dann, wenn beide Bloecke leer sind. */}
      {showSuggestionGroup && (
        <dl className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Ausschuss-Vorschlag</dt>
            <dd className="font-medium text-text-h">{formatSuggestionStatusLabel(suggestion)}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text">Grund</dt>
            <dd className="font-medium text-text-h">{formatSuggestionReason(suggestion)}</dd>
          </div>
        </dl>
      )}
    </div>
  )
}
