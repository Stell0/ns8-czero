import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    {
      name: 'bundled-license-notices',
      generateBundle(_options, bundle) {
        const packages = new Set<string>([resolve('node_modules/tailwindcss')])
        const modules = Object.values(bundle).flatMap((chunk) =>
          chunk.type === 'chunk'
            ? Object.entries(chunk.modules)
                .filter(([, value]) => value.renderedLength > 0)
                .map(([id]) => id)
            : [],
        )
        for (const id of modules) {
          const matched = id.match(/^(.*\/node_modules\/(?:@[^/]+\/)?[^/]+)/)
          if (matched) packages.add(matched[1])
        }
        const notices = [...packages].sort().map((directory) => {
          const metadata = JSON.parse(
            readFileSync(resolve(directory, 'package.json'), 'utf8'),
          )
          const files = readdirSync(directory)
            .filter((name) =>
              /^(?:licen[cs]e|copying|notice)(?:\.|$)/i.test(name),
            )
            .sort()
          if (!files.length) {
            if (
              metadata.name === '@headlessui/vue' &&
              metadata.version === '1.7.23'
            )
              return `${metadata.name} ${metadata.version}\n${readFileSync(resolve('licenses/headlessui-vue-1.7.23.txt'), 'utf8')}`
            throw new Error(`Missing bundled license: ${metadata.name}`)
          }
          return `${metadata.name} ${metadata.version}\n${files.map((name) => readFileSync(resolve(directory, name), 'utf8')).join('\n')}`
        })
        this.emitFile({
          type: 'asset',
          fileName: 'vendor/third-party-notices.txt',
          source: notices.join('\n\n────────────────────\n\n'),
        })
      },
    },
  ],
  base: './',
  build: { manifest: true },
  test: { environment: 'jsdom', include: ['tests/**/*.test.ts'] },
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
