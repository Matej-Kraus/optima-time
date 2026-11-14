import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, /api goes to the backend (optima-time run --port 8787).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8787" } },
});
