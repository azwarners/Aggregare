# Phase 2.5 live verification record

This record contains outcomes only. It intentionally excludes private IP
addresses, credentials, client IDs, Vault contents, and CA private material.
All live changes in this record target aggregare-dev; production and router
configuration were not changed.

## 2026-10-11: temporary HTTPS and retired Pocket ID evaluation

This records a historical dev-only evaluation. Issue #13 removed the Pocket ID
installer, catalog entry, API client provisioner, and source inventory wiring.
The source cleanup does not stop a previously deployed service, revoke an
existing `STATIC_API_KEY`, or remove its data. Treat those as separate host and
credential operations; preserve user data unless explicitly approved.

| Check | Result | Evidence |
| --- | --- | --- |
| Dev-only inventory and isolated Vault | Passed | External config under the dev user's protected config directory; values are outside the source checkout. |
| Caddy test edge | Passed | Caddy 2.11.7 is active and bound only to the dev server's private address on TCP 443. No TCP 80 listener was present. |
| Caddy internal CA persistence/export | Passed | Root certificate exported; CA state remains in the dev data directory. No CA private key entered the repo. |
| Pocket ID 2.18.0 service | Passed | Quadlet service is active; container health endpoint returned HTTP 204. |
| OIDC discovery over HTTPS | Passed | The discovered issuer, authorization, token, and user-info endpoints all use the expected dev HTTPS host. Certificate validation succeeded using the exported dev root. |
| Router / production changes | None | No router or production configuration was touched. UFW was inactive, so no firewall rule was added. |
| Browser trust and Pocket ID administrator/passkey | Pending | Requires setup on Nick's browser device. |
| HabitSync deployment and real OIDC login/recovery | Pending | Waiting for Pocket ID's HabitSync public client ID and browser-side HTTPS trust. |
| Memos and Vikunja OIDC/login/recovery | Pending | Begin only after HabitSync's real login and local recovery checks pass. |

The external dev inventory also contains a generated HabitSync local recovery
credential in a mode-600 file. It has not yet been exercised. Its username and
password must not be copied into this record or the repository.

Phase 2.5 remains incomplete until each supported app completes a real browser
login and local recovery test, including logout/relogin and safe reapply.
