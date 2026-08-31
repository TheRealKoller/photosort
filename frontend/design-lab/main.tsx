/*
 * TEMPORAER (specs/features/0287-design-richtungen-vergleich.md): Einstiegspunkt des
 * Design-Labors. Bewusst OHNE QueryClientProvider/BrowserRouter/StrictMode-Router-Kombination der
 * echten App - das Labor hat kein Backend, keine Routen und keinen Zustand ausser den drei
 * Umschaltern der Huelle.
 *
 * Importreihenfolge ist bedeutungstragend: base.css (richtungsinvariante Struktur, ungescopte
 * .dl-*-Selektoren) MUSS vor den Richtungsdateien stehen, die ueber ./directions geladen werden.
 * Die [data-direction]-Selektoren der Richtungen haben ohnehin die hoehere Spezifitaet, die
 * Reihenfolge macht das Zusammenspiel aber unabhaengig von Spezifitaetsgleichstaenden eindeutig.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './base.css'
import './shell.css'
import { App } from './App'

const container = document.getElementById('lab-root')
if (container === null) {
  throw new Error('Design-Labor: #lab-root fehlt in design-lab/index.html')
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>
)
