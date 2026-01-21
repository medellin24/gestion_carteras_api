import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      devOptions: { enabled: true },
      includeAssets: ['favicon.svg', 'icons/home.png', 'icons/home_512.png'],
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
          {
            src: '/icons/home.png',
            sizes: '194x194',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/home.png',
            sizes: '194x194',
            type: 'image/png',
            purpose: 'maskable'
          },
          {
            src: '/icons/home_512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any'
          },
          {
            src: '/icons/home_512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable'
          }
        ],
        screenshots: [
          {
            src: '/screenshots/screenshot_1.png',
            sizes: '1206x2483',
            type: 'image/png',
            form_factor: 'narrow',
            label: 'Vista Principal'
          },
          {
            src: '/screenshots/screenshot_2.png',
            sizes: '1204x2459',
            type: 'image/png',
            form_factor: 'narrow',
            label: 'Gestión de Tarjetas'
          },
          {
            src: '/screenshots/screenshot_3.png',
            sizes: '1205x2443',
            type: 'image/png',
            form_factor: 'narrow',
            label: 'Detalle de Cobro'
          },
          {
            src: '/screenshots/screenshot_4.png',
            sizes: '1206x2490',
            type: 'image/png',
            form_factor: 'narrow',
            label: 'Liquidación Diaria'
          },
          {
            src: '/screenshots/screenshot_5.png',
            sizes: '1206x2498',
            type: 'image/png',
            form_factor: 'narrow',
            label: 'Estadísticas'
          },
          {
            src: '/screenshots/screenshot_6.png',
            sizes: '1206x2498',
            type: 'image/png',
            form_factor: 'narrow',
            label: 'Configuración'
          }
        ],
        shortcuts: [
          {
            name: 'Descargar',
            short_name: 'Descargar',
            description: 'Descargar tarjetas para trabajar offline',
            url: '/descargar',
            icons: [{ src: '/icons/home.png', sizes: '194x194', type: 'image/png' }]
          },
          {
            name: 'Ver tarjetas',
            short_name: 'Tarjetas',
            description: 'Ir a listado de tarjetas',
            url: '/tarjetas',
            icons: [{ src: '/icons/home.png', sizes: '194x194', type: 'image/png' }]
          },
          {
            name: 'Subir cambios',
            short_name: 'Subir',
            description: 'Sincronizar cambios pendientes',
            url: '/subir',
            icons: [{ src: '/icons/home.png', sizes: '194x194', type: 'image/png' }]
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


