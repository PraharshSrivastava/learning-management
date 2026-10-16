import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type ProxyOptions } from 'vite'

const PUBLIC_MOUNT = '/lms'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.LMS_DEV_BACKEND || 'http://127.0.0.1:3060'
  // Dev requests carry the same headers that nginx sets in production.
  const proxy = (prefix: string): ProxyOptions => ({
    target: backend,
    ws: true,
    headers: { 'X-LMS-App': 'employee', 'X-Forwarded-Prefix': prefix },
    rewrite: prefix ? (path) => path.slice(prefix.length) : undefined,
  })
  return {
    // Relative base: one build is served at / and at the public mount (see nginx.conf).
    base: './',
    resolve: { tsconfigPaths: true },
    plugins: [react(), tailwindcss()],
    define: { __LMS_PUBLIC_MOUNT__: JSON.stringify(PUBLIC_MOUNT) },
    build: {
      // `assets/` is reserved for backend slides and videos behind nginx.
      assetsDir: 'static',
    },
    server: {
      host: '0.0.0.0',
      port: 5174,
      strictPort: true,
      proxy: {
        '/api': proxy(''),
        '/assets': proxy(''),
        [`${PUBLIC_MOUNT}/api`]: proxy(PUBLIC_MOUNT),
        [`${PUBLIC_MOUNT}/assets`]: proxy(PUBLIC_MOUNT),
      },
    },
    preview: { host: '0.0.0.0', port: 5174, strictPort: true },
  }
})
