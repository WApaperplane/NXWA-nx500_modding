/* Development only: let an extracted Xvfb find an extracted xkbcomp.
 * No /usr/bin files are installed or replaced. Not linked into the camera UI.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>
__attribute__((constructor)) static void configure_xkb_path(void) {
    char **directory = (char **)dlsym(RTLD_DEFAULT, "XkbBinDirectory");
    char *path = getenv("NXUI_XKB_BINDIR");
    if (directory && path) *directory = path;
}
