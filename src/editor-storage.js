// Keep the legacy code key readable, and track the lesson source separately.
function readState(storage, key) {
  const raw = storage.getItem(`${key}:state`)
  if (raw) {
    try {
      const state = JSON.parse(raw)
      if (state.version === 1 && Array.isArray(state.history)) return state
    } catch {
      // Legacy entries contain only the code string, without source metadata.
    }
  }
  return { version: 1, source: null, history: [], pending: null }
}

function writeState(storage, key, state) {
  storage.setItem(`${key}:state`, JSON.stringify(state))
}

function archive(state, code, source) {
  let index = state.history.findIndex(entry => entry.code === code && entry.source === source)
  if (index === -1) {
    index = state.history.length
    state.history.push({ code, source })
  }
  return index
}

export function loadEditorCode(storage, key, source) {
  const state = readState(storage, key)
  let code = storage.getItem(key)
  if (code !== null && code !== source && state.source !== source) {
    state.pending = archive(state, code, state.source)
    storage.removeItem(key)
    code = null
  } else if (code === source) {
    storage.removeItem(key)
  }
  state.source = source
  writeState(storage, key, state)
  return { code: code ?? source, recoveredCode: state.history[state.pending]?.code ?? null }
}

export function saveEditorCode(storage, key, source, code) {
  const state = readState(storage, key)
  state.source = source
  if (code === source) storage.removeItem(key)
  else storage.setItem(key, code)
  writeState(storage, key, state)
}

export function restoreEditorCode(storage, key, source, currentCode) {
  const state = readState(storage, key)
  const recovered = state.history[state.pending]?.code
  if (recovered === undefined) return currentCode
  if (currentCode !== source && currentCode !== recovered) archive(state, currentCode, source)
  state.pending = null
  writeState(storage, key, state)
  saveEditorCode(storage, key, source, recovered)
  return recovered
}

export function useCurrentExample(storage, key, source, currentCode) {
  const state = readState(storage, key)
  if (currentCode !== source) archive(state, currentCode, source)
  state.pending = null
  writeState(storage, key, state)
  saveEditorCode(storage, key, source, source)
  return source
}
