#define _POSIX_C_SOURCE 200809L
#include "nxui_services.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static void fixture(const char *path, const char *lines) {
    FILE *file = fopen(path, "w"); assert(file);
    fputs("  sl local_address rem_address st\n", file); fputs(lines, file); assert(!fclose(file));
}
int main(void) {
    char dir[] = "/tmp/nxui-services-XXXXXX", tcp[512], tcp6[512], label[192];
    struct nx_services a, b;
    assert(mkdtemp(dir));
    snprintf(tcp, sizeof tcp, "%s/tcp", dir); snprintf(tcp6, sizeof tcp6, "%s/tcp6", dir);
    nx_services_read(&a, dir); assert(!a.known);
    fixture(tcp, "0: 00000000:0017 00000000:0000 01\n");
    nx_services_read(&a, dir); assert(a.known && !a.telnet && !a.ftp);
    fixture(tcp, "0: 00000000:0017 00000000:0000 0A\n");
    fixture(tcp6, "1: 00000000000000000000000000000000:0015 00000000000000000000000000000000:0000 0A\n");
    nx_services_read(&a, dir); assert(a.telnet && a.ftp);
    fixture(tcp6, ""); nx_services_read(&b, dir);
    assert(b.known && b.telnet && !b.ftp && !nx_services_equal(&a, &b));
    nx_services_label(&b, label, sizeof label); assert(strstr(label, "Telnet:开 FTP:关"));
    unlink(tcp); unlink(tcp6); rmdir(dir);
    puts("PASS service state: listener-only, IPv4/IPv6, partial and unreadable status");
    return 0;
}
