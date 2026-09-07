import { useId, useState } from 'react'
import { useNavigate } from 'react-router'

import { ApiError } from '../api/client'
import { useDeleteProjectMutation } from '../hooks/useProjects'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Dialog } from './ui/dialog'
import { Input } from './ui/input'

/**
 * Vergleicht die getippte Bestaetigung mit dem Projektnamen - EXAKT: kein Trim, kein
 * `toLowerCase()` (specs/features/0044-projekte-loeschen.md).
 *
 * Bewusst als eigene, exportierte und einzeln geprüfte Funktion statt als Ausdruck im JSX: die
 * Reibung ist hier der Zweck der Konstruktion, und ein spaeterer "Aufraeum"-Refactor, der still
 * trimmt oder Gross-/Kleinschreibung ignoriert, MUSS an einem Test scheitern.
 *
 * Die Asymmetrie zum Server (der trimmt) ist beabsichtigt: dort wehrt der Trim einen per curl
 * abgesetzten Zeilenumbruch ab, hier bliebe die Huerde sonst nicht die, die sie sein soll.
 */
export function isExactProjectNameMatch(input: string, projectName: string): boolean {
  return input === projectName
}

interface DeleteProjectDialogProps {
  open: boolean
  onClose: () => void
  projectId: number
  projectName: string
}

/** Was der Server geantwortet hat - bestimmt Ausprägung, Titel und Bedienbarkeit der Meldung. */
interface DeleteFailure {
  status: number | null
  detail: string
}

function toFailure(error: unknown): DeleteFailure {
  if (error instanceof ApiError) {
    return { status: error.status, detail: error.detail }
  }
  return {
    status: null,
    detail: 'Das Projekt konnte nicht gelöscht werden. Bitte versuche es erneut.',
  }
}

/**
 * Bestaetigungsdialog vor der Projektloeschung (specs/features/0044-projekte-loeschen.md).
 *
 * Erster Konsument des seit Spec 0320 vorhandenen `ui/dialog.tsx` - natives `<dialog>`, keine neue
 * Abhaengigkeit. Bewusst KEIN `icon`: das Grundelement zeichnet das Titelsymbol in `--accent`,
 * `x-circle` in Bernstein waere gleichzeitig das Aussortiert-Symbol in der Favoritenfarbe.
 *
 * Der Inhalt ist KEIN `<form>`: die Eingabetaste darf nicht ausloesen, ausgeloest wird
 * ausschliesslich ueber die Schaltflaeche. Die bewusste Reibung ist der Zweck.
 */
export function DeleteProjectDialog({
  open,
  onClose,
  projectId,
  projectName,
}: DeleteProjectDialogProps) {
  const navigate = useNavigate()
  const [confirmation, setConfirmation] = useState('')
  const [failure, setFailure] = useState<DeleteFailure | null>(null)
  const deleteMutation = useDeleteProjectMutation(projectId)
  const nameId = useId()

  const isPending = deleteMutation.isPending
  // Nach einem 404 gibt es nichts mehr zu loeschen - Feld und Schaltflaeche werden dauerhaft
  // stillgelegt. Nach 409/400/Netzwerkfehler bleiben beide bedienbar: die Loeschen-Schaltflaeche
  // IST die Wiederholung, ein zweites "Erneut versuchen" waeren zwei Bedienelemente fuer
  // dieselbe Aktion, ausgerechnet an der gefaehrlichsten Stelle des Produkts.
  const isGone = failure?.status === 404
  const canDelete = isExactProjectNameMatch(confirmation, projectName) && !isGone

  function goToProjectList(): void {
    void navigate('/projects')
  }

  /*
   * Esc und "Abbrechen" laufen beide hier durch. Drei Faelle, in dieser Reihenfolge:
   *  1. Anfrage laeuft -> ignorieren. Das Grundelement erzwingt das nicht und sieht ein bewusstes
   *     Ignorieren durch den Aufrufer ausdruecklich vor; Esc wuerde den Dialog sonst schliessen,
   *     ohne die Anfrage abzubrechen, und den Nutzer auf einer Einstellungsseite zuruecklassen,
   *     deren Gegenstand gerade verschwindet.
   *  2. Das Projekt ist weg (404) -> derselbe Weg wie "Zur Projektliste": die Seite dahinter ist
   *     gegenstandslos geworden. Der Aufrufer bekommt trotzdem sein `onClose` (Copilot-Fund,
   *     PR #351) - sonst bliebe der Dialog bei ihm offen, und mit ihm der Zustand `isGone`.
   *  3. Sonst -> regulaeres Schliessen.
   */
  function handleClose(): void {
    if (isPending) {
      return
    }
    onClose()
    if (isGone) {
      goToProjectList()
    }
  }

  function handleDelete(): void {
    setFailure(null)
    deleteMutation.mutate(confirmation, {
      onSuccess: () => {
        onClose()
        goToProjectList()
      },
      onError: (error) => {
        setFailure(toFailure(error))
      },
    })
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title="Projekt löschen?"
      description="Diese Aktion kann nicht rückgängig gemacht werden."
      cancelLabel={isGone ? 'Zur Projektliste' : 'Abbrechen'}
      cancelDisabled={isPending}
      actions={
        <Button
          variant="destructive"
          busy={isPending}
          disabled={!canDelete}
          onClick={handleDelete}
        >
          {isPending ? 'Wird gelöscht…' : 'Projekt löschen'}
        </Button>
      }
    >
      <p className="text-sm text-text">
        Gelöscht werden alle PhotoSort-Daten dieses Projekts (Fotodatensätze, Bewertungen,
        Kategorien, Bewertungs- und Kuratierungsläufe). Die Original-Fotos auf OpenCloud bleiben
        erhalten.
      </p>
      <label className="flex flex-col gap-2">
        <span className="text-xs font-medium text-text-h">
          Projektnamen zur Bestätigung eintippen
        </span>
        {/* Der zu tippende Name muss SICHTBAR sein - sonst muesste der Nutzer den Dialog
            verlassen, um ihn nachzulesen, und das ist keine Huerde, sondern eine Sackgasse.
            `font-mono` auf beiden Seiten, weil ein Literal verglichen wird, bei dem l/1/I und
            O/0 unterscheidbar sein muessen. Projektnamen sind vom Nutzer eingegebener Text und
            stehen ausschliesslich als regulaerer React-Textknoten. */}
        <span id={nameId} className="font-mono text-sm break-words text-text-h">
          {projectName}
        </span>
        <Input
          className="font-mono"
          value={confirmation}
          onChange={(event) => {
            setConfirmation(event.target.value)
          }}
          disabled={isPending || isGone}
          aria-describedby={nameId}
          aria-invalid={failure?.status === 400 ? true : undefined}
          // `autoCapitalize="off"` ist nicht Kosmetik: Mobilgeraete schreiben den ersten
          // Buchstaben automatisch gross, was den gross-/kleinschreibungsgenauen Vergleich
          // bricht - die Schaltflaeche schaltete sich nie frei, ohne dass irgendetwas einen
          // Fehler zeigt.
          autoComplete="off"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
        />
      </label>
      {/* Der Meldungsbereich steht UNTER dem Feld, direkt ueber der Schaltflaechenzeile - bewusste
          Abweichung vom Muster "Banner am Formularanfang": eine oben eingefuegte Meldung schoebe
          das Eingabefeld unter dem Finger nach unten. So wandert nur die Schaltflaechenzeile, und
          ein Fehlgriff geht ins Leere statt auf ein anderes Bedienelement.

          Kein `onRetry` in keinem der Faelle (siehe `canDelete` oben). */}
      {failure !== null && failure.status === 409 && (
        <Alert variant="warning" title="Ein Lauf ist noch aktiv">
          {failure.detail}
        </Alert>
      )}
      {failure !== null && failure.status === 404 && (
        <Alert variant="warning" title="Projekt nicht gefunden">
          Dieses Projekt existiert nicht mehr — es wurde offenbar bereits gelöscht.
        </Alert>
      )}
      {failure !== null && failure.status === 400 && (
        <Alert variant="error" title="Löschen nicht möglich">
          Der eingegebene Name stimmt nicht mit dem aktuellen Projektnamen überein. Möglicherweise
          wurde das Projekt zwischenzeitlich umbenannt.
        </Alert>
      )}
      {failure !== null &&
        failure.status !== 409 &&
        failure.status !== 404 &&
        failure.status !== 400 && <Alert variant="error">{failure.detail}</Alert>}
    </Dialog>
  )
}
