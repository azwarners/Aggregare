# Phase 2.5 HTTPS and OIDC test on a development environment

This guide covers temporary LAN-only HTTPS for testing an application with an
OIDC provider selected outside Aggregare. It uses temporary host-file entries
and Caddy's internal CA. It does not configure permanent DNS, VPN DNS, router
access, or Internet access; those belong to Phase 2.75.

The checked-in dev and prod inventories use the reserved `example.invalid`
namespace as documentation fixtures, not as Aggregare's required domain or a
live site configuration. Replace the namespace and all hostnames independently
in each protected environment inventory before use. See the [identity DNS and
TLS contract](../contracts/phase-2.5.md#identity-dns-and-tls-boundary) for
domain choices, trust models, and identity-domain stability requirements.

The provider is not installed or provisioned by Aggregare. Configure an issuer
URL and client ID in the protected external inventory, and store any required
confidential-client secret in that environment's encrypted Vault file. The
application contract remains provider-neutral.

## Test boundary and stored state

- Run these steps against the dev inventory and `--limit dev-host` only.
- Keep the inventory, encrypted Vault file, Vault password, Caddy CA state,
  provider data, and app data outside the source checkout and separate from
  production.
- Caddy CA state is under `/var/lib/aggregare/phase-2.5/caddy-data`. Its
  private key stays on the development host. The exported `caddy-root.crt` is public
  and safe to distribute to test clients.
- The temporary HTTPS edge binds only the dev host's private LAN address on
  TCP 443. It installs no HTTP listener, changes no router settings, and must
  not be given a router port-forward rule.
- Never copy dev state or credentials to prod.

## 1. Prepare the external dev inventory

Copy the example to a protected directory outside the repository, replace its
documentation-only address with the dev host's private address and subnet, and
create the encrypted Vault file:

```sh
cp -a ansible/inventory-examples/dev /secure/config/dev-environment
chmod -R go-rwx /secure/config/dev-environment
ansible-vault create /secure/config/dev-environment/group_vars/aggregare/vault.yml
chmod 600 /secure/config/dev-environment/group_vars/aggregare/vault.yml
```

Use unique, persistent dev values for application secrets. Keep the encrypted
Vault file and its password outside the repository. Set the OIDC issuer and
client ID in `group_vars/aggregare/main.yml` after registering the client with
your selected provider.

## 2. Install the temporary HTTPS edge

From the Aggregare checkout root, run:

```sh
cd ansible
ansible-playbook -i /secure/config/dev-environment/hosts.ini \
  --limit dev-host playbooks/phase25-dev-edge.yml --ask-vault-pass
```

The playbook adds test names to the server's hosts file and sets up Caddy with
an internal CA. It also adds the CA to the dev host's OS and Java trust stores
so app containers can reach an HTTPS issuer. If UFW is already active, it
allows TCP 443 from the configured private subnet. It does not enable UFW.

## 3. Add temporary names and trust the CA on the browser device

On Linux, copy the generated hosts entries and public root certificate from
the dev host. Append the entries to `/etc/hosts`, then trust the public root:

```sh
REMOTE_USER='<remote-user>'
DEV_HOST='<dev-host-or-address>'
scp "${REMOTE_USER}@${DEV_HOST}:/var/lib/aggregare/phase-2.5/hosts.entries" ./dev-hosts.entries
sudo sh -c 'cat ./dev-hosts.entries >> /etc/hosts'
scp "${REMOTE_USER}@${DEV_HOST}:/var/lib/aggregare/phase-2.5/caddy-root.crt" ./dev-caddy-root.crt
sudo install -m 0644 dev-caddy-root.crt /usr/local/share/ca-certificates/dev-caddy-root.crt
sudo update-ca-certificates
```

Restart the browser after trusting the certificate. Firefox may use its own
certificate store. Do not copy or export Caddy's private CA key. Remove the
temporary entries and test root certificate when testing is complete.

## 4. Configure and test an application

Set the app's HTTPS base URL, OIDC issuer URL, provider slug, scopes, and client
ID in the external inventory. Put a confidential client secret in the
encrypted Vault file only when required by that app's supported flow. Keep each
application's local recovery path enabled.

For HabitSync, apply the playbook with the dev inventory:

```sh
ansible-playbook -i /secure/config/dev-environment/hosts.ini \
  --limit dev-host playbooks/habitsync.yml \
  --ask-become-pass --ask-vault-pass
```

Verify the provider redirect, callback, sign-in, sign-out and subsequent
sign-in, local recovery, and session persistence after restart. Also verify
that the application container trusts the issuer's certificate. Keep recovery
credentials private; never send them in chat or commit them.

Repeat equivalent local and provider login checks for Memos and Vikunja where
configured. Do not disable local recovery after a successful federated login.

## Phase 2.75 requirements

Phase 2.75 must provide managed private DNS for LAN and VPN clients, define
resolver distribution and outage behavior, and manage reverse-proxy and
certificate lifecycle. It must establish a safe CA trust distribution path.
Phase 2.5 depends on stable HTTPS URLs and trusted issuer connections, not on a
specific OIDC provider, Caddy, or DNS product.
