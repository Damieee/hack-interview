import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const rootEnv = loadEnv(mode, path.resolve(__dirname, ".."));
  Object.assign(process.env, rootEnv);

  return {
    plugins: [react()],
    server: {
      port: 5173,
    },
  };
});
