// .vitepress\config.ts

import { defineConfig } from 'vitepress'
import path from 'path'
import { vitepressPythonEditor } from '../src/vite-plugin'

// const base = '/investment-management-with-python-and-machine-learning-specialization/'
const base = '/'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "Investment Management with Python",
  description: "Portfolio construction and analysis with Python: returns, risk, optimization, factor exposures, covariance estimation, and risk budgeting.",
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
      {
        icon: { svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M12 .297c-6.63 0-12 5.373-12 12c0 5.303 3.438 9.8 8.205 11.385c.6.113.82-.258.82-.577c0-.285-.01-1.04-.015-2.04c-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729c1.205.084 1.838 1.236 1.838 1.236c1.07 1.835 2.809 1.305 3.495.998c.108-.776.417-1.305.76-1.605c-2.665-.3-5.466-1.332-5.466-5.93c0-1.31.465-2.38 1.235-3.22c-.135-.303-.54-1.523.105-3.176c0 0 1.005-.322 3.3 1.23c.96-.267 1.98-.399 3-.405c1.02.006 2.04.138 3 .405c2.28-1.552 3.285-1.23 3.285-1.23c.645 1.653.24 2.873.12 3.176c.765.84 1.23 1.91 1.23 3.22c0 4.61-2.805 5.625-5.475 5.92c.42.36.81 1.096.81 2.22c0 1.606-.015 2.896-.015 3.286c0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>' },
        ariaLabel: 'GitHub',
        link: 'https://github.com/AElQazouiInsights/investment-management-with-python-and-machine-learning-specialization'
      }
    ],
    sidebar: {
      '/': [
        {
          text: 'Portfolio Management Fundamentals',
          collapsed: true,
          items: [
            { text: 'Overview', link: '/1.0-overview' },
            { text: 'Understanding Returns and Assessing Risks with Value at Risk', link: '/1.1-risks' },
            { text: 'Fundamentals of Portfolio Optimization', link: '/1.2-optimization' },
            { text: 'Strategies Beyond Diversification', link: '/1.3-diversification' },
            { text: 'Fundamentals of Asset-Liability Management', link: '/1.4-alm' }
          ]
        },
        {
          text: 'Advanced Portfolio Construction and Analysis',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/2.0-overview' },
            { text: 'Style and Factor Exposures', link: '/2.1-style-factors' },
            { text: 'Covariance Matrix Estimation for Portfolio Construction', link: '/2.2-covariance' },
            { text: 'Black–Litterman: Reference Portfolios, Views, and Uncertainty', link: '/2.3-black-litterman' },
            { text: 'Robust Portfolio Construction: Diversification and Risk Budgets', link: '/2.4-robust-portfolios' },
            { text: 'Comparing Portfolio Decisions: A Capstone', link: '/2.5-capstone' }
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
    { text: 'Portfolio Fundamentals', link: '/1.0-overview' },
    { text: 'Advanced Portfolio Analysis', link: '/2.0-overview' }
  ]
}
