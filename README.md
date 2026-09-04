# GlowUp Guide

A free, evidence-based looksmaxing / self-improvement website: specific,
non-generic skincare, grooming, posture, fitness, and lifestyle protocols —
no products, procedures, or purchases required.

## Features

- **60-second Glow-Up Assessment** — a 4-question quiz that opens the site
  and generates a personalized "Priority Stack" (your top 3 actions), with
  the result saved in your browser so it's there when you come back.
- **Concrete, specific advice** — real ingredient names and percentages,
  exact technique steps, and named exercises with sets/reps instead of vague
  tips.
- **Daily routine checklist with a streak counter** — track habits day to
  day, stored entirely in your browser via `localStorage` by default.
- **Dark mode** — a toggle in the header (🌙/☀️) that overrides your system
  preference and remembers your choice.
- **Motion & micro-interactions** — an animated hero background, scroll-reveal
  on content cards, hover/press feedback on buttons and cards, and a streak
  badge pulse — all pure CSS/JS, no image or video assets, and everything
  respects `prefers-reduced-motion`.
- **Optional free accounts (`login.html`)** — sign in to sync your Priority
  Stack and daily routine across devices via a free Firebase backend (Auth +
  Firestore). Fully optional: without it, or before it's configured, the
  site works exactly as before, entirely local and private.
- No frameworks, no build step — plain HTML, CSS, and vanilla JavaScript.
  The only external code loaded is the Firebase SDK, and only if you enable
  cloud sync (see below).

## Running locally

The site uses JS modules (for the theme toggle and optional auth), which
browsers block from loading over the `file://` protocol. Serve it locally
instead:

```bash
python3 -m http.server 8000
# then visit http://localhost:8000
```

## Deploying for free

**GitHub Pages**
1. Push this repo to GitHub (already done if you're reading this from the repo).
2. Go to Settings → Pages.
3. Under "Build and deployment", choose "Deploy from a branch", pick this
   branch and the root folder.
4. Your site will be live at `https://<username>.github.io/<repo>/`.

Any other free static host (Netlify, Vercel, Cloudflare Pages, GitHub
Codespaces port forwarding, etc.) works the same way — there's no server or
build step required.

## Optional: enable free cloud accounts (Firebase)

Sign-in works out of the box in the sense that `login.html` renders and
explains itself — but it needs a one-time, free setup before accounts
actually work, because that requires a real backend project that only you
can create (this repo can't provision cloud resources on its own).

1. Go to the [Firebase console](https://console.firebase.google.com) and
   create a project (the free "Spark" plan — no billing required for this
   site's usage level).
2. **Authentication** → Sign-in method → enable **Email/Password**.
3. **Firestore Database** → Create database → start in production mode, pick
   a region.
4. **Firestore → Rules** tab → paste in the contents of `firestore.rules`
   from this repo → Publish. This restricts every user to reading/writing
   only their own data.
5. **Project settings** (gear icon) → General → "Your apps" → add a **Web**
   app → copy the `firebaseConfig` object it gives you.
6. Paste those values into `firebase-config.js` in this repo, and change
   `firebaseConfigured` to `true`.
7. Commit, push, redeploy.

Visitors can now create an account on `login.html`; their quiz result and
daily routine (including streak) sync to Firestore under their own user ID,
in addition to the local `localStorage` copy used for instant, offline-friendly
UI. Skipping all of this is completely fine — every other feature works
without it.

## Disclaimer

This site provides general wellness information only and is not medical
advice. It intentionally avoids extreme, unproven, or unsafe practices. If
appearance-related thoughts are affecting your wellbeing, please talk to a
doctor or mental health professional.
