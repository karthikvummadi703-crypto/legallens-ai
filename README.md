# legallens-ai

Submission project for the Prompt Wars exclusive challenge.

**LegalLens AI** is a full-stack legal document intelligence assistant. Upload a
contract, NDA, lease or employment agreement and get clause-level analysis,
risk/obligation/deadline extraction, a "Before You Sign" checklist, and
instant grounded Q&A that cites exact pages and sections.

- Backend: Python (FastAPI) · Gemini 2.5 for analysis · RAG over an embedded vector store
- Frontend: React + Vite + TypeScript · Firebase Authentication (Google sign-in)
- Deployment: Vercel serverless (Python API + static SPA, same-origin or CORS)
- Cloud persistence: Firebase Realtime Database — works on the free **Spark** plan, no billing account needed

## Features

- PDF / text document upload with automatic clause extraction and page-level citation
- Full document analysis: executive summary, important clauses, risks, obligations, payments, key dates, termination & renewal
- "Before You Sign" interactive checklist built from the analysis
- Multi-turn chat grounded in your documents (RAG) plus general legal Q&A
- Persistent chat history and per-user document isolation
- Developer mode for local testing without Firebase credentials

## Repository structure

```
legallens-ai/
├── app/                      # FastAPI server (imported as ``backend/app`` below)
├── backend/
│   ├── app/                  # Backend source (main entrypoint, routes, services)
│   └── .env.example          # Backend environment template
├── scripts/assemble_public.py# Vercel build helper: dist/ -> public/
├── src/                      # React frontend (Vite + TS)
├── main.py                   # Vercel Python entrypoint (re-exports the backend app)
├── pyproject.toml            # Python deps + [tool.vercel] config (experimental Python)
└── vercel.json               # Vercel function config (maxDuration)
```

## Local development

Backend (requires Python 3.10+):

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env                             # fill in GEMINI_API_KEY
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
npm install
npm run dev       # http://localhost:3000
```

Local mode uses on-disk `backend/data/db.json`, `backend/uploads/`, and a
bundled in-process vector index — nothing is sent to Firebase. With
`AUTH_DEV_MODE=auto` (default) and no service-account file, the API accepts a
fixed dev user so the app runs out of the box.

## Deploying to Vercel (free)

1. Push this repo to GitHub and import it into Vercel (root directory `/`).
   Vercel detects the Python entrypoint via `pyproject.toml` and runs the
   build (`npm ci && npm run build` + copy to `public/`); the SPA and `/api`
   are served from the same Vercel function.

2. Enable Firebase **Realtime Database** in your project (Firebase console →
   Build → Realtime Database → Create). On the free **Spark** plan there is
   **no Cloud Storage bucket needed** — documents persist as RTDB nodes.

3. Grab a service-account key: Firebase console → Project settings →
   Service accounts → **Generate new private key** (`key.json`).

4. Set these environment variables in Vercel (Project → Settings →
   Environment Variables):

   | Variable | Value |
   |---|---|
   | `STORAGE_BACKEND` | `cloud` |
   | `AUTH_DEV_MODE` | `off` |
   | `FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT` | full JSON contents of `key.json` |
   | `FIREBASE_DATABASE_URL` | `https://<project>-default-rtdb.firebaseio.com` |
   | `GEMINI_API_KEY` (+ `_2`, `_3`) | Gemini API keys (optional but recommended) |
   | `VITE_FIREBASE_API_KEY` / `AUTH_DOMAIN` / `PROJECT_ID` / `APP_ID` | public Firebase web-app config (console → Project settings → Your apps) |
   | `FRONTEND_ORIGIN` | `https://<your-app>.vercel.app` (optional) |

   Leave `VITE_API_BASE_URL` unset — the SPA calls the same-origin `/api`.

5. Deploy. On Vercel the `VERCEL` env var engages cloud mode automatically:
   documents, analyses and chat history live in RTDB (`db/documents`,
   `db/analyses`, `db/conversations`), document files in `db/doc_files`
   (base64 nodes), and vectors in `db/vectors`.

## Persistence modes

- **local** (default): `backend/data/db.json` + `uploads/` + embedded vector DB.
- **cloud**: active when `STORAGE_BACKEND=cloud` or the `VERCEL` env var exists.
  Entirely Firebase RTDB-backed, dev fallback is disabled, and the upload
  pipeline extracts the document from a `/tmp` copy (Vercel FS is read-only).

## Notes

- Gemini keys are rotated automatically and the backend falls back to a
  rule-based offline answer when quotas are exhausted, so the app stays
  responsive at the free-tier limits.