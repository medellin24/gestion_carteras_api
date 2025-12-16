// IndexedDB minimalista para trabajo offline
const DB_NAME = 'carteras_offline'
const DB_VERSION = 2
const STORES = { tarjetas: 'tarjetas', stats: 'stats', outbox: 'outbox', abonos: 'abonos' }

let dbPromise

function openDB() {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = (ev) => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORES.tarjetas)) db.createObjectStore(STORES.tarjetas)
      if (!db.objectStoreNames.contains(STORES.stats)) db.createObjectStore(STORES.stats)
      if (!db.objectStoreNames.contains(STORES.outbox)) db.createObjectStore(STORES.outbox, { keyPath: 'id' })
      if (!db.objectStoreNames.contains(STORES.abonos)) db.createObjectStore(STORES.abonos)
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return dbPromise
}

async function put(store, key, value) {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite')
    const os = tx.objectStore(store)
    const req = os.put(value, key)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

async function get(store, key) {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly')
    const os = tx.objectStore(store)
    const req = os.get(key)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function setTarjetas(list) { return put(STORES.tarjetas, 'all', list) }
async function getTarjetas() { return (await get(STORES.tarjetas, 'all')) || [] }
async function setStats(stats) { return put(STORES.stats, 'current', stats) }
async function getStats() { return (await get(STORES.stats, 'current')) || { monto: 0, abonos: 0 } }
async function setAbonos(tarjetaCodigo, list) { return put(STORES.abonos, String(tarjetaCodigo), list || []) }
async function getAbonos(tarjetaCodigo) { return (await get(STORES.abonos, String(tarjetaCodigo))) || [] }

async function queueOperation(op) {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.outbox, 'readwrite')
    const os = tx.objectStore(STORES.outbox)
    const item = { id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, ts: Date.now(), ...op }
    const req = os.add(item)
    req.onsuccess = () => { window.dispatchEvent(new Event('outbox-updated')); resolve(item) }
    req.onerror = () => reject(req.error)
  })
}

async function readOutbox() {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.outbox, 'readonly')
    const os = tx.objectStore(STORES.outbox)
    const req = os.getAll()
    req.onsuccess = () => resolve(req.result || [])
    req.onerror = () => reject(req.error)
  })
}

async function removeOutbox(id) {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.outbox, 'readwrite')
    const os = tx.objectStore(STORES.outbox)
    const req = os.delete(id)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

async function readOutboxCount() {
  const list = await readOutbox().catch(() => [])
  return Array.isArray(list) ? list.length : 0
}

async function close() {
  if (!dbPromise) return
  const db = await dbPromise.catch(() => null)
  if (db) {
    db.close()
  }
  dbPromise = null
}

async function resetWorkingMemory() {
  // CRITICO: Cerrar conexión antes de borrar para evitar bloqueo (deadlock)
  await close()
  return new Promise((resolve, reject) => {
    try {
      const req = indexedDB.deleteDatabase(DB_NAME)
      req.onsuccess = () => { dbPromise = null; resolve() }
      req.onerror = () => reject(req.error)
      req.onblocked = () => {
        console.warn('Delete blocked in resetWorkingMemory')
        // Intentar cerrar de nuevo por si acaso
        close().then(() => resolve())
      }
    } catch (e) {
      reject(e)
    }
  })
}

export const offlineDB = {
  setTarjetas, getTarjetas, setStats, getStats, setAbonos, getAbonos, queueOperation, readOutbox, removeOutbox, readOutboxCount, resetWorkingMemory, close,
}
