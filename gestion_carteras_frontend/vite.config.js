import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      devOptions: { enabled: true },
      includeAssets: ['favicon.svg', 'icons/app-icon.svg', 'icons/maskable-icon.svg'],
      manifest: {
        id: '/',
        name: 'NeonBlue',
        short_name: 'NeonBlue',
        description: 'PWA para gestión de carteras',
        lang: 'es',
        dir: 'ltr',
        theme_color: '#0ea5e9',
        background_color: '#ffffff',
        display: 'standalone',
        display_override: ['window-controls-overlay', 'standalone', 'fullscreen', 'minimal-ui'],
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        categories: ['finance', 'business', 'productivity'],
        icons: [
          { src: '/icons/home.png', sizes: '192x192', type: 'image/png', purpose: 'any maskable' },
          { src: '/icons/home.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
          { src: '/icons/manifest-icon-192.maskable.png', sizes: '192x192', type: 'image/png', purpose: 'any maskable' },
          { src: '/icons/manifest-icon-512.maskable.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
        ],
        shortcuts: [
          {
            name: 'Descargar',
            short_name: 'Descargar',
            description: 'Descargar tarjetas para trabajar offline',
            url: '/descargar',
            icons: [{ src: '/icons/manifest-icon-192.maskable.png', sizes: '192x192', type: 'image/png' }]
          },
          {
            name: 'Ver tarjetas',
            short_name: 'Tarjetas',
            description: 'Ir a listado de tarjetas',
            url: '/tarjetas',
            icons: [{ src: '/icons/manifest-icon-192.maskable.png', sizes: '192x192', type: 'image/png' }]
          },
          {
            name: 'Subir cambios',
            short_name: 'Subir',
            description: 'Sincronizar cambios pendientes',
            url: '/subir',
            icons: [{ src: '/icons/manifest-icon-192.maskable.png', sizes: '192x192', type: 'image/png' }]
          }
        ]
      },
      workbox: {
        navigateFallback: '/index.html',
        globPatterns: ['**/*.{js,css,html,ico,svg,png,jpg,jpeg,webp,webmanifest}'],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.origin === self.location.origin,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'static-resources' }
          }
        ]
      }
    })
  ],
  server: { port: 5173 }
})


