// Empty shim for Node built-in modules in browser bundles
const empty = {}

// Support both ES modules and CommonJS
export default empty
export { empty }

// For path module
export const resolve = () => ''
export const sep = '/'
export const pathToFileURL = () => ''

// For source-map-js module
export const SourceMapConsumer = class {}
export const SourceMapGenerator = class {}

// For fs module
export const existsSync = () => false
export const readFileSync = () => ''
export const writeFileSync = () => {}

// For postcss module
export const parse = () => ({ nodes: [], toString: () => '' })
export const stringify = () => ''

// For crypto module
export const randomBytes = () => new Uint8Array(16)
export const createHash = () => ({ update: () => ({}), digest: () => '' })
