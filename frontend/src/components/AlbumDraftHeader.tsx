import type { RefObject } from 'react'

import { STATION_LABELS } from '../utils/projectRoutes'
import { EyeAttribution } from './EyeAttribution'

export interface AlbumDraftHeaderProps {
  headingRef: RefObject<HTMLHeadingElement | null>
  /** `null`: keine Übersichtszeile (Entwurf nicht bereit oder ohne Events). */
  overviewText: string | null
  showEye: boolean
}

/** Kopf des Album-Entwurfs; die `h1` ist das Fokusziel nach einem filterversteckten Tausch. */
export function AlbumDraftHeader({ headingRef, overviewText, showEye }: AlbumDraftHeaderProps) {
  return (
    <header className="flex flex-col gap-1">
      <h1 ref={headingRef} tabIndex={-1} className="text-xl sm:text-2xl">
        {STATION_LABELS.album}
      </h1>
      {overviewText !== null && <p className="text-sm text-text">{overviewText}</p>}
      {showEye && <EyeAttribution />}
    </header>
  )
}
