// Thin wrapper around Firebase Auth + Firestore, loaded lazily and only
// when firebase-config.js has real values. Both login.js and script.js
// import this module, so they share one Firebase app instance.

import { firebaseConfig, firebaseConfigured } from "./firebase-config.js";

const FIREBASE_VERSION = "10.13.2";
const CDN = "https://www.gstatic.com/firebasejs/" + FIREBASE_VERSION + "/";

let appMod, authMod, fsMod;
let auth, db;
let loadPromise = null;

function loadFirebase() {
  if (!firebaseConfigured) return Promise.resolve(false);
  if (loadPromise) return loadPromise;

  loadPromise = (async () => {
    try {
      [appMod, authMod, fsMod] = await Promise.all([
        import(/* webpackIgnore: true */ CDN + "firebase-app.js"),
        import(/* webpackIgnore: true */ CDN + "firebase-auth.js"),
        import(/* webpackIgnore: true */ CDN + "firebase-firestore.js")
      ]);
      const app = appMod.initializeApp(firebaseConfig);
      auth = authMod.getAuth(app);
      db = fsMod.getFirestore(app);
      return true;
    } catch (err) {
      console.error("GlowUp: could not reach the Firebase backend.", err);
      return false;
    }
  })();

  return loadPromise;
}

export function isBackendConfigured() {
  return firebaseConfigured;
}

// callback(user | null) fires immediately with current state, then on every change.
// Returns an unsubscribe function.
export async function onAuthChange(callback) {
  const ready = await loadFirebase();
  if (!ready) {
    callback(null);
    return function () {};
  }
  return authMod.onAuthStateChanged(auth, callback);
}

export async function signUp(email, password) {
  const ready = await loadFirebase();
  if (!ready) throw new Error("The free backend isn't configured yet — see README.md.");
  return authMod.createUserWithEmailAndPassword(auth, email, password);
}

export async function signIn(email, password) {
  const ready = await loadFirebase();
  if (!ready) throw new Error("The free backend isn't configured yet — see README.md.");
  return authMod.signInWithEmailAndPassword(auth, email, password);
}

export async function signOutUser() {
  const ready = await loadFirebase();
  if (!ready) return;
  return authMod.signOut(auth);
}

export async function resetPassword(email) {
  const ready = await loadFirebase();
  if (!ready) throw new Error("The free backend isn't configured yet — see README.md.");
  return authMod.sendPasswordResetEmail(auth, email);
}

// Merges `data` into users/{uid}/data/{docName}.
export async function saveUserData(uid, docName, data) {
  const ready = await loadFirebase();
  if (!ready) return false;
  const ref = fsMod.doc(db, "users", uid, "data", docName);
  await fsMod.setDoc(ref, data, { merge: true });
  return true;
}

// Returns the document's data, or null if it doesn't exist / backend unavailable.
export async function loadUserData(uid, docName) {
  const ready = await loadFirebase();
  if (!ready) return null;
  const ref = fsMod.doc(db, "users", uid, "data", docName);
  const snap = await fsMod.getDoc(ref);
  return snap.exists() ? snap.data() : null;
}
