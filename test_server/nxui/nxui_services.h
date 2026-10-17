#ifndef NXUI_SERVICES_H
#define NXUI_SERVICES_H
#include <stddef.h>
struct nx_services { int known, telnet, ftp; char ip[32]; };
void nx_services_read(struct nx_services *, const char *net_dir);
int nx_services_equal(const struct nx_services *, const struct nx_services *);
void nx_services_label(const struct nx_services *, char *, size_t);
#endif
