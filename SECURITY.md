# Security Policy — LegalLens AI

## Reporting
Do **not** open a public issue for security problems. Report vulnerabilities privately
by emailing the project maintainer (contact via the GitHub repository) — include the
endpoint, a minimal repro, and impact. Patches are prioritized.

## Auth model
- All document/analysis/chat APIs require a verified Firebase ID token (`AUTH_DEV_MODE`).
- Production deployments run in strict mode (`AUTH_DEV_MODE=off`): an unauthenticated or
  invalid request is rejected with `401` — the app **fails closed**. On serverless
  (Vercel) the unverified dev-user fallback is disabled even in `auto` mode so a
  credential misconfig can never leak one user's documents to another login.
- Email/password accounts must be email-verified; Google sign-ins are pre-verified.

## Data isolation
- Every document, analysis, conversation and vector is scoped by `user_id`; database
  readers re-filter by owner and **never** fall back across owned documents.

## Secrets
- Service-account key, Gemini keys and web-app keys live only in environment variables
  / local `.env` files. They are gitignored; the repository contains no credentials.
- `/api/health` and `/api/debug/persistence` report booleans/counts only — never keys.

## Transport & hardening
- Baseline headers set on every response: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, restrictive `Permissions-Policy`.
- Per-IP sliding-window rate limiting on non-health endpoints.
- Uploads are size-capped, sanitized to safe filenames, parsed without executing them,
  and served back only when they belong to the requesting user.

## Persistence
- Atomic local writes (`tmp` + `os.replace`) with corrupt-DB backup; Firebase RTDB
  writes are validated and read-back-checked in CI/diagnostics.

## Local dev
- `AUTH_DEV_MODE=auto` with no service account enables the fixed dev user — never enable
  that on a public deployment.