import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as photosApi from '../api/photos'
import type { PhotoOut, RankingOut } from '../api/types'
import { CATEGORY_SET } from '../test/categorySetFixture'
import { CurationPhotoTile } from './CurationPhotoTile'
import type { CategoryOverrideControls } from './CurationPhotoTile'

vi.mock('../api/photos')

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    cluster_key: 'cluster-0',
    category_key: 'landschaft',
    rank_score: 0.8,
    rank_position: 1,
    partition_size: 1,
    is_primary: true,
    curation_position: 1,
    ...overrides,
  }
}

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: 'urlaub/a.jpg',
    taken_at: '2026-07-20T10:00:00',
    ratings: [],
    suggestion: null,
    rankings: [ranking()],
    criterion_scores: [],
    fine_labels: [],
    remote_category: null,
    category_confidence: null,
    category_override: null,
    category_candidates: [],
    cloud_vision_status: [],
    ...overrides,
  }
}

const CONTROLS: CategoryOverrideControls = {
  overrideCategory: vi.fn(),
  resetOverride: vi.fn(),
  pendingOverrideKeyFor: () => null,
  isResetPendingFor: () => false,
}

function renderTile(props: Partial<React.ComponentProps<typeof CurationPhotoTile>> = {}): {
  onReject: ReturnType<typeof vi.fn>
} {
  const onReject = vi.fn()
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  render(
    <ul>
      <CurationPhotoTile
        photo={photo()}
        ranking={ranking()}
        categories={CATEGORY_SET}
        categoriesLoading={false}
        categoriesError={false}
        onRetryCategories={vi.fn()}
        categoryOverrideControls={CONTROLS}
        ownStatus={null}
        rejecting={false}
        onReject={onReject}
        {...props}
      />
    </ul>,
    { wrapper },
  )
  return { onReject }
}

describe('CurationPhotoTile', () => {
  beforeEach(() => {
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockReset()
    vi.mocked(photosApi.fetchPhotoImageBlobUrl).mockResolvedValue('blob:fake-url')
  })

  it('shows the file name and a reject action named after the photo', () => {
    renderTile()

    expect(screen.getByText('a.jpg')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Verwerfen: urlaub/a.jpg' })).toBeInTheDocument()
  })

  it('calls onReject when the action is pressed', async () => {
    const user = userEvent.setup()
    const { onReject } = renderTile()

    await user.click(screen.getByRole('button', { name: 'Verwerfen: urlaub/a.jpg' }))

    expect(onReject).toHaveBeenCalledTimes(1)
  })

  it('disables the action while its own rejection is running', () => {
    renderTile({ rejecting: true })

    expect(screen.getByRole('button', { name: 'Verwerfen: urlaub/a.jpg' })).toBeDisabled()
  })

  it('marks a secondary membership, and only that one', () => {
    // Die Kachel ist seit specs/features/0300-nebenkategorien.md nicht durch das Foto allein
    // bestimmt: DASSELBE Foto traegt den Nebenkategorie-Marker nur unter der Zugehoerigkeit, in
    // der es Nebenkategorie ist.
    const secondary = ranking({ category_key: 'tier', is_primary: false })
    renderTile({ ranking: secondary })

    expect(screen.getByLabelText('Nebenkategorie')).toBeInTheDocument()
  })

  it('does not mark a primary membership as a secondary one', () => {
    renderTile()

    expect(screen.queryByLabelText('Nebenkategorie')).not.toBeInTheDocument()
  })
})
