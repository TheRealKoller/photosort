import type { CSSProperties } from 'react'

/**
 * Der Stil eines Bildkastens, der genau die in einen Container mit `container-type: size`
 * eingepasste Bildgroesse hat: so breit wie moeglich, ohne hoeher als der Container zu werden.
 *
 * SICHERHEIT: `aspectRatio` stammt aus der API. Die Breite ist zwangslaeufig eine zusammengesetzte
 * Zeichenkette; sie entsteht nur aus einer endlichen positiven ZAHL und festen Literalen. Jeder
 * andere Wert - auch eine Zahl als Zeichenkette - ergibt `undefined`, also keinen Stil: Eine
 * ungepruefte Zeichenkette truege beliebige CSS-Token (bis hin zu `url()`) in den Stil.
 */
export function fittedImageBoxStyle(aspectRatio: unknown): CSSProperties | undefined {
  if (typeof aspectRatio !== 'number' || !Number.isFinite(aspectRatio) || aspectRatio <= 0) {
    return undefined
  }
  return { aspectRatio, width: `min(100cqw, ${aspectRatio} * 100cqh)` }
}
