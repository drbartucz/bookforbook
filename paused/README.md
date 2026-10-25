# Paused page

Static "taking a break" notice for Cloudflare Pages. Every route serves `index.html`
(`_redirects`), and the page unregisters any old PWA service worker.

## Deploy
Cloudflare Pages project -> Settings -> Build:
- Build command: *(blank)*
- Build output directory: `paused`
- Root directory: repo root

Or upload the `paused/` folder directly (Workers & Pages -> Upload assets).
If your project builds from this repo, set the output directory back to `frontend/dist`
(and build command to `cd frontend && npm ci && npm run build`) to resume.
