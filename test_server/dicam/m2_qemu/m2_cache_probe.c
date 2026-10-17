/* Offline gettext cache probe. Run only against disposable fixture directories.
 * It renames an explicitly supplied fixture catalog, never mounts or edits rootfs.
 * Link with the camera's libc; this is not the camera App or a UI emulator.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <locale.h>
#include <libintl.h>
#include <gnu/libc-version.h>

static const char *domain = "di-camera-app";
static const char *keys[] = {
    "CAP_MENU_CUSTOM_MODE_1", "CAP_MENU_CUSTOM_MODE_2",
    "CAP_MENU_CUSTOM_MODE_3", "CAP_FN_PW"
};

static void query(const char *phase)
{
    unsigned i;
    for (i = 0; i < sizeof(keys) / sizeof(keys[0]); i++)
        printf("%s|%s|%s\n", phase, keys[i], dcgettext(NULL, keys[i], LC_MESSAGES));
}

static void replace_fixture(const char *staged, const char *directory)
{
    char destination[4096];
    int n = snprintf(destination, sizeof(destination),
                     "%s/zh_CN/LC_MESSAGES/di-camera-app.mo", directory);
    if (n < 0 || (size_t)n >= sizeof(destination) || rename(staged, destination)) {
        perror("replace fixture catalog");
        exit(3);
    }
}

int main(int argc, char **argv)
{
    char language[256];
    char *locale;
    if (argc != 5) {
        fprintf(stderr, "usage: m2_cache_probe warm|cold|fresh DIR_A DIR_B STAGED\n");
        return 2;
    }
    locale = setlocale(LC_ALL, "");
    if (!locale || strlen(locale) >= sizeof(language)) {
        fprintf(stderr, "locale unavailable or too long\n");
        return 2;
    }
    strcpy(language, locale);
    printf("# libc=%s locale=%s\n", gnu_get_libc_version(), language);
    if (!bindtextdomain(domain, argv[2]) || !textdomain(domain))
        return 2;

    if (!strcmp(argv[1], "cold")) {
        replace_fixture(argv[4], argv[2]);
        query("cold_first_lookup");
        return 0;
    }
    if (!strcmp(argv[1], "fresh")) {
        query("fresh_process");
        return 0;
    }
    if (strcmp(argv[1], "warm"))
        return 2;

    query("warm_before_replace");
    replace_fixture(argv[4], argv[2]);
    query("warm_after_replace");
    if (!textdomain(domain))
        return 2;
    query("same_textdomain");
    if (!setlocale(LC_MESSAGES, "C"))
        return 2;
    query("locale_C");
    if (!setlocale(LC_MESSAGES, language))
        return 2;
    query("locale_round_trip");
    if (!bindtextdomain(domain, argv[2]))
        return 2;
    query("same_directory");
    if (!bindtextdomain(domain, argv[3]))
        return 2;
    query("different_directory");
    return 0;
}
