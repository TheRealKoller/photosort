/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

/*
 * Build-Marker fuer e2e/tests/release-wechsel.spec.ts: eine Zuweisung an eine globale Eigenschaft
 * nur im Einstiegs-Chunk, damit ein zweiter Build einen anderen Einstiegs-Hash bekommt. Ohne
 * Marker (Normalfall) bleibt der Chunk unveraendert. Nur Kleinbuchstaben, Ziffern und Bindestrich -
 * sonst koennte der Wert das String-Literal schliessen und Code ins Bundle schreiben.
 */
const buildMarker = process.env.PHOTOSORT_BUILD_MARKER ?? ''
if (!/^[a-z0-9-]*$/.test(buildMarker)) {
  throw new Error('PHOTOSORT_BUILD_MARKER: nur a-z, 0-9 und "-" erlaubt')
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    {
      name: 'photosort-build-marker',
      renderChunk: (code, chunk) =>
        buildMarker && chunk.isEntry
          ? `globalThis.photosortBuildMarker = '${buildMarker}';\n${code}`
          : null,
    },
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      workbox: {
        /*
         * Die Standard-globPatterns von vite-plugin-pwa decken Schriftdateien NICHT ab
         * (js/css/html/ico/png/svg). Ohne diesen Eintrag laegen Inter und JetBrains Mono zwar im
         * Bundle, wuerden offline aber nicht ausgeliefert - die App fiele auf die System-Schrift
         * zurueck. Genau das war der Grund, die Schriften ueberhaupt self-zu-hosten statt sie von
         * der Google-Fonts-CDN zu laden (specs/features/0320-dark-utility-register.md, Security-
         * Abschnitt "Bedrohung 3").
         *
         * Bewusst nur woff2, nicht auch woff: @fontsource liefert beide Formate, die generierte
         * CSS nennt woff2 zuerst: jeder Browser, der diese PWA installieren kann, unterstuetzt es.
         * Beide Formate zu precachen wuerde den Offline-Cache ohne Gegenwert etwa verdoppeln.
         */
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        /*
         * Navigationen kommen online immer aus dem Netz, damit F5 bzw. ein Neustart nach einem
         * Release sofort die aktuelle index.html (und damit die neuen Asset-Hashes) laedt. Nur
         * offline oder nach 3 s ohne Antwort liefert der Precache index.html - HTML und Assets dann
         * aus demselben Stand. Diese Route trifft ausschliesslich Navigationen und schreibt in
         * keinen Runtime-Cache: sonst laegen nutzerbezogene API-Antworten im profilweiten
         * SW-Cache. Erzwungen von src/serviceWorker.build.test.ts.
         *
         * Das Zeitgrenzen-Plugin wird als Quelltext ins sw.js serialisiert: keine Closure, kein
         * Import, keine aeussere Konstante. Der Timer wird bei Erfolg wie Fehlschlag geloescht,
         * sonst bricht der Body einer langsamen, aber erfolgreichen Antwort nach 3 s ab.
         */
        // Leer statt "index.html": sonst beantwortet die Precache-Route eine Navigation auf "/"
        // vor der Navigationsroute unten aus dem Precache.
        directoryIndex: '',
        navigateFallback: null,
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.mode === 'navigate',
            handler: 'NetworkOnly',
            options: {
              precacheFallback: { fallbackURL: 'index.html' },
              plugins: [
                {
                  requestWillFetch: async ({ request, state }) => {
                    const controller = new AbortController()
                    state!.timer = setTimeout(() => controller.abort(), 3000)
                    return new Request(request, { signal: controller.signal })
                  },
                  fetchDidSucceed: async ({ response, state }) => {
                    clearTimeout(state!.timer as number)
                    return response
                  },
                  fetchDidFail: async ({ state }) => {
                    clearTimeout(state!.timer as number)
                  },
                },
              ],
            },
          },
        ],
      },
      manifest: {
        name: 'PhotoSort',
        short_name: 'PhotoSort',
        description: 'Urlaubsfotos sortieren, kategorisieren und die besten auswählen.',
        // Markenfarben des Design-Systems "Dark Utility Register" (specs/features/0320-dark-
        // utility-register.md) - muessen dem tatsaechlichen Akzent/Grund entsprechen, sonst blitzt
        // beim Start der PWA die alte Palette auf.
        theme_color: '#FFB000',
        background_color: '#0B0C10',
        display: 'standalone',
        start_url: '/',
        icons: [
          {
            src: 'favicon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
          },
        ],
      },
    }),
  ],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
  },
})
