# Phase 2.5 live verification record

## 2026-10-13: issue #14 identity DNS and TLS contract

| Check | Result | Evidence |
| --- | --- | --- |
| Deployment-neutral DNS/TLS and Kanidm stability contract | Passed | Reviewed `docs/contracts/phase-2.5.md`; documents per-environment configuration, LAN and registered-domain options, private/public certificate trust, issuer checks, migration risks, and #11/#12 ownership. |
| Site-specific names in reusable logic | Passed | Source review found no site-specific namespace dependency in reusable application logic, role defaults, or install wiring; inventory names are replaceable documentation fixtures. |
| Existing endpoint configuration checks | Passed | Reviewed `ansible/playbooks/habitsync.yml`; pre-tasks require HTTPS base and issuer URLs, no trailing slash, a valid provider slug, and a nonempty client ID before application deployment. |
| Live DNS, certificate, discovery, or identity migration | Not run | This change is contract and source verification only; no environment or identity provider was deployed or modified. |

This record contains outcomes only. It intentionally excludes private IP
addresses, credentials, client IDs, Vault contents, and CA private material.
All live changes in this record target a development environment; production and router
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
| Browser trust and Pocket ID administrator/passkey | Abandoned | Not completed before the Pocket ID integration was removed; no further setup is planned under issue #13. |
| HabitSync deployment and real OIDC login/recovery through Pocket ID | Abandoned | Not completed; the provider-specific client registration was removed with the integration. A later provider evaluation requires a separate decision and work item. |
| Memos and Vikunja OIDC/login/recovery | Abandoned | Not started; these were follow-up plans contingent on the retired provider evaluation. |

The external dev inventory was reported to contain a generated HabitSync
local recovery credential in a mode-600 file. It had not been exercised when
this record was written. Its username and password must not be copied into
this record or the repository. Source cleanup does not edit that inventory.

These provider and browser follow-ups were abandoned when the integration was
removed. They are not outstanding tasks for issue #13. The earlier health and
discovery results above remain historical results and do not establish a real
user login.
