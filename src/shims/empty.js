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

// For sanitize-html module - provide a minimal implementation
const sanitizeHtml = (dirty, options) => {
  // Very basic HTML sanitization - just strip script tags and return
  if (typeof dirty !== 'string') return ''
  return dirty.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
}

// Add the allowedSchemes property that the error is looking for
sanitizeHtml.defaults = {
  allowedTags: ['div', 'span', 'p', 'b', 'i', 'em', 'strong', 'a', 'img'],
  allowedAttributes: {},
  allowedSchemes: ['http', 'https', 'ftp', 'mailto', 'tel']
}

// For default export
export { sanitizeHtml as default }
