import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react"

// CONV-5: frontend en 5173. /api se redirige al backend (Contrato B) para que el navegador vea un solo origen.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": { target: env.VITE_API_TARGET || "http://localhost:8000", changeOrigin: true } },
    },
    test: { environment: "jsdom", include: ["src/**/*.test.ts", "src/**/*.test.tsx"] },
  }
})
