/* c2_harness.c — C-2 补丁的 QEMU 验证载体（相机 ABI：glibc 2.13 / EABI5 softfp）
 *
 * 目标：在 qemu-arm-static 里"亲跑"补丁后的真字节，验证四级：
 *   T2  unit      : 直接调用桩（真字节，从补丁后二进制读取）→ system(cmd)
 *   T2b guard     : argc=1 时应直接返回、不执行（bxlo lr 守卫）
 *   T3  dispatch  : 用**真 libshell-command.so** 的 shell_exec 匹配 "film" → 桩
 *   T4  server    : 复刻 App 侧（set_start_function + start_shellthread(0x8828)），
 *                   接受真 `st app film …` 经 SysV 队列送达的命令 → 桩
 *   T5  unit2     : ★ v2 专用 —— 多参数拼接验证（"sh <f.sh> a b"）
 *
 * 原理：桩里的 `b system@plt` 是绝对距离编码 —— 只要把桩字节映射回**原虚拟地址**
 *       0xca3a8，分支自然落在 0xadd08；0xadd08 处放蹦床 `ldr pc,[pc,#-4]` + 目标函数。
 *       （qemu 用户态不模拟 I-cache，self-modifying 无需 cacheflush；真机则不然，注意。）
 *
 * ★ 2026-10-12 改造：
 *   1) 桩长度 16 → STUB_LEN(256)：v2 桩 156B（含 .ltorg 字面量池与前缀串），v1 仍 16B
 *   2) 蹦床目标改成 spy_system：把 system() 实际收到的命令行打印出来
 *      ⇒ v1 打印 `SYSTEM_CMD[touch /tmp/x]`，v2 打印 `SYSTEM_CMD[sh /opt/usr/nx-ks/f.sh touch /tmp/x ]`
 *        —— v1/v2 差异一眼可辨，无需依赖真实 f.sh 存在
 *
 * 用法: c2_harness.arm <unit|guard|dispatch|server|unit2> "<cmd>" [patched.bin]
 *                     默认 patched.bin = /tmp/dicam_c2/di-camera-app.patched
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>
#include <sys/mman.h>

/* ---- libshell-command.so 导出（C++ 修饰名，asm 别名直引） ---- */
extern int shell_exec(int argc, char **argv, void *table)
    __asm__("_Z10shell_execiPPcP11ShelCommand");
extern int start_shellthread(int key)
    __asm__("_Z17start_shellthreadi");
extern int shell_app_set_start_function(int (*fn)(int, char **))
    __asm__("_Z28shell_app_set_start_functionPFiiPPcE");

/* ---- 补丁常量（NX500 v1.12） ---- */
#define STUB_VADDR 0x00CA3A8u   /* FUN_000ca3a8（桩所在） */
#define SYS_PLT    0x000ADD08u  /* system@plt（桩分支目标） */
#define FILE_STUB  0x000C23A8u  /* 桩在文件中的偏移 */
#define FILE_NAME  0x003656DCu  /* "film" 名字串在文件中的偏移 */
#define STUB_LEN   256          /* ★ v1=16 / v2=156，统一读 256 一并映射 */

static unsigned char g_stub[STUB_LEN];
static char g_film_name[8];
static struct { char *name; void *fn; } g_app_table[2];

static void fatal(const char *m)
{
    printf("FATAL: %s\n", m);
    fflush(stdout);
    _exit(9);
}

/* ★ 间谍 system：打印实际收到的命令行，再交给真 system */
static int spy_system(const char *cmd)
{
    printf("SYSTEM_CMD[%s]\n", cmd ? cmd : "(null)");
    fflush(stdout);
    /* 若目标是 f.sh 且不存在，真 system 会返回非零——不影响判据（我们要看的是串） */
    return system(cmd);
}

static void map_page(uint32_t addr)
{
#ifndef MAP_FIXED_NOREPLACE
#define MAP_FIXED_NOREPLACE 0x100000
#endif
    void *want = (void *)(uintptr_t)addr;
    void *p = mmap(want, 0x1000, PROT_READ | PROT_WRITE | PROT_EXEC,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    if (p == MAP_FAILED)
        p = mmap(want, 0x1000, PROT_READ | PROT_WRITE | PROT_EXEC,
                 MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    if (p != want) {
        printf("mmap %08x failed -> %p\n", addr, p);
        fatal("mmap");
    }
}

/* 复刻 App 的 ui_shell_command（真身 20B thunk：shell_exec(argc,argv,App表)） */
static int mock_ui_shell_command(int argc, char **argv)
{
    int r = shell_exec(argc, argv, (void *)g_app_table);
    printf("[mock app] shell_exec(argc=%d, argv[1]=%s) -> %d\n",
           argc, argc > 1 ? argv[1] : "(none)", r);
    return r;
}

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IONBF, 0);

    const char *mode = argc > 1 ? argv[1] : "unit";
    const char *cmd  = argc > 2 ? argv[2] : "true";
    const char *bin  = argc > 3 ? argv[3] : "/tmp/dicam_c2/di-camera-app.patched";

    /* 1) 从补丁后二进制取真字节（桩 + film 名字串） */
    FILE *f = fopen(bin, "rb");
    if (!f) { perror("open patched"); return 1; }
    if (fseek(f, FILE_STUB, SEEK_SET) != 0) fatal("seek stub");
    if (fread(g_stub, 1, STUB_LEN, f) != STUB_LEN) fatal("read stub");
    if (fseek(f, FILE_NAME, SEEK_SET) != 0) fatal("seek name");
    if (fread(g_film_name, 1, 8, f) != 8) fatal("read name");
    fclose(f);

    printf("== c2_harness (%s) ==\n", mode);
    printf("stub @%08x : %02x%02x%02x%02x %02x%02x%02x%02x %02x%02x%02x%02x %02x%02x%02x%02x\n",
           STUB_VADDR,
           g_stub[0], g_stub[1], g_stub[2], g_stub[3], g_stub[4], g_stub[5], g_stub[6], g_stub[7],
           g_stub[8], g_stub[9], g_stub[10], g_stub[11], g_stub[12], g_stub[13], g_stub[14], g_stub[15]);
    printf("name @file 0x%x: '%s'\n", FILE_NAME, g_film_name);

    /* 2) 映射桩页 + 蹦床页 */
    map_page(0xCA000);
    map_page(0xAD000);
    memcpy((void *)(uintptr_t)STUB_VADDR, g_stub, STUB_LEN);
    *(volatile uint32_t *)(uintptr_t)(SYS_PLT)     = 0xE51FF004u; /* ldr pc,[pc,#-4] */
    *(volatile uint32_t *)(uintptr_t)(SYS_PLT + 4) = (uint32_t)(uintptr_t)&spy_system;
    printf("trampoline @%08x -> spy_system @%p (real system=%p)\n",
           SYS_PLT, (void *)&spy_system, (void *)&system);

    /* 3) 模拟 App 命令表（名字取自补丁后真串） */
    g_app_table[0].name = g_film_name;
    g_app_table[0].fn   = (void *)(uintptr_t)STUB_VADDR;
    g_app_table[1].name = "end";
    g_app_table[1].fn   = 0;

    if (!strcmp(mode, "unit")) {
        char *av[3];
        av[0] = g_film_name; av[1] = (char *)cmd; av[2] = 0;
        int r = ((int (*)(int, char **))(uintptr_t)STUB_VADDR)(2, av);
        printf("unit ret=%d\n", r);
    } else if (!strcmp(mode, "unit2")) {
        /* ★ v2 专用：3 个参数（验证 "prefix + a + ' ' + b + ' '" 拼接） */
        char *av[4];
        av[0] = g_film_name; av[1] = (char *)cmd; av[2] = (char *)"23"; av[3] = 0;
        int r = ((int (*)(int, char **))(uintptr_t)STUB_VADDR)(3, av);
        printf("unit2 ret=%d\n", r);
    } else if (!strcmp(mode, "guard")) {
        char *av[2];
        av[0] = g_film_name; av[1] = 0;
        int r = ((int (*)(int, char **))(uintptr_t)STUB_VADDR)(1, av);
        printf("guard done ret=%d (cmd should NOT have run)\n", r);
    } else if (!strcmp(mode, "dispatch")) {
        char *av[4];
        av[0] = (char *)"/usr/bin/st"; av[1] = g_film_name;
        av[2] = (char *)cmd; av[3] = 0;
        int r = shell_exec(3, av, (void *)g_app_table);
        printf("dispatch ret=%d\n", r);
    } else if (!strcmp(mode, "server")) {
        shell_app_set_start_function(mock_ui_shell_command);
        start_shellthread(0x8828);
        printf("server up: queue=0x8828 pid=%d\n", (int)getpid());
        for (;;)
            sleep(5);
    } else {
        printf("unknown mode: %s\n", mode);
        return 2;
    }

    fflush(stdout);
    return 0;
}
