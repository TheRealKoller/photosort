import { useId, useRef, useState } from 'react'

import { Button } from './ui/button'
import { Icon } from './ui/icon'

/**
 * SICHERHEIT (S12): Der Erklärtext merkt sich EINEN Wahrheitswert, nie Inhalt. Schlüssel ist ein
 * festes Präfix plus der Anmeldename (nur zur Unterscheidung je Nutzer, keine Zugriffsentscheidung),
 * Wert ein einziges festes Literal für „zugeklappt". Alles andere - fehlend, fremd, beschädigt -
 * gilt als aufgeklappt; jeder Zugriff steht in `try/catch` und fällt nach „aufgeklappt" aus.
 */
const STORAGE_PREFIX = 'photosort.albumDraft.explainerCollapsed.'
const COLLAPSED_VALUE = 'collapsed'

export function explainerStorageKey(username: string): string {
  return `${STORAGE_PREFIX}${username}`
}

function readCollapsed(username: string | null): boolean {
  if (username === null) {
    return false
  }
  try {
    return window.localStorage.getItem(explainerStorageKey(username)) === COLLAPSED_VALUE
  } catch {
    return false
  }
}

function writeCollapsed(username: string | null, collapsed: boolean): void {
  if (username === null) {
    return
  }
  try {
    if (collapsed) {
      window.localStorage.setItem(explainerStorageKey(username), COLLAPSED_VALUE)
    } else {
      window.localStorage.removeItem(explainerStorageKey(username))
    }
  } catch {
    // Kein Speicher (gesperrt, Private-Modus, Kontingent): die Seite bleibt bedienbar.
  }
}

/** Der zuklappbare Erklärtext über dem ersten Foto des Album-Entwurfs. */
export function DraftExplainer({ username }: { username: string | null }) {
  const [collapsed, setCollapsed] = useState(() => readCollapsed(username))
  const panelId = useId()
  const toggleRef = useRef<HTMLButtonElement>(null)

  function toggle(next: boolean): void {
    setCollapsed(next)
    writeCollapsed(username, next)
    // Der Fokus bleibt auf dem Umschalter, der danach sichtbar ist (beide tragen den Ref).
    requestAnimationFrame(() => toggleRef.current?.focus())
  }

  if (collapsed) {
    return (
      <div>
        <Button
          ref={toggleRef}
          type="button"
          variant="ghost"
          size="sm"
          aria-expanded={false}
          aria-controls={panelId}
          onClick={() => toggle(false)}
        >
          <Icon name="info" size={16} />
          So funktioniert der Entwurf
        </Button>
      </div>
    )
  }
  return (
    <div
      id={panelId}
      className="flex items-start gap-3 rounded-lg border border-border bg-surface p-3"
    >
      <Icon name="info" size={18} className="shrink-0" />
      <div className="flex min-w-0 flex-1 flex-col gap-1 text-sm text-text">
        <p>Hier steht der Vorschlag des Systems als dein Entwurf.</p>
        <p>
          Greif nur dort ein, wo dich etwas stört – streichen, tauschen oder ein Foto hinzufügen.
        </p>
        <p>Nichts muss bestätigt werden; du bist fertig, wenn du zufrieden bist.</p>
      </div>
      <Button
        ref={toggleRef}
        type="button"
        variant="ghost"
        size="sm"
        aria-expanded
        aria-controls={panelId}
        onClick={() => toggle(true)}
      >
        Ausblenden
      </Button>
    </div>
  )
}
