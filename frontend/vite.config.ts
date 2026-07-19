import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build straight into backend/static so FastAPI serves the SPA in production.
// During dev, proxy /api to the uvicorn backend on :8000.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
