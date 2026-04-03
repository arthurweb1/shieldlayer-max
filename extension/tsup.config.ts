import { defineConfig } from "tsup";

export default defineConfig({
  entry: {
    "content/injector": "src/content/injector.ts",
    "content/interceptor": "src/content/interceptor.ts",
    "background/service_worker": "src/background/service_worker.ts",
  },
  format: ["iife"],
  outDir: "dist",
  clean: true,
  minify: false,
});
