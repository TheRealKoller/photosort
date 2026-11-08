import type { EyeResultOut, FineLabelOut } from '../api/types'

/**
 * Eyes Feinlabels in der Form, die `PhotoVerdict` liest (Spec 0609, Spec 0621 Punkt 7).
 *
 * Die Albumstufe kommt seit 0621 aus `PhotoOut.album_suitability` - sie reist dort mit ihrer
 * Herkunft (`source`). Eye liefert hier nur noch die Feinlabels: rohe Eye-Tags ohne kanonischen
 * Eintrag, Anzeige- und Rohtext sind derselbe Tag, die Quelle ist `eye`. Der Listenschlüssel
 * kommt aus der Position, nie aus dem Text (S3 von `FineLabelList`).
 */
export function eyeVerdict(eyeResult: EyeResultOut): {
  fineLabels: FineLabelOut[]
} {
  return {
    fineLabels: eyeResult.fine_labels.map((label, index) => ({
      canonical_key: `eye-${index}`,
      display_name: label,
      raw_label: label,
      provider: 'eye',
    })),
  }
}
