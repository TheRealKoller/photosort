import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { QualityMeter } from './QualityMeter'

describe('QualityMeter', () => {
  it('shows the written-out level name as the actual screenreader-visible text', () => {
    render(<QualityMeter level="high" />)

    expect(screen.getByText('Hohe Bildqualität')).toBeInTheDocument()
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
