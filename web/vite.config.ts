import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const target = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target,
        changeOrigin: true,
        secure: false,
      },
      "/static": {
        target,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
