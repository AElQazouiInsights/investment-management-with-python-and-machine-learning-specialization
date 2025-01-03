// src/vite-plugin.js
import { copyFile, mkdir, readFile, writeFile } from 'fs/promises'
import { join } from 'path'

export function vitepressPythonEditor(
 { assetsDir } = { assetsDir: '.vitepress/dist/assets' }
) {
 return {
   name: 'vite-plugin-vitepress-python-editor',
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
       await mkdir(assetsDir, { recursive: true })
       await mkdir(join(assetsDir, 'data'), { recursive: true })
       
       // Copy Pyodide files
       const pyodideFiles = [
         'pyodide-lock.json',
         'pyodide.asm.js',
         'pyodide.asm.wasm',
         'python_stdlib.zip',
       ]
       for (const file of pyodideFiles) {
         await copyFile(
           join('node_modules/pyodide', file),
           join(assetsDir, file)
         )
       }

       // Copy and update PortfolioOptimizationKit
       const kitContent = await readFile('PortfolioOptimizationKit.py', 'utf-8')
       const updatedContent = kitContent.replace(
         'return "data"',
         'return "/assets/data"'
       )
       await writeFile(
         join(assetsDir, 'PortfolioOptimizationKit.py'), 
         updatedContent
       )

       // Copy data files
       await copyFile(
         join('data', 'Portfolios_Formed_on_ME_monthly_EW.csv'),
         join(assetsDir, 'data', 'Portfolios_Formed_on_ME_monthly_EW.csv')
       )
              // Copy data files
        await copyFile(
          join('data', 'edhec-hedgefundindices.csv'),
          join(assetsDir, 'data', 'edhec-hedgefundindices.csv')
        )
               // Copy data files
       await copyFile(
        join('data', 'stocks_dynamic.csv'),
        join(assetsDir, 'data', 'stocks_dynamic.csv')
      )
     } catch (error) {
       console.error('Error in generateBundle:', error)
     }
   },
 }
}