import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ALBUM_SUITABILITY_NOT_RATED_TEXT } from '../utils/albumSuitability'
import { QualityMeter } from './QualityMeter'

describe('QualityMeter', () => {
  it('shows the written-out level name as the actual screenreader-visible text', () => {
    render(<QualityMeter level="high" />)

    expect(screen.getByText('Gut albumtauglich')).toBeInTheDocument()
  })

  it('renders three filled dots for the high level', () => {
    render(<QualityMeter level="high" />)

    expect(screen.getByText('●●●')).toBeInTheDocument()
  })

  it('renders two filled dots for the medium level', () => {
    render(<QualityMeter level="medium" />)

    expect(screen.getByText('●●○')).toBeInTheDocument()
  })

  it('renders one filled dot for the low level', () => {
    render(<QualityMeter level="low" />)

    expect(screen.getByText('●○○')).toBeInTheDocument()
  })

  it('marks the dot meter as decorative (aria-hidden), not the sole source of information', () => {
    render(<QualityMeter level="low" />)

    expect(screen.getByText('●○○')).toHaveAttribute('aria-hidden', 'true')
  })
})

describe('QualityMeter without a model verdict', () => {
  it('says "Noch nicht bewertet" instead of a level', () => {
    render(<QualityMeter level={null} />)

    expect(screen.getByText(ALBUM_SUITABILITY_NOT_RATED_TEXT)).toBeInTheDocument()
  })

  it('renders no meter glyph at all', () => {
    // Kardinalität Null über das Datenattribut, nicht über eine Textsuche: `●○○` oder `○○○`
    // hieße „schlechteste Stufe" statt „nicht beurteilt", und genau das ist hier die Zusage.
    const { container } = render(<QualityMeter level={null} />)

    expect(container.querySelectorAll('[data-quality-meter-dots]')).toHaveLength(0)
  })

  it('renders the meter glyph when there is a level', () => {
    // Gegenprobe - sonst bestünde der Fall darüber auch mit einem nie gerenderten Attribut.
    const { container } = render(<QualityMeter level="low" />)

    expect(container.querySelectorAll('[data-quality-meter-dots]')).toHaveLength(1)
  })
})
