// src\vite-plugin.d.ts

import { Plugin } from 'vitepress'

export function vitepressPythonEditor(
  { assetsDir }?: { assetsDir: string }
): Plugin
