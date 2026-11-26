import { Button } from './ui/button'

export interface AlbumDraftDayControlsProps {
  onExpandAll: () => void
  onCollapseAll: () => void
}

export function AlbumDraftDayControls({ onExpandAll, onCollapseAll }: AlbumDraftDayControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button type="button" variant="secondary" size="sm" onClick={onExpandAll}>
        Alle Tage aufklappen
      </Button>
      <Button type="button" variant="secondary" size="sm" onClick={onCollapseAll}>
        Alle Tage zuklappen
      </Button>
    </div>
  )
}
