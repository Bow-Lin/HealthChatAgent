import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(), // Tailwind v4 官方 Vite 插件
  ],
  server: {
    proxy: {
      "/api": "http://localhost:9000", // 如果后端端口不是 8000，就在这里改
    },
  },
});
