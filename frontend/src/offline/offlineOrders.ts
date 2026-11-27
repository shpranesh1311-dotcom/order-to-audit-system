export interface OfflineOrderPayload {
  idempotency_key: string;
  customer_id: number;
  customer_name: string;
  order_date: string;
  offline_created_at: string;
  notes?: string;
  items: { product_id: number; product_name: string; quantity: number; unit_price: number }[];
  total_estimated: number;
  status: "pending" | "failed";
  error_message?: string;
}

const DB_NAME = "order_to_audit_offline";
const DB_VERSION = 1;
const STORE_ORDERS = "pending_orders";
const STORE_CACHE = "master_cache";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_ORDERS)) {
        db.createObjectStore(STORE_ORDERS, { keyPath: "idempotency_key" });
      }
      if (!db.objectStoreNames.contains(STORE_CACHE)) {
        db.createObjectStore(STORE_CACHE, { keyPath: "key" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function queueOfflineOrder(order: OfflineOrderPayload): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_ORDERS, "readwrite");
    tx.objectStore(STORE_ORDERS).put(order);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getPendingOfflineOrders(): Promise<OfflineOrderPayload[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_ORDERS, "readonly");
    const req = tx.objectStore(STORE_ORDERS).getAll();
    req.onsuccess = () => resolve((req.result as OfflineOrderPayload[]) || []);
    req.onerror = () => reject(req.error);
  });
}

export async function removeOfflineOrder(idempotencyKey: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_ORDERS, "readwrite");
    tx.objectStore(STORE_ORDERS).delete(idempotencyKey);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function cacheMasterData(key: string, data: unknown): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_CACHE, "readwrite");
      tx.objectStore(STORE_CACHE).put({ key, data, updated_at: new Date().toISOString() });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    // Ignore IndexedDB quota errors in restricted environments
  }
}

export async function getCachedMasterData<T>(key: string): Promise<T | null> {
  try {
    const db = await openDb();
    return await new Promise<T | null>((resolve, reject) => {
      const tx = db.transaction(STORE_CACHE, "readonly");
      const req = tx.objectStore(STORE_CACHE).get(key);
      req.onsuccess = () => resolve(req.result ? (req.result.data as T) : null);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return null;
  }
}
