# Phase 2.5: credentials, application onboarding, and sign-in

Related contract: [Phase 2 catalog and Ansible foundation](phase-2.md).

Phase 2.5 makes selected Aggregare-installed applications easier to configure
and use. It separates credential storage, account bootstrap, federated sign-on,
and authorization. A shared secret store does not create single sign-on, and
application credentials remain separate from Ubuntu administrator access.

Where an app supports OIDC/OAuth, its inputs are provider-neutral: issuer URL,
provider slug, scopes, app client ID, and (only for confidential clients) a
separately protected secret. The catalog describes callback paths, client
modes, PKCE, scopes, local recovery, and verification status. Selecting
`kanidm` deploys the identity service described below; application OIDC clients
remain future work. Apps without
federation need a documented, secure bootstrap path. Do not describe the app
set as SSO-enabled unless each app supports the configured flow.

The durable provider choice is `/etc/aggregare/identity.json`. Version 1
records `identity_provider` as `kanidm`, `external_oidc`, or `none`. Version 2
also stores the administrator-selected Kanidm `identity_domain` and
`identity_origin`. Both `install.sh` and direct Ansible use this same file, and
each host/environment has its own copy. Later installer runs reuse the saved
provider and endpoint. Established Kanidm domains and origins cannot be changed
in place; changing them after enrollment requires a planned migration.

Selecting `kanidm` deploys the pinned `docker.io/kanidm/server:1.11.2` image
as a Podman Quadlet using UID/GID 1000 and persistent data at
`/var/lib/aggregare/kanidm`. The administrator supplies a certificate chain
and matching private key. Aggregare does not create DNS records, issue
certificates, configure a reverse proxy, open firewall/router ports, or expose
the service. The configured HTTPS origin must already resolve and present a
trusted certificate before the service is applied; the site edge should route
that origin to the local listener on `127.0.0.1:8443`. DNS/TLS preflight runs
before persistent identity configuration or Kanidm data is changed. Safe
reapplication preserves the data directory and restarts the service only when
its definition, server configuration, or TLS files change.

For direct Ansible Kanidm setup, provide `aggregare_identity_provider=kanidm`,
`aggregare_identity_domain`, `aggregare_identity_origin`,
`aggregare_kanidm_tls_chain_source`, and `aggregare_kanidm_tls_key_source` in
protected variables, then run `ansible-playbook -i INVENTORY
playbooks/phase25-identity-config.yml --become -e @/secure/config/kanidm.json`.
A private CA bundle can be supplied with `identity_preflight_cafile`; it must
already be available at that path on the managed host. For `external_oidc` or
`none`, only the provider choice is required and no Kanidm-specific hostname or
TLS material is requested.

## Identity DNS and TLS boundary

Each deployment administrator chooses a stable DNS namespace and configures
its identity service name, issuer URL, and trusted HTTPS origin independently
for each environment. Aggregare does not own a domain or prescribe a suffix.
Keep dev and prod names, provider configuration, CA state, client IDs, and
secrets separate. The issuer URL is the provider's canonical OIDC issuer
(including any provider-specific path); the browser-facing identity origin is
the HTTPS origin users visit. They may share a hostname, but clients must use
the exact issuer advertised by the provider's discovery document. Configure
these values in protected environment inventory, not in reusable application
roles or installation wiring.

An administrator may use LAN-only names under `home.arpa` as specified by
[RFC 8375](https://www.rfc-editor.org/rfc/rfc8375), or a subdomain of a
registered domain they control. These are supported choices, not requirements.
`.net` is a public top-level domain, not a private LAN suffix; do not invent
names beneath it for private use. With a registered domain, split-horizon DNS
can return private addresses inside the LAN while the public DNS view remains
independent. Private DNS does not require services to be exposed to the public
Internet.

TLS trust has two supported patterns. A private CA can issue certificates for
LAN names, provided administrators securely distribute its public root to
every browser and service client that must validate those certificates and
protect the CA signing key. Alternatively, publicly trusted certificates can
be used for names under an administrator-controlled registered domain; DNS
validation (for example, ACME DNS-01) can issue certificates without opening
the service to inbound Internet traffic. DNS control and public certificate
issuance do not imply public service exposure. Certificate renewal and trust
distribution must be tested for every client runtime, including containers.

For Kanidm, choose the configured identity domain and origin before enrolling
users or registering clients, and preserve them as durable environment
configuration. Kanidm uses the domain and origin in security-sensitive
identity and WebAuthn contexts. Renaming after enrollment can invalidate
passkeys and OAuth tokens, require OIDC client reconfiguration, and lock users
out. Treat a rename as a planned identity migration: back up first, follow
Kanidm's domain-rename procedure, plan credential recovery/re-enrollment, and
update every relying party. Before deployment, validate that the configured
FQDN resolves from clients and service containers, the certificate covers the
configured HTTPS origin, each client trusts its issuer certificate, and the
provider's OIDC discovery document returns the exact configured issuer and
HTTPS endpoints. Do not enroll users or applications until those checks pass.
See Kanidm's guidance on [choosing a domain name](https://kanidm.github.io/kanidm/stable/choosing_a_domain_name.html)
and [renaming a domain](https://kanidm.github.io/kanidm/stable/domain_rename.html).

For the current Ansible integration, HabitSync's pre-task assertions reject
missing or non-HTTPS base and issuer URLs, trailing slashes, malformed provider
slugs, and empty client IDs before the application role runs. This is a
configuration sanity check, not proof of DNS resolution, certificate trust,
or discovery correctness; perform those network and TLS checks separately.
Use the [identity DNS and TLS preflight](../deployment/identity-dns-tls-preflight.md)
to check the configured origin and issuer from the host and explicitly selected
service containers before enrolling users or applications.

Ownership is split across work items: #11 validates the identity endpoint and
this contract; #12 handles general DNS resolver distribution and endpoint
policy. This contract does not deploy site DNS, select a site namespace, or
provision a provider. Example inventory values below and elsewhere in this
repository are documentation fixtures only and must be replaced for each
environment.

## Inspect login requirements

From the repository root, list catalogued login and first-run setup:

```sh
./tools/aggregare-auth
./tools/aggregare-auth memos grafana --format json
```

The JSON report is versioned (`schema_version: v1`). Applications without
evidence-backed authentication metadata are reported as `not-assessed`; that
does not mean they have no login. The report contains secret handles and setup
instructions only, never secret values.

## Server credential provider: Ansible Vault

Ansible Vault encrypts selected bootstrap credentials for Grafana and
Semaphore UI at rest. Ansible delivers them to root-owned mode `0600` files
under `/etc/aggregare/`; containers read them through Quadlet `EnvironmentFile`
references. Secrets are not written into the Quadlet, catalog, status record,
or normal task output. Vault is an encrypted file workflow, not a multi-user
vault or runtime secret service. Its master password must be supplied
interactively.

From `ansible/`, copy a safe example inventory outside the checkout. Keep
non-secret LAN addresses and application URLs in that environment's main
variables, and credentials in its encrypted Vault file. Never reuse signing
keys or application secrets between environments.

```sh
cp -a ansible/inventory-examples/dev /secure/config/dev-environment
chmod -R go-rwx /secure/config/dev-environment
ansible-vault create /secure/config/dev-environment/group_vars/aggregare/vault.yml
chmod 600 /secure/config/dev-environment/group_vars/aggregare/vault.yml
```

Example values:

```yaml
grafana_admin_password: "a unique Grafana password"
semaphore_admin_password: "a different Semaphore password"
habitsync_jwt_secret: "a unique value generated with openssl rand -base64 64"
```

Do not commit an unencrypted copy. Apply only the desired applications. For
production, use the separate `prod` example, its own address and private DNS
zone, and different Vault values. Read passwords with `ansible-vault view` from
a trusted terminal; avoid copying them into shell commands, chat, tickets, or
logs. Keep a protected recovery copy of the encrypted file and master
password. A host or VM snapshot can still capture decrypted service files and
application databases.

Changing an Ansible variable is not guaranteed to rotate an application
password: an app may preserve its account database and ignore initial-admin
settings after initialization. Change existing passwords through the app's
supported admin UI/API, then update Vault to match. Reapplying a playbook does
not prove an old credential was revoked.

## First-run account setup

The initial productivity set is HabitSync, Memos, and Vikunja. Memos and
Vikunja were already running on the development host. A temporary Caddy HTTPS edge is
available on that dev host for testing. Earlier Phase 2.5 work also deployed
Pocket ID 2.18.0 and exercised its health and discovery endpoints, but its
playbooks, catalog entry, inventory wiring, and provider-specific guide have
now been removed. Aggregare does not install or configure that provider.

The removed Pocket ID provisioning path supplied its admin-level
`STATIC_API_KEY` from an external Vault and used it to create a HabitSync OIDC
client. That API-key variable and client-provisioning playbook are obsolete and
are not part of the current contract. This repository cleanup does not modify
an external inventory, revoke a deployed key, stop a running provider, or
remove its data. Handle any existing dev instance and credential separately;
do not delete user data as part of this source change.

- **HabitSync**: upstream documents OIDC public clients using PKCE, multiple
  issuers, and optional approval for new users. Aggregare pins 0.19.3 and
  requires a user-facing HTTPS URL, generic OIDC issuer/client ID, stable JWT
  session secret, and local recovery login. There is no live sign-in result in
  this contract.
- **Memos**: on a fresh instance, the first user becomes host administrator.
  Memos supports OAuth2 identity providers and personal access tokens. Test
  local bootstrap and provider sign-in separately; keep registration/public
  access choices explicit. Save a PAT when first shown and revoke it in the UI
  when no longer needed.
- **Vikunja**: Vikunja supports OpenID Connect. Test local account bootstrap
  and provider sign-in separately, then test API token creation and revocation
  through its UI.

## Temporary HTTPS prerequisites

Phase 2.5 testing on a development host uses a dev-only Caddy internal CA,
persistent state under `/var/lib/aggregare/phase-2.5/`, and temporary
host-file records. Do not use this configuration on production.

Before a browser login test:

1. Add the dev test names and private LAN address to the **client device's**
   `/etc/hosts` (or platform equivalent). The edge playbook also adds those
   names to the dev server so apps can reach HTTPS endpoints inside containers.
2. Import the public Caddy root certificate into the client's trusted root CA
   store, then restart the browser. The certificate is public; the private CA
   key and persistent state stay on the development host and out of the repo.
3. Ensure app containers trust that CA. The dev setup mounts the system CA
   bundle into Go-based apps and Java's trust store into HabitSync.
4. Open services only over configured HTTPS names. Do not expose the temporary
   listener to the Internet or configure router port forwarding.

The public certificate is available at
`/var/lib/aggregare/phase-2.5/caddy-root.crt`. Treat a changed hostname or
recreated CA as a new test identity. See the [temporary HTTPS and OIDC
guide](../deployment/phase-2.5-https-oidc.md).

### Phase 2.75 integration requirements

Phase 2.75 must replace temporary host records with managed private DNS for
LAN and VPN clients, define resolver distribution and outage behavior, and
manage the reverse proxy's HTTPS listener, certificate lifecycle, and CA trust
distribution without opening Internet access by default. Phase 2.5 depends on
stable HTTPS URLs and trusted OIDC issuer URLs, not on a specific provider,
Caddy, or DNS product.

Grafana and Semaphore UI bootstrap local administrator accounts from distinct
Vault values on first initialization. Their catalog entries include login
names and supported token lifecycle steps.

## Initial live test set

The current Phase 2.5 live evaluation is limited to a development environment. Use the protected
external dev inventory; never use prod or the full `site.yml` for these checks.
Record first apply, health result, real browser login/recovery result, and
reapply behavior without recording secret values.

```sh
cd ansible
ansible-playbook -i /secure/config/dev-environment/hosts.ini --limit dev-host playbooks/habitsync.yml --ask-vault-pass
```

Repeat the playbook and expect no identity reset or account duplication. Keep
Memos password sign-in and Vikunja local authentication enabled. Never ask for
passwords or tokens in chat.

| Application | Initial test | Follow-up |
| --- | --- | --- |
| HabitSync | Register a public PKCE client with the chosen provider; verify first OIDC sign-in, callback, and local recovery on `0.19.3`. | Verify logout/session behavior, JWT session persistence after restart, safe reapply, and API token use/revocation. |
| Memos | Verify first-admin bootstrap and private access on the fresh instance. | Configure and test selected OIDC/OAuth login/logout; separately verify PAT use and revocation. |
| Vikunja | Verify local account bootstrap and password login. | Configure and test selected OIDC login/logout; separately verify API token use and revocation. |

Run UI and token checks only on a disposable target. Do not put test
passwords or tokens in the verification record. Record provider and app
versions, configuration outcome, login/logout outcome, reapply behavior, and
manual steps without secret values in the [Phase 2.5 verification
record](phase-2.5-verification.md).

## Boundaries and recovery

- There is no desktop Secret Service adapter or general systemd credential
  adapter. Root-owned env files are a limited server delivery mechanism and
  are not machine-bound encrypted credentials or isolation from host
  administrators.
- Catalog metadata distinguishes upstream app support from tested Aggregare
  configuration. Live provider and app sign-in remain unverified unless the
  verification record says otherwise.
- Back up application data and encrypted Vault material separately. VM
  snapshots may contain application credential databases and decrypted runtime
  files. Machine-bound encryption will need a separate host migration or
  restore procedure.
- Removing an application removes its Aggregare service and environment file
  but preserves application data. Account deletion, token revocation, and
  identity migration must use the application's supported interfaces.

The initial test selection prioritizes HabitSync, Memos, and Vikunja. Grafana
and Semaphore UI demonstrate separate Vault-backed credentials. Phase 2.5 aims
to remove repetitive setup where vendor-supported interfaces allow it; it does
not promise universal SSO or automatic account creation for unsupported apps.
