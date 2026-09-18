import type { FineLabelOut } from '../api/types'
import { Badge } from './ui/badge'

interface FineLabelListProps {
  /** Bis zu zwei frei formulierte Feinlabels - reine Zusatzinformation am Foto, kein Motiv.
   *
   * SICHERHEIT (S1/S5): `display_name` und `raw_label` sind freier, extern erzeugter LLM-Text.
   * Ausschließlich als regulärer React-Textknoten rendern - nie `dangerouslySetInnerHTML`, nie als
   * HTML-String-Prop, nie in `href`/`src`/`style`, nie in einem `url()`-Kontext, nie als
   * React-`key`. Das Session-Token liegt in `localStorage`; ein eingeschleustes Skript liest es
   * unmittelbar aus und hat damit bis zu 30 Tage Sitzungsübernahme ohne Widerrufsweg. Bricht in
   * `FineLabelList.test.tsx > rendert einen feindlich belegten Anzeigenamen als reinen
   * Textknoten`. */
  fineLabels: FineLabelOut[]
}

/**
 * Die Feinlabel-Chips - geteilt zwischen dem kompakten Kachel-Popover
 * (`CriterionDetailsList`) und dem Seitenurteil (`PhotoVerdict`).
 *
 * OHNE FEINLABELS ENTFÄLLT DER BEREICH ERSATZLOS: kein Platzhalter, keine leere Liste, keine
 * Überschrift. Die Überschrift trägt die jeweilige Aufrufstelle, nicht dieser Baustein - im
 * Popover steht sie als `h4` in der Bildinhalt-Gruppe, im Urteil auf einer anderen Stufe.
 *
 * S3 — DER SCHLÜSSEL KOMMT AUS `canonical_key`, nie aus dem Anzeigenamen. Gleichnamigkeit ist der
 * Normalfall; ein aus dem Text gebildeter Schlüssel brächte die Listenabgleichung von React
 * durcheinander.
 */
export function FineLabelList({ fineLabels }: FineLabelListProps) {
  if (fineLabels.length === 0) {
    return null
  }

  return (
    <ul aria-label="Feinlabels" className="flex flex-wrap gap-2">
      {fineLabels.map((label) => (
        <li key={label.canonical_key}>
          {/* Reiner React-Textknoten - freier LLM-Text, nie als HTML. Bewusst OHNE Icon/Symbol,
              damit die Chips nicht mit den Bewertungs-Chips verwechselt werden. */}
          <Badge tone="accent" suggested className="max-w-full truncate">
            {label.display_name}
          </Badge>
        </li>
      ))}
    </ul>
  )
}
