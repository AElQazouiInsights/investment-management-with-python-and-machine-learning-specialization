// src/vite-plugin.js
import { mkdir, readFile, writeFile } from 'fs/promises'
import { join, resolve } from 'path'

export function vitepressPythonEditor(
 { assetsDir } = {}
) {
 let outputAssets
 return {
    name: 'vite-plugin-vitepress-python-editor',
    configResolved(config) {
      outputAssets = assetsDir ?? resolve(config.root, config.build.outDir, 'assets')
    },
   config: () => ({
     build: {
       target: 'esnext',
     },
     worker: {
       format: 'es',
     },
     optimizeDeps: {
       exclude: ['pyodide'],
     },
   }),
   configureServer: (server) => {
     // Add headers
     server.middlewares.use((_, res, next) => {
       res.setHeader('Cross-Origin-Opener-Policy', 'same-origin')
       res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp')
       next()
     })

     // Serve Python files properly
     server.middlewares.use(async (req, res, next) => {
       if (req.url?.endsWith('.py')) {
         try {
           const content = await readFile(req.url.slice(1), 'utf-8')
           res.setHeader('Content-Type', 'text/plain')
           res.end(content)
           return
         } catch (error) {
           console.error('Error serving Python file:', error)
           next()
         }
       }
       
       // Serve CSV files properly
       if (req.url?.endsWith('.csv')) {
         try {
           const content = await readFile(req.url.slice(1), 'utf-8')
           res.setHeader('Content-Type', 'text/csv')
           res.end(content)
           return
         } catch (error) {
           console.error('Error serving CSV file:', error)
           next()
         }
       }
       
       next()
     })
   },
  generateBundle: async () => {
    try {
      // Create directories
      await mkdir(outputAssets, { recursive: true })
      await mkdir(join(outputAssets, 'data'), { recursive: true })

      // Copy and update PortfolioOptimizationKit
      const kitContent = await readFile('PortfolioOptimizationKit.py', 'utf-8')
      const updatedContent = kitContent.replace(
        'return "data"',
        'return "/assets/data"'
      )
      await writeFile(
        join(outputAssets, 'PortfolioOptimizationKit.py'),
        updatedContent
      )

      // Data files are served from public/assets/data at runtime; no copy needed
     } catch (error) {
       throw new Error(`Could not publish PortfolioOptimizationKit.py: ${error.message}`)
     }
   },
 }
}
