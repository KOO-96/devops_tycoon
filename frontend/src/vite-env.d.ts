/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PIXI_DEBUG?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
