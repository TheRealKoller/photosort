import { useId, useState } from 'react'

import { ApiError } from '../api/client'
import type {
  ClassificationReviewCloudModelOptionOut,
  ClassificationReviewCreatedOut,
  ClassificationReviewOptionsOut,
  ClassificationReviewSideIn,
} from '../api/types'
import {
  useClassificationReviewEstimateQuery,
  useClassificationReviewOptionsQuery,
  useCreateClassificationReviewMutation,
} from '../hooks/useClassificationReviews'
import {
  CLASSIFICATION_REVIEW_TEXTS,
  PROVIDER_BLOCKED_TEXT,
  SIDE_COST_LABELS,
  SIDE_LABELS,
  sideOriginText,
  UNAVAILABLE_REASON_TEXTS,
  type ReviewSideOrigin,
} from '../utils/classificationReviewLabels'
import { formatCount, formatProviderLabel, formatUsd } from '../utils/formatStats'
import { EyeAttribution } from './EyeAttribution'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Input } from './ui/input'

/** Ein gewaehltes Verfahren EINER Seite, samt der Felder, die zu seiner Art gehoeren. */
type SideChoice =
  | { kind: 'cloud'; provider: string; model: string }
  | { kind: 'eye'; eye_model_revision: string; eye_mapping_version: string }
  | { kind: 'local' }

type SideLetter = 'a' | 'b'

const SIDE_ORDER: readonly SideLetter[] = ['a', 'b']

const CHOICE_ROW_CLASS =
  'flex min-h-11 w-full cursor-pointer flex-col justify-center gap-1 rounded-sm border ' +
  'border-border px-3 py-2 has-[:checked]:border-accent'

/** Die Felder, die der Server von einer Wahl sehen darf - nie ein Preis, nie ein Anbieter. */
function toSideIn(choice: SideChoice): ClassificationReviewSideIn {
  if (choice.kind === 'cloud') {
    return { kind: 'cloud', model: choice.model }
  }
  if (choice.kind === 'eye') {
    return { kind: 'eye', eye_mapping_version: choice.eye_mapping_version }
  }
  return { kind: 'local' }
}

/** Die Erkennung einer Zeile in ihrem `fieldset` - zwei Fassungen unterscheiden sich nur hier. */
function choiceKey(choice: SideChoice): string {
  if (choice.kind === 'cloud') {
    return `cloud:${choice.model}`
  }
  if (choice.kind === 'eye') {
    return `eye:${choice.eye_mapping_version}`
  }
  return 'local'
}

/** Cloud-Modelle nach Anbieter, in der Reihenfolge des Servers - nicht alphabetisch umsortiert. */
function groupByProvider(
  models: readonly ClassificationReviewCloudModelOptionOut[],
): { provider: string; models: ClassificationReviewCloudModelOptionOut[] }[] {
  const groups = new Map<string, ClassificationReviewCloudModelOptionOut[]>()
  for (const model of models) {
    const group = groups.get(model.provider)
    if (group === undefined) {
      groups.set(model.provider, [model])
    } else {
      group.push(model)
    }
  }
  return [...groups].map(([provider, groupModels]) => ({ provider, models: groupModels }))
}

function SideRow({
  name,
  choice,
  selectedKey,
  costLabel,
  onSelect,
}: {
  name: string
  choice: SideChoice
  selectedKey: string | null
  costLabel: string
  onSelect: (choice: SideChoice) => void
}) {
  const key = choiceKey(choice)
  const origin: ReviewSideOrigin =
    choice.kind === 'cloud'
      ? {
          kind: 'cloud',
          provider: choice.provider,
          model: choice.model,
          eye_model_revision: null,
          eye_mapping_version: null,
        }
      : choice.kind === 'eye'
        ? {
            kind: 'eye',
            provider: null,
            model: null,
            eye_model_revision: choice.eye_model_revision,
            eye_mapping_version: choice.eye_mapping_version,
          }
        : {
            kind: 'local',
            provider: null,
            model: null,
            eye_model_revision: null,
            eye_mapping_version: null,
          }
  return (
    <label className={CHOICE_ROW_CLASS}>
      <span className="flex items-center gap-2">
        <input
          type="radio"
          name={name}
          value={key}
          checked={selectedKey === key}
          onChange={() => onSelect(choice)}
          className="size-4 accent-accent"
        />
        {/* Herkunft als reiner Textknoten, nie gekuerzt: zwei Fassungen unterscheiden sich oft
            erst am Ende. */}
        <span className="break-words text-sm font-medium text-text-h">
          {sideOriginText(origin)}
        </span>
      </span>
      <span className="pl-6 text-xs text-text-muted">{costLabel}</span>
    </label>
  )
}

function SideChoices({
  letter,
  options,
  choice,
  onChange,
}: {
  letter: SideLetter
  options: ClassificationReviewOptionsOut
  choice: SideChoice | null
  onChange: (choice: SideChoice) => void
}) {
  const name = useId()
  const selectedKey = choice === null ? null : choiceKey(choice)
  const cloudKind = options.kinds.find((option) => option.kind === 'cloud')
  const eyeKind = options.kinds.find((option) => option.kind === 'eye')
  const cloudBlocked = cloudKind !== undefined && !cloudKind.available
  const eyeBlocked = eyeKind !== undefined && !eyeKind.available

  return (
    <fieldset className="flex w-full flex-col gap-2" data-testid={`review-side-${letter}`}>
      <legend className="text-sm font-medium text-text-h">{SIDE_LABELS[letter]}</legend>

      {cloudBlocked ? (
        // Der Grund steht an der Stelle der Gruppe, nicht in einer Fussnote: ohne ihn raet der
        // Nutzer, warum die Cloud fehlt.
        <p className="text-xs text-text">
          Nicht wählbar —{' '}
          {UNAVAILABLE_REASON_TEXTS[cloudKind.unavailable_reasons[0] ?? 'no_consent']}.
        </p>
      ) : (
        groupByProvider(options.cloud_models).map(({ provider, models }) => {
          const open = models.filter((model) => model.available)
          return (
            <div key={provider} className="flex flex-col gap-2">
              <p className="text-xs font-semibold text-text-h">{formatProviderLabel(provider)}</p>
              {open.length === 0 ? (
                <p className="text-xs text-text">
                  Nicht wählbar — für {formatProviderLabel(provider)} {PROVIDER_BLOCKED_TEXT}.
                </p>
              ) : (
                open.map((model) => (
                  <SideRow
                    key={`${provider}:${model.model}`}
                    name={name}
                    choice={{ kind: 'cloud', provider, model: model.model }}
                    selectedKey={selectedKey}
                    costLabel={SIDE_COST_LABELS.cloud}
                    onSelect={onChange}
                  />
                ))
              )}
            </div>
          )
        })
      )}

      {eyeBlocked ? (
        <p className="text-xs text-text">
          Nicht wählbar — {UNAVAILABLE_REASON_TEXTS.eye_disabled}.
        </p>
      ) : (
        options.eye_mappings.map((mapping) => (
          <SideRow
            key={mapping.eye_mapping_version}
            name={name}
            choice={{
              kind: 'eye',
              eye_model_revision: mapping.eye_model_revision,
              eye_mapping_version: mapping.eye_mapping_version,
            }}
            selectedKey={selectedKey}
            costLabel={SIDE_COST_LABELS.free}
            onSelect={onChange}
          />
        ))
      )}

      <SideRow
        name={name}
        choice={{ kind: 'local' }}
        selectedKey={selectedKey}
        costLabel={SIDE_COST_LABELS.free}
        onSelect={onChange}
      />

      {!eyeBlocked && options.eye_mappings.length > 0 && (
        <div className="pl-6">
          <EyeAttribution />
        </div>
      )}
    </fieldset>
  )
}

/** Die Kostenzeile EINER Seite: Wort, Betrag plus Menge - oder der Grund der Schaetzluecke. */
function sideEstimateText(part: {
  photo_count: number
  estimated_cost_usd: number | null
}): string {
  if (part.estimated_cost_usd === null) {
    return 'kein Preis hinterlegt'
  }
  if (part.estimated_cost_usd === 0) {
    return SIDE_COST_LABELS.free
  }
  return `${formatUsd(part.estimated_cost_usd)} für ${formatCount(part.photo_count)} Fotos`
}

interface ClassificationReviewCreatePanelProps {
  projectId: number
  /** Ziel von `aria-controls` des Umschalters im Kopf. */
  id: string
  onCreated: (review: ClassificationReviewCreatedOut) => void
}

/**
 * Das Anlegen-Panel der Klassifizierungspruefung (Spec 0616, Seite 1).
 *
 * Es steht inline unter dem Kopf, nicht in einem Dialog, und bleibt beim Zuklappen nicht im DOM.
 * Die Wahl folgt dem Muster "Wegwahl ohne Vorgabe": zwei `fieldset`s mit vollbreiten Radio-Zeilen,
 * KEINE Vorauswahl - ein vorbelegtes Radio waere eine Entscheidung, die niemand getroffen hat, und
 * bei einer Cloud-Seite die teuerste.
 *
 * Die Kostenvorschau erscheint erst nach beiden Wahlen und steht DAUERHAFT ueber dem Ausloeser:
 * kein Bestaetigungsdialog, die Kosten sind beim Betätigen sichtbar. Der Preis ist nie eine
 * Eingabe des Clients - er kommt aus `GET …/estimate`.
 *
 * Nach Erfolg meldet das Panel die angelegte Pruefung nach oben; die Navigation zur Uebersicht
 * entscheidet die Seite, weil sie den Projektpfad kennt.
 */
export function ClassificationReviewCreatePanel({
  projectId,
  id,
  onCreated,
}: ClassificationReviewCreatePanelProps) {
  const optionsQuery = useClassificationReviewOptionsQuery(projectId, true)
  const [sideA, setSideA] = useState<SideChoice | null>(null)
  const [sideB, setSideB] = useState<SideChoice | null>(null)
  const [sampleSizeInput, setSampleSizeInput] = useState<string | null>(null)

  const choices: Record<SideLetter, SideChoice | null> = { a: sideA, b: sideB }
  const sides = sideA !== null && sideB !== null ? { a: toSideIn(sideA), b: toSideIn(sideB) } : null
  const estimateQuery = useClassificationReviewEstimateQuery(projectId, sides)
  const createMutation = useCreateClassificationReviewMutation(projectId)
  const options = optionsQuery.data

  const sampleSize =
    sampleSizeInput ?? (options === undefined ? '' : String(options.sample_size.default))
  const sampleSizeValue = Number(sampleSize)
  const sampleSizeValid =
    options !== undefined &&
    Number.isInteger(sampleSizeValue) &&
    sampleSizeValue >= options.sample_size.min &&
    sampleSizeValue <= options.sample_size.max

  const isSubmitting = createMutation.isPending
  const isReady = sides !== null && sampleSizeValid && !isSubmitting

  // Der Sperrgrund steht als Satz an der Schaltflaeche - ein ausgegrauter Knopf ohne Begruendung
  // laesst raten, was fehlt.
  const disabledReason = isSubmitting
    ? 'Die Prüfung wird angelegt…'
    : sides === null
      ? 'Wähle für beide Seiten ein Verfahren — ohne Wahl startet keine Prüfung.'
      : !sampleSizeValid
        ? `Die Prüfgröße muss zwischen ${options?.sample_size.min} und ${options?.sample_size.max} liegen.`
        : null

  const createErrorDetail = createMutation.isError
    ? createMutation.error instanceof ApiError
      ? createMutation.error.detail
      : 'Fehler beim Anlegen der Prüfung.'
    : null

  function handleStart(): void {
    if (!isReady || sides === null) {
      return
    }
    createMutation.mutate(
      { a: sides.a, b: sides.b, sample_size: sampleSizeValue },
      { onSuccess: (created) => onCreated(created) },
    )
  }

  const estimate = estimateQuery.data
  const unknownPrice =
    estimate !== undefined &&
    (estimate.a.estimated_cost_usd === null || estimate.b.estimated_cost_usd === null)
  const total =
    estimate === undefined || unknownPrice
      ? null
      : (estimate.a.estimated_cost_usd ?? 0) + (estimate.b.estimated_cost_usd ?? 0)

  return (
    <section
      id={id}
      aria-label={CLASSIFICATION_REVIEW_TEXTS.createOpen}
      className="flex w-full flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      {optionsQuery.isPending && (
        <p role="status" className="text-sm text-text">
          Verfahren werden geladen…
        </p>
      )}
      {optionsQuery.isError && (
        <Alert onRetry={() => void optionsQuery.refetch()}>
          {optionsQuery.error instanceof ApiError
            ? optionsQuery.error.detail
            : 'Die wählbaren Verfahren konnten nicht geladen werden.'}
        </Alert>
      )}

      {options !== undefined && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {SIDE_ORDER.map((letter) => (
              <SideChoices
                key={letter}
                letter={letter}
                options={options}
                choice={choices[letter]}
                onChange={(choice) => (letter === 'a' ? setSideA(choice) : setSideB(choice))}
              />
            ))}
          </div>

          <div className="flex w-full max-w-xs flex-col gap-1">
            <label htmlFor={`${id}-sample-size`} className="text-sm font-medium text-text-h">
              {CLASSIFICATION_REVIEW_TEXTS.sampleSizeLabel}
            </label>
            <Input
              id={`${id}-sample-size`}
              type="number"
              inputMode="numeric"
              min={options.sample_size.min}
              max={options.sample_size.max}
              value={sampleSize}
              aria-invalid={sampleSize === '' || !sampleSizeValid}
              onChange={(event) => setSampleSizeInput(event.target.value)}
            />
            <p className="text-xs text-text-muted">{CLASSIFICATION_REVIEW_TEXTS.sampleSizeHint}</p>
          </div>

          {/* Erst mit beiden Seiten: vorher gibt es keinen Durchlauf, dessen Kosten sie
              beschriebe. Sie steht dauerhaft ueber dem Ausloeser, nicht in einem Dialog. */}
          {sides !== null && (
            <div
              data-testid="review-estimate"
              aria-live="polite"
              className="flex w-full max-w-sm flex-col gap-1 text-sm"
            >
              <h3 className="text-sm font-semibold text-text-h">
                {CLASSIFICATION_REVIEW_TEXTS.estimateTitle}
              </h3>
              {estimateQuery.isPending && (
                <p className="text-sm text-text">Kostenvorschau wird geladen…</p>
              )}
              {estimateQuery.isError && (
                <Alert onRetry={() => void estimateQuery.refetch()}>
                  {estimateQuery.error instanceof ApiError
                    ? estimateQuery.error.detail
                    : 'Kostenschätzung konnte nicht geladen werden.'}
                </Alert>
              )}
              {estimate !== undefined && (
                <>
                  {/* Eine Zeile je Seite, wortgleich "Seite A: kostenfrei" - ein Textknoten,
                      damit Vorlesehilfe und Test dieselbe Zeile lesen. */}
                  <p className="text-sm text-text">{`${SIDE_LABELS.a}: ${sideEstimateText(estimate.a)}`}</p>
                  <p className="text-sm text-text">{`${SIDE_LABELS.b}: ${sideEstimateText(estimate.b)}`}</p>
                  <p className="flex items-baseline justify-between gap-3 border-t border-separator pt-1">
                    <span className="font-semibold text-text-h">Gesamtsumme</span>
                    <span className="shrink-0 font-semibold text-text-h">
                      {total === null
                        ? 'kein Preis hinterlegt'
                        : total === 0
                          ? SIDE_COST_LABELS.free
                          : formatUsd(total)}
                    </span>
                  </p>
                  {unknownPrice && (
                    <p className="text-xs text-text-muted">
                      Für dieses Modell ist kein Preis hinterlegt — die Kosten lassen sich nicht
                      schätzen.
                    </p>
                  )}
                </>
              )}
            </div>
          )}

          {createErrorDetail !== null && <Alert>{createErrorDetail}</Alert>}
          {disabledReason !== null && (
            <p className="text-xs text-text-muted" data-testid="review-disabled-reason">
              {disabledReason}
            </p>
          )}

          <div>
            <Button onClick={handleStart} disabled={!isReady} busy={isSubmitting}>
              {CLASSIFICATION_REVIEW_TEXTS.start}
            </Button>
          </div>
        </>
      )}
    </section>
  )
}
