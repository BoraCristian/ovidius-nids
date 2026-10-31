# Security Policy

Ovidius NIDS is an academic project (my bachelor's thesis) maintained by one person. It is built
to run locally as a demo and teaching tool, not as a hardened production service. That said, I
take security reports seriously and appreciate responsible disclosure.

## Supported versions

| Version                       | Supported |
|-------------------------------|-----------|
| Latest release / `main` branch | ✅        |
| Older commits                 | ❌        |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub instead:
**[Security → Report a vulnerability](https://github.com/BoraCristian/ovidius-nids/security/advisories/new)**

Helpful details to include:

- what the issue is and where it is (file, endpoint or page);
- steps to reproduce, or a minimal proof of concept;
- the impact you expect (e.g. authentication bypass, path traversal, code execution);
- the commit or release you tested.

I aim to acknowledge reports within 7 days and will keep you updated while I work on a fix.
Once it's resolved, I'm happy to credit you in the advisory if you'd like.

## Scope

**In scope:** the backend API and WebSocket endpoints, authentication and token handling, the
signature and ML detection engines, forensic capture downloads, the React frontend, the
launcher scripts (`run.py`, `run.bat`, `run.sh`) and the CI workflow.

**Out of scope** (known and documented behaviour):

- The demo account `admin` / `admin` and its pre-filled login form while `DEBUG=true`. These
  are intentional for local demos; the README explains how to change them.
- Problems that require an attacker to already control `backend/.env`, the local database or
  the machine running the app.
- The built-in traffic simulator and Attack Console generating attack-like traffic. That is
  their purpose.
- Advisories that only affect frontend build tooling (Vite, Tailwind) and never ship to the
  browser.
- Live packet capture needing raw-socket / administrator privileges, which is inherent to
  packet sniffing.

## Security measures already in place

- Both servers listen on localhost only by default.
- JWT signing key generated randomly per install; passwords hashed with bcrypt.
- Model files are named server-side, so user input never reaches a filesystem path.
- CodeQL code scanning and the full test suite run on every push; Dependabot watches the
  dependencies for new advisories.
