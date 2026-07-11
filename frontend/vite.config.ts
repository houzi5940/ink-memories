import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'static/js',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: './index.html',
        review: './review.html',
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: '[name].js',
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name?.split('.') ?? []
          const ext = info[info.length - 1]
          if (/\.(css)$/i.test(assetInfo.name ?? '')) {
            return `assets/[name][extname]`
          }
          return `assets/[name]-[hash][extname]`
        },
      },
    },
  },
})
