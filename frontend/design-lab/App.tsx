/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): Huelle des Design-Labors mit
 * den drei Umschaltern Richtung / Ansicht / Modus plus den beiden Vergleichsmodi
 * "Nebeneinander" (alle fuenf Richtungen) und "Beide Modi" (hell und dunkel derselben Richtung).
 *
 * Die Huelle selbst nutzt einen eigenen, absichtlich unauffaelligen Klassenraum (`lab-*`, siehe
 * shell.css) mit neutralem Grau - die Rahmung darf keine der fuenf Richtungen bevorzugen. Jede
 * Richtung rendert in einen eigenen Wurzelknoten mit `data-direction`/`data-mode`; alle
 * Richtungs-CSS ist auf genau diese Attribute gescopt (Schutzgelaender G2).
 *
 * SICHERHEIT (Auflage D3): Der URL-Zustand ist die EINZIGE Fremdeingabe im gesamten Artefakt. Jeder
 * Parameter wird gegen eine feste Positivliste aufgeloest, bevor er irgendetwas beeinflusst -
 * `dir` gegen die Ids der Richtungs-Registry, `view`/`mode`/`compare` gegen ihre Tabellen. Ein
 * nicht getroffener Wert faellt auf den Standard zurueck. Ein nicht validierter Wert darf niemals
 * in data-direction/data-mode, in einen Klassennamen, in einen CSS-Selektor oder -Wert, in einen
 * SVG-String oder in history.replaceState durchgereicht werden: React maskiert Attributwerte
 * zwar, der Umweg ueber CSS oder eine Selektorkonstruktion tut das nicht.
 *
 * Bewusst kein React Router im Labor - es soll keine zweite Routing-Realitaet neben der App geben.
 */
import { useEffect, useState } from 'react'

import { DIRECTIONS, type DirectionId } from './directions'
import { localPhotoCount } from './photoSvg'
import { DetailView } from './views/DetailView'
import { GridView } from './views/GridView'
import { PipelineView } from './views/PipelineView'

type ViewId = 'grid' | 'detail' | 'pipeline'
type ModeId = 'light' | 'dark'
type CompareId = 'off' | 'directions' | 'modes'

const VIEWS: readonly { id: ViewId; label: string }[] = [
  { id: 'grid', label: 'Fotogrid' },
  { id: 'detail', label: 'Foto-Detail' },
  { id: 'pipeline', label: 'Pipeline & Kuratierung' },
]

const MODES: readonly { id: ModeId; label: string }[] = [
  { id: 'light', label: 'Hell' },
  { id: 'dark', label: 'Dunkel' },
]

const COMPARE_MODES: readonly { id: CompareId; label: string }[] = [
  { id: 'off', label: 'Einzeln' },
  { id: 'directions', label: 'Nebeneinander' },
  { id: 'modes', label: 'Beide Modi' },
]

const DEFAULT_DIRECTION: DirectionId = 'organic'
const DEFAULT_VIEW: ViewId = 'grid'
const DEFAULT_MODE: ModeId = 'light'
const DEFAULT_COMPARE: CompareId = 'off'

/*
 * Positivliste des `compare`-Parameters. `1` ist der in der Spec dokumentierte Wert fuer
 * "Nebeneinander"; `modes` kam mit dem zweiten Vergleichsmodus dazu. Alles andere - auch ein
 * leerer oder gefaelschter Wert - faellt auf `off` zurueck.
 */
const COMPARE_BY_PARAM: Readonly<Record<string, CompareId>> = {
  '1': 'directions',
  modes: 'modes',
}

const COMPARE_PARAM_BY_ID: Readonly<Record<CompareId, string | null>> = {
  off: null,
  directions: '1',
  modes: 'modes',
}

function resolveDirection(raw: string | null): DirectionId {
  // Aufloesung ueber die Registry selbst - eine Id ohne Eintrag existiert nicht.
  return DIRECTIONS.find((entry) => entry.id === raw)?.id ?? DEFAULT_DIRECTION
}

function resolveView(raw: string | null): ViewId {
  return VIEWS.find((entry) => entry.id === raw)?.id ?? DEFAULT_VIEW
}

function resolveMode(raw: string | null): ModeId {
  return MODES.find((entry) => entry.id === raw)?.id ?? DEFAULT_MODE
}

function resolveCompare(raw: string | null): CompareId {
  if (raw !== null && Object.hasOwn(COMPARE_BY_PARAM, raw)) {
    return COMPARE_BY_PARAM[raw]
  }
  return DEFAULT_COMPARE
}

interface LabState {
  direction: DirectionId
  view: ViewId
  mode: ModeId
  compare: CompareId
}

function readStateFromUrl(): LabState {
  const params = new URLSearchParams(window.location.search)
  return {
    direction: resolveDirection(params.get('dir')),
    view: resolveView(params.get('view')),
    mode: resolveMode(params.get('mode')),
    compare: resolveCompare(params.get('compare')),
  }
}

function writeStateToUrl(state: LabState): void {
  // Ausschliesslich bereits aufgeloeste Werte - nichts aus der Adresszeile wird durchgereicht.
  const params = new URLSearchParams()
  params.set('dir', state.direction)
  params.set('view', state.view)
  params.set('mode', state.mode)
  const compareParam = COMPARE_PARAM_BY_ID[state.compare]
  if (compareParam !== null) {
    params.set('compare', compareParam)
  }
  window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`)
}

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
 * Ein einzelner Vergleichsrahmen: eine Richtung, eine Ansicht, ein Modus, in fester Mobilbreite
 * (~390 px). Die Beschriftung darueber traegt Richtungsnamen und Ein-Satz-Charakterisierung.
 */
function DirectionFrame({
  direction,
  view,
  mode,
  caption,
}: {
  direction: DirectionId
  view: ViewId
  mode: ModeId
  caption: { name: string; character: string }
}) {
  return (
    <figure className="lab-frame">
      <figcaption className="lab-frame__caption">
        <span className="lab-frame__name">{caption.name}</span>
        <span className="lab-frame__character">{caption.character}</span>
      </figcaption>
      <div className="lab-frame__viewport" data-direction={direction} data-mode={mode}>
        {view === 'grid' && <GridView />}
        {view === 'detail' && <DetailView />}
        {view === 'pipeline' && <PipelineView />}
      </div>
    </figure>
  )
}

function characterOf(direction: DirectionId): { name: string; character: string } {
  const entry = DIRECTIONS.find((candidate) => candidate.id === direction)
  return { name: entry?.label ?? direction, character: entry?.character ?? '' }
}

export function App() {
  const [state, setState] = useState<LabState>(readStateFromUrl)

  useEffect(() => {
    writeStateToUrl(state)
  }, [state])

  const { direction, view, mode, compare } = state
  const caption = characterOf(direction)
  const modeLabel = MODES.find((entry) => entry.id === mode)?.label ?? ''

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
          onChange={(value) => setState((previous) => ({ ...previous, direction: value }))}
        />
        <LabSwitch
          legend="Ansicht"
          options={VIEWS}
          value={view}
          onChange={(value) => setState((previous) => ({ ...previous, view: value }))}
        />
        <LabSwitch
          legend="Modus"
          options={MODES}
          value={mode}
          onChange={(value) => setState((previous) => ({ ...previous, mode: value }))}
        />
        <LabSwitch
          legend="Vergleich"
          options={COMPARE_MODES}
          value={compare}
          onChange={(value) => setState((previous) => ({ ...previous, compare: value }))}
        />
      </div>

      <main className={compare === 'off' ? 'lab-stage lab-stage--single' : 'lab-stage'}>
        {compare === 'off' && (
          <DirectionFrame direction={direction} view={view} mode={mode} caption={caption} />
        )}

        {compare === 'directions' &&
          DIRECTIONS.map((entry) => (
            <DirectionFrame
              key={entry.id}
              direction={entry.id}
              view={view}
              mode={mode}
              caption={{ name: entry.label, character: entry.character }}
            />
          ))}

        {compare === 'modes' &&
          MODES.map((entry) => (
            <DirectionFrame
              key={entry.id}
              direction={direction}
              view={view}
              mode={entry.id}
              caption={{ name: `${caption.name} · ${entry.label}`, character: caption.character }}
            />
          ))}
      </main>

      <p className="lab-diagnostics">
        {compare === 'off'
          ? `Einzelansicht · ${caption.name} · ${modeLabel}`
          : compare === 'directions'
            ? `Nebeneinander · alle fünf Richtungen · ${modeLabel}`
            : `Beide Modi · ${caption.name}`}
      </p>
    </div>
  )
}
