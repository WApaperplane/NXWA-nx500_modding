/* pwsend.c — PW 属性「用户态直推」POC（NX-KS2 / O3 产物）
 * =====================================================================
 * 【这是什么】
 *   di-camera-app「画面向导确认」写 PW 参数的**最小等价复现**：
 *   把 PW 值经 MCB 通道推给 p7（= ISP 侧真正生效的路径）。
 *
 * 【原理链（2026-10-09 静态全解，见 docs/current/ATTR_BUS_MCB_2026-10-09.md）】
 *   di-camera-app: 画面向导确认
 *     → libcapture-fw-prod.so: SetVariableDataMCB(id, &v, 4)     [导出 @0x49f84]
 *         cmd = ((id - 0xff) & 0xFFFF) | 0x1300
 *     → CMCBAdapter::SetParam(cmd, 4, &v)                        [@0x83ea4]
 *     → CMulticoreBridge::Send(0x81, cmd, 4, &v)                 [libmulticore-bridge.so]
 *     → CSender → 队列 → ipcc_write_pkt → p7 → ISP
 *
 *   PW 属性 id（外部编码 = libcapture setter 用）：
 *     0x10e = PWCOLOR(聚合) ｜ 0x10f/0x110/0x111/0x112 = 经归一化到内部 SAT/SHARP/CON
 *   ★ 10-10 静态全解（p7 镜像：d6bac 分发表 + 0x51b80 档位应用序列 双证）：
 *     内部 id（直发目标）     变量
 *       0x10e              →  PWCOLOR（聚合）
 *       0x10f              →  PWSATURATION
 *       0x110              →  PWSHARPNESS
 *       0x111              →  PWCONTRAST
 *       0x130              →  PWCOLOR_R   ★
 *       0x131              →  PWCOLOR_G   ★
 *       0x132              →  PWCOLOR_B   ★
 *       0x133              →  PWHUE       ★
 *     外部→内部归一化（p7 FUN_00051090）：0x110→0x10f / 0x111→0x110 / 0x112→0x111 / 0x10f→0x10e
 *
 * 【安全设计（本工具不是玩具）】
 *   1. 默认 dry-run：不加 --yes 只打印将发送的内容，绝不动硬件
 *   2. id 白名单：[0x100, 0x13e]（= p7 d6bac 分发表输入域边界；
 *      10-10 由 [0x100,0x12b] 扩至此 —— 依据：p7 侧 `cmp r1, #0x13e` 跳转表上限）
 *   3. 一次调用只发一个值（one-shot）；失败【不重试】
 *   4. 只做"发送"；读回验证走 st cap capdtm varlist（已有工具）
 *
 * 【上机前置（必须，否则画面可能异常）】
 *   * 相机停在「菜单界面」（不是拍摄态）——与 PW 确认的场景一致
 *   * 发送后用 `st cap capdtm varlist` 读回 4 个 PW 变量确认
 *   * 回退：重新走一次"画面向导选自定义1"（或重启相机）
 *
 * 编译（★ -O0 必须；与 lutapi.arm 同工具链）
 *   .uploads/zig/zig-windows-x86_64-0.13.0/zig.exe cc \
 *     -target arm-linux-gnueabi.2.15 -O0 -o pwsend.arm pwsend.c -ldl
 *
 * 用法：
 *   pwsend.arm info                         # 符号可用性自检（零风险）
 *   pwsend.arm send 0x10e 0x0700            # dry-run：打印，不发
 *   pwsend.arm send 0x10e 0x0700 --yes      # 真发
 *   pwsend.arm seq 0x10e 900 0x111 47 0x112 31 --yes [--sleep 150]
 *                                           # 一次进程顺序发多条（一键滤镜用）
 * =====================================================================
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <dlfcn.h>

typedef int (*fn_svdm)(unsigned short id, void *data, unsigned short len);

static void usage(const char *p)
{
    printf("用法:\n");
    printf("  %s info                        # 库/符号自检（零风险）\n", p);
    printf("  %s send <id> <value> [--yes]   # 发送（默认 dry-run）\n", p);
    printf("  %s seq <id> <v> [<id> <v>...] [--yes] [--sleep ms]\n", p);
    printf("                                 # 顺序发多条（一键滤镜；默认 dry-run）\n");
    printf("\n");
    printf("  id    白名单 0x100..0x13e；PW: 0x10e/0x10f/0x110/0x111 + R/G/B/HUE=0x130..0x133\n");
    printf("        0x130(R) 0x131(G) 0x132(B) 0x133(HUE)（10-10 静态解出）\n");
    printf("  value 32 位（低 16 位有效；编码语义见 ATTR_BUS_MCB 文档）\n");
    printf("  --yes 缺省为 dry-run（只打印不发送）；--sleep 条间毫秒（默认 150）\n");
}

static int check_id(unsigned long id)
{
    if (id < 0x100 || id > 0x13e) {
        printf("★ id 0x%lx 超出白名单 [0x100, 0x13e]\n", id);
        printf("  （边界 = p7 d6bac 分发表上限 0x13e；10-10 由 0x12b 扩展）\n");
        return -1;
    }
    return 0;
}

/* ---- ★ MCB 桥初始化（真机必需）----------------------------------------
 * 2026-10-09 23:2x 真机实测：缺少此步时 SetVariableDataMCB 恒返回 -1
 * （Send 链路内部检查"桥已初始化"标志，未初始化直接失败）。
 * 依据官方样例 mcbtest 的初始化序列（@0x67504）：
 *     mcb_init();  mcb_register_handler(0xb1, ...);
 * mcb_init 无参可用、幂等（CMulticoreBridge::Initialize 检查 bInitd 标志）。
 * ---------------------------------------------------------------------- */
static int mcb_bring_up(void)
{
    void *h2 = dlopen("libmulticore-bridge.so", RTLD_NOW);
    if (!h2) h2 = dlopen("/usr/lib/libmulticore-bridge.so", RTLD_NOW);
    if (!h2) {
        printf("★ dlopen(libmulticore-bridge.so) 失败: %s\n", dlerror());
        return -1;
    }
    {
        int (*p_init)(void) = (int (*)(void))dlsym(h2, "mcb_init");
        /* mangled: _ZN16CMulticoreBridge18IsDestinationAliveEv */
        int (*p_alive)(void) = (int (*)(void))dlsym(h2,
            "_ZN16CMulticoreBridge18IsDestinationAliveEv");
        int rc;
        if (!p_init) { printf("★ dlsym(mcb_init) 失败: %s\n", dlerror()); return -1; }
        rc = p_init();
        printf("  [mcb] mcb_init rc=%d\n", rc);
        /* ★★ 关键（2026-10-09 夜真机破案）：CSender::Send 检查 m_bDestAlive
         *   （"目的地存活"标志，只在与 p7 建链/收到广播后才为 1）。
         *   libmulticore-bridge 导出官方开关 mcb_set_ignore_init_checking()
         *   （@0x64b8：mov r0,#1 → SetDestinationState）——直接绕过该检查。
         *   不走这一步 SetVariableDataMCB 恒返回 -1（本夜实测四个版本验证）。 */
        {
            int (*p_ignore)(void) = (int (*)(void))dlsym(h2, "mcb_set_ignore_init_checking");
            if (p_ignore) {
                p_ignore();
                printf("  [mcb] ignore_init_checking: set (destAlive=1)\n");
            } else {
                printf("★ dlsym(mcb_set_ignore_init_checking) 失败: %s\n", dlerror());
            }
        }
        /* Send 链检查 CSender::m_bDestAlive。轮询 IsDestinationAlive 把"等"变成"测"：
         * 若它始终 0 ⇒ 异步握手没发生（诊断价值） */
        if (p_alive) {
            int i;
            for (i = 0; i < 40; i++) {
                int a = p_alive();
                if (i % 5 == 0 || a)
                    printf("  [mcb] destAlive=%d  (t=%dms)\n", a, i * 100);
                if (a) break;
                usleep(100000);
            }
        } else {
            printf("  [mcb] (无 IsDestinationAlive 符号，改盲等 800ms)\n");
            usleep(800000);
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    void *h;
    fn_svdm svdm;

    setvbuf(stdout, NULL, _IOLBF, 0);
    if (argc < 2) { usage(argv[0]); return 1; }

    /* ---- dlopen（只为 dlsym 符号，不 touch MCB）---- */
    h = dlopen("libcapture-fw-prod.so", RTLD_NOW);
    if (!h) h = dlopen("/usr/lib/libcapture-fw-prod.so", RTLD_NOW);
    if (!h) {
        printf("★ dlopen(libcapture-fw-prod.so) 失败: %s\n", dlerror());
        printf("  ⇒ 检查库是否在 /usr/lib（本机 1.12: 已确认存在）\n");
        return 2;
    }
    svdm = (fn_svdm)dlsym(h, "SetVariableDataMCB");
    if (!svdm) {
        printf("★ dlsym(SetVariableDataMCB) 失败: %s\n", dlerror());
        return 3;
    }

    if (strcmp(argv[1], "info") == 0) {
        printf("OK: libcapture-fw-prod.so 已加载\n");
        printf("OK: SetVariableDataMCB @ %p\n", (void *)svdm);
        printf("---- 已知 PW 属性 id（10-10 静态全解）----\n");
        printf("  0x10e PWCOLOR(聚合) | 0x10f SAT | 0x110 SHARP | 0x111 CON\n");
        printf("  0x130 PWCOLOR_R | 0x131 PWCOLOR_G | 0x132 PWCOLOR_B | 0x133 PWHUE\n");
        printf("  （外部 0x110/0x111/0x112 经 p7 FUN_00051090 → 内部 0x10f/0x110/0x111）\n");
        printf("★ info 模式不发送任何数据（零风险）\n");
        return 0;
    }

    if (strcmp(argv[1], "send") == 0) {
        unsigned long id, val;
        int yes = (argc > 4 && strcmp(argv[4], "--yes") == 0);
        int rc;
        int v32;

        if (argc < 4) { usage(argv[0]); return 1; }
        id  = strtoul(argv[2], NULL, 0);
        /* ★ 用 strtoul（不是 strtol）：32 位平台上 strtol("0xFFEFD80A") 溢出成
         *   LONG_MAX（0x7FFFFFFF）——实测踩过；strtoul 正确接受全 32 位无符号。
         *   负数字符串（如 -1）按标准回绕（-1 → ULONG_MAX → (int) 截断 = -1），两种用法都对。 */
        val = strtoul(argv[3], NULL, 0);

        if (check_id(id) != 0) return 4;

        printf("=== pwsend：%s ===\n", yes ? "真发（--yes）" : "dry-run");
        printf("  id    = 0x%lx\n", id);
        printf("  value = 0x%lx (%ld)\n", val, (long)val);
        printf("  cmd   = 0x%lx  (= (id-0xff)|0x1300)\n", ((id - 0xff) & 0xFFFF) | 0x1300);
        printf("  len   = 4\n");

        if (!yes) {
            printf("★ dry-run：未调用 SetVariableDataMCB。加 --yes 才真发。\n");
            return 0;
        }

        mcb_bring_up();   /* ★ 必需：否则 SetVariableDataMCB 返回 -1（真机实测） */
        v32 = (int)val;   /* 低 32 位；发送 4 字节 */
        printf("  → SetVariableDataMCB(0x%lx, &%08x, 4) ...\n", id, (unsigned)v32);
        rc = svdm((unsigned short)id, &v32, 4);
        printf("  返回 = %d %s\n", rc, rc == 0 ? "OK" : "★非0（查白名单/相机状态）");
        printf("★ 下一步（PC 侧/相机侧读回验证）：\n");
        printf("   /opt/usr/nx-ks/filmlab.sh check   或   st cap capdtm varlist\n");
        printf("   期望：PWCOLOR_*/PWSATURATION 等的高 16 位跟随 value\n");
        usleep(300000);   /* 让 MCB 队列收尾，不重试 */
        return rc == 0 ? 0 : 5;
    }

    if (strcmp(argv[1], "seq") == 0) {
        /* seq <id> <v> [<id> <v> ...] [--yes] [--sleep ms]
         * 一键滤镜路径：一次进程按顺序发多条（每条间隔 sleep，默认 150ms）。 */
        int yes = 0, slp = 150, i, npair = 0;
        unsigned long ids[64], vals[64];
        int rc_all = 0;

        for (i = 2; i < argc; i++) {
            if (strcmp(argv[i], "--yes") == 0) { yes = 1; continue; }
            if (strcmp(argv[i], "--sleep") == 0 && i + 1 < argc) {
                slp = atoi(argv[i + 1]);
                if (slp < 0) slp = 0;
                if (slp > 2000) slp = 2000;      /* 上限保护：别在单核上久占 */
                i++;
                continue;
            }
            /* 数值对：id 永远不以 - 开头（0x1xx）；val 为全 32 位（strtoul，勿用 strtol——会溢出） */
            if (i + 1 < argc && argv[i][0] != '-') {
                if (npair >= 64) break;
                ids[npair]  = strtoul(argv[i], NULL, 0);
                vals[npair] = strtoul(argv[i + 1], NULL, 0);
                if (check_id(ids[npair]) != 0) return 4;
                npair++;
                i++;
            } else {
                printf("★ 奇数个数值参数（id/value 必须成对）\n");
                usage(argv[0]);
                return 1;
            }
        }
        if (npair == 0) { usage(argv[0]); return 1; }

        printf("=== pwsend seq：%d 条 %s（条间 %dms）===\n",
               npair, yes ? "真发（--yes）" : "dry-run", slp);
        for (i = 0; i < npair; i++) {
            printf("  [%d] id=0x%lx cmd=0x%lx value=0x%04lx (%ld)\n", i,
                   ids[i], ((ids[i] - 0xff) & 0xFFFF) | 0x1300,
                   vals[i] & 0xFFFF, (long)vals[i]);
        }
        if (!yes) {
            printf("★ dry-run：未调用 SetVariableDataMCB。加 --yes 才真发。\n");
            return 0;
        }
        mcb_bring_up();   /* ★ 必需：否则 SetVariableDataMCB 返回 -1（真机实测） */
        for (i = 0; i < npair; i++) {
            int v32 = (int)vals[i];
            int rc = svdm((unsigned short)ids[i], &v32, 4);
            printf("  [%d] 0x%lx <- 0x%lx  rc=%d %s\n", i, ids[i], vals[i], rc,
                   rc == 0 ? "OK" : "★非0");
            if (rc != 0) rc_all = 5;
            if (i + 1 < npair) usleep((useconds_t)slp * 1000);
        }
        printf("★ 下一步：st cap capdtm varlist（或 filmlab.sh check）读回对照\n");
        usleep(300000);
        return rc_all;
    }

    usage(argv[0]);
    return 1;
}
