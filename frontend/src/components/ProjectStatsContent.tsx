import type { ProjectStatsOut } from '../api/types'
import { FeedbackDiagnosisSection } from './FeedbackDiagnosisSection'
import { StatsCostSection } from './StatsCostSection'
import { StatsDiagnosticsSection } from './StatsDiagnosticsSection'
import { StatsMotifsSection } from './StatsMotifsSection'
import { StatsProgressSection } from './StatsProgressSection'
import { StatsScopeSection } from './StatsScopeSection'

export function ProjectStatsContent({ stats }: { stats: ProjectStatsOut }) {
  return (
    <div className="flex flex-col gap-8">
      <StatsScopeSection stats={stats} />
      <StatsCostSection cost={stats.cost} />
      <StatsProgressSection
        progress={stats.progress}
        ratings={stats.ratings}
        total={stats.photo_count}
      />
      {/* EIN Abschnitt statt der beiden Kategorie-Bloecke. */}
      <StatsMotifsSection stats={stats} />
      <StatsDiagnosticsSection stats={stats} />

      {/* Der Abschnitt laedt seine Zahlen SELBST und projektuebergreifend - er steht deshalb
          ausserhalb von `stats` und nimmt keine Projekt-Id entgegen. */}
      <FeedbackDiagnosisSection />
    </div>
  )
}
