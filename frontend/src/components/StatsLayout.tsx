import type { HTMLAttributes, ReactNode } from 'react'

/**
 * Die Bausteine der Statistikseite: Abschnitt, Kennzahl, Kennzahlenreihe, Detailzeile.
 *
 * Sie stehen hier und nicht mehr in `ProjectStatsPage.tsx`, weil die Seite seit der Rückmeldung
 * aus der Nacharbeit nicht mehr ihr einziger Nutzer ist. Eine zweite, danebenstehende Kopie liefe
 * beim ersten Feinschliff auseinander, und die Seite trüge dann zwei Abschnittsformen.
 *
 * Rein darstellend: kein Zustand, keine Abfrage, kein Zugriff auf die Antwortformen.
 */

/**
 * Wiederkehrendes Muster "Grosszahl + Label" (Design-System): der Wert in `text-xl`, darunter das
 * Label klein. Rein typografisch, kein eigener Hintergrund, kein Rahmen.
 */
export function Metric({
  value,
  label,
  info,
  children,
  ...rest
}: {
  value: string
  label: string
  info?: ReactNode
  children?: ReactNode
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className="col-span-12 flex min-w-0 flex-col gap-1 sm:col-span-6 lg:col-span-3" {...rest}>
      {/* Kennzahlen in Festbreitenschrift (Board): eine Zahl ist eine Datenausgabe, kein
          Fliesstext - und untereinander stehende Kennzahlen fluchten dadurch. */}
      <span className="font-mono text-xl font-semibold text-text-h">{value}</span>
      <span className="flex items-center gap-1 text-sm text-text">
        {label}
        {info}
      </span>
      {children}
    </div>
  )
}

/**
 * Kennzahlen stehen auf breiten Schirmen nebeneinander und auf dem Smartphone gestapelt.
 *
 * Das 12-Spalten-Raster des Boards (Spaltenbreite fluessig, Zwischenraum 12px = `gap-x-3`).
 * Bewusst hier und nicht als Seitengeruest: eine Kennzahlenreihe ist genau der Fall, fuer den ein
 * festes Spaltenraster gegenueber `flex-wrap` etwas bringt - die Werte stehen untereinander auf
 * einer Achse statt inhaltsabhaengig zu springen.
 */
export function MetricRow({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-12 gap-x-3 gap-y-6">{children}</div>
}

export function Section({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: ReactNode
}) {
  return (
    // Abschnittstrenner auf --separator: als freistehende Linie auf dem Grund erreichte --border
    // 1.45:1 und war praktisch keine Linie.
    <section aria-labelledby={id} className="flex flex-col gap-4 border-t border-separator pt-6">
      <h2 id={id} className="text-lg text-text-h">
        {title}
      </h2>
      {children}
    </section>
  )
}

/** Eine Zeile "Bezeichnung … x von y Fotos" bzw. "Bezeichnung … Wert". */
export function DetailRow({
  term,
  children,
  ...rest
}: { term: ReactNode; children: ReactNode } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-2 border-b border-separator py-2 last:border-b-0"
      {...rest}
    >
      <dt className="flex items-center gap-1 text-sm text-text">{term}</dt>
      <dd className="text-sm font-medium text-text-h">{children}</dd>
    </div>
  )
}
