#define _GNU_SOURCE

#include <errno.h>
#include <grp.h>
#include <pwd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

static const char *const worker_user = "redless";
static const char *const worker_binary = "/opt/aggregare/venvs/redless/bin/redless-machine";

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;

    struct passwd *account = getpwnam(worker_user);
    if (account == NULL) {
        fprintf(stderr, "redless-machine: account %s is unavailable\n", worker_user);
        return 126;
    }
    if (initgroups(worker_user, account->pw_gid) != 0 || setgid(account->pw_gid) != 0 ||
        setuid(account->pw_uid) != 0) {
        fprintf(stderr, "redless-machine: cannot drop privileges: %s\n", strerror(errno));
        return 126;
    }
    clearenv();
    if (setenv("HOME", account->pw_dir, 1) != 0 ||
        setenv("MSWEA_CONFIG_DIR", "/etc/redless", 1) != 0 ||
        setenv("PATH", "/usr/local/bin:/usr/bin:/bin", 1) != 0) {
        fprintf(stderr, "redless-machine: cannot configure worker environment\n");
        return 126;
    }
    execl(worker_binary, worker_binary, (char *)NULL);
    fprintf(stderr, "redless-machine: cannot execute worker: %s\n", strerror(errno));
    return 126;
}
