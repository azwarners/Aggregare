# Redless GitHub App setup

This is an operator-assisted setup for authenticated Redless issue reads. It uses a GitHub App installation, never a personal access token. The installed helper only provides allowlisted, read-only calls to the `redless` account; branch pushes, issue updates, comments, and pull requests remain a separate runner-owned publication phase.

## Create and install the app

In GitHub, create a GitHub App owned by the organization or account that owns the selected repositories. Disable webhooks unless another use requires them. Set repository permissions to **Issues: Read & write**, **Contents: Read & write**, and **Pull requests: Read & write**; **Metadata: Read** is mandatory and is granted automatically. Those write permissions are required only by a future controlled publication runner, not by the helper delivered here. The App cannot act outside repositories where its installation is selected, and it cannot bypass branch protection or organization policy.

Choose one repository policy for the local helper:

- **Explicit**: install the App on selected repositories and list each allowed repository in the local configuration.
- **Installation**: if the App is intentionally installed on every repository for an account, configure one allowed owner. The helper discovers only repositories GitHub reports for that installation and rejects every other owner. Account-wide installation does not authorize any issue for execution; normal queue and approval gates still apply.

Download the private key directly to the host over an administrator-controlled channel. Do not paste it into chat, a model prompt, inventory, a shell history, source control, or a workspace.

On the Aggregare host, as an administrator, create root-only files (replace the sample IDs and repository names):

```sh
sudo install -d -o root -g root -m 0700 /etc/aggregare/secrets
sudo install -o root -g root -m 0600 /secure-transfer/redless-github-app.pem /etc/aggregare/secrets/redless-github-app.pem
sudo sh -c 'umask 077; printf %s "{\"app_id\":12345,\"installation_id\":67890,\"allowed_repositories\":[\"OWNER/REPOSITORY\"]}" > /etc/aggregare/redless-github-app.json'
sudo chown root:root /etc/aggregare/redless-github-app.json
sudo chmod 0600 /etc/aggregare/redless-github-app.json
```

`installation_id` is the numeric installation ID from the GitHub App installation URL. The default explicit policy is a second fail-closed boundary: a repository must be both installed for the App and listed in this file. Do not use wildcard repository names.

For an intentional installation-wide policy, omit `allowed_repositories` and use an owner boundary instead:

```sh
sudo sh -c 'umask 077; printf %s "{\"app_id\":12345,\"installation_id\":67890,\"repository_policy\":\"installation\",\"allowed_owner\":\"OWNER\"}" > /etc/aggregare/redless-github-app.json'
sudo chown root:root /etc/aggregare/redless-github-app.json
sudo chmod 0600 /etc/aggregare/redless-github-app.json
```

This mode discovers a newly created repository only after GitHub has granted it to the App installation. It does not trust an account-wide name pattern, accept a cross-owner repository, or make App permissions equivalent to execution approval.

Reapply Aggregare so it installs the controlled wrapper, then test without exposing a credential:

```sh
sudo -u redless -- sudo -n /usr/local/bin/redless-github-app doctor
sudo -u redless -- redless-issue-queue --github-app --owner OWNER
```

The doctor output lists only configured/installed repositories and supported operations. It never prints the private key, JWT, installation token, or token expiry. The helper mints a fresh installation token for each request, keeps it only in root-process memory, and sends it through HTTPS request headers rather than command-line arguments, Git remotes, logs, workspace files, or persistent Git configuration. Revoking the installation, removing a repository, or a permission failure causes an error and no anonymous fallback.

The installed `/usr/local/bin/redless-github-app-git` helper is intentionally unavailable through `sudo` to `redless`. A future root-owned publication runner can use it only as a transient Git credential helper, for example `git -c credential.useHttpPath=true -c credential.helper='!/usr/local/bin/redless-github-app-git' push`; `credential.useHttpPath=true` is required so Git supplies `OWNER/REPOSITORY.git` for the helper's allowlist check. It refuses terminal output and non-root invocation. Do not add it to Git's global/system configuration or invoke it directly. This separates token-backed Git authentication from model-visible workspaces while allowing fresh-token pushes when the publication state machine is added.

For an isolated permission check, use a disposable repository and draft pull request policy before enabling any future publication runner. Confirm branch protection separately: GitHub App `Contents` and `Pull requests` permissions do not grant an exception to required reviews, signed commits, checks, or rulesets. Commit/PR bot attribution and token-backed Git credential handling are intentionally deferred with the publication state machine.
