# Deployment report verification

## Repository verification

- `python3 -m unittest discover -s tests` — passed, 33 tests.
- `bash -n install.sh tools/aggregare` — passed.
- `ansible-playbook -i ansible/inventory.ini.example ansible/playbooks/report.yml --syntax-check` — passed.
- `ansible-playbook -i ansible/inventory.ini.example ansible/playbooks/site.yml --syntax-check` — passed.
- `git diff --check` — passed.

## Disposable VM verification

Not run in this workspace. No local VM runtime is installed, and the checked-in dev inventory contains only the reserved documentation address `192.0.2.10` and a placeholder SSH user. No already-installed disposable VM target is configured here.

Before marking the issue fully verified, use an already-installed disposable Ubuntu Server VM to rerun the normal installer, confirm application data and service state remain untouched, confirm the report and administrator home shortcut are readable, run `aggregare report` from another working directory, and repeat the run to check for duplicate entries and stable report content apart from the generation timestamp.
