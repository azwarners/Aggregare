# Identity DNS and TLS preflight

`tools/aggregare-identity-preflight` checks that a configured identity HTTPS
origin is usable. For a first Kanidm deployment, the HTTPS service does not
exist yet, so the deployment playbook uses its `--dns-only` mode before
installing Kanidm. It separately checks the supplied certificate hostname,
expiry, and matching private key before changing persistent state. After
starting Kanidm, the playbook checks the live HTTPS `/status` endpoint.
When a provider issuer already exists, the tool can also validate that issuer
and its discovery document.
It makes no DNS, certificate, firewall, or router changes. It does not accept
or print credentials.

Use `--dns-only` before deploying a new Kanidm service. It verifies that the
origin hostname resolves without requiring a running HTTPS endpoint. The
deployment still requires an administrator-selected origin and domain plus a
certificate chain and matching private key for that hostname. For a private
CA, provide its public PEM root certificate with `--cafile`; never provide a
CA private key. DNS-only mode does not attempt TLS or OIDC discovery.

Run the normal origin check after the service is available, or when checking
an existing endpoint. The origin-only mode does not attempt OIDC discovery
because application clients are not part of this deployment step.

```sh
./tools/aggregare-identity-preflight \
  --origin https://id.home.arpa \
  --cafile /secure/config/dev-root-ca.pem
```

The normal report checks DNS and certificate chain, validity dates, and
hostname coverage for the origin. With `--issuer`, it additionally requires the exact
discovery issuer and HTTPS endpoint schemes. A nonzero exit status means at
least one check failed. Use `--format json` for the versioned machine-readable
report.

The host is always checked. To include a relevant running Podman container,
repeat `--container` with its exact container name. The container needs Python 3
and the same CA trust path; when using `--cafile`, that path must exist inside
each selected container as well. Containers are never selected automatically.

```sh
./tools/aggregare-identity-preflight \
  --origin https://identity.example.test \
  --issuer https://identity.example.test/oauth2 \
  --container habitsync \
  --format json
```

The preflight performs network reads only. DNS resolution can vary by context,
so run it from the host and each service container that must reach the issuer.
It does not replace a browser login or application-specific trust test.

## Run through Ansible

For an existing issuer, set these non-secret values in the selected environment
inventory. The CA path, when used, must be present on the managed host and at
the same path in checked containers.

```yaml
identity_preflight_origin: https://identity.example.test
identity_preflight_issuer: https://identity.example.test/oauth2
identity_preflight_cafile: /etc/ssl/certs/site-root-ca.pem
identity_preflight_containers:
  - habitsync
```

Run the dedicated read-only playbook against only the intended host:

```sh
ansible-playbook -i /secure/config/dev-environment/hosts.ini \
  --limit dev-host playbooks/phase25-identity-preflight.yml
```

The playbook transfers and runs the same CLI on the selected host, then prints
its JSON report. It does not run the application roles or edit DNS, firewall,
router, or certificate configuration.
