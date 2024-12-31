// // .vitepress\theme\index.ts

// import type { Theme } from 'vitepress'
// import DefaultTheme from 'vitepress/theme'
// import Editor from 'vitepress-python-editor'
// import OutputDisplay from '../../src/OutputDisplay.vue'

// export default {
//   extends: DefaultTheme,
//   enhanceApp({ app }) {
//     app.component('Editor', Editor)
//     app.component('OutputDisplay', OutputDisplay)
//   },
// } satisfies Theme
// .vitepress/theme/index.ts

import type { Theme } from 'vitepress'
import DefaultTheme from 'vitepress/theme'
import { defineAsyncComponent } from 'vue'
import ClientOnly from '../../src/ClientOnly.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    // Dynamically import Editor and OutputDisplay to ensure they're only loaded on the client
    app.component('Editor', defineAsyncComponent(() => import('vitepress-python-editor')))
    app.component('OutputDisplay', defineAsyncComponent(() => import('../../src/OutputDisplay.vue')))
    app.component('ClientOnly', ClientOnly)
  },
} satisfies Theme