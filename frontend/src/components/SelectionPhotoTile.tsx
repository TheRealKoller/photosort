import type { AlbumParticipantOut, PhotoOut } from '../api/types'
import type { ParticipantStance } from '../utils/albumSelection'
import { participantStance } from '../utils/albumSelection'
import { PhotoCard } from './PhotoCard'
import { PhotoImage } from './PhotoImage'
import { RatingBadge } from './RatingBadge'
import { Badge } from './ui/badge'
import { Button } from './ui/button'

/**
 * Die Kennzeichnung „die beiden haben hier ausdrücklich entschieden".
 *
 * Sie ist eine EIGENE Angabe, kein Farbton: Einigkeit ist eine Vorbelegung, eine Entscheidung ist
 * eine getroffene Aussage. Ohne sichtbaren Unterschied wäre nicht erkennbar, ob jemand das Bild
 * schon angesehen hat.
 */
export const SELECTION_DECIDED_BADGE_TEXT = 'gemeinsam entschieden'

export interface SelectionPhotoTileProps {
  photo: PhotoOut
  /**
   * ALLE Teilnehmer, vom Server, nach `user_id` sortiert - sie und nicht `photo.ratings[]`
   * bestimmen die Zahl der Haltungszeilen. Aus `ratings[]` abgeleitet fehlte genau der Nutzer,
   * der noch nie etwas angefasst hat.
   */
  participants: AlbumParticipantOut[]
  /**
   * Welcher Wert wird gerade geschrieben? `null` = es läuft nichts.
   *
   * EIN Wert statt eines Wahrheitswerts, damit NUR die gedrückte Schaltfläche `busy` trägt: Bei
   * zwei Schaltflächen auf derselben Kachel sagte ein bloßes „hier läuft etwas" nicht, welche von
   * beiden gedrückt wurde, und beide trügen den Spinner.
   */
  decidingIncluded: boolean | null
  onDecide: (included: boolean) => void
}

/** Das Kennzeichen einer Haltung - der bestehende `RatingBadge`, nie ein neues Symbol. */
function StanceBadge({ stance }: { stance: ParticipantStance }) {
  if (stance === 'taken') {
    return <RatingBadge status="album_worthy" />
  }
  if (stance === 'struck') {
    return <RatingBadge status="rejected" />
  }
  // Das neutrale „–" heißt hier „hat nicht bewertet" - genau die Lesart, für die `PhotoCard` es
  // seinen übrigen Aufrufstellen vorbehält.
  return <RatingBadge status={null} />
}

/**
 * EINE Kachel der gemeinsamen Endauswahl: die Haltung JEDES Teilnehmers, benannt und untereinander,
 * dazu die eine Trefferfläche der gemeinsamen Entscheidung.
 *
 * EIGENE KACHEL STATT EINER ZWEITEN AUSPRÄGUNG VON `CurationPhotoTile`: jene trägt den Zweizustand
 * und die Alternativen des Einzelentwurfs, die es hier nicht gibt. Diese trägt weder
 * Motivstärkeliste noch Info-Popover - sie zeigt die Haltungen und die eine Entscheidung, sonst
 * nichts.
 *
 * ZWEI BENANNTE ZEILEN SIND DIE ZUSICHERUNG „die Haltung des einen wird nie als die des anderen
 * dargestellt": Die Zuordnung entsteht aus dem vorangestellten Namen und aus `user_id`, nie aus
 * Position, Reihenfolge oder Farbe allein. Jede Haltung ist dreifach codiert (Name des
 * Teilnehmers, eigenes Symbol, zugänglicher Name) und nie allein farbig - das Symbol `check` ist
 * dabei ausgeschlossen, es ist im Produkt bereits die Erfolgsmeldung.
 *
 * `variant="destructive"` KOMMT HIER NICHT VOR (Kollisionsregel im Docstring von `ui/button.tsx`):
 * gefülltes `--danger` mit dunkler Tinte bei Radius 6px ist formgleich mit dem Kennzeichen
 * „Aussortiert", und diese Kachel zeigt Bewertungs-Kennzeichen je Teilnehmer. Bedienelement und
 * Kennzeichen wären sonst verwechselbar.
 *
 * SICHERHEIT (S10): `username` und Dateiname sind fremdbestimmter Text und erscheinen
 * ausschließlich als reguläre React-Textknoten - nie über `dangerouslySetInnerHTML`, nie in
 * `href`, `src`, `style` oder einer URL. Das Session-Token liegt in `localStorage`, und
 * eingeschleuster Inhalt liefe im Browser BEIDER Nutzer.
 */
export function SelectionPhotoTile({
  photo,
  participants,
  decidingIncluded,
  onDecide,
}: SelectionPhotoTileProps) {
  // Die drei Anzeigezustände liegen ausschließlich in den Serverfeldern. Die Oberfläche leitet die
  // Zugehörigkeit nie selbst her - `utils/albumDraft.ts::isInAlbum` gilt nur innerhalb der
  // Antwortmenge des Entwurfszweigs und wird hier ausdrücklich nicht benutzt.
  const takenOut = photo.final_selection_decision === false
  const decidedIn = photo.final_selection_decision === true

  function decisionButton(included: boolean, label: string) {
    return (
      <Button
        type="button"
        variant={included ? 'default' : 'secondary'}
        size="sm"
        className="flex-1"
        busy={decidingIncluded === included}
        // Der zugängliche Name trägt den Dateinamen - sonst hießen auf einer Seite mit vielen
        // Kacheln alle Schaltflächen gleich.
        aria-label={`${label}: ${photo.relative_path}`}
        onClick={() => onDecide(included)}
      >
        {label}
      </Button>
    )
  }

  return (
    <PhotoCard
      relativePath={photo.relative_path}
      image={
        <PhotoImage
          photoId={photo.id}
          variant="thumbnail"
          alt={photo.relative_path}
          className="size-full object-cover"
        />
      }
      /* Der ausdrücklich HERAUSGENOMMENE Zustand - dasselbe Muster wie ein gestrichenes Foto im
         Entwurf (ADR 0071 Entscheidung 3): gedämpfte Bildfläche, durchgestrichener Dateiname,
         Kennzeichen und Bedienelement voll deckend.

         `setAside` und NICHT `status='rejected'`: Die Karte trägt hier gar keinen
         Bewertungszustand. Ein unbenanntes „Verworfen" am Kartenkörper wäre neben den benannten
         Haltungszeilen als Haltung einer Person lesbar — und „verworfen" ist das Wort der
         Bewertung eines Nutzers, nicht der Herausnahme durch das Projekt. */
      setAside={takenOut}
      footer={
        <div className="flex flex-col gap-2">
          {/* Je Teilnehmer EINE Zeile, in der Reihenfolge von `participants`. Der Dateiname im
              zugänglichen Namen der Liste macht sie je Kachel eindeutig. Senkrecht gestapelt,
              damit die Kachel bei 360px vollständig bedienbar bleibt. */}
          <ul
            aria-label={`Haltung zu ${photo.relative_path}`}
            className="flex flex-col gap-1 text-xs text-text"
          >
            {participants.map((participant) => (
              <li key={participant.user_id} className="flex flex-wrap items-center gap-1">
                <span className="min-w-0 truncate">{participant.username}:</span>
                <StanceBadge stance={participantStance(photo, participant)} />
              </li>
            ))}
          </ul>

          {decidedIn && (
            <div>
              <Badge tone="neutral">{SELECTION_DECIDED_BADGE_TEXT}</Badge>
            </div>
          )}

          {/* Ein Druck schreibt die Entscheidung SOFORT - kein Dialog, kein Bestätigungsschritt,
              keine Abstimmung. Die Aufspannung auf 44px bringt `Button` über `tap-target` selbst
              mit; eine eigene Höhenklasse baute sie daneben noch einmal nach. */}
          <div className="flex gap-3">
            {photo.contested ? (
              <>
                {decisionButton(true, 'Aufnehmen')}
                {decisionButton(false, 'Nicht aufnehmen')}
              </>
            ) : (
              decisionButton(
                !photo.in_final_selection,
                photo.in_final_selection ? 'Herausnehmen' : 'Aufnehmen',
              )
            )}
          </div>
        </div>
      }
    />
  )
}
