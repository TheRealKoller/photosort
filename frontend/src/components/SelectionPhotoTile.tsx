import type { Ref } from 'react'

import type { AlbumParticipantOut, PhotoOut } from '../api/types'
import type { ParticipantStance } from '../utils/albumSelection'
import { participantStance } from '../utils/albumSelection'
import { NOT_IN_DRAFT_LABEL } from '../utils/albumStateLabels'
import { iconOnly } from '../utils/curationLayout'
import { AlbumStateBadge } from './AlbumStateBadge'
import { CurationDetails } from './CurationDetails'
import { PhotoCard } from './PhotoCard'
import { PhotoImage } from './PhotoImage'
import { TileAction } from './TileAction'
import { Badge } from './ui/badge'

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
  /** Gerechnete Kachelbreite und Bildhoehe (`useJustifiedRows`). */
  width: number
  imageHeight: number
  /**
   * ALLE Teilnehmer, vom Server, nach `user_id` sortiert - sie und nicht `photo.ratings[]`
   * bestimmen die Zahl der Haltungszeilen. Aus `ratings[]` abgeleitet fehlte genau der Nutzer,
   * der noch nie etwas angefasst hat.
   */
  participants: AlbumParticipantOut[]
  /**
   * Welcher Wert wird gerade geschrieben? `null` = es läuft nichts.
   *
   * EIN Wert statt eines Wahrheitswerts, damit NUR die gedrückte Schaltfläche `busy` trägt.
   */
  decidingIncluded: boolean | null
  onDecide: (included: boolean) => void
  /** Oeffnet die Grossansicht dieses Fotos - Ausloeser ist die Bildflaeche. */
  onOpenLarge: (photoId: number) => void
  /** Erhaelt den Ausloeser der Grossansicht - Ziel der Fokus-Rueckgabe nach dem Schliessen. */
  largeTriggerRef: Ref<HTMLButtonElement>
}

/**
 * Das Kennzeichen einer Haltung: dasselbe Symbolzeichen wie im Album-Entwurf, das Wort ist sein
 * zugänglicher Name. „Vorschlag" liest allein das lauf-globale `ranking.proposed`; beide
 * Datenformen von „nicht vorgeschlagen" ergeben das neutrale „–" mit dem Namen „Nicht im Entwurf".
 */
function StanceBadge({ stance, proposed }: { stance: ParticipantStance; proposed: boolean }) {
  if (stance === 'taken') {
    return <AlbumStateBadge state="taken" />
  }
  if (stance === 'struck') {
    return <AlbumStateBadge state="struck" />
  }
  if (proposed) {
    return <AlbumStateBadge state="proposal" />
  }
  return <Badge aria-label={NOT_IN_DRAFT_LABEL}>–</Badge>
}

/**
 * EINE Kachel der gemeinsamen Endauswahl: die Kuratierungskachel mit der gemeinsamen Entscheidung
 * als Knopfzeile und darunter der Haltung JEDES Teilnehmers.
 *
 * ZWEI BENANNTE ZEILEN SIND DIE ZUSICHERUNG „die Haltung des einen wird nie als die des anderen
 * dargestellt": Die Zuordnung entsteht aus dem vorangestellten Namen und aus `user_id`, nie aus
 * Position, Reihenfolge oder Farbe allein. Das Symbol `check` ist ausgeschlossen, es ist im
 * Produkt bereits die Erfolgsmeldung.
 *
 * `variant="destructive"` KOMMT HIER NICHT VOR (Kollisionsregel im Docstring von `ui/button.tsx`):
 * Diese Kachel zeigt Bewertungs-Kennzeichen je Teilnehmer.
 *
 * SICHERHEIT (S10): `username` und Dateiname sind fremdbestimmter Text und erscheinen
 * ausschließlich als reguläre React-Textknoten - nie über `dangerouslySetInnerHTML`, nie in
 * `href`, `src`, `style` oder einer URL. Das Session-Token liegt in `localStorage`, und
 * eingeschleuster Inhalt liefe im Browser BEIDER Nutzer.
 */
export function SelectionPhotoTile({
  photo,
  width,
  imageHeight,
  participants,
  decidingIncluded,
  onDecide,
  onOpenLarge,
  largeTriggerRef,
}: SelectionPhotoTileProps) {
  // Die drei Anzeigezustände liegen ausschließlich in den Serverfeldern. Die Oberfläche leitet die
  // Zugehörigkeit nie selbst her - `utils/albumDraft.ts::draftMembership` gilt nur innerhalb der
  // Antwortmenge des Entwurfs-Lesepfads und wird hier ausdrücklich nicht benutzt.
  const takenOut = photo.final_selection_decision === false
  const decidedIn = photo.final_selection_decision === true
  const symbolsOnly = iconOnly(width, photo.contested ? 'selection-contested' : 'selection-single')

  function decisionButton(included: boolean, label: string, align: 'start' | 'end') {
    return (
      <TileAction
        icon={included ? 'book' : 'x-circle'}
        label={label}
        // Der zugängliche Name trägt den Dateinamen - sonst hießen auf einer Seite mit vielen
        // Kacheln alle Schaltflächen gleich.
        accessibleName={`${label}: ${photo.relative_path}`}
        iconOnly={symbolsOnly}
        tileWidth={width}
        align={align}
        busy={decidingIncluded === included}
        onClick={() => onDecide(included)}
      />
    )
  }

  return (
    <PhotoCard
      width={width}
      imageHeight={imageHeight}
      relativePath={photo.relative_path}
      onImageActivate={() => onOpenLarge(photo.id)}
      imageTriggerLabel={`Großansicht: ${photo.relative_path}`}
      imageTriggerRef={largeTriggerRef}
      image={
        <PhotoImage
          photoId={photo.id}
          variant="thumbnail"
          alt={photo.relative_path}
          className="size-full object-contain"
        />
      }
      // Der ausdrücklich HERAUSGENOMMENE Zustand: durchgestrichener Dateiname, Bildfläche in voller
      // Helligkeit, kein Bewertungs-Kennzeichen - „Gestrichen" ist das Wort der Bewertung eines
      // Nutzers, nicht der Herausnahme durch das Projekt.
      setAside={takenOut}
      details={<CurationDetails photo={photo} />}
      // Ein Druck schreibt die Entscheidung SOFORT - kein Dialog, kein Bestätigungsschritt.
      actions={
        photo.contested ? (
          <>
            {decisionButton(true, 'Aufnehmen', 'start')}
            {decisionButton(false, 'Nicht aufnehmen', 'end')}
          </>
        ) : (
          decisionButton(
            !photo.in_final_selection,
            photo.in_final_selection ? 'Herausnehmen' : 'Aufnehmen',
            'start',
          )
        )
      }
      footer={
        <div className="mt-2 flex flex-col gap-1">
          {/* Je Teilnehmer EINE Zeile, in der Reihenfolge von `participants`. Der Dateiname im
              zugänglichen Namen der Liste macht sie je Kachel eindeutig. */}
          <ul
            aria-label={`Haltung zu ${photo.relative_path}`}
            className="flex flex-col gap-1 text-xs text-text"
          >
            {participants.map((participant) => (
              <li key={participant.user_id} className="flex items-center gap-1">
                <span className="min-w-0 truncate">{participant.username}:</span>
                <StanceBadge
                  stance={participantStance(photo, participant)}
                  proposed={photo.ranking?.proposed === true}
                />
              </li>
            ))}
          </ul>

          {decidedIn && (
            <div>
              <Badge tone="neutral">{SELECTION_DECIDED_BADGE_TEXT}</Badge>
            </div>
          )}
        </div>
      }
    />
  )
}
