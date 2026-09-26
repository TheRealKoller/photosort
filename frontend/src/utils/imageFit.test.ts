import { describe, expect, it } from 'vitest'

import { fittedImageBoxStyle } from './imageFit'

/*
 * specs/features/0531-kuratierung-grossansicht.md, Auflage S4: `aspect_ratio` kommt aus der API
 * und geht nur als gepruefte endliche Zahl in eine zusammengesetzte Stilangabe.
 */
describe('fittedImageBoxStyle', () => {
  it('fits the box from a finite positive number', () => {
    expect(fittedImageBoxStyle(1.5)).toEqual({
      aspectRatio: 1.5,
      width: 'min(100cqw, 1.5 * 100cqh)',
    })
  })

  it.each([
    ['eine feindliche Zeichenkette', 'url(https://x.example/a);color:red'],
    ['eine Zahl als Zeichenkette', '1.5'],
    ['null', null],
    ['undefined', undefined],
    ['NaN', Number.NaN],
    ['Infinity', Number.POSITIVE_INFINITY],
    ['0', 0],
    ['eine negative Zahl', -1.5],
  ])('falls back without a style for %s', (_, value) => {
    expect(fittedImageBoxStyle(value)).toBeUndefined()
  })
})
