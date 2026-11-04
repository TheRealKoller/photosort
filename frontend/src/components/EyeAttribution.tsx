/**
 * Die Namensnennung des Eye-Modells (Spec 0609, S12) - an der VERWENDUNGSSTELLE, nicht in einer
 * Fußzeile: unter der Eye-Zeile der Laufwahl, unter der Grundlagenzeile bei `source === 'eye'`
 * und unter dem Eye-Band der Fotoansicht.
 *
 * Form der GeoNames-Nennung (`ProjectListPage`): `text-xs text-text-muted`, fremder Link mit
 * fester `https`-Adresse, `rel="noopener noreferrer"` und `target="_blank"`. Nicht aufklappbar,
 * nicht ausblendbar, kein `localStorage`-Flag - die Lizenz des Modells verlangt die sichtbare
 * Nennung, und ein "schon gesehen"-Speicher wäre genau ihr Abschalten.
 */
export function EyeAttribution() {
  return (
    <p className="text-xs text-text-muted" data-testid="eye-attribution">
      Powered by{' '}
      <a
        href="https://desertant.com"
        className="underline"
        rel="noopener noreferrer"
        target="_blank"
      >
        Desert Ant Labs
      </a>
    </p>
  )
}
