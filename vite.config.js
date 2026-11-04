import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// Relative base so the built site works from any path (Vercel, Netlify, GitHub Pages sub-folder, etc.)
export default defineConfig({
    base: './',
    plugins: [react()],
});
