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
  day, stored entirely in your browser via `localStorage`. Nothing is sent
  to a server.
- No frameworks, no build step, no dependencies, no API keys — plain HTML,
  CSS, and vanilla JavaScript.

## Running locally

Just open `index.html` in a browser, or serve it so relative paths and
`localStorage` behave exactly like production:

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

## Disclaimer

This site provides general wellness information only and is not medical
advice. It intentionally avoids extreme, unproven, or unsafe practices. If
appearance-related thoughts are affecting your wellbeing, please talk to a
doctor or mental health professional.
