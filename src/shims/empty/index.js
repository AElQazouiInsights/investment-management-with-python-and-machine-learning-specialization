// Empty shim for Node built-in modules in browser bundles
const empty = {}

// Support both ES modules and CommonJS-style default
export default empty
export { empty }

// path-like APIs
export const resolve = () => ''
export const sep = '/'
export const pathToFileURL = () => ''

// source-map-js placeholders
export const SourceMapConsumer = class {}
export const SourceMapGenerator = class {}

// fs placeholders
export const existsSync = () => false
export const readFileSync = () => ''
export const writeFileSync = () => {}

// postcss placeholders
export const parse = () => ({ nodes: [], toString: () => '' })
export const stringify = () => ''

// crypto placeholders
export const randomBytes = () => new Uint8Array(16)
export const createHash = () => ({ update: () => ({}), digest: () => '' })

