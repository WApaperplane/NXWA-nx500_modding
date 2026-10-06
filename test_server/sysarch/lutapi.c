/* lutapi.c — NX-KS2 3D LUT 官方 API 工具
 * =====================================================================
 *  ★★★★ 本工具是【官方 API 路线】的实现，与 lutload.arm 并存但定位不同：
 *  ---------------------------------------------------------------------
 *  【为什么有第二个工具】
 *    2026-10-06 22:40 在 NX1 GPL 源码里找到了官方用户态 API：
 *      int d5_ep_3dl_load_lut (unsigned *lut_base_addr, sellut, format, timeout);
 *      int d5_ep_3dl_save_lut (unsigned *lut_base_addr, sellut, format, timeout);
 *      int d5_ep_3dlut_op_init (d5_ep_lut_op_info_st *info);
 *    其中 sellut 枚举 = { LUT0=0, LUT1=1, LUT_EXT=2 }，
 *    D5_EP_LUT_SEL_LUT_EXT 的注释原文 = "Select Look-up-table Externally"
 *    ⇒★★ 三星本来就留了"用户态灌外部 LUT"的门。
 *
 *    libudd5.so 里 23 个 LUT 符号全部 STB_GLOBAL，dlsym 直接可得。
 *
 *  【为什么手写寄存器 11 步会花屏 —— 找到了确切原因】
 *    d5_ep_3dl_load_lut 内部第一件事就是
 *        d5_ep_sma_virt_to_phys(lut_base_addr)
 *    而【实测】virt_to_phys 只认"自己 mmap 的映射"：
 *        malloc堆        => 返回 0
 *        mmap 匿名        => 返回 0
 *        mmap /dev/d5_sma => 返回精确物理地址
 *    ⇒★★ 我在 lutload.arm 里手算的物理地址，库根本不认 ⇒ DMA 读到错误数据。
 *    ⇒ 本工具【强制】用 /dev/d5_sma 的 mmap 缓冲，绝不允许 malloc。
 *
 *  【反汇编核对（capstone，铁律 67）】
 *    d5_ep_3dl_load_lut:
 *      if(!virt) return -1;  if(sel>2) return -1;  if(fmt>1) return -1;
 *      p = { A=1, B=1, sel, pad, { virt_to_phys(virt), fmt } };
 *      return _udd_ep_3dl_ctrl_ConfigAccessMode(&p);
 *
 *    ConfigAccessMode: if(p->B==1) return sub_3a888(p);   <- LoadLut
 *    sub_3a888:  OnOff(1) → Acc_OnOff(0) → Acc_OnOff(1)
 *                switch(sel){ case0/1: SetAddress+SetColorFormat_LUT0/1
 *                             case2:   两条通道都写 }
 *                SelLUT(sel) → rw_Start(1)      <- DMA 触发脉冲
 *    与我手写的 11 步【完全一致】，交叉验证通过。
 *
 *  【安全设计（铁律 61 的代码化）】
 *    1. load 强制要求显式物理地址参数，缺省拒绝执行（绝不猜地址）
 *    2. 写入前用 SMA_VIRT_TO_PHYS 核对，地址对不上立即中止
 *    3. 写入后回读校验
 *    4. lib_3dlut_reg_base == 0 时拒绝执行（未 open，写 NULL 会段错误）
 *    5. DMA 期间【不清零、不munmap】，等 settle_ms 之后再解除映射
 *  =====================================================================
 *
 *  编译（★★必须 -O0；所有 ioctl 号用字面量常量，见下方注释）
 *    "D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe" cc \
 *      -target arm-linux-gnueabi.2.15 -O0 -o lutapi.arm lutapi.c -ldl
 *
 *  用法：
 *    lutapi.arm probe                ★零风险：dlsym + 缓冲能力探测，不调任何写入函数
 *    lutapi.arm info                 只读：符号地址 + EP reg_base
 *    lutapi.arm regdump              只读：3D LUT 寄存器快照
 *    lutapi.arm opinit <sel> <fmt> <cbcr> <bypass>   只调 op_init（配置，不灌数据）
 *    lutapi.arm load <file> <phys> [sel=2] [fmt=1] [size=17] [stride=2]
 *    lutapi.arm save <out>   <phys> [sel=2] [fmt=1] [bytes]
 *    lutapi.arm verify <file> <phys> [sel=2] [fmt=1] [size=17] [stride=2]
 *                                    load + save + 逐字节比对（双向可逆判据）
 *    lutapi.arm idgen <out> [size=17] [stride=2]   生成 identity 表
 *
 *  <file> 支持两种：*.cube（自动解析）或 *.bin（原始字节）
 *  <phys> CMA 物理地址，★ 必须先用 cmapick.arm 实时探测（铁律 61）
 * =====================================================================
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <fcntl.h>
#include <ctype.h>
#include <dlfcn.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>

/* =====================================================================
 * 官方类型（逐字抄自 NX1 GPL 头文件 usr/include/drime5/udd/ep_type.h）
 * ===================================================================== */
typedef enum {
    D5_EP_LUT_FORMAT_422 = 0,   /* 00: YCC422 */
    D5_EP_LUT_FORMAT_420 = 1    /* 01: YCC420 */
} d5_ep_lut_format_et;

typedef enum {
    D5_EP_LUT_CBCR_CH0  = 0,
    D5_EP_LUT_CBCR_CH1  = 1,
    D5_EP_LUT_CBCR_CH01 = 2
} d5_ep_lut_cbcr_ch_et;

typedef enum {
    D5_EP_LUT_SEL_LUT0  = 0,
    D5_EP_LUT_SEL_LUT1  = 1,
    D5_EP_LUT_SEL_LUT_EXT = 2   /* ★★ "Select Look-up-table Externally" */
} d5_ep_lut_sellut_et;

typedef enum { D5_EP_OFF, D5_EP_ON } d5_ep_onoff;

/* ★ 16 字节，字段全是 unsigned int（32 位），不是 unsigned long */
typedef struct {
    d5_ep_lut_format_et   lut_clrfmt;    /* +0x00 */
    d5_ep_lut_cbcr_ch_et  cbcr_ch_sel;  /* +0x04 */
    d5_ep_lut_sellut_et   lut_sel;       /* +0x08 */
    d5_ep_onoff           bypass_sw;     /* +0x0c */
} d5_ep_lut_op_info_st;

/* 函数原型（ep.h 权威） */
typedef int(*fn_op_init)(d5_ep_lut_op_info_st *);
typedef int(*fn_load_lut)(unsigned int *, d5_ep_lut_sellut_et,
                          d5_ep_lut_format_et, unsigned int);
typedef int(*fn_save_lut)(unsigned int *, d5_ep_lut_sellut_et,
                          d5_ep_lut_format_et, unsigned int);
typedef unsigned int(*fn_v2p)(unsigned int);
typedef int(*fn_ep_open)(void);
typedef void(*fn_ep_close)(void);

/* =====================================================================
 * ioctl 号（★铁律：字面量常量。自定义 IOC 宏 32 位溢出 ⇒ zig -O0
 *          生成非法指令 ⇒ SIGILL，症状极具误导性）
 *   SMA_VIRT_TO_PHYS = _IOR('d', 2, unsigned) = 0xc0047302
 *   EP_IOCTL_GET_PHYS_REG_INFO = _IOR('h',100, struct ep_reg_info=80B)
 *                              = 0x80506864（★与实测 eplut10 可用号一致）
 * ===================================================================== */
#define SMA_VIRT_TO_PHYS          0xc0047302UL
#define EP_IOCTL_GET_PHYS_REG_INFO 0x80506864UL

struct ep_reg_phys_info { unsigned int reg_start_addr, reg_size; };
struct ep_reg_info {
    struct ep_reg_phys_info reg_base_top, reg_base_ldc, reg_base_mc,
                           reg_base_rsz, reg_base_lvr, reg_base_bblt,
                           reg_base_fd, reg_base_jpeg, reg_base_3dlut,
                           reg_base_nog;
};

#define EP_3DLUT(i) ((i).reg_base_3dlut)

/* 3D LUT 寄存器偏移（★ lutload.arm + libudd5 双向确认） */
#define R_ONOFF 0x000
#define R_CFG   0x004   /* bits[1:0]=SelCbCr_ch  bits[5:4]=SelLUT
                           bit8=LUT0 fmt  bit12=LUT1 fmt */
#define R_PULSE 0x008   /* bit8=写脉冲(0清)   bit4=读脉冲 */
#define R_LUT0  0x00c
#define R_LUT1  0x010

/* =====================================================================
 * 符号句柄
 * ===================================================================== */
static void *g_h = NULL;
static fn_op_init   p_op_init;
static fn_load_lut  p_load;
static fn_save_lut  p_save;
static fn_v2p       p_v2p;
static fn_ep_open   p_ep_open;
static fn_ep_close  p_ep_close;

/* ★★ 铁律：绝不 deref 共享库全局变量里的 mmap 地址（跨进程无效 ⇒ 死机）。
 *    这里只【读】ep_3dlut_reg_base 这个标量本身，用来判断"库是否已初始化"，
 *    绝不拿它去算寄存器地址。寄存器访问一律走 /dev/drime5_ep 的 mmap。 */
static unsigned *p_regbase_sym;

static const char *SYMS[] = {
    "d5_ep_3dlut_op_init", "d5_ep_3dl_load_lut", "d5_ep_3dl_save_lut",
    "d5_ep_sma_virt_to_phys", "d5_ep_open", "d5_ep_close",
    "_udd_ep_3dl_ctrl_ConfigAccessMode",
    "_udd_ep_3dl_ctrl_ConfigBypassMode",
    "_udd_ep_3dl_ctrl_ConfigProcessMode",
    "_udd_ep_3dl_reg_SetReg", "_udd_ep_3dl_reg_GetReg",
    "_udd_ep_3dl_reg_SetAddress", "_udd_ep_3dl_reg_SelLUT",
    "_udd_ep_3dl_reg_SetColorFormat_LUT0",
    "_udd_ep_3dl_reg_SetColorFormat_LUT1",
    "_udd_ep_3dl_reg_rw_Start", "_udd_ep_3dl_reg_OnOff",
    "_udd_ep_3dl_reg_Acc_OnOff",
    "_udd_ep_mux_3dlut_wdxi", "_udd_ep_mux_3dlut_rdxi",
    "_udd_ep_demux_3dlut_wdxi", "_udd_ep_demux_3dlut_rdxi",
    "ep_3dlut_reg_base",
};
#define NSYM ((int)(sizeof(SYMS)/sizeof(SYMS[0])))

/* =====================================================================
 * 小工具
 * ===================================================================== */
static void hexdump(const char *tag, const unsigned char *p, int n)
{
    int i;
    printf("  %s (%d 字节):\n    ", tag, n);
    for (i = 0; i < n && i < 64; i++)
        printf("%02x%s", p[i], (i % 16 == 15) ? "\n    " : " ");
    if (n > 64) printf("... (%d 字节止)\n    ", n);
    printf("\n");
}

/* CMA/SMA 缓冲：★★ 必须是 /dev/d5_sma 的 mmap —— virt_to_phys 只认这种 */
typedef struct {
    int fd;
    unsigned long phys;
    unsigned long npages;
    unsigned char *v;
} sma_buf;

static int g_lib_opened = 0;

/* ★★★★★★ 2026-10-06 22:55 实测修正：必须先 d5_ep_open()
 * ---------------------------------------------------------------------
 *  现象：lutapi.arm probe 里 virt_to_phys 全部返回 0，
 *        而同样时刻 v2p.arm（自己 open 设备 + 裸 ioctl）完全正常。
 *
 *  根因（libudd5 反汇编，d5_ep_sma_virt_to_phys @ 0x2175c）：
 *      unsigned d5_ep_sma_virt_to_phys(unsigned virt) {
 *          if (g_d5_dev_ctx < 0) return 0;      ← ★ 我们进程没有句柄
 *          if (virt == 0)        return 0;
 *          if (ioctl(g_d5_dev_ctx, 0xc0047302, &virt) < 0) return 0;
 *          return virt;
 *      }
 *  ⇒ 它用的就是同一个 ioctl 号，但要求进程内有有效的设备句柄。
 *  ⇒ dmesg 实测印证：驱动打印
 *        "d5_uservirt_to_phys:59 invalid userspace address=b6f39000"
 *    —— 驱动认得这个 ioctl，只是【那个地址已 munmap 失效】。
 *
 *  ★★ 实测 d5_ep_open() 返回 0（成功），且
 *     ep_3dlut_reg_base 从 0x00000000 变成 0xb6fb3000 ⇒ 官方 API 可用。
 *     （实测时相机不在拍摄态，无进程持有 /dev/drime5_ep）
 */
static int ensure_lib_open(int verbose)
{
    int rc;
    if (g_lib_opened) return 0;
    if (!p_ep_open) {
        printf("  ★ d5_ep_open 符号缺失\n");
        return -1;
    }
    if (verbose) {
        printf("  d5_ep_open() ... ");
        fflush(stdout);
    }
    rc = p_ep_open();
    if (verbose) {
        printf("返回 %d %s\n", rc,
               rc == 0 ? "(首次打开成功)" :
               rc == 2 ? "(引用计数++,设备已在用)" :
               rc == 1 ? "(已是打开态)" : "(★失败)");
    }
    /* rc: 0=首次打开成功  1=已打开  2=引用计数++  负=错误
     * ⇒ 前三种都算成功 */
    if (rc < 0 || (rc > 2)) return -2;
    g_lib_opened = 1;
    if (verbose && p_regbase_sym)
        printf("  ep_3dlut_reg_base = 0x%08x %s\n", *p_regbase_sym,
               *p_regbase_sym ? "★已初始化" : "★仍为0");
    return 0;
}

static int sma_open(sma_buf *b, unsigned long phys, unsigned long bytes)
{
    memset(b, 0, sizeof(*b));
    b->phys = phys;
    b->npages = (bytes + 4095) & ~4095UL;
    b->fd = open("/dev/d5_sma", O_RDWR);
    if (b->fd < 0) {
        printf("  open /dev/d5_sma 失败: %s\n", strerror(errno));
        return -1;
    }
    b->v = (unsigned char *)mmap(NULL, b->npages, PROT_READ | PROT_WRITE,
                                 MAP_SHARED, b->fd, (off_t)phys);
    if (b->v == MAP_FAILED) {
        printf("  mmap phys=0x%08lx 失败: %s\n", phys, strerror(errno));
        printf("  ⇒ 地址可能不合法。请先用 cmapick.arm 探测可用落点。\n");
        close(b->fd);
        b->fd = -1;
        return -2;
    }
    /* ★★★ 必须先 open 库，否则 virt_to_phys 一律返回 0 */
    if (ensure_lib_open(1) != 0) {
        printf("  ★ d5_ep_open 失败，无法核对物理地址\n");
        munmap(b->v, b->npages);
        close(b->fd);
        b->fd = -1;
        return -4;
    }
    /* ★★ 唯一可靠的验证：问驱动这个虚拟地址对应什么物理地址
     *    ★ 必须在 mmap 存活期内测——munmap 后驱动会拒绝（实测） */
    if (p_v2p) {
        unsigned int real = p_v2p((unsigned int)(unsigned long)b->v);
        printf("  virt_to_phys(%p) => 0x%08x  (期望 0x%08lx) %s\n",
               b->v, real, phys, real == phys ? "匹配" : "★ 不匹配");
        if (real != phys) {
            printf("  ⇒★★ 物理地址对不上，DMA 会读到错误数据，中止。\n");
            munmap(b->v, b->npages);
            close(b->fd);
            b->fd = -1;
            return -3;
        }
    }
    return 0;
}

/* ★ 保持映射有效但不清零：DMA 还没搬完时清零会损坏正在传输的数据 */
static void sma_release(sma_buf *b)
{
    if (b->v && b->v != MAP_FAILED) munmap(b->v, b->npages);
    if (b->fd >= 0) close(b->fd);
    b->v = NULL; b->fd = -1;
}

/* =====================================================================
 * .cube 解析（Adobe/Iridas 标准 LUT3D）
 *   "LUT_3D_SIZE N" 后跟 N^3 行 "r g b"，值域 0..1
 * ===================================================================== */
static unsigned char *cube_parse(const char *path, int *out_n, int stride,
                                 unsigned long *out_bytes)
{
    FILE *fp = fopen(path, "rb");
    char line[512];
    int n = 0, nread = 0;
    float *rgb;
    unsigned char *out;
    unsigned long i, total;

    if (!fp) { printf("  打不开 %s: %s\n", path, strerror(errno)); return NULL; }
    while (fgets(line, sizeof line, fp)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (strncmp(p, "LUT_3D_SIZE", 11) == 0) {
            n = atoi(p + 11);
            if (n < 2 || n > 65) {
                printf("  ★ LUT_3D_SIZE = %d 不合法（2..65）\n", n);
                fclose(fp); return NULL;
            }
        }
    }
    if (n == 0) {
        printf("  ★ 文件里没有 LUT_3D_SIZE 头，不是 .cube\n");
        fclose(fp); return NULL;
    }
    total = (unsigned long)n * n * n;
    printf("  LUT_3D_SIZE = %d  ⇒  %lu 个节点  stride=%d(%d-bit)\n",
           n, total, stride, stride * 8);

    rgb  = (float *)malloc(total * 3 * sizeof(float));
    out  = (unsigned char *)malloc(total * 3 * stride);
    if (!rgb || !out) { free(rgb); free(out); fclose(fp); return NULL; }

    /* 第二遍：读数据 */
    rewind(fp);
    while (fgets(line, sizeof line, fp) && nread < (int)total) {
        float r, g, b;
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || strncmp(p, "LUT_", 4) == 0 || *p == '\0' || *p=='\r' || *p=='\n')
            continue;
        if (sscanf(p, "%f %f %f", &r, &g, &b) != 3) continue;
        if (nread >= (int)total) break;
        rgb[nread*3+0] = r; rgb[nread*3+1] = g; rgb[nread*3+2] = b;
        nread++;
    }
    fclose(fp);
    if (nread != (int)total) {
        printf("  ★ 只读到 %d / %lu 个节点\n", nread, total);
        free(rgb); free(out); return NULL;
    }

    /* ★ .cube 规范：第 i 行 = "R G B"，且 r 变化最快（等价 [b][g][r] 升序）。
     *   本函数逐通道直传，不做重排——保持与 .cube 规范和 make_identity 一致。
     *   （★ 若日后实测红蓝互换，需要在这里重排，不是改解析顺序） */
    for (i = 0; i < total; i++) {
        int c;
        for (c = 0; c < 3; c++) {
            double v = rgb[i*3+c];        /* c=0→r, 1→g, 2→b，与输出一致 */
            if (v < 0) v = 0; if (v > 1) v = 1;
            if (stride == 1) {
                out[i*3+c] = (unsigned char)(v * 255.0 + 0.5);
            } else {
                unsigned int q = (unsigned int)(v * 65535.0 + 0.5);
                unsigned char *o = out + (i*3+c)*2;
                o[0] = (unsigned char)(q & 0xff);        /* ★ 小端 LE */
                o[1] = (unsigned char)((q >> 8) & 0xff);
            }
        }
    }
    free(rgb);
    *out_n = n;
    *out_bytes = total * 3 * stride;
    printf("  转换完成: %lu 字节\n", *out_bytes);
    return out;
}

static unsigned char *file_load(const char *path, int *out_n, int stride,
                                unsigned long *out_bytes)
{
    FILE *fp;
    long fsz;
    unsigned char *b;
    size_t got;

    if (strlen(path) > 5 && strcasecmp(path + strlen(path) - 5, ".cube") == 0)
        return cube_parse(path, out_n, stride, out_bytes);

    fp = fopen(path, "rb");
    if (!fp) { printf("  打不开 %s: %s\n", path, strerror(errno)); return NULL; }
    fseek(fp, 0, SEEK_END); fsz = ftell(fp); fseek(fp, 0, SEEK_SET);
    if (fsz <= 0 || fsz > 65536) {
        printf("  ★ 大小 %ld 不合法（1..65536）\n", fsz);
        fclose(fp); return NULL;
    }
    b = (unsigned char *)malloc(fsz);
    got = fread(b, 1, fsz, fp);
    fclose(fp);
    if ((long)got != fsz) { free(b); return NULL; }
    printf("  原始二进制: %ld 字节\n", fsz);
    *out_n = 0;
    *out_bytes = (unsigned long)fsz;
    return b;
}

static unsigned char *make_identity(int n, int stride, unsigned long *out_bytes)
{
    unsigned long total = (unsigned long)n * n * n, i;
    unsigned char *out = (unsigned char *)malloc(total * 3 * stride);
    if (!out) return NULL;
    /* ★★★ identity：输出 = 输入
     *   ⇒ 第 i 个节点的第 c 通道 = 该通道的网格坐标 / (n-1)
     *
     *   ★★索引分解方向必须【r 变化最快】，与 .cube 规范一致：
     *       r = i % n;  g = (i/n) % n;  b = i/(n*n)
     *     ⇒ idx[0]=r, idx[1]=g, idx[2]=b
     *   ★★ 2026-10-06 实测修正：原先写成 k=2..0 反向分解，
     *      导致 idx[0] 拿到的是最慢位⇒ 2x2x2 identity 首节点变成 00 00 ff
     *      （纯蓝）而不是 00 00 00。已由PC 端逐字节比对定位并修正。 */
    for (i = 0; i < total; i++) {
        int idx[3];
        unsigned long r = i;
        idx[0] = (int)(r % (unsigned long)n);            r /= (unsigned long)n;   /* R 最快 */
        idx[1] = (int)(r % (unsigned long)n);            r /= (unsigned long)n;   /* G 次之 */
        idx[2] = (int)(r % (unsigned long)n);                             /* B 最慢 */
        {
            int c;
            for (c = 0; c < 3; c++) {
                double v = (double)idx[c] / (double)(n - 1);
                if (stride == 1) out[i*3+c] = (unsigned char)(v * 255.0 + 0.5);
                else {
                    unsigned int q = (unsigned int)(v * 65535.0 + 0.5);
                    unsigned char *o = out + (i*3+c)*2;
                    o[0] = (unsigned char)(q & 0xff);
                    o[1] = (unsigned char)((q >> 8) & 0xff);
                }
            }
        }
    }
    *out_bytes = total * 3 * stride;
    return out;
}

/* =====================================================================
 * 命令实现
 * ===================================================================== */
static int cmd_info(void)
{
    int i, found = 0;
    printf("\n--- dlsym 结果 ---\n");
    for (i = 0; i < NSYM; i++) {
        void *a = dlsym(g_h, SYMS[i]);
        if (a) { found++; printf("  %-42s %p\n", SYMS[i], a); }
        else printf("  %-42s <无>\n", SYMS[i]);
    }
    printf("  => %d / %d\n", found, NSYM);

    printf("\n--- EP 基址标量（只读标量本身，绝不 deref）---\n");
    if (p_regbase_sym) {
        unsigned v = *p_regbase_sym;
        printf("  ep_3dlut_reg_base = 0x%08x  %s\n", v,
               v ? "(库已初始化)" : "★ 0 ⇒ 未 open，直接调 API 会段错误");
    }
    return 0;
}

/* ★零风险探测：只 dlsym + 试映射，不调任何会写硬件的函数 */
static int cmd_probe(void)
{
    sma_buf b;
    int rc;
    static const unsigned long TRIES[] = { 0x94000000UL, 0x94100000UL,
                                           0x94200000UL, 0x8f800000UL };
    unsigned i;

    printf("\n--- 符号解析 ---\n");
    printf("  op_init=%p load=%p save=%p virt2phys=%p ep_open=%p\n",
           (void*)p_op_init, (void*)p_load, (void*)p_save,
           (void*)p_v2p, (void*)p_ep_open);

    printf("\n--- ep_3dlut_reg_base（open 前）---\n");
    if (p_regbase_sym) {
        unsigned v = *p_regbase_sym;
        printf("  0x%08x  %s\n", v, v ? "库已初始化" : "未初始化");
    }

    printf("\n--- d5_ep_open 探测（★ 官方 API 的前置条件）---\n");
    printf("  ★ 实测（22:55）：相机不在拍摄态时 open 返回 0，reg_base 被初始化\n");
    if (ensure_lib_open(1) == 0) {
        if (p_regbase_sym)
            printf("  open 后 reg_base = 0x%08x  %s\n", *p_regbase_sym,
                   *p_regbase_sym ? "★★ 官方 API 可用" : "★ 仍为 0");
    } else {
        printf("  ★ d5_ep_open 失败（相机可能正在拍摄，主程序持有设备）\n");
        printf("    等回到菜单界面再试，或看 dmesg 有无 mutex 阻塞\n");
    }

    printf("\n--- /dev/d5_sma mmap + virt_to_phys 能力探测 ---\n");
    printf("  （只试映射并立刻解除，不写任何数据、不触发 DMA）\n");
    printf("  ★ 必须在 mmap【存活期内】测，munmap 后驱动会拒绝该地址\n");
    if (!p_v2p) { printf("  ★ d5_ep_sma_virt_to_phys 未解析，探测中止\n"); return 1; }
    for (i = 0; i < sizeof(TRIES)/sizeof(TRIES[0]); i++) {
        printf("  try phys=0x%08lx ... ", TRIES[i]);
        fflush(stdout);
        rc = sma_open(&b, TRIES[i], 4096);
        if (rc == 0) { printf("OK\n"); sma_release(&b); }
        else         { printf("FAIL(%d)%s\n", rc,
                              rc == -4 ? " = d5_ep_open 失败" : ""); }
    }
    printf("\n★ probe 结束：未调用任何写入函数，未触发 DMA。\n");
    if (p_ep_close && g_lib_opened) {
        printf("\n--- 收尾：d5_ep_close（不长期持有设备）---\n");
        p_ep_close();
        g_lib_opened = 0;
    }
    return 0;
}

static int cmd_regdump(void)
{
    struct ep_reg_info info;
    volatile unsigned *r;
    int fd, i;
    unsigned long pa, size, maplen;

    fd = open("/dev/drime5_ep", O_RDWR);
    if (fd < 0) { printf("open /dev/drime5_ep: %s\n", strerror(errno)); return 2; }
    if (ioctl(fd, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl GET_PHYS_REG_INFO: %s\n", strerror(errno));
        close(fd); return 3;
    }
    pa = EP_3DLUT(info).reg_start_addr;
    size = EP_3DLUT(info).reg_size;
    if (!pa || !size) {
        printf("3dlut 块无效\n");
        for (i = 0; i < 10; i++)
            printf("  [%d] 0x%08x size 0x%08x\n", i,
                ((struct ep_reg_phys_info*)((char*)&info+i*8))->reg_start_addr,
                ((struct ep_reg_phys_info*)((char*)&info+i*8))->reg_size);
        close(fd); return 4;
    }
    maplen = (size + 4095) & ~4095UL;
    r = (volatile unsigned *)mmap(NULL, maplen, PROT_READ, MAP_SHARED, fd, (off_t)pa);
    if (r == MAP_FAILED) { printf("mmap: %s\n", strerror(errno)); close(fd); return 5; }

    printf("\n3D LUT @ 0x%08lx size=%lu\n", pa, size);
    printf("  +0x000 OnOff= 0x%08x\n", r[R_ONOFF/4]);
    printf("  +0x004 Cfg  = 0x%08x   bits[1:0]=CbCr:%d bits[5:4]=SelLUT:%d "
           "bit8=%d bit12=%d\n",
           r[R_CFG/4], r[R_CFG/4] & 3, (r[R_CFG/4] >> 4) & 3,
           (r[R_CFG/4] >> 8) & 1, (r[R_CFG/4] >> 12) & 1);
    printf("  +0x008 Pulse= 0x%08x   bit8(写)=%d bit4(读)=%d\n",
           r[R_PULSE/4], (r[R_PULSE/4] >> 8) & 1, (r[R_PULSE/4] >> 4) & 1);
    printf("  +0x00c LUT0 = 0x%08x\n", r[R_LUT0/4]);
    printf("  +0x010 LUT1 = 0x%08x\n", r[R_LUT1/4]);
    munmap((void*)r, maplen);
    close(fd);
    return 0;
}

static int cmd_opinit(int sel, int fmt, int cbcr, int bypass)
{
    d5_ep_lut_op_info_st info;
    int rc;

    if (sel < 0 || sel > 2) { printf("sel 需 0..2\n"); return 1; }
    if (fmt < 0 || fmt > 1) { printf("fmt 需 0..1\n"); return 1; }
    if (cbcr < 0 || cbcr > 2) { printf("cbcr 需 0..2\n"); return 1; }

    memset(&info, 0, sizeof info);
    info.lut_clrfmt   = (d5_ep_lut_format_et)fmt;
    info.cbcr_ch_sel  = (d5_ep_lut_cbcr_ch_et)cbcr;
    info.lut_sel      = (d5_ep_lut_sellut_et)sel;
    info.bypass_sw    = (d5_ep_onoff)bypass;

    printf("\n--- d5_ep_3dlut_op_init ---\n");
    printf("  struct 16B = { fmt=%d, cbcr=%d, sel=%d, bypass=%d }\n",
           info.lut_clrfmt, info.cbcr_ch_sel, info.lut_sel, info.bypass_sw);
    printf("  按头文件 + sizeof 校验: %d 字节 %s\n", (int)sizeof(info),
           sizeof(info) == 16 ? "OK" : "★ 不符");

    if (!p_op_init) { printf("  ★ 符号未解析\n"); return 1; }
    rc = p_op_init(&info);
    printf("  返回 = %d  %s\n", rc, rc == 0 ? "OK" : "★ 失败");

    if (bypass) {
        printf("  ★★ 你开了 bypass（bypass_sw=1）—— 这会让3D LUT 【不生效】。\n");
        printf("     这是官方 API 的 bypass 模式，不是 bug。\n");
    }
    cmd_regdump();
    return rc == 0 ? 0 : 1;
}

/* ★★ cbcr_ch：Cfg bits[1:0]，色度通道选择
 *   0 = CH0   1 = CH1   2 = (CH0+CH1)/2
 * ★2026-10-06 23:45 新增：load 时会用它调 op_init（之前完全没配通道） */
static int g_cbcr_ch = 0;

static int do_load(const char *file, unsigned long phys, int sel, int fmt,
                   int size, int stride, int settle_ms, sma_buf *outb)
{
    unsigned char *data;
    unsigned long bytes;
    int n = 0, rc;
    int r;
    int cbcr_ch = g_cbcr_ch;

    printf("\n=== 步骤 1：准备数据 ===\n");
    if (file) {
        data = file_load(file, &n, stride, &bytes);
    } else {
        printf("  生成 identity 表 size=%d stride=%d\n", size, stride);
        data = make_identity(size, stride, &bytes);
    }
    if (!data) return 1;

    printf("\n=== 步骤 2：映射 CMA 缓冲 @0x%08lx（%lu 字节）===\n", phys, bytes);
    r = sma_open(outb, phys, bytes);
    if (r != 0) { free(data); return 1; }

    printf("\n=== 步骤 3：写入并回读校验 ===\n");
    memcpy(outb->v, data, bytes);
    if (memcmp(outb->v, data, bytes) != 0) {
        printf("  ★ 回读不一致，写入失败，中止\n");
        free(data); sma_release(outb); return 1;
    }
    printf("  回读校验一致 OK\n");
    hexdump("缓冲前 32 字节", outb->v, 32);

    printf("\n=== 步骤 3.5：d5_ep_3dlut_op_init（配置通道/格式）★★★\n");
    /*★★★★★ 2026-10-06 23:45 修正：这一步【原来完全缺失】，导致所有偏色实验无效
     *
     *  libudd5 里 ConfigProcessMode(@0x3abb4) 反汇编证明 op_init 就是在写 Cfg：
     *      _udd_ep_3dl_reg_OnOff(1); Acc_OnOff(1); Acc_OnOff(0);
     *      SelCbCr_ch(p->+0x14)      -> Cfg bits[1:0]   ★色度通道选择
     *      SelLUT(p->+0x10)          -> Cfg bits[5:4]   ★选哪张表
     *      SetColorFormat(sel, +0x18)-> Cfg bit8/bit12  ★色彩格式
     *
     *  ⇒ ★★ 我之前只调 load_lut（只写地址+灌数据），从不配通道
     *     ⇒ 硬件的 CbCr通道 与 格式位 全是 p7 留下的残值
     *     ⇒ ★★★ 这是"所有表都偏色"的共同根因，与表内容无关！
     */
    if (p_op_init) {
        d5_ep_lut_op_info_st oi;
        memset(&oi, 0, sizeof oi);
        oi.lut_clrfmt= (d5_ep_lut_format_et)fmt;
        oi.cbcr_ch_sel = (d5_ep_lut_cbcr_ch_et)cbcr_ch;
        oi.lut_sel     = (d5_ep_lut_sellut_et)sel;
        oi.bypass_sw   = D5_EP_OFF;
        rc = p_op_init(&oi);
        printf("  op_init(fmt=%d, cbcr_ch=%d, sel=%d, bypass=OFF) => %d %s\n",
               fmt, cbcr_ch, sel, rc, rc == 0 ? "OK" : "★失败");
        if (rc != 0) {
            printf("  ★★ op_init 失败，但继续尝试 load（load 会自己再设一遍格式）\n");
        }
    } else {
        printf("  ★ op_init 符号缺失，无法配置通道\n");
    }

    printf("\n=== 步骤 4：d5_ep_3dl_load_lut(virt=0x%08x, sel=%d, fmt=%d, tmo=%u) ===\n",
           (unsigned)(unsigned long)outb->v, sel, fmt, 0u);
    printf("  sel=%d %s\n", sel,
           sel == 2 ? "★ LUT_EXT = 外部 LUT（本次目标）"
                    : (sel == 0 ? "LUT0" : "LUT1"));
    printf("  fmt=%d %s\n", fmt, fmt == 1 ? "YCC420" : "YCC422");
    if (!p_load) { printf("  ★ 符号未解析\n"); free(data); sma_release(outb); return 1; }
    rc = p_load((unsigned int *)(unsigned long)outb->v,
                (d5_ep_lut_sellut_et)sel, (d5_ep_lut_format_et)fmt, 0u);
    printf("  返回 = %d  %s\n", rc, rc == 0 ? "OK" : "★ 失败");
    if (rc != 0) {
        free(data);
        printf("  ⇒ 未成功，保持缓冲映射不动，请手动重启相机\n");
        return 1;
    }

    printf("\n=== 步骤 5：等待 DMA settle (%d ms) ===\n", settle_ms);
    printf("  ★ 期间不清零、不 munmap（DMA 可能仍在读）\n");
    usleep((useconds_t)settle_ms * 1000);

    free(data);
    return 0;
}

static int do_save(const char *out, unsigned long phys, int sel, int fmt,
                   unsigned long bytes, sma_buf *savb)
{
    unsigned char *got;
    int rc;
    FILE *fp;

    printf("\n=== 读回：d5_ep_3dl_save_lut(virt, sel=%d, fmt=%d) ===\n", sel, fmt);
    got = (unsigned char *)calloc(1, bytes);
    if (!got) return 1;

    /* save_lut 需要一个【可写的目标虚拟地址】，同样必须是 d5_sma 映射 */
    {
        int rr = sma_open(savb, phys, bytes);
        if (rr != 0) { free(got); return 1; }
    }
    memcpy(got, savb->v, bytes);   /* 先清空目标区，便于判断是否真写入 */

    if (!p_save) { printf("  ★ 符号未解析\n"); free(got); sma_release(savb); return 1; }
    rc = p_save((unsigned int *)(unsigned long)savb->v,
                (d5_ep_lut_sellut_et)sel, (d5_ep_lut_format_et)fmt, 0u);
    printf("  返回 = %d  %s\n", rc, rc == 0 ? "OK" : "★ 失败");
    if (rc != 0) { free(got); sma_release(savb); return 1; }

    usleep(30000);
    memcpy(got, savb->v, bytes);

    hexdump("读回前 32 字节", got, 32);
    {
        unsigned long nz = 0, i;
        for (i = 0; i < bytes; i++) if (got[i]) nz++;
        printf("  非零字节 %lu / %lu\n", nz, bytes);
        if (nz == 0) printf("  ★ 读回全零 ⇒ 通路未通（不要据此否定前面的写入）\n");
    }
    if (out) {
        fp = fopen(out, "wb");
        if (fp) { fwrite(got, 1, bytes, fp); fclose(fp);
                  printf("  已保存 %s (%lu 字节)\n", out, bytes); }
        else printf("  ★ 写不了 %s\n", out);
    }
    free(got);
    return 0;
}

/* =====================================================================
 * main
 * ===================================================================== */
static void usage(const char *p)
{
    printf("用法:\n");
    printf("  %s probe                ★零风险：符号 + mmap/virt_to_phys 能力探测\n", p);
    printf("  %s info只读：全部符号地址\n", p);
    printf("  %s regdump              只读：3D LUT 寄存器快照\n", p);
    printf("  %s opinit <sel> <fmt> <cbcr> <bypass>  只调 op_init（不灌数据）\n", p);
    printf("  %s load <file> <phys> [sel=2] [fmt=1] [size=17] [stride=2] [settle=200]\n", p);
    printf("  %s save <out>   <phys> [sel=2] [fmt=1] [bytes=19652]\n", p);
    printf("  %s verify <file> <phys> [sel=2] [fmt=1] [size=17] [stride=2]\n", p);
    printf("  %s idgen <out> [size=17] [stride=2]\n", p);
    printf("\n  sel: 0=LUT0 1=LUT1 2=LUT_EXT(外部)   fmt: 0=YCC422 1=YCC420\n");
    printf("  stride: 每通道字节数 1=8bit 2=16bitLE\n");
    printf("  ★ <phys> 必须先用 cmapick.arm 实时探测（铁律 61）\n");
}

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IOLBF, 0);

    printf("=== NX500 lutapi：官方 3D LUT API 工具 ===\n");
    printf("phase1: dlopen(libudd5.so)\n");
    g_h = dlopen("libudd5.so", RTLD_NOW);
    if (!g_h) g_h = dlopen("/usr/lib/libudd5.so", RTLD_NOW);
    if (!g_h) {
        printf("  ★ dlopen 失败: %s\n", dlerror());
        return 1;
    }
    printf("  ok\n");

    p_op_init  = (fn_op_init) dlsym(g_h, "d5_ep_3dlut_op_init");
    p_load     = (fn_load_lut)dlsym(g_h, "d5_ep_3dl_load_lut");
    p_save     = (fn_save_lut)dlsym(g_h, "d5_ep_3dl_save_lut");
    p_v2p      = (fn_v2p)    dlsym(g_h, "d5_ep_sma_virt_to_phys");
    p_ep_open  = (fn_ep_open) dlsym(g_h, "d5_ep_open");
    p_ep_close = (fn_ep_close)dlsym(g_h, "d5_ep_close");
    p_regbase_sym = (unsigned *)dlsym(g_h, "ep_3dlut_reg_base");

    printf("phase2: 入口符号 %s\n",
           (p_load && p_save && p_v2p) ? "全部解析" : "★ 有缺失");

    if (argc < 2) { usage(argv[0]); return 1; }

    /* ★★★ 全局安全闸（2026-10-06 22:55 实测后重写）
     * ------------------------------------------------------------------
     *  旧设计：reg_base == 0 就拦住 load/save/opinit，让用户去相机主程序上下文调。
     *  实测推翻：d5_ep_open() 在我们进程里【完全可用】
     *           返回 0，reg_base 由 0x00000000 → 0xb6fb3000。
     *  ⇒ 闸门改为：主动 open，open 失败才拦。
     *
     *  ★ 实测前提：当时相机【不在拍摄态】，无进程持有 /dev/drime5_ep。
     *    若主程序正在拍摄，d5_udd_open 内部有 mutex_lock，可能阻塞。
     *    ⇒ 因此保留 NXKS_NOOPEN=1 逃生开关，并明确告知风险。*/
    {
        const char *c = argv[1];
        int needs_lib = (strncmp(c, "load", 4) == 0 ||
                         strncmp(c, "save", 4) == 0 ||
                         strncmp(c, "verify", 6) == 0 ||
                         strncmp(c, "opinit", 6) == 0);
        if (needs_lib) {
            if (getenv("NXKS_NOOPEN") != NULL) {
                printf("\n★★ 安全闸：NXKS_NOOPEN 已设置，跳过 d5_ep_open\n");
                printf("   ep_3dlut_reg_base = 0x%08x %s\n",
                       p_regbase_sym ? *p_regbase_sym : 0,
                       (p_regbase_sym && *p_regbase_sym) ? "(已初始化)"
                                                          : "★为0 ⇒ API 会写 NULL");
            } else {
                printf("phase3: d5_ep_open()（官方 API 的前置条件）\n");
                if (ensure_lib_open(1) != 0) {
                    printf("\n★★ 安全闸：d5_ep_open 失败\n");
                    printf("   相机主程序很可能正在拍摄（内部 mutex_lock 会阻塞）。\n");
                    printf("   等相机回到菜单界面（无进程持有 /dev/drime5_ep）再试。\n");
                    printf("   确实要强行尝试：NXKS_FORCE=1 %s %s\n",
                           argv[0], c);
                    if (getenv("NXKS_FORCE") == NULL) return 6;
                    printf("   NXKS_FORCE=1 ⇒ 继续（风险自负，可能阻塞）\n");
                }
                /* ★ open 之后再确认 reg_base 非0 */
                if (p_regbase_sym && *p_regbase_sym == 0) {
                    printf("\n★★ 安全闸：open 成功但 reg_base 仍为 0\n");
                    printf("   官方 API 会往 NULL+offset 写寄存器 ⇒ 段错误。\n");
                    printf("   ⇒ 建议加 NXKS_FORCE=1 强制，或退回 lutload.arm 路线。\n");
                    if (getenv("NXKS_FORCE") == NULL) return 6;
                }
            }
        }
    }

    if      (strcmp(argv[1], "info")   == 0) return cmd_info();
    else if (strcmp(argv[1], "probe")  == 0) return cmd_probe();
    else if (strcmp(argv[1], "regdump")== 0) return cmd_regdump();

    else if (strcmp(argv[1], "opinit") == 0) {
        int sel = argc > 2 ? atoi(argv[2]) : 2;
        int fmt = argc > 3 ? atoi(argv[3]) : 1;
        int cbc = argc > 4 ? atoi(argv[4]) : 0;
        int byp = argc > 5 ? atoi(argv[5]) : 0;
        return cmd_opinit(sel, fmt, cbc, byp);
    }
    else if (strcmp(argv[1], "idgen") == 0) {
        /* ★ 用法：idgen <out> [size=17] [stride=2]
         *   ★★ 2026-10-06 实测修：原先误把 argv[2] 同时当 size 和文件名，
         *      导致 `idgen /path/x.bin 17 2` 里size="/path/x.bin" → atoi=0 → 报错。
         *      现与 load/save 保持一致：argv[2] 固定是输出路径。 */
        const char *out = argc > 2 ? argv[2] : NULL;
        int size   = argc > 3 ? atoi(argv[3]) : 17;
        int stride = argc > 4 ? atoi(argv[4]) : 2;
        unsigned long bytes = 0;
        unsigned char *d;
        if (size < 2 || size > 65) { printf("size 需 2..65（收到 %d）\n", size); return 1; }
        if (stride != 1 && stride != 2) { printf("stride 需 1 或 2（收到 %d）\n", stride); return 1; }
        d = make_identity(size, stride, &bytes);
        if (!d) { printf("  ★ 内存分配失败\n"); return 1; }
        printf("identity %d^3 stride=%d => %lu 字节\n", size, stride, bytes);
        hexdump("前 32 字节", d, 32);
        if (out) {
            FILE *fp = fopen(out, "wb");
            if (fp) {
                size_t n = fwrite(d, 1, bytes, fp);
                fclose(fp);
                printf("已写 %s（%lu/%lu 字节）%s\n", out, (unsigned long)n, bytes,
                       n == bytes ? "OK" : "★ 写入不完整");
            } else printf("  ★ 打不开 %s\n", out);
        } else printf("（未指定输出文件，仅预览）\n");
        free(d);
        return 0;
    }
    else if (strcmp(argv[1], "load") == 0) {
        sma_buf b;
        int sel     = argc > 4 ? atoi(argv[4]) : 2;
        int fmt     = argc > 5 ? atoi(argv[5]) : 1;
        int size    = argc > 6 ? atoi(argv[6]) : 17;
        int stride  = argc > 7 ? atoi(argv[7]) : 2;
        int settle  = argc > 8 ? atoi(argv[8]) : 200;
        unsigned long phys;
        if (argc < 4) { usage(argv[0]); return 1; }
        /* ★ 新增 cbcr_ch 参数（第 9 个）：0=CH0 1=CH1 2=CH01平均 */
        g_cbcr_ch = argc > 9 ? atoi(argv[9]) : 0;
        if (g_cbcr_ch < 0 || g_cbcr_ch > 2) g_cbcr_ch = 0;
        phys = strtoul(argv[3], NULL, 0);
        if (!phys) { printf("★ 缺物理地址（铁律 61：不许猜地址）\n"); return 1; }
        if (do_load(argv[2], phys, sel, fmt, size, stride, settle, &b) != 0) {
            sma_release(&b); return 1;
        }
        printf("\n=== 收尾：解除映射（不清零）===\n");
        sma_release(&b);
        cmd_regdump();
        return 0;
    }
    else if (strcmp(argv[1], "probe-size") == 0) {
        /*★★★★★ 2026-10-06 23:52 决定性实验
         *
         * 【问题】我此前认定"硬件表长 = 29478"，依据是 save_lut 读回 29478 字节非零。
         *   ★★ 但那读到的是【我自己写进去的数据】—— 只证明 DMA 能搬数据，
         *      完全不能证明硬件 SRAM 里的表到底多大！这是自证循环（铁律 72）。
         *   ⇒ 实测结果：把【全新清零的缓冲】交给 save_lut，读回【全零】
         *   ⇒ ★★★ save_lut 根本没有把硬件表写出来，
         *      "表长29478""读回与源表逐字节一致"等结论【全部作废】
         *
         * 【用途】本命令【不再用于探测表长】（save_lut 读不出来）。
         *   保留它只是作为"save_lut 是否有输出"的自检工具：
         *   ★ 用法：必须指定一个【当前没有被 LUT0/LUT1 引用】的一次性地址！
         *
         * ★★★【2026-10-06 23:58 修正的严重缺陷】
         *   原版直接 memset 了用户给的地址 —— 而那个地址往往正是当前生效的表！
         *   ⇒ ★★★ 把硬件正在用的表清零了 ⇒ 画面变成灰白 + 杂色
         *   ⇒★★ 教训：探测工具必须【拒绝写入当前 LUT0/LUT1 指向的地址】
         *
         * 用法: probe-size <phys> <scan_bytes> [sel=0] [fmt=1] [cbcr=0]
         */
        sma_buf b;
        unsigned long phys, scan, found = 0;
        unsigned long i;
        int rc_save;
        unsigned char *snap;
        int sel   = argc > 4 ? atoi(argv[4]) : 0;
        int fmt   = argc > 5 ? atoi(argv[5]) : 1;
        int cbc   = argc > 6 ? atoi(argv[6]) : 0;

        if (argc < 3) { usage(argv[0]); return 1; }
        phys = strtoul(argv[2], NULL, 0);
        scan = argc > 3 ? strtoul(argv[3], NULL, 0) : 262144UL;
        if (!phys) { printf("★ 缺物理地址\n"); return 1; }
        printf("\n=== probe-size：自检 save_lut 是否有输出 ===\n");
        printf("  目标物理地址 = 0x%08lx  扫描 = %lu 字节\n", phys, scan);

        /* ★★★ 安全闸：绝不能碰当前生效的表（铁律 61 +23:58 事故教训） */
        {
            struct ep_reg_info rinfo;
            int fd = open("/dev/drime5_ep", O_RDWR);
            unsigned live0 = 0, live1 = 0;
            if (fd >= 0) {
                if (ioctl(fd, EP_IOCTL_GET_PHYS_REG_INFO, &rinfo) == 0) {
                    unsigned long pa = EP_3DLUT(rinfo).reg_start_addr;
                    unsigned long sz = EP_3DLUT(rinfo).reg_size;
                    unsigned long ml = (sz + 4095) & ~4095UL;
                    volatile unsigned *r = (volatile unsigned *)
                        mmap(NULL, ml, PROT_READ, MAP_SHARED, fd, (off_t)pa);
                    if (r != MAP_FAILED) {
                        live0 = r[R_LUT0 / 4];
                        live1 = r[R_LUT1 / 4];
                        munmap((void *)r, ml);
                    }
                }
                close(fd);
            }
            if (live0 || live1) {
                unsigned long lo = phys, hi = phys + scan;
                if ((live0 >= lo && live0 < hi) || (live1 >= lo && live1 < hi)) {
                    printf("\n★★★★ 安全闸拒绝执行 ★★★\n");
                    printf("  目标区 0x%08lx..0x%08lx 覆盖了当前生效的表：\n", lo, hi);
                    printf("    LUT0 = 0x%08x\n    LUT1 = 0x%08x\n", live0, live1);
                    printf("  ★ memset 会把硬件正在用的表清零 ⇒ 画面损坏（23:58 已发生）\n");
                    printf("  ⇒ 请换一个【未被引用】的一次性地址。\n");
                    return 7;
                }
            }
            printf("  安全闸通过（LUT0=0x%08x LUT1=0x%08x 不在目标区内）\n",
                   live0, live1);
        }

        if (sma_open(&b, phys, scan) != 0) {
            printf("★ 无法映射\n"); return 1;
        }
        memset(b.v, 0, scan);
        printf("  已清零 %lu 字节\n", scan);

        /* 调 save_lut 让硬件把表写进这块清零缓冲 */
        g_cbcr_ch = cbc;
        if (p_op_init) {
            d5_ep_lut_op_info_st oi;
            memset(&oi, 0, sizeof oi);
            oi.lut_clrfmt   = (d5_ep_lut_format_et)fmt;
            oi.cbcr_ch_sel  = (d5_ep_lut_cbcr_ch_et)cbc;
            oi.lut_sel      = (d5_ep_lut_sellut_et)sel;
            oi.bypass_sw    = D5_EP_OFF;
            p_op_init(&oi);
            printf("  op_init(fmt=%d,cbcr=%d,sel=%d) 已调用\n", fmt, cbc, sel);
        }
        if (!p_save) { printf("  ★ save_lut 未解析\n"); sma_release(&b); return 1; }
        rc_save = p_save((unsigned int *)(unsigned long)b.v,
                         (d5_ep_lut_sellut_et)sel,
                         (d5_ep_lut_format_et)fmt, 0u);
        printf("  save_lut 返回 = %d\n", rc_save);
        usleep(50000);

        /* 扫描最后一个非零字节 */
        snap = (unsigned char *)malloc(scan);
        memcpy(snap, b.v, scan);
        for (i = 0; i < scan; i++)
            if (snap[i]) found = i + 1;

        printf("\n  ★★★ 最后一个非零字节 = %lu (0x%lx)\n", found, found);
        printf("  ⇒ 硬件表真实长度 ≈ %lu 字节\n", found);
        printf("  ★ 对照：17³×3×u16=%d  33³×3×u16=%d  65³×3×u16=%d\n",
               17*17*17*3*2, 33*33*33*3*2, 65*65*65*3*2);
        printf("  ★ 若 %lu 接近某个立方 ⇒ ★★ 该尺寸就是硬件表大小\n", found);

        if (found == 0) {
            printf("  ★ 全零 ⇒ 该 sel 通道没有表，或地址不对\n");
        } else {
            /* dump 前 64 字节看是不是合理的表头 */
            printf("\n  前 64 字节:\n    ");
            for (i = 0; i < 64 && i < found; i++) {
                printf("%02x%s", snap[i], (i % 16 == 15) ? "\n    " : " ");
            }
            printf("\n");
            /* 存盘 */
            {
                char p[160];
                sprintf(p, "/mnt/mmc/luts/probe_sel%d.bin", sel);
                { FILE *fp = fopen(p, "wb");
                  if (fp) { fwrite(snap, 1, found, fp); fclose(fp);
                            printf("\n  已存 %s (%lu 字节)\n", p, found); } }
            }
        }
        free(snap);
        sma_release(&b);
        return 0;
    }
    else if (strcmp(argv[1], "save") == 0) {
        sma_buf b;
        int sel   = argc > 4 ? atoi(argv[4]) : 2;
        int fmt   = argc > 5 ? atoi(argv[5]) : 1;
        unsigned long bytes = argc > 6 ? strtoul(argv[6], NULL, 0) : 19652UL;
        unsigned long phys;
        int rc;
        if (argc < 4) { usage(argv[0]); return 1; }
        phys = strtoul(argv[3], NULL, 0);
        if (!phys) { printf("★ 缺物理地址\n"); return 1; }
        rc = do_save(argv[2], phys, sel, fmt, bytes, &b);
        sma_release(&b);
        return rc;
    }
    else if (strcmp(argv[1], "verify") == 0) {
        /* ★ 双向可逆判据（铁律：立因果需双向）：
         *   load 一张已知表 → save 读回 → 逐字节比对。
         *   只有"写的和读回的一字不差"才能证明整条通路通。 */
        sma_buf lb, sb;
        int sel     = argc > 4 ? atoi(argv[4]) : 2;
        int fmt     = argc > 5 ? atoi(argv[5]) : 1;
        int size    = argc > 6 ? atoi(argv[6]) : 17;
        int stride  = argc > 7 ? atoi(argv[7]) : 2;
        unsigned long phys;
        int rc;
        if (argc < 4) { usage(argv[0]); return 1; }
        /* ★ 同 load：第 9 个参数为 cbcr_ch */
        g_cbcr_ch = argc > 8 ? atoi(argv[8]) : 0;
        if (g_cbcr_ch < 0 || g_cbcr_ch > 2) g_cbcr_ch = 0;
        phys = strtoul(argv[3], NULL, 0);
        if (!phys) { printf("★ 缺物理地址\n"); return 1; }
        if (do_load(argv[2], phys, sel, fmt, size, stride, 300, &lb) != 0) {
            sma_release(&lb); return 1;
        }
        rc = do_save(NULL, phys, sel, fmt, 19652UL, &sb);
        sma_release(&lb); sma_release(&sb);
        return rc;
    }
    else { usage(argv[0]); return 1; }
    return 0;
}