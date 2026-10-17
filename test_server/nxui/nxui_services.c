#define _POSIX_C_SOURCE 200809L
#include "nxui_services.h"
#include <arpa/inet.h>
#include <ifaddrs.h>
#include <stdio.h>
#include <string.h>

static int listeners(const char *path, struct nx_services *state) {
    char line[512], address[96], status[8], *port;
    FILE *file = fopen(path, "r");
    if (!file) return 0;
    while (fgets(line, sizeof line, file)) {
        if (sscanf(line, "%*u: %95s %*s %7s", address, status) != 2 || strcmp(status, "0A")) continue;
        port = strrchr(address, ':');
        if (!port) continue;
        if (!strcmp(port, ":0017")) state->telnet = 1;
        if (!strcmp(port, ":0015")) state->ftp = 1;
    }
    if (ferror(file)) { fclose(file); return 0; }
    fclose(file); return 1;
}
void nx_services_read(struct nx_services *state, const char *net_dir) {
    char path[1024]; struct ifaddrs *all, *item; int a, b;
    memset(state, 0, sizeof *state);
    snprintf(path, sizeof path, "%s/tcp", net_dir); a = listeners(path, state);
    snprintf(path, sizeof path, "%s/tcp6", net_dir); b = listeners(path, state);
    state->known = a || b;
    if (getifaddrs(&all) == 0) {
        for (item = all; item; item = item->ifa_next) {
            if (item->ifa_addr && item->ifa_addr->sa_family == AF_INET && !strcmp(item->ifa_name, "mlan0")) {
                struct sockaddr_in *address = (struct sockaddr_in*)item->ifa_addr;
                inet_ntop(AF_INET, &address->sin_addr, state->ip, sizeof state->ip); break;
            }
        }
        freeifaddrs(all);
    }
}
int nx_services_equal(const struct nx_services *a, const struct nx_services *b) {
    return a->known == b->known && a->telnet == b->telnet && a->ftp == b->ftp && !strcmp(a->ip, b->ip);
}
void nx_services_label(const struct nx_services *state, char *text, size_t size) {
    snprintf(text, size, "%s  [Telnet:%s FTP:%s]", *state->ip ? state->ip : "WiFi未开",
        state->known ? (state->telnet ? "开" : "关") : "?",
        state->known ? (state->ftp ? "开" : "关") : "?");
}
