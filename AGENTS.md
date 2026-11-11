Please provide a good commit message based on the task completed upon completion.

## Deployment architecture

`install.sh` is the product deployment entrypoint. It must perform the complete
installation and upgrade locally on the target host, including invoking the
bundled Ansible roles with a local connection. Do not require an external
Ansible controller, controller-side SSH orchestration, or a separate Ansible
server for normal Aggregare deployment and verification.

## GitHub and push workflow

- You may make and commit authorized changes locally.
- Do not push, force-push, merge pull requests, update remote branches, or otherwise write to GitHub on my behalf. Leave pushing and merging to me unless I explicitly authorize a specific remote action in the current conversation.
- You may use GitHub integrations to read Issues in this repository when useful.
- Do not use other GitHub integrations for this repository unless I explicitly ask you to. Prefer local Git and repository tools.
