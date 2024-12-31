// .vitepress\config.ts

import { defineConfig } from 'vitepress'
import { vitepressPythonEditor } from '../src/vite-plugin'

// const base = '/investment-management-with-python-and-machine-learning-specialization/'
const base = '/'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "Investment Management with Python",
  description: "Portfolio management techniques with Python and Machine Learning",
  base,
  head: [
    ['link', { rel: 'icon', type: 'image/x-icon', href: `${base}favicon.ico` }],
    ['link', { rel: 'stylesheet', href: `${base}theme.css` }],
    // Cross Origin Isolation headers
    ['meta', { 'http-equiv': 'Cross-Origin-Embedder-Policy', content: 'require-corp' }],
    ['meta', { 'http-equiv': 'Cross-Origin-Opener-Policy', content: 'same-origin' }],
    ['meta', { 'http-equiv': 'Cross-Origin-Resource-Policy', content: 'same-origin' }],
    // Origin Trial token for SharedArrayBuffer
    ['meta', { 
      'http-equiv': 'origin-trial', 
      content: 'AuatyxizBLUuF1Bg0Cd24qcSR6cTo9XGlyhT2cUPXpwFAPJWWDYn90ih56m2l4bCoY+Z6ZxbBBsyziFbtR+EugUAAABgeyJvcmlnaW4iOiJodHRwOi8vbG9jYWxob3N0OjQxNzMiLCJmZWF0dXJlIjoiVW5yZXN0cmljdGVkU2hhcmVkQXJyYXlCdWZmZXIiLCJleHBpcnkiOjE3NTMxNDI0MDB9' 
    }]
  ],

  cleanUrls: true,
  srcDir: 'docs',
  vite: {
    plugins: [vitepressPythonEditor()],
    optimizeDeps: {
      include: ['echarts', 'vue-echarts']
    },
    ssr: {
      noExternal: ['vue-echarts', 'echarts'] // Ensure these packages are bundled for SSR
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
    logo: '/pi.svg',
    siteTitle: 'Investment Management with Python',
    socialLinks: [
      { icon: 'github', link: 'https://github.com/Crypto-Aggressor/Investment-Management-with-Python-and-Machine-Learning-Specialization' }
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
            { text: 'Overview', link: '/2-advanced/2.0-overview' },
            { text: 'Advanced Insights into Style & Factor Exposures for Portfolio Optimization', link: '/2-advanced/2.1-style-factors' },
            { text: 'Strategies for Robust Covariance Matrix Estimation in Portfolio Management', link: '/2-advanced/2.2-covariance' }
          ]
        }
      ]
    },
    footer: {
      message: 'Translated post certification complex financial theories into practical Python modules post EDHEC Business School Certification , openly shared under the MIT License.',
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
    { text: 'Advanced Portfolio Analysis', link: '/2-advanced/2.0-overview' }
  ]
}