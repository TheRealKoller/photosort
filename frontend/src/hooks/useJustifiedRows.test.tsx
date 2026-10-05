import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { installResizeObserver } from '../test/observers'
import { CURATION_TARGET_ROW_HEIGHT_PX } from '../utils/curationLayout'
import { useJustifiedRows } from './useJustifiedRows'

function Probe({ ratios }: { ratios: (number | null)[] }) {
  const { ref, rows } = useJustifiedRows<HTMLUListElement>(ratios)
  return (
    <ul ref={ref}>
      {rows.map((row, rowIndex) => (
        <li key={rowIndex} data-testid="row" data-height={row.height}>
          {row.tiles.map((tile) => `${tile.index}:${tile.width}`).join(' ')}
        </li>
      ))}
    </ul>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useJustifiedRows', () => {
  it('lays all tiles out in natural width before the first measurement', () => {
    installResizeObserver()
    render(<Probe ratios={[1.5, 2 / 3]} />)

    const rows = screen.getAllByTestId('row')
    expect(rows).toHaveLength(1)
    expect(rows[0]).toHaveAttribute('data-height', String(CURATION_TARGET_ROW_HEIGHT_PX))
    expect(rows[0]).toHaveTextContent('0:420 1:187')
  })

  it('justifies the rows once the container width is known', () => {
    const observer = installResizeObserver()
    render(<Probe ratios={[2 / 3, 2 / 3, 3 / 2]} />)

    observer.resizeTo(328)

    const rows = screen.getAllByTestId('row')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('0:158 1:158')
    expect(rows[1]).toHaveTextContent('2:328')
  })
})
