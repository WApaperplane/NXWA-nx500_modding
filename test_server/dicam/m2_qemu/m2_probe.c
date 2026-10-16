/*
 * m2_probe.c — M2 配方名 locale 探针（相机 ABI：glibc 2.13 / EABI5 softfp）
 *
 * 目的（U5 上机前的 VM 预演核心）：
 *   在 rootfs-112 chroot（qemu-arm-static）里用**相机自己的 glibc 2.13** 调 gettext，
 *   验证「官方 .mo → 自定义 1 / 样机 .mo → Portra 400」。
 *
 * 真机链路参照（UI_R1_SUPPLEMENT §10）：
 *   App 主显示名 = dcgettext(0, msgid, 5) —— domain 由 textdomain() 设置。
 *   探针同时覆盖三种调用形态：
 *     A. dcgettext("di-camera-app", msgid, LC_MESSAGES)   （显式域）
 *     B. textdomain("di-camera-app") + gettext(msgid)     （default domain）
 *     C. bindtextdomain + dcgettext                       （显式绑定目录）
 *
 * 输出格式：`msgid|value`（供 run_m2_qemu.sh grep 断言）
 */
#include <stdio.h>
#include <stdlib.h>
#include <locale.h>
#include <libintl.h>

static const char *keys[] = {
    "CAP_MENU_CUSTOM_MODE_1",
    "CAP_MENU_CUSTOM_MODE_2",
    "CAP_MENU_CUSTOM_MODE_3",
    "CAP_FN_PW",
    "MSG_MENU_PW_CUSTOM03",
};
#define NKEYS (sizeof(keys) / sizeof(keys[0]))

int main(void)
{
    const char *dom = "di-camera-app";
    char *r;
    const char *env;
    unsigned i;

    r = setlocale(LC_ALL, "");
    printf("# setlocale(LC_ALL,\"\") = %s\n", r ? r : "(NULL)");
    env = getenv("LC_ALL");
    if (!env) env = getenv("LANG");
    printf("# env LC_ALL/LANG = %s\n", env ? env : "(unset)");

    printf("# -- A: dcgettext(domain) --\n");
    for (i = 0; i < NKEYS; i++)
        printf("%s|%s\n", keys[i], dcgettext(dom, keys[i], LC_MESSAGES));

    printf("# -- B: default domain via textdomain() --\n");
    textdomain(dom);
    for (i = 0; i < NKEYS; i++)
        printf("%s|%s\n", keys[i], gettext(keys[i]));

    printf("# -- C: after bindtextdomain(/usr/share/locale) --\n");
    bindtextdomain(dom, "/usr/share/locale");
    for (i = 0; i < NKEYS; i++)
        printf("%s|%s\n", keys[i], dcgettext(dom, keys[i], LC_MESSAGES));

    printf("# probe done\n");
    return 0;
}
