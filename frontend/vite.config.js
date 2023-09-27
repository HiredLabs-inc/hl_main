import { defineConfig } from 'vite'
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [],
    build: {
        manifest: true,
        rollupOptions: {
            input: 'src/main.js',
        },
        outDir: 'build',
        assetsDir: 'static',
    },
})

