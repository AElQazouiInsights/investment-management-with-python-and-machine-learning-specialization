// .vitepress\config.ts

import { defineConfig } from 'vitepress'
import path from 'path'
import { vitepressPythonEditor } from '../src/vite-plugin'

// const base = '/investment-management-with-python-and-machine-learning-specialization/'
const base = '/'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "Investment Management with Python",
  description: "Portfolio management techniques with Python and Machine Learning",
  base,
  head: [
    ['link', { rel: 'stylesheet', href: `${base}theme.css` }],
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${base}pi.svg` }]
  ],

  cleanUrls: true,
  srcDir: 'docs',
  vite: {
    plugins: [vitepressPythonEditor()],
    optimizeDeps: {
      include: [
        'echarts', 
        'vue-echarts',
        '@jupyter-widgets/html-manager',
        '@jupyter-widgets/base',
        '@jupyter-widgets/controls',
        '@jupyter-widgets/schema'
      ],
      exclude: [
        '@phosphor/coreutils',
        '@jupyter-widgets/output'
      ]
    },
    resolve: {
      alias: [
        // Strip node: prefix if any
        { find: /^node:(.*)$/, replacement: '$1' },
        // Map Node core/polyfill needs to a safe empty shim directory
        { find: 'fs', replacement: path.resolve(process.cwd(), 'src/shims/empty') },
        { find: 'fs/promises', replacement: path.resolve(process.cwd(), 'src/shims/empty/promises.js') },
        { find: 'path', replacement: path.resolve(process.cwd(), 'src/shims/empty') },
        { find: 'vm', replacement: path.resolve(process.cwd(), 'src/shims/empty') },
        { find: 'url', replacement: path.resolve(process.cwd(), 'src/shims/empty') },
        { find: 'child_process', replacement: path.resolve(process.cwd(), 'src/shims/empty') },
        { find: 'crypto', replacement: path.resolve(process.cwd(), 'src/shims/empty') },
        // Provide lightweight shims for browser compatibility
        { find: 'sanitize-html', replacement: path.resolve(process.cwd(), 'src/shims/sanitize-html.js') },
        { find: 'json5', replacement: path.resolve(process.cwd(), 'src/shims/json5.js') }
      ]
    },
    define: {
      global: 'globalThis',
      'process.env': {},
      'process.browser': true,
      'process.version': '""',
      'Buffer': 'undefined'
    },
    ssr: {
      noExternal: ['vue-echarts', 'echarts', 'zrender', '@jupyter-widgets/html-manager', '@jupyter-widgets/base', '@jupyter-widgets/controls', '@jupyter-widgets/schema'] // Ensure these packages are bundled for SSR
    },
    server: {
      headers: {
        'Cross-Origin-Opener-Policy': 'same-origin',
        'Cross-Origin-Embedder-Policy': 'require-corp',
        'Cross-Origin-Resource-Policy': 'same-origin'
      }
    },
    preview: {
      headers: {
        'Cross-Origin-Opener-Policy': 'same-origin',
        'Cross-Origin-Embedder-Policy': 'require-corp',
        'Cross-Origin-Resource-Policy': 'same-origin'
      }
    }
  },
  themeConfig: {
    logo: '/pi-red.jpg',
    outline: 'deep', // This will ensure that the TOC includes deeper levels of headings, creating a nested structure
    siteTitle: 'Investment Management with Python',
    socialLinks: [
      { icon: 'github', link: 'https://github.com/AElQazouiInsights/investment-management-with-python-and-machine-learning-specialization' }
    ],
    sidebar: {
      '/': [
        {
          text: 'Introduction to Portfolio Construction & Analysis',
          collapsed: true,
          items: [
            { text: 'Overview', link: '/1.0-overview' },
            { text: 'Understanding Risks', link: '/1.1-risks' },
            { text: 'Portfolio Optimization', link: '/1.2-optimization' },
            { text: 'Diversification Strategies', link: '/1.3-diversification' },
            { text: 'Asset Liability Management', link: '/1.4-alm' }
          ]
        },
        {
          text: 'Advanced Portfolio Construction and Analysis',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/2.0-overview' },
            { text: 'Advanced Insights into Style & Factor Exposures for Portfolio Optimization', link: '/2.1-style-factors' },
            { text: 'Strategies for Robust Covariance Matrix Estimation in Portfolio Management', link: '/2.2-covariance' },
            { text: 'Black–Litterman: Reference Portfolios, Views, and Uncertainty', link: '/2.3-black-litterman' },
            { text: 'Robust Portfolio Construction: Diversification and Risk Budgets', link: '/2.4-robust-portfolios' }
          ]
        }
      ]
    },
    footer: {
      message: 'After earning certification from EDHEC Business School, I translated complex financial theories into practical Python modules, openly shared under the MIT License.',
      copyright: 'Copyright © 2024-present, Amine El Qazoui.'
    },
    nav: nav()
  },
  markdown: {
    math: true
  }
})

function nav() {
  return [
    { text: 'Home', link: '/' },
    { text: 'Intro to Portfolio Construction', link: '/1.0-overview' },
    { text: 'Advanced Portfolio Analysis', link: '/2.0-overview' }
  ]
}
