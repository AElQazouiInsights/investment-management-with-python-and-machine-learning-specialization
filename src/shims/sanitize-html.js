// Minimal sanitize-html shim for browser builds
// Provides a default export function and a `defaults` property

function sanitizeHtml(dirty, options = {}) {
  if (typeof dirty !== 'string') return ''
  // Very basic sanitization: strip script tags
  const withoutScripts = dirty.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
  return withoutScripts
}

sanitizeHtml.defaults = {
  allowedTags: ['div', 'span', 'p', 'b', 'i', 'em', 'strong', 'a', 'img'],
  allowedAttributes: {},
  allowedSchemes: ['http', 'https', 'ftp', 'mailto', 'tel']
}

export default sanitizeHtml

