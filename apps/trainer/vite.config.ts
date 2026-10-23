import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { createRequire } from 'node:module'
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { defineConfig, loadEnv, type Plugin, type ProxyOptions } from 'vite'

const PUBLIC_MOUNT = '/lms/trainer'

/** Keep PDF decoding resources local, under static/ (assets/ belongs to the backend). */
function pdfResources(): Plugin {
  const source = dirname(createRequire(import.meta.url).resolve('pdfjs-dist/package.json'))
  const resources = new Map<string, Buffer>()
  for (const directory of ['cmaps', 'standard_fonts', 'wasm']) {
    for (const name of readdirSync(join(source, directory), { withFileTypes: true })) {
      if (name.isFile())
        resources.set(`${directory}/${name.name}`, readFileSync(join(source, directory, name.name)))
    }
  }
  return {
    name: 'local-pdf-resources',
    generateBundle() {
      for (const [name, content] of resources)
        this.emitFile({ type: 'asset', fileName: `static/pdf-support/${name}`, source: content })
    },
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const name = request.url?.split('/static/pdf-support/')[1]?.split('?')[0]
        const resource = name ? resources.get(name) : undefined
        if (!resource) return next()
        response.setHeader(
          'Content-Type',
          name?.endsWith('.wasm') ? 'application/wasm' : 'application/octet-stream',
        )
        response.end(resource)
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.LMS_DEV_BACKEND || 'http://127.0.0.1:3060'
  // Dev requests carry the same headers that nginx sets in production.
  const proxy = (prefix: string): ProxyOptions => ({
    target: backend,
    ws: true,
    headers: { 'X-LMS-App': 'trainer', 'X-Forwarded-Prefix': prefix },
    rewrite: prefix ? (path) => path.slice(prefix.length) : undefined,
  })
  return {
    // Relative base: one build is served at / and at the public mount (see nginx.conf).
    base: './',
    resolve: { tsconfigPaths: true },
    plugins: [react(), tailwindcss(), pdfResources()],
    define: { __LMS_PUBLIC_MOUNT__: JSON.stringify(PUBLIC_MOUNT) },
    build: {
      // `assets/` is reserved for backend slides and videos behind nginx.
      assetsDir: 'static',
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': proxy(''),
        '/assets': proxy(''),
        [`${PUBLIC_MOUNT}/api`]: proxy(PUBLIC_MOUNT),
        [`${PUBLIC_MOUNT}/assets`]: proxy(PUBLIC_MOUNT),
      },
    },
    preview: { host: '0.0.0.0', port: 5173, strictPort: true },
  }
})
