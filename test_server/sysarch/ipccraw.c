/*★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
 * ipccraw.c —— IPCC 裸 ioctl 探测器（★ 绕过 libudd5 的锁）
 *
 * ★★★ 为什么绕过（2026-10-07 实测）
 *   ipcc_open() 内部：
 *       pthread_mutex_lock();
 *       rc = d5_udd_open(2, 1);      // 与 EP 同一个设备上下文
 *       if (rc == 1) ... else if (rc == 2) return -1;   // ★ 被主程序占用 ⇒ -1
 *       ...
 *   ⇒ 库自己加锁抢不到，但【内核驱动是同一个】
 *   ⇒ 直接 open("/dev/d5_ipcc") 拿自己的 fd，ioctl 一样能用
 *
 * ★★★ 权威来源（NX1 GPL 头文件 media/drime5/ipcc/d5_ipcc_ioctl.h）
 *   #define IPCC_MAGIC 't'
 *   struct ipcc_available_info { int core_id; int ret; };              // 8B
 *   struct ipcc_buf_info { int core_id; unsigned len; int ret; uchar*buf; }; // 12B
 *   IPCC_INIT                _IOWR('t', 1, int)                    0xc0080174
 *   IPCC_GET_WRITE_AVAILABLE _IOWR('t', 3, struct ipcc_available_info) 0xc0080374
 *   IPCC_GET_READ_AVAILABLE  _IOWR('t', 4, ...)                    0xc0080474
 *   IPCC_GET_READ_PKT_LENTH _IOWR('t', 5, ...)                    0xc0080574
 *   IPCC_READ_PKT           _IOWR('t', 6, struct ipcc_buf_info)   0xc0100674
 *   IPCC_WRITE_PKT          _IOWR('t', 7, struct ipcc_buf_info)   0xc0100774
 *   IPCC_INTERRUPT_ENABLE   _IO ('t', 8)                          0xc0000874
 *   IPCC_RAW_INT_WAIT       _IOR ('t',10, struct ipcc_raw_status) 0xc0080a74
 *
 * ★★ ioctl 号已用 capstone 从 libudd5 实际指令交叉验证
 *    （movw/movt 立即数：0x7403/0x7404/0x7405/0x7406/0x7407/0x740b/0x740c）
 *
 * ★★★ 安全设计
 *   scan  模式：只做 INIT / GET_*_AVAILABLE / GET_READ_PKT_LENTH —— 全是查询
 *   ★★ 默认不写任何包。要发包必须显式加 -w 参数
 *
 * 用法：
 *   ipccraw.scan              ★ 只读扫描（默认，绝不写）
 *   ipccraw.init              只发 IPCC_INIT（握手，必要）
 *   ipccraw.write <core> <file>   ★★ 发包（危险，需显式）
 * ================================================================*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/stat.h>

/* ── ioctl 号（★★ 权威来源 = libudd5 实际指令，立即数逐条反汇编得到）
 * ★ 不要用头文件宏重算：NX1 GPL 头文件与实机 libudd5 的 size 字段不一致
 *   头文件算出 READ_PKT=0xc00c7406，库实测 = 0xc0107406（size 16 vs 12）
 *   ⇒ 三个查询类（nr 3/4/5）两者一致 ✔，但 pkt 类不一致 ⇒ 一律用库实测值
 * ─────────────────────────────────────────────────────────────*/
#define IPCC_INIT               0xc0087401UL
#define IPCC_GET_WRITE_AVAIL    0xc0087403UL
#define IPCC_GET_READ_AVAIL     0xc0087404UL
#define IPCC_GET_READ_PKT_LENTH 0xc0087405UL
#define IPCC_READ_PKT           0xc0107406UL
#define IPCC_WRITE_PKT          0xc0107407UL
#define IPCC_RAW_INT_WAIT       0xc008740bUL

/* ── 头文件结构体（逐字节对齐照抄）──────────────────────────
 * struct ipcc_available_info { int core_id; int ret; };              8 字节
 * struct ipcc_buf_info { int core_id; unsigned len; int ret; uchar *buf; };  12 字节
 *（ARM EABI 32位：int=4, unsigned=4, ptr=4 ⇒ 4+4+4+4=12 ✔） */
struct ipcc_available_info { int core_id; int ret; };
struct ipcc_buf_info       { int core_id; unsigned int len; int ret; unsigned char *buf; };

/* ── 中断类型（d5_lib.h）—— CA9 = p7 ───────────────────────── */
static const char *INTR_NAME[] = {
    "CA7_1 (Linux)", "CA7_2 raw", "CA9_1 (p7)", "CA9_2 raw",
    "CM4_1", "CM4_2", "CM4_3", "SRP", "MAX"
};
#define CORE_MAX 16

static int g_fd = -1;

static int dev_open(void)
{
    g_fd = open("/dev/d5_ipcc", O_RDWR);
    if (g_fd < 0) {
        printf("  open(/dev/d5_ipcc) 失败: %s\n", strerror(errno));
        return -1;
    }
    printf("  open(/dev/d5_ipcc) => fd=%d  OK  ★ 不经 libudd5，无锁竞争\n", g_fd);
    return 0;
}

static void dev_close(void)
{
    if (g_fd >= 0) { close(g_fd); g_fd = -1; }
}

static int do_init(void)
{
    int a = 0;
    int rc = ioctl(g_fd, IPCC_INIT, &a);
    printf("  IPCC_INIT(arg=0) => %d  %s\n", rc,
           rc == 0 ? "OK" : (rc < 0 ? strerror(errno) : "★ 非 0"));
    return rc;
}

static int cmd_scan(int do_init_first)
{
    int core, rc, any = 0;
    struct ipcc_available_info ai;

    printf("\n=== IPCC 裸 ioctl 扫描（★ 只读）===\n");
    if (dev_open() < 0) return 1;
    if (do_init_first) { printf("\n--- 握手 ---\n"); do_init(); }

    printf("\n--- IPCC_INIT 不带参数 的效果 ---\n");
    do_init();

    printf("\n--- 逐 core 查询 ---\n");
    printf("  core | write_avail | read_avail | pkt_lenth | 备注\n");
    printf("  -----+-------------+------------+-----------+------\n");
    for (core = 0; core < CORE_MAX; core++) {
        int w, r, l;
        memset(&ai, 0, sizeof ai); ai.core_id = core;
        w = (ioctl(g_fd, IPCC_GET_WRITE_AVAIL, &ai) == 0) ? ai.ret : -errno;
        memset(&ai, 0, sizeof ai); ai.core_id = core;
        r = (ioctl(g_fd, IPCC_GET_READ_AVAIL, &ai) == 0) ? ai.ret : -errno;
        memset(&ai, 0, sizeof ai); ai.core_id = core;
        l = (ioctl(g_fd, IPCC_GET_READ_PKT_LENTH, &ai) == 0) ? ai.ret : -errno;
        printf("  %4d | %11d | %10d | %9d | %s\n", core, w, r, l,
               (w > 0 || r > 0) ? "★ 有数据" : "");
        if (w > 0 || r > 0) any = 1;
    }

    printf("\n--- 中断类型编号（发包时用）---\n");
    for (core = 0; core < 9; core++)
        printf("  INT_IPCC[%d] = %s\n", core, INTR_NAME[core]);

    printf("\n--- 写能力探测（★ 只查不写）---\n");
    memset(&ai, 0, sizeof ai); ai.core_id = 2;   /* CA9 = p7 */
    rc = ioctl(g_fd, IPCC_GET_WRITE_AVAIL, &ai);
    printf("  CA9(p7) write_available => rc=%d ret=%d  %s\n", rc, ai.ret,
           rc == 0 ? "OK" : strerror(errno));
    printf("  ⇒★ 若是【CA9 可写】，就能给 p7 发 LUT 数据包\n");

    dev_close();
    printf("\n%s\n", any ? "★ 找到可用的 core" : "★ 全部为空（可能需要先握手/等 p7 请求）");
    return 0;
}

static int cmd_write(int core, const char *path)
{
    struct ipcc_buf_info bi;
    FILE *fp;
    long n;
    unsigned char *buf;
    int rc;

    printf("\n=== ★★ 发包模式（危险）★★\n");
    printf("  core=%d  file=%s\n", core, path);
    fp = fopen(path, "rb");
    if (!fp) { printf("  打开文件失败: %s\n", strerror(errno)); return 1; }
    fseek(fp, 0, SEEK_END); n = ftell(fp); fseek(fp, 0, SEEK_SET);
    buf = (unsigned char *)malloc(n);
    if (fread(buf, 1, n, fp) != (size_t)n) { printf("  读文件失败\n"); fclose(fp); free(buf); return 1; }
    fclose(fp);
    printf("  读入 %ld 字节\n", n);

    if (dev_open() < 0) { free(buf); return 1; }
    do_init();

    memset(&bi, 0, sizeof bi);
    bi.core_id = core;
    bi.len     = (unsigned int)n;
    bi.buf     = buf;
    rc = ioctl(g_fd, IPCC_WRITE_PKT, &bi);
    printf("  IPCC_WRITE_PKT => %d  ret=%d  %s\n", rc, bi.ret,
           rc == 0 ? "OK" : strerror(errno));
    dev_close();
    free(buf);
    return rc == 0 ? 0 : 1;
}

int main(int argc, char **argv)
{
    const char *cmd = argc > 1 ? argv[1] : "scan";
    int ret = 0;

    printf("=== NX500 ipccraw：IPCC 裸 ioctl 探测器 ===\n");

    if (strcmp(cmd, "scan") == 0) {
        ret = cmd_scan(0);
    } else if (strcmp(cmd, "init") == 0) {
        if (dev_open() == 0) { do_init(); dev_close(); } else ret = 1;
    } else if (strcmp(cmd, "write") == 0) {
        if (argc < 4) { printf("用法: %s write <core> <file>\n", argv[0]); return 1; }
        ret = cmd_write(atoi(argv[2]), argv[3]);
    } else {
        printf("用法: %s [scan|init|write <core> <file>]\n", argv[0]);
        printf("  scan            ★ 只读扫描（默认）\n");
        printf("  init            只做 IPCC_INIT 握手\n");
        printf("  write           ★★ 发包（危险）\n");
        ret = 1;
    }
    return ret;
}
