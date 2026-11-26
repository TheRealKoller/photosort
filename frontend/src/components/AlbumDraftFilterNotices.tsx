import { Button } from './ui/button'

export interface AlbumDraftFilterNoticesProps {
  isFiltered: boolean
  visibleCount: number
  inAlbumCount: number
  /** Das zuletzt eingetauschte Foto ist durch den aktuellen Filter ausgeblendet. */
  hiddenExchange: boolean
  onReset: () => void
}

/** Statuszeile und Leerzustand des Personenfilters im Album-Entwurf. */
export function AlbumDraftFilterNotices({
  isFiltered,
  visibleCount,
  inAlbumCount,
  hiddenExchange,
  onReset,
}: AlbumDraftFilterNoticesProps) {
  if (!isFiltered) {
    return null
  }
  return (
    <>
      <p role="status" className="text-sm text-text">
        {hiddenExchange
          ? 'Das eingetauschte Foto ist durch den Filter ausgeblendet.'
          : `${visibleCount} von ${inAlbumCount} Fotos des Entwurfs sichtbar.`}
      </p>
      {visibleCount === 0 && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">Keine Fotos des Entwurfs mit diesem Filter.</p>
          <Button type="button" variant="outline" size="sm" onClick={onReset}>
            Filter zurücksetzen
          </Button>
        </div>
      )}
    </>
  )
}
