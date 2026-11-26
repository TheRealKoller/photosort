import { Link } from 'react-router'

import { Button } from './ui/button'

export interface AlbumDraftNoticeProps {
  text: string
  to: string
  linkLabel: string
}

/** Ein Hinweis des Album-Entwurfs: ein Satz und der Weg, der ihn auflöst. */
export function AlbumDraftNotice({ text, to, linkLabel }: AlbumDraftNoticeProps) {
  return (
    <div className="flex flex-col items-start gap-3">
      <p className="text-sm text-text">{text}</p>
      <Button asChild variant="secondary" size="sm">
        <Link to={to}>{linkLabel}</Link>
      </Button>
    </div>
  )
}
