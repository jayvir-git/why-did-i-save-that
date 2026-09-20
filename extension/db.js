/* IndexedDB transactions prevent lost updates across tabs and service-worker restarts. */
let goldDatabase;
function openGoldDB() {
  return goldDatabase ||= new Promise((resolve, reject) => {
    const req = indexedDB.open('gold-library', 1);
    req.onupgradeneeded = () => req.result.createObjectStore('posts', {keyPath:'key'});
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function getPosts() {
  const db = await openGoldDB();
  return new Promise((resolve, reject) => {
    const req = db.transaction('posts').objectStore('posts').getAll();
    req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
  });
}
async function savePosts(posts) {
  const db = await openGoldDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('posts', 'readwrite'), store = tx.objectStore('posts');
    let added = 0;
    for (const p of posts) {
      const req = store.get(p.key);
      req.onsuccess = () => { if (!req.result) added++; store.put(GoldCore.merge(req.result, p)); };
    }
    tx.oncomplete = () => resolve({added, processed:posts.length});
    tx.onerror = () => reject(tx.error); tx.onabort = () => reject(tx.error || new Error('Storage write aborted'));
  });
}
async function updatePost(key, changes) {
  const db = await openGoldDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('posts','readwrite'), store = tx.objectStore('posts');
    const req = store.get(key);
    req.onsuccess = () => { if (req.result) store.put({...req.result,...changes}); };
    tx.oncomplete = resolve; tx.onerror = () => reject(tx.error);
  });
}
