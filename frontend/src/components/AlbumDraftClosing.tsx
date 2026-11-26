import { Link } from 'react-router'

import { Button } from './ui/button'

export interface AlbumDraftClosingProps {
  sentences: string[]
  selectionPath: string
}

/** Der Abschluss des Album-Entwurfs: der Stand in Sätzen und der Weg zur Endauswahl. */
export function AlbumDraftClosing({ sentences, selectionPath }: AlbumDraftClosingProps) {
  return (
    <section className="flex flex-col items-start gap-2 border-t border-separator pt-6">
      <h2 className="text-lg">Stand des Entwurfs</h2>
      {sentences.map((sentence) => (
        <p key={sentence} className="text-sm text-text">
          {sentence}
        </p>
      ))}
      <Button asChild>
        <Link to={selectionPath}>Zur Endauswahl</Link>
      </Button>
    </section>
  )
}
