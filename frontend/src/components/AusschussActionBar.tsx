import type { ReactNode } from 'react'

import type { ScoringRunSummary } from '../api/types'
import type { ProcessStatus } from '../utils/processStatus'
import { cancelledAtText } from '../utils/operationTexts'
import type { StepAction } from '../utils/stepActions'
import { StatusDot } from './StatusDot'
import { StepActionBar } from './StepActionBar'
import { Progress } from './ui/progress'

export function AusschussActionBar({
  action,
  statusDot,
  statusText,
  photosProcessed,
  photosTotal,
  scoringStatus,
  onAction,
  busy,
  onCancel,
  cancelRequested,
  cancelPending,
  cancelFocusToken,
}: {
  action: StepAction
  statusDot: ProcessStatus | null
  statusText: string
  photosProcessed: number
  photosTotal: number
  scoringStatus: ScoringRunSummary['status'] | null
  onAction: () => void
  busy: boolean
  onCancel: () => void
  cancelRequested: boolean
  cancelPending: boolean
  cancelFocusToken: unknown
}) {
  let detail: ReactNode
  if (scoringStatus === 'running') {
    detail = (
      <div className="flex w-full max-w-sm flex-col gap-2">
        <p className="text-sm text-text">
          {photosProcessed} von {photosTotal} Fotos verarbeitet
        </p>
        {photosTotal > 0 ? (
          <Progress aria-hidden="true" value={photosProcessed} max={photosTotal} />
        ) : (
          <Progress aria-hidden="true" />
        )}
      </div>
    )
  } else if (scoringStatus === 'cancelled' && photosTotal > 0) {
    // Eingefrorener Stand, keine Restdauer.
    detail = (
      <div className="flex w-full max-w-sm flex-col gap-2">
        <p className="text-sm text-text">
          {cancelledAtText(photosProcessed, photosTotal, 'Fotos')}
        </p>
        <Progress aria-hidden="true" value={photosProcessed} max={photosTotal} />
      </div>
    )
  } else {
    detail = null
  }

  return (
    <StepActionBar
      action={action}
      status={
        <>
          <StatusDot status={statusDot} />
          {statusText}
        </>
      }
      detail={detail}
      onAction={onAction}
      busy={busy}
      onCancel={onCancel}
      cancelRequested={cancelRequested}
      cancelPending={cancelPending}
      cancelFocusToken={cancelFocusToken}
      operation="ausschuss"
    />
  )
}
