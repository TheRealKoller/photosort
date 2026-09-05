/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
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
