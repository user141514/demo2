import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/static/leadership-react/",
  plugins: [react()],
  build: {
    outDir: "../../static/leadership-react",
    emptyOutDir: true
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:5000"
    }
  }
});
