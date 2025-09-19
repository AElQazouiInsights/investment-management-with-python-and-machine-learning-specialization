// Minimal sanitize-html shim for browser builds that provides enough surface
// area for @jupyter-widgets/html-manager to operate.

function sanitizeHtml(dirty, options = {}) {
  if (typeof dirty !== 'string') return ''
  // Very basic sanitisation: strip script tags
  const withoutScripts = dirty.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
  return withoutScripts
}

sanitizeHtml.defaults = {
  allowedTags: ['div', 'span', 'p', 'b', 'i', 'em', 'strong', 'a', 'img'],
  allowedAttributes: {},
  allowedSchemes: ['http', 'https', 'ftp', 'mailto', 'tel']
}

function simpleTransform(newTagName, newAttribs = {}) {
  return (tagName, attribs = {}) => ({
    tagName: newTagName || tagName,
    attribs: { ...attribs, ...newAttribs }
  })
}

sanitizeHtml.simpleTransform = simpleTransform

export default sanitizeHtml
export { simpleTransform }

try { sanitizeHtml.default = sanitizeHtml } catch {}
