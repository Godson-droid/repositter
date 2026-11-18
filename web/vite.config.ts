import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Published to GitHub Pages from the repo's gh-pages branch:
// https://godson-droid.github.io/repositter/
export default defineConfig({
  base: '/repositter/',
  plugins: [react()],
})
