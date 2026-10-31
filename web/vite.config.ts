import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served by FastAPI under /app. In dev, API calls proxy to the local backend.
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8088",
    },
  },
});
