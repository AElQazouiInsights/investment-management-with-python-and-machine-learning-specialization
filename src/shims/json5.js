// Lightweight JSON5 shim exposing a named `parse` export
// NOTE: This does not support full JSON5 syntax; it is a fallback.

export const parse = (text) => {
  // Try native JSON first; if it fails, return an empty object to avoid crashes.
  try {
    return JSON.parse(text)
  } catch (_) {
    // Best-effort fallback: strip simple // and /* */ comments, then parse
    try {
      const withoutLine = text.replace(/(^|\n)\s*\/\/.*(?=\n|$)/g, '$1')
      const withoutBlock = withoutLine.replace(/\/\*[\s\S]*?\*\//g, '')
      return JSON.parse(withoutBlock)
    } catch (__) {
      return {}
    }
  }
}

export default { parse }

