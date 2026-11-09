import { useEffect, useId, useState } from 'react'

import { ApiError } from '../api/client'
import type { CloudModelOut, ModelChoiceOut } from '../api/types'
import { useModelChoiceQuery, useUpdateModelChoiceMutation } from '../hooks/useProjects'
import { MODEL_CHOICE_TEXTS, noApiKeyText } from '../utils/classificationReviewLabels'
import { formatProviderLabel, formatUsd, formatUsdPerImage } from '../utils/formatStats'
import { EyeAttribution } from './EyeAttribution'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Skeleton } from './ui/skeleton'

/**
 * Der Abschnitt „Modellwahl" der Projekteinstellungen (Spec 0383, ADR 0143).
 *
 * Je Tätigkeit genau EIN Radio (nie zwei Kontrollkästchen: „keine Kategorisierung" schließt das
 * Datenmodell aus), alle Marken einer Tätigkeit in einer Gruppe über `name`. Beide Marken dürfen
 * gleichzeitig auf derselben Karte stehen; keine löscht die andere.
 *
 * Gespeichert wird EINMAL unter dem Raster, nicht je Karte: der `PUT` schreibt alle drei Spalten
 * in einem Commit, und erst diese Atomarität macht „ein fehlgeschlagenes Speichern lässt die
 * bisherige Wahl unverändert" wahr. Nach einem Fehlschlag springen die Marken auf die
 * Serverantwort zurück, statt den geänderten Entwurf stehen zu lassen.
 *
 * Die Fakten der Karte bleiben in JEDEM Zustand lesbar; `disabled` trägt nur das Bedienelement.
 */

type Draft = {
  categoryMethod: 'cloud' | 'eye'
  categoryModel: string | null
  // Die Herkunft gehört zum Entwurf: `true` heißt "Spalte steht auf `NULL`", und `NULL` ist die
  // Installationsvorgabe, kein Modellname. Ohne diese Marke schriebe jedes Speichern das
  // aufgelöste Modell fest - der Bestand verlöre die Eigenschaft, der Vorgabe zu folgen, und in
  // einer Installation ohne Schlüssel scheiterte der `PUT` sogar (`422`).
  categoryIsDefault: boolean
  landmarkModel: string | null
  landmarkIsDefault: boolean
}

function draftFrom(current: ModelChoiceOut['current']): Draft {
  return {
    categoryMethod: current.category_method,
    categoryModel: current.category_model,
    categoryIsDefault: current.category_is_default,
    landmarkModel: current.landmark_model,
    landmarkIsDefault: current.landmark_is_default,
  }
}

function isUnchanged(current: ModelChoiceOut['current'], draft: Draft): boolean {
  return (
    current.category_method === draft.categoryMethod &&
    current.category_model === draft.categoryModel &&
    current.category_is_default === draft.categoryIsDefault &&
    current.landmark_model === draft.landmarkModel &&
    current.landmark_is_default === draft.landmarkIsDefault
  )
}

/** Der Rumpf des `PUT`: die Vorgabe wird als `null` gespeichert, nie als ihr aufgelöster Wert. */
function storedBody(draft: Draft): {
  category_method: 'cloud' | 'eye'
  category_model: string | null
  landmark_model: string | null
} {
  return {
    category_method: draft.categoryMethod,
    category_model: draft.categoryIsDefault ? null : draft.categoryModel,
    landmark_model: draft.landmarkIsDefault ? null : draft.landmarkModel,
  }
}

/** Anbieter und Modell in einer Zeile für den zugänglichen Namen der Marke. */
function activityName(provider: string, model: string): string {
  return `${formatProviderLabel(provider)}, ${model}`
}

export function ModelChoiceSection({ projectId }: { projectId: number }) {
  const query = useModelChoiceQuery(projectId)
  const mutation = useUpdateModelChoiceMutation(projectId)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saved, setSaved] = useState(false)
  const categoryGroupName = useId()
  const landmarkGroupName = useId()

  const current = query.data?.current ?? null

  // Die Marken folgen der Serverantwort: nach dem Laden und nach jedem Speichern (Erfolg wie
  // Fehlschlag) ist die Antwort die Wahrheit - der Entwurf ist nur eine Ableitung davon.
  useEffect(() => {
    if (current !== null) {
      setDraft(draftFrom(current))
    }
  }, [current])

  if (query.isPending) {
    return (
      <section className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4">
        <h2 className="text-lg text-text-h">Modellwahl</h2>
        <div role="status" aria-label="Modellwahl wird geladen" className="flex flex-col gap-3">
          <Skeleton className="h-40 w-full rounded-lg" />
          <Skeleton className="h-40 w-full rounded-lg" />
        </div>
      </section>
    )
  }

  if (query.isError || query.data === undefined || current === null || draft === null) {
    return (
      <section className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4">
        <h2 className="text-lg text-text-h">Modellwahl</h2>
        <Alert variant="error" onRetry={() => void query.refetch()}>
          {query.error instanceof ApiError
            ? query.error.detail
            : 'Die Modellwahl konnte nicht geladen werden.'}
        </Alert>
      </section>
    )
  }

  const catalogue = query.data.cloud_models
  const eyeAvailable = query.data.eye.available
  const eyeReasons = query.data.eye.unavailable_reasons
  const noLandmarkModel = catalogue.every((entry) => !entry.available)

  const removedCategory =
    current.category_model !== null && current.category_provider === null
      ? current.category_model
      : null
  const removedLandmark = current.landmark_provider === null ? current.landmark_model : null
  const blockedByRemovedModel = removedCategory !== null || removedLandmark !== null

  const dirty = !isUnchanged(current, draft)
  const saving = mutation.isPending
  const saveDisabled = !dirty || saving || blockedByRemovedModel

  const saveError = mutation.isError ? mutation.error : null
  const saveErrorDetail =
    saveError === null
      ? null
      : saveError instanceof ApiError
        ? saveError.detail
        : 'Die Modellwahl konnte nicht gespeichert werden.'
  const saveErrorStatus = saveError instanceof ApiError ? saveError.status : null
  const saveRetry =
    saveErrorStatus === null || saveErrorStatus >= 500
      ? () => {
          if (!saveDisabled) {
            handleSave()
          }
        }
      : undefined

  function handleSave(): void {
    if (saveDisabled || draft === null) {
      return
    }
    setSaved(false)
    mutation.mutate(storedBody(draft), {
      onSuccess: (answer) => {
        setDraft(draftFrom(answer.current))
        setSaved(true)
      },
      // Fehlschlag: die Marken springen auf die Serverantwort zurück.
      onError: () => {
        if (current !== null) {
          setDraft(draftFrom(current))
        }
      },
    })
  }

  function chooseCategoryModel(entry: CloudModelOut): void {
    if (draft === null) {
      return
    }
    setSaved(false)
    setDraft({
      ...draft,
      categoryMethod: 'cloud',
      categoryModel: entry.model,
      categoryIsDefault: false,
    })
  }

  function chooseCategoryEye(): void {
    if (draft === null) {
      return
    }
    setSaved(false)
    setDraft({
      ...draft,
      categoryMethod: 'eye',
      categoryModel: null,
      categoryIsDefault: false,
    })
  }

  function chooseLandmarkModel(entry: CloudModelOut): void {
    if (draft === null) {
      return
    }
    setSaved(false)
    setDraft({ ...draft, landmarkModel: entry.model, landmarkIsDefault: false })
  }

  return (
    <section
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
      data-testid="model-choice-section"
    >
      <div>
        <h2 className="text-lg text-text-h">Modellwahl</h2>
        <p className="text-sm text-text">
          Für jede Tätigkeit eine eigene Wahl. Beide gelten für beide Nutzer dieses Projekts. Eine
          Änderung wirkt auf künftige Läufe; vorhandene Ergebnisse und abgerechnete Beträge bleiben
          unverändert.
        </p>
      </div>

      {removedCategory !== null && (
        <p className="text-sm text-text" data-testid="model-choice-removed-category">
          Kategorisierung: {removedCategory} — dieses Modell ist nicht mehr wählbar. Wähle ein
          anderes.
        </p>
      )}
      {removedLandmark !== null && (
        <p className="text-sm text-text" data-testid="model-choice-removed-landmark">
          Sehenswürdigkeits-Erkennung: {removedLandmark} — dieses Modell ist nicht mehr wählbar.
          Wähle ein anderes.
        </p>
      )}

      {noLandmarkModel && (
        <p className="text-sm text-text-muted" data-testid="model-choice-no-landmark-model">
          Für die Sehenswürdigkeits-Erkennung ist derzeit kein Modell wählbar — für keinen Anbieter
          ist ein API-Schlüssel hinterlegt.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {catalogue.map((entry) => (
          <ModelCard
            key={`${entry.provider}/${entry.model}`}
            entry={entry}
            categoryGroupName={categoryGroupName}
            landmarkGroupName={landmarkGroupName}
            draft={draft}
            current={current}
            locked={saving}
            onChooseCategory={() => chooseCategoryModel(entry)}
            onChooseLandmark={() => chooseLandmarkModel(entry)}
          />
        ))}
        <EyeCard
          categoryGroupName={categoryGroupName}
          draft={draft}
          locked={saving}
          available={eyeAvailable}
          unavailableReason={
            eyeReasons.includes('eye_disabled') ? MODEL_CHOICE_TEXTS.eyeDisabled : null
          }
          onChoose={chooseCategoryEye}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={handleSave} disabled={saveDisabled}>
          Speichern
        </Button>
        {blockedByRemovedModel && (
          <p className="text-xs text-text-muted">
            Ein Modell ist nicht mehr wählbar — wähle für die betroffene Tätigkeit ein anderes.
          </p>
        )}
        {!blockedByRemovedModel && !dirty && !saving && (
          <p className="text-xs text-text-muted">Keine Änderung offen.</p>
        )}
      </div>

      {saveErrorDetail !== null && (
        <Alert variant="error" onRetry={saveRetry}>
          {saveErrorDetail} {MODEL_CHOICE_TEXTS.unchanged}
          {saveErrorStatus === 409
            ? ' Die Wahl lässt sich ändern, sobald der Lauf beendet ist.'
            : ''}
        </Alert>
      )}
      {saved && (
        <p role="status" className="text-sm text-text">
          {MODEL_CHOICE_TEXTS.saved}
        </p>
      )}
    </section>
  )
}

interface ModelCardProps {
  entry: CloudModelOut
  categoryGroupName: string
  landmarkGroupName: string
  draft: Draft
  current: ModelChoiceOut['current']
  locked: boolean
  onChooseCategory: () => void
  onChooseLandmark: () => void
}

function ModelCard({
  entry,
  categoryGroupName,
  landmarkGroupName,
  draft,
  current,
  locked,
  onChooseCategory,
  onChooseLandmark,
}: ModelCardProps) {
  const providerLabel = formatProviderLabel(entry.provider)
  const unavailableReason = entry.available ? null : noApiKeyText(providerLabel)
  const categoryChecked = draft.categoryMethod === 'cloud' && draft.categoryModel === entry.model
  const landmarkChecked = draft.landmarkModel === entry.model
  const categoryLocked = categoryChecked && !entry.available
  const landmarkLocked = landmarkChecked && !entry.available

  return (
    <div
      data-testid={`model-card-${entry.model}`}
      className="flex flex-col gap-3 rounded-lg border border-border bg-elevated p-3"
    >
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium text-text-h">{providerLabel}</span>
        <span className="font-mono text-xs break-words text-text">{entry.model}</span>
        <span className="text-xs text-text">{formatUsdPerImage(entry.estimate_usd_per_image)}</span>
        <span className="text-xs text-text-muted">
          {entry.input_usd_per_mtok === null ? 'unbekannt' : formatUsd(entry.input_usd_per_mtok)} je
          Million Eingabe-Token ·{' '}
          {entry.output_usd_per_mtok === null ? 'unbekannt' : formatUsd(entry.output_usd_per_mtok)}{' '}
          je Million Ausgabe-Token
        </span>
        <span className="text-xs text-text-muted">
          {entry.requests_per_minute} Anfrage{entry.requests_per_minute === 1 ? '' : 'n'} pro Minute
          — gilt für alle Projekte gemeinsam
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <ChoiceRow
          groupName={categoryGroupName}
          value={`category:${entry.model}`}
          checked={categoryChecked}
          disabled={locked || !entry.available}
          onChange={onChooseCategory}
          label={MODEL_CHOICE_TEXTS.categoryGroup}
          accessibleName={`${MODEL_CHOICE_TEXTS.categoryGroup}: ${activityName(entry.provider, entry.model)}`}
          reason={unavailableReason}
          stillSelected={categoryLocked ? MODEL_CHOICE_TEXTS.stillSelected : null}
          installationDefault={
            categoryChecked && current.category_method === 'cloud' && current.category_is_default
          }
        />
        <ChoiceRow
          groupName={landmarkGroupName}
          value={`landmark:${entry.model}`}
          checked={landmarkChecked}
          disabled={locked || !entry.available}
          onChange={onChooseLandmark}
          label={MODEL_CHOICE_TEXTS.landmarkGroup}
          accessibleName={`${MODEL_CHOICE_TEXTS.landmarkGroup}: ${activityName(entry.provider, entry.model)}`}
          reason={unavailableReason}
          stillSelected={landmarkLocked ? MODEL_CHOICE_TEXTS.stillSelected : null}
          installationDefault={landmarkChecked && current.landmark_is_default}
        />
      </div>
    </div>
  )
}

interface EyeCardProps {
  categoryGroupName: string
  draft: Draft
  locked: boolean
  available: boolean
  unavailableReason: string | null
  onChoose: () => void
}

function EyeCard({
  categoryGroupName,
  draft,
  locked,
  available,
  unavailableReason,
  onChoose,
}: EyeCardProps) {
  const checked = draft.categoryMethod === 'eye'
  return (
    <div
      data-testid="model-card-eye"
      className="flex flex-col gap-3 rounded-lg border border-border bg-elevated p-3"
    >
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium text-text-h">Eye</span>
        <span className="text-xs text-text">{MODEL_CHOICE_TEXTS.free}</span>
      </div>

      <div className="flex flex-col gap-2">
        <ChoiceRow
          groupName={categoryGroupName}
          value="category:eye"
          checked={checked}
          disabled={locked || !available}
          onChange={onChoose}
          label={MODEL_CHOICE_TEXTS.categoryGroup}
          accessibleName={`${MODEL_CHOICE_TEXTS.categoryGroup}: Eye`}
          reason={unavailableReason}
          stillSelected={checked && !available ? MODEL_CHOICE_TEXTS.stillSelected : null}
          installationDefault={false}
        />
        <p className="text-xs text-text-muted">{MODEL_CHOICE_TEXTS.eyeNoLandmark}</p>
      </div>

      <div className="flex flex-col gap-1">
        <EyeAttribution />
        <p className="text-xs text-text-muted">{MODEL_CHOICE_TEXTS.eyeLicenceNotice}</p>
      </div>
    </div>
  )
}

interface ChoiceRowProps {
  groupName: string
  value: string
  checked: boolean
  disabled: boolean
  onChange: () => void
  label: string
  accessibleName: string
  reason: string | null
  stillSelected: string | null
  installationDefault: boolean
}

/** Eine Auswahlzeile in der Form der bestehenden Wegwahl - ganze Zeile anklickbar. */
function ChoiceRow({
  groupName,
  value,
  checked,
  disabled,
  onChange,
  label,
  accessibleName,
  reason,
  stillSelected,
  installationDefault,
}: ChoiceRowProps) {
  return (
    <label className="flex min-h-11 cursor-pointer flex-col justify-center gap-1 rounded-sm border border-border px-3 py-2 has-[:checked]:border-accent">
      <span className="flex items-center gap-2">
        <input
          type="radio"
          name={groupName}
          value={value}
          checked={checked}
          disabled={disabled}
          onChange={onChange}
          aria-label={accessibleName}
          className="size-4 accent-accent"
        />
        <span className="text-sm text-text">{label}</span>
        {installationDefault && (
          <span className="text-xs text-text-muted">{MODEL_CHOICE_TEXTS.installationDefault}</span>
        )}
      </span>
      {reason !== null && <span className="pl-6 text-xs text-text-muted">{reason}</span>}
      {stillSelected !== null && (
        <span className="pl-6 text-xs text-text-muted">
          {stillSelected}
          {reason !== null ? ` ${reason}` : ''}
        </span>
      )}
    </label>
  )
}
