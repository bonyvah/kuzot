import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, the API is proxied so the browser talks to one origin (no CORS).
const API_TARGET = process.env.VITE_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
      "/health": { target: API_TARGET, changeOrigin: true },
    },
  },
});
