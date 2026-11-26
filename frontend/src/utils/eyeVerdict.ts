import type { EyeResultOut, FineLabelOut } from '../api/types'

/**
 * Eyes Feinlabels in der Form, die PhotoVerdict liest.
 *
 * Die Albumstufe steht in `PhotoOut.album_suitability` und reist dort mit ihrer Herkunft
 * (`source`). Eye liefert hier nur die Feinlabels: rohe Eye-Tags ohne kanonischen Eintrag,
 * Anzeige- und Rohtext sind derselbe Tag, die Quelle ist `eye`. Der Listenschlüssel kommt aus der
 * Position, nie aus dem Text.
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
