# Aggregare deployment report

The installer generates a current report at `/var/lib/aggregare/deployment-report.md` after application deployment checks. It uses the application catalog, saved status records, and systemd observations; rerunning the installer refreshes it even when healthy applications are skipped. The report includes generated first-login usernames and passwords for HabitSync and Apmatia, plus login and first-use instructions for other applications. After changing the HabitSync password, the report no longer includes that password.

The report contains sensitive credentials. The installer sets it to mode `0600` and makes the installing administrator its owner so `aggregare report` works for that account. Keep the report and any backups protected. `aggregare summary` shows service status and endpoints without displaying login credentials.

The HabitSync section includes the password-change command. From your home directory, run `cd ~/Aggregare && ./tools/aggregare-habitsync-password`; it prompts twice without echoing the password, applies the new login while preserving the installer's saved LAN access and base URL, removes the superseded initial login handoff, and refreshes this report without recording the new password.

Read it from any working directory with:

```sh
aggregare report
```

The installer also prints a concise application summary from the same data. Run `aggregare summary` to print that summary again.

During interactive installation, Aggregare also creates `~/Aggregare-Report.md` if that name is available in the invoking administrator's home directory. Both entry points refer to the same authoritative report. Direct Ansible users can run `ansible-playbook -i inventory.ini playbooks/report.yml` to refresh the report. Configured endpoints and local service observations do not establish remote reachability. Unknown or unavailable deployment facts are labeled accordingly.

Repository test results and the outstanding disposable VM verification are recorded in [`../contracts/deployment-report-verification.md`](../contracts/deployment-report-verification.md).
