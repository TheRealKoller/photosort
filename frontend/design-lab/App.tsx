/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): Huelle des Design-Labors mit
 * den drei Umschaltern Richtung / Ansicht / Modus.
 *
 * Die Huelle selbst nutzt einen eigenen, absichtlich unauffaelligen Klassenraum (`lab-*`, siehe
 * shell.css) mit neutralem Grau - die Rahmung darf keine der fuenf Richtungen bevorzugen. Jede
 * Richtung rendert in einen eigenen Wurzelknoten mit `data-direction`/`data-mode`; alle
 * Richtungs-CSS ist auf genau diese Attribute gescopt (Schutzgelaender G2).
 */
import { useState } from 'react'

import { DIRECTIONS, type DirectionId } from './directions'
import { localPhotoCount } from './photoSvg'

type ViewId = 'grid' | 'detail' | 'pipeline'
type ModeId = 'light' | 'dark'

interface ViewDefinition {
  id: ViewId
  label: string
}

const VIEWS: readonly ViewDefinition[] = [
  { id: 'grid', label: 'Fotogrid' },
  { id: 'detail', label: 'Foto-Detail' },
  { id: 'pipeline', label: 'Pipeline & Kuratierung' },
]

const MODES: readonly { id: ModeId; label: string }[] = [
  { id: 'light', label: 'Hell' },
  { id: 'dark', label: 'Dunkel' },
]

interface SwitchProps<T extends string> {
  legend: string
  options: readonly { id: T; label: string }[]
  value: T
  onChange: (value: T) => void
}

function LabSwitch<T extends string>({ legend, options, value, onChange }: SwitchProps<T>) {
  return (
    <fieldset className="lab-switch">
      <legend className="lab-switch__legend">{legend}</legend>
      <div className="lab-switch__options">
        {options.map((option) => (
          <button
            key={option.id}
            type="button"
            className="lab-switch__button"
            aria-pressed={option.id === value}
            onClick={() => onChange(option.id)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
  )
}

/**
 * Ein einzelner Vergleichsrahmen: eine Richtung, eine Ansicht, ein Modus. Feste Mobilbreite
 * (~390 px), damit die Rahmen im Vergleich "Nebeneinander" vergleichbar bleiben.
 */
function DirectionFrame({
  direction,
  view,
  mode,
}: {
  direction: DirectionId
  view: ViewId
  mode: ModeId
}) {
  return (
    <div className="lab-frame__viewport" data-direction={direction} data-mode={mode}>
      {/* Die drei Ansichtskomponenten entstehen in Schritt 3 der Umsetzungsreihenfolge. */}
      <p className="dl-placeholder">
        {view} · {direction} · {mode}
      </p>
    </div>
  )
}

export function App() {
  const [direction, setDirection] = useState<DirectionId>('organic')
  const [view, setView] = useState<ViewId>('grid')
  const [mode, setMode] = useState<ModeId>('light')

  return (
    <div className="lab">
      <header className="lab-header">
        <h1 className="lab-header__title">PhotoSort · Design-Labor</h1>
        <p className="lab-header__note">
          Temporäres Wegwerf-Artefakt (Spec 0287). Nur im Vite-Dev-Server erreichbar, nicht Teil
          der ausgelieferten Anwendung.
        </p>
        {/* Selbstdiagnose statt eines Tests: der photos-local/-Glob ist der einzige Mechanismus
            im Labor, dessen Fehlschlag STILL waere - man saehe generierte Motive und wuesste
            nicht, ob die eigenen Dateien am falschen Ort liegen oder der Import nicht greift. */}
        <p className="lab-diagnostics">
          {localPhotoCount > 0
            ? `${localPhotoCount} lokale Fotos aktiv`
            : 'keine lokalen Fotos gefunden (frontend/design-lab/photos-local/) — es werden generierte Motive gezeigt'}
        </p>
      </header>

      <div className="lab-controls">
        <LabSwitch
          legend="Richtung"
          options={DIRECTIONS.map((entry) => ({ id: entry.id, label: entry.label }))}
          value={direction}
          onChange={setDirection}
        />
        <LabSwitch legend="Ansicht" options={VIEWS} value={view} onChange={setView} />
        <LabSwitch legend="Modus" options={MODES} value={mode} onChange={setMode} />
      </div>

      <main className="lab-stage">
        <DirectionFrame direction={direction} view={view} mode={mode} />
      </main>
    </div>
  )
}
