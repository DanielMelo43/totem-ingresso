import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const productionHeaders = {
  'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self' http://localhost:8000 ws://localhost:*; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'no-referrer',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Cache-Control': 'no-store, no-cache, must-revalidate',
}

const developmentHeaders = {
  ...productionHeaders,
  // O React Fast Refresh do Vite injeta um preâmbulo inline somente em desenvolvimento.
  'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' http://localhost:8000 ws://localhost:*; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
}

export default defineConfig({ plugins: [react()], server: { headers: developmentHeaders }, preview: { headers: productionHeaders } })
