# Phase 2.5: credentials, application onboarding, and sign-in

Related contract: [Phase 2 catalog and Ansible foundation](phase-2.md).

Phase 2.5 makes selected Aggregare-installed applications easier to configure
and use. It separates credential storage, account bootstrap, federated sign-on,
and authorization. A shared secret store does not create single sign-on, and
application credentials remain separate from Ubuntu administrator access.

Where an app supports OIDC/OAuth, its inputs are provider-neutral: issuer URL,
provider slug, scopes, app client ID, and (only for confidential clients) a
separately protected secret. The catalog describes callback paths, client
modes, PKCE, scopes, local recovery, and verification status. No identity
provider is currently installed or provisioned by Aggregare. Apps without
federation need a documented, secure bootstrap path. Do not describe the app
set as SSO-enabled unless each app supports the configured flow.

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
cp -a ansible/inventory-examples/dev /secure/config/aggregare-dev
chmod -R go-rwx /secure/config/aggregare-dev
ansible-vault create /secure/config/aggregare-dev/group_vars/aggregare/vault.yml
chmod 600 /secure/config/aggregare-dev/group_vars/aggregare/vault.yml
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
Vikunja were already running on aggregare-dev. A temporary Caddy HTTPS edge is
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

Phase 2.5 testing on aggregare-dev uses a dev-only Caddy internal CA,
persistent state under `/var/lib/aggregare/phase-2.5/`, and temporary
host-file records. Do not use this configuration on production.

Before a browser login test:

1. Add the dev test names and private LAN address to the **client device's**
   `/etc/hosts` (or platform equivalent). The edge playbook also adds those
   names to the dev server so apps can reach HTTPS endpoints inside containers.
2. Import the public Caddy root certificate into the client's trusted root CA
   store, then restart the browser. The certificate is public; the private CA
   key and persistent state stay on aggregare-dev and out of the repo.
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

The current Phase 2.5 live evaluation is aggregare-dev only. Use the protected
external dev inventory; never use prod or the full `site.yml` for these checks.
Record first apply, health result, real browser login/recovery result, and
reapply behavior without recording secret values.

```sh
cd ansible
ansible-playbook -i ~/.config/aggregare/phase25-dev/hosts.ini --limit aggregare-dev playbooks/habitsync.yml --vault-password-file ~/.config/aggregare/phase25-dev/vault-password
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
