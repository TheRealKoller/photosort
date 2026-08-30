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
         * (js/css/html/ico/png/svg). Ohne diesen Eintrag laegen Caprasimo und Figtree zwar im
         * Bundle, wuerden offline aber nicht ausgeliefert - die App fiele auf die System-Schrift
         * zurueck. Genau das war der Grund, die Schriften ueberhaupt self-zu-hosten statt sie von
         * der Google-Fonts-CDN zu laden (specs/features/0285-organic-design-import.md).
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
        // Markenfarben aus dem Organic-Design-System (specs/features/0285-organic-design-import.md)
        // - muessen dem tatsaechlichen Akzent/Grund entsprechen, sonst blitzt beim Start der PWA
        // die alte Palette auf.
        theme_color: '#c67139',
        background_color: '#f5ead8',
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
