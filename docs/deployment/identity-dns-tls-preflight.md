# Identity DNS and TLS preflight

`tools/aggregare-identity-preflight` checks that a configured identity HTTPS
origin and OIDC issuer are usable before account enrollment or client setup.
It makes no DNS, certificate, firewall, or router changes. It does not accept
or print credentials.

Provide the origin and exact issuer URL from the protected environment
inventory. An issuer may include a provider-specific path. For a private CA,
provide its public PEM root certificate with `--cafile`; never provide a CA
private key.

```sh
./tools/aggregare-identity-preflight \
  --origin https://identity.example.test \
  --issuer https://identity.example.test/oauth2 \
  --cafile /secure/config/dev-root-ca.pem
```

The report checks DNS and certificate chain, validity dates, and hostname
coverage for both URL hosts. It also fetches the OIDC discovery document,
requires its `issuer` to exactly match the configured issuer, and rejects
discovery metadata that advertises HTTP endpoints. A nonzero exit status means
at least one check failed. Use `--format json` for the versioned machine-readable
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

Set these non-secret values in the selected environment inventory. The CA path,
when used, must be present on the managed host and at the same path in checked
containers.

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
