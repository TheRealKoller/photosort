import type { AlbumSuitabilityOut, EyeResultOut, FineLabelOut } from '../api/types'

/**
 * Eyes Albumstufe und Feinlabels in der Form, die `PhotoVerdict` liest (Spec 0609).
 *
 * Eye liefert keine Begründung, also `reason: null` - das Urteil zeigt dann keine
 * Begründungszeile. Die Feinlabels sind rohe Eye-Tags ohne kanonischen Eintrag: Anzeige- und
 * Rohtext sind derselbe Tag, die Quelle ist `eye`. Der Listenschlüssel kommt aus der Position,
 * nie aus dem Text (S3 von `FineLabelList`).
 */
export function eyeVerdict(eyeResult: EyeResultOut): {
  albumSuitability: AlbumSuitabilityOut
  fineLabels: FineLabelOut[]
} {
  return {
    albumSuitability: { level: eyeResult.album_level, reason: null },
    fineLabels: eyeResult.fine_labels.map((label, index) => ({
      canonical_key: `eye-${index}`,
      display_name: label,
      raw_label: label,
      provider: 'eye',
    })),
  }
}
