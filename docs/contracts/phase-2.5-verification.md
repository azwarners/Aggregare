# Phase 2.5 live verification record

## 2026-10-23: issue #17 fresh-deployment preflight correction

| Check | Result | Evidence |
| --- | --- | --- |
| Fresh-install ordering review | Defect confirmed | The identity playbook previously required a successful HTTPS/TLS handshake before installing Kanidm, so a clean host without the service endpoint failed before installation. |
| Pre-deployment validation | Passed | Shared preflight now supports DNS-only checks; the playbook also validates certificate hostname/expiry and certificate/private-key pairing before persistent changes. |
| Saved endpoint reapplication | Passed | The playbook reuses the persisted domain and origin when replacement variables are omitted and only writes identity config when it is absent or needs schema migration. |
| Focused regression tests | Passed | `python3 -m unittest tests.test_identity_preflight tests.test_identity_config -v` (23 tests), including DNS-only without HTTPS and no mutation for DNS or certificate/key failures. |
| Live Kanidm deployment | Not run | The dev host still needs an administrator-selected domain/origin, working DNS, and matching certificate/key; no site values were guessed. |

No DNS, certificate, proxy/router/firewall, or production settings were changed.

## 2026-10-23: issue #17 pinned Kanidm deployment

| Check | Result | Evidence |
| --- | --- | --- |
| Automated tests on development host | Passed | `python3 -m unittest discover -s tests -v` (29 tests). Includes origin-only DNS/TLS preflight behavior, endpoint persistence schema, immutable established domains, and no mutation on failed preflight. |
| Ansible syntax and saved-provider reapplication on development host | Passed | Identity playbook syntax check passed. Reapplied the host's saved `none` choice: 7 tasks ok, 0 changed, 19 skipped; Kanidm tasks were skipped. |
| Local validation | Passed | `bash -n install.sh`, Python compilation of both identity tools, Ansible playbook syntax check, and `git diff --check`. |
| Fresh Kanidm service deployment and health check | Not run | The dev host has no selected Kanidm FQDN/origin or Kanidm TLS material. No hostname or certificate values were guessed. |
| DNS, certificate, proxy/router/firewall changes | None | These remain administrator-managed prerequisites. No production or site network configuration was changed. |

This record contains outcomes only and excludes credentials, private IP
addresses, certificate private keys, and CA private material.

## 2026-10-13: issue #15 identity DNS and TLS preflight hardening

| Check | Result | Evidence |
| --- | --- | --- |
| Malformed URL and invalid port handling | Passed | CLI rejects malformed authority, nonnumeric/out-of-range/zero ports, whitespace, and embedded credentials with actionable argument errors and no traceback. |
| Container execution reporting | Passed | Fixtures cover successful JSON output, missing Python 3, Podman nonzero exit, missing Podman executable, and execution timeout. |
| OIDC advertised endpoint behavior | Passed | Discovery endpoint fields are checked for HTTPS scheme only; the individual advertised endpoints are not contacted. |
| Automated verification | Passed | `python3 -m unittest discover -s tests -v` (19 tests), CLI `--help`, `git diff --check`, and Ansible playbook syntax check. |
| Live identity DNS/TLS check | Not run | No live endpoint was selected for this focused hardening pass. No provider was deployed and no DNS, certificate, firewall, or router settings were changed. |

This record contains outcomes only and excludes credentials, private IP
addresses, and CA private material.

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
