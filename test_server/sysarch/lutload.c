/* lutload.c — NX-KS2 自定义 3D LUT 导入器
 *
 * =====================================================================
 *  ★★★★ 本工具的重大意义：把"LUT 数据必须改 p7"这个结论推翻了
 * ---------------------------------------------------------------------
 *  【10-06 下午的错误结论】
 *    "4 个预置 LUT 缓冲在 0x81xxxxxx，超出 Linux mem=512M
 *     ⇒ 用户态永远改不了 LUT 内容 ⇒ 魔灯必须改 p7"
 *
 *  【真相：libudd5 的 load_lut 走的是 WDMA 硬件 DMA】
 *    d5_ep_3dl_load_lut(buf, sel, lut_type, fmt)
 *      → d5_ep_sma_virt_to_phys(buf)      ← 拿【自己 CMA 缓冲】的物理地址
 *      → _udd_ep_3dl_ctrl_ConfigAccessMode
 *          → sub_3a888 (0x3a888)           ← 静态函数，无符号名
 *              OnOff(1) → Acc_OnOff(0) → Acc_OnOff(1)
 *              switch (sel) {
 *                case 0: SetAddress(*(p+8), *(p+4)); fmt(*(p+10), (*(p+8))[8])
 *                case 1: SetAddress(*(p+0xc), *(p+4)); fmt(*(p+10), (*(p+0xc))[8])
 *                case 2: SetAddress(*(p+8), *(p+4)); fmt(*(p+10), (*(p+8))[8])
 *                        SetAddress(*(p+0xc), *(p+4)); fmt(1, (*(p+0xc))[8])
 *              }
 *              SelLUT(sel)
 *              rw_Start(1)              ★★★ 关键：发起 DMA 搬运
 *
 *    其中 rw_Start(1) 反汇编（_udd_ep_3dl_reg_rw_Start @ 0x1fd9c）：
 *      GetReg(base+8) | = 0x100; SetReg(base+8);    ← 置bit8
 *      GetReg(base+8) &~ 0x100; SetReg(base+8);    ← 清 bit8（脉冲）
 *    rw_Start(≠1) 用bit4（读方向）
 *
 *  ⇒ ★★★ 硬件 DMA 把 CMA 缓冲"搬进"3DLUT 内部 RAM。
 *    这条通路【不要求 Linux 能读写 0x81xxxxxx】！
 *    ⇒ 只要缓冲区在 /dev/d5_sma（CMA）里就行 ⇒ **不需要改 p7**。
 *
 *  【与"4 档切换"的区别】
 *    4 档切换 = 往 +0x0c 写固件自己的常量地址（挂地址，不搬数据）
 *    本工具   = 往 +0x0c 写【我的 CMA 地址】+ rw_Start 脉冲（★ 硬件搬运）
 *
 * =====================================================================
 *  编译（★★铁律：必须 -O0，且所有 ioctl 号用字面量常量）
 *    cd test_server/sysarch
 *    "D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe" cc \
 *        -target arm-linux-gnueabi.2.15 -O0 -o lutload.arm lutload.c \
 *        -I D:/download/NX-KS2-88/.uploads/nx1_open/pkg/standard-armv7l/usr/include
 *
 *  用法：
 *    lutload.arm import <file.bin>   导入并激活（file = .cube 转出的 nxks 二进制）
 *    lutload.arm preset <0|1|2|3>    切到 4 个预置档
 *    lutload.arm restore              恢复出厂基线（档3）
 *    lutload.arm read只读回读寄存器
 * =====================================================================
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>

/* ★★★ 结构体：从 NX1 官方 GPL 头文件 d5_ep_type.h 直接抄（★权威，不是猜的）
 *   路径：NX1_packages / rootfs_dev/standard-armv7l/usr/include/media/drime5/ep/d5_ep_type.h
 *   ★ 注意字段是 unsigned int（32 位），不是 unsigned long！
 *   ★ 总共【10 块】：top / ldc / mc / rsz / lvr / bblt / fd / jpeg / 3dlut / nog
 *   ⇒ reg_base_3dlut 是第 9 块（0-based index 8）—— 与我们实测 10/10 吻合。*/
struct ep_reg_phys_info {
    unsigned int reg_start_addr;
    unsigned int reg_size;
};
struct ep_reg_info {
    struct ep_reg_phys_info reg_base_top;
    struct ep_reg_phys_info reg_base_ldc;
    struct ep_reg_phys_info reg_base_mc;
    struct ep_reg_phys_info reg_base_rsz;
    struct ep_reg_phys_info reg_base_lvr;
    struct ep_reg_phys_info reg_base_bblt;
    struct ep_reg_phys_info reg_base_fd;
    struct ep_reg_phys_info reg_base_jpeg;
    struct ep_reg_phys_info reg_base_3dlut;   /* index 8 */
    struct ep_reg_phys_info reg_base_nog;
};

/* ★★★ ioctl 号必须是字面量常量（铁律：自定义 IOC 宏 32 位溢出
 *     ⇒ zig -O0 生成非法指令 ⇒ SIGILL，症状极具误导性）
 *   官方：EP_IOCTL_GET_PHYS_REG_INFO = _IOR('h', 100, struct ep_reg_info)
 *   struct ep_reg_info = 10 块 × 8 字节 = 80
 *   _IOR('h',100,80) = (2<<30)|(80<<16)|('h'<<8)|100
 *   = (2<<30)=0x80000000 | (80<<16)=0x00500000 | 0x6800 | 0x64
 *   = 0x80506864   ★★ 与 eplut10 实测可用号完全一致（交叉验证） */
#define EP_IOCTL_GET_PHYS_REG_INFO  0x80506864UL

/* ---- 3D LUT 寄存器（p7 + libudd5 双向验证）---- */
#define R_ONOFF   0x000        /* bit0 = OnOff / Acc_OnOff 同bit  */
#define R_CFG     0x004        /* bits[1:0]=SelCbCr  bit8/12=色彩格式 */
#define R_PULSE   0x008        /* ★ bit8 = DMA 写脉冲(清零式)bit4 = 读 */
#define R_LUT0    0x00c        /* LUT0 数据物理地址 */
#define R_LUT1    0x010        /* LUT1 数据物理地址 */

/* ---- 4 个预置缓冲（p7 .data 常量，只读不可写）---- */
/* ★ 4 个预置缓冲（p7 .data 常量，只读不可写） */
static const unsigned int PRE[4] = {
    0x810fd100UL,  /* 0 标准：非单调 = 风格化曲线 */
    0x81101e00UL,  /* 1 黑白：完美线性 = 纯 identity */
    0x81106b00UL,  /* 2 电影：与档 0 内容相同 */
    0x81115200UL   /* 3 肤色：R↑G↓ = ★ 出厂 +0x00c 原值 */
};
static const char *PN[4] = {"标准", "黑白", "电影", "肤色(出厂)"};

#define FACTORY PRE[3]

/* ---- CMA 缓冲落点（★★ 实机探测结果，不是猜的）----
 *
 *  dmesg 实测：
 *    cma: CMA: reserved 288 MiB at 94000000
 *    cma: CMA: reserved  72 MiB at 8f800000
 *
 *  cmaprobe.arm 实测（144MB 区间，每 MB 采样）：
 *    0x94000000 .. 0x95300000  ⇒ 全部 zero（★ 连续 20MB 空闲）
 *    0x95400000 起⇒ 非零（CMA 正被 ISP 的 DMA 缓冲占用）
 *
 *  ⇒ 选0x94000000：区首、空闲、1MB 对齐、远离占用区 1MB 以上
 *  ⚠️ 不选 0x95400000 及以后：撞上正在跑的 DMA 缓冲 = 画面花/崩溃
 */
#define CMA_DEFAULT  0x94000000UL   /* ★ 已被占用！必须用 cmapick 实时选落点 */
static unsigned long g_phys = 0;     /* ★ 实际落点，0 = 用默认 */
#define CMA_MAX      65536UL         /* 64KB，足够 17³×3×2=29478 字节 */

/* ★★★★ 【2026-10-06 卡死事故后的加固】★★★★ ★★★
 *
 *  【事故】在 0x94000000 写 LUT =>相机卡死，拔电池才恢复
 *        dmesg: alloc_contig_range test_pages_isolated(91a40,91a79) failed
 *   ⇒★★ 那块内存是 ISP 的 WDMA 硬件工作区
 *      "探测时全 zero" != "可以安全独占"（★ 铁律 61）
 *
 *  【SMA_ALLOC 动态分配：实测不可用】
 *    扫描 12 种参数组合（size 1B~4MB / addr 作 hint / size=0）=> 全部 EFAULT
 *    dmesg: d4_cma_alloc failed. Device is null or invalid argument
 *    ⇒★★★ 三星这个驱动只给内核内部用，不给用户态分配
 *
 *  【★ 关键收获：VIRT_TO_PHYS 可用，但只认自己 mmap 的映射】
 *    malloc 堆        => 返回 0（不支持）
 *    mmap 匿名=> 返回 0（不支持）
 *    mmap /dev/d5_sma => ★★ 返回精确的物理地址
 *    ⇒ ★ 我们现在能【核对】物理地址，不必再靠"写完回读"间接判断
 *
 *  【★★ 使用纪律（铁律 61 的具体落实）】
 *    1. import 前用 VIRT_TO_PHYS 核对地址，不靠猜
 *    2. ★ 导入完成立即释放映射，不让硬件长期引用
 *    3. 出现异常先重启，不要在不确定状态下反复试
 */

/* ★★ 官方 SMA ioctl（NX1 GPL 头文件权威，★ 已与 libudd5 交叉验证） */
#define SMA_GET_REGION_SIZE       0x80047301UL
#define SMA_VIRT_TO_PHYS          0xc0047302UL
#define SMA_GET_REGION_START_ADDR 0x80047304UL

/* ★★ 核对物理地址：唯一可靠的验证手段 */
static unsigned int verify_phys(int fds, void *vaddr)
{
    unsigned int p = (unsigned int)(unsigned long)vaddr;
    if (ioctl(fds, SMA_VIRT_TO_PHYS, &p) < 0) return 0;
    return p;
}

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

/* ★ 官方结构体只有 10 块，3dlut 是 index 8（0-based）
   ⇒ 直接用具名字段更安全（编译期即可校验） */
#define EP_3DLUT(info)  ((info).reg_base_3dlut)

/* ================================================================
 * ★ 完整的 11 步序列（libudd5 sub_3a888 + rw_Start 逆向）
 * ================================================================ */
static int g_cbcr_ch = 0;     /* SelCbCr_ch值（bits[1:0]），-1 = 不改 */
static int g_fmt = -1;       /* bit8/bit12 格式位，-1 = 不改；1 = LUT0 fmt=1 */
#define cbcr_ch g_cbcr_ch

static int do_write_seq(volatile unsigned *b, unsigned long phys, int sel, int fmt)
{
    unsigned v;

    /* ---- 步骤 1~3：开模块 + 访问开关脉冲 ---- */
    b[R_ONOFF / 4] |= 1UL;               /* ① OnOff(1) */
    b[R_PULSE / 4] &= ~1UL;/* ② 脉冲清0 */
    b[R_PULSE / 4] |= 1UL;               /* ③ 置位（硬件接受启动）*/

/* ---- 步骤 4：色彩格式（bit8=LUT0fmt / bit12=LUT1 fmt）
     * ★★★★ 2026-10-06 18:47 重大修正：
     *   p7 prepare 后 +0x004 = 0x00000100（bit8 = 1）
     *   而我此前一律写 0⇒ 与 p7 的设置不匹配
     *   ⇒ 表现为【结构正确但整体粉红偏色】（实测截图确认）
     * ★★ 修法：**完全不碰 bit8/bit12**，只改 bits[1:0] 和 bits[5:4]。
     *     格式设置交回 p7 —— 它比我们更清楚该用什么格式。
     */
    /* ★ 故意不设置 bit8/bit12 —— 保留硬件/p7 现有值 */
    /* ★★ 但若 g_fmt >= 0，则显式设置（单变量实验用）*/
    if (g_fmt >= 0) {
        v = b[R_CFG / 4];
        if (g_fmt & 1) v |= 0x0100UL;  else v &= ~0x0100UL;   /* bit8  = LUT0 fmt */
        if (g_fmt & 2) v |= 0x1000UL;  else v &= ~0x1000UL;   /* bit12 = LUT1 fmt */
        b[R_CFG / 4] = v;
    }

    /* ---- 步骤 5~8：SelCbCr_ch（+0x004 bits[1:0]）★★★
     * 【2026-10-06 定案修正】之前这里强制写 0，是花屏的直接原因之一。
     * dump 实验证明：DMA 搬运长度 = 提供的字节数（9248 字节一字不差读回），
     * 而硬件内部表远大于 9248 ⇒ 必须【按通道分别写】。
     * libudd5的 sub_3a888 switch(sel) 里 case 0/1/2 各写不同地址槽，
     * 说明 sel 本身就是"通道/表选择"，不该固定 0。       */
    if (cbcr_ch >= 0) {
        v = b[R_CFG / 4];
        v &= ~0x3UL;
        v |= ((unsigned)cbcr_ch & 3);
        b[R_CFG / 4] = v;
    }

    /* ---- 步骤 9：SetAddress（sub_3a7e4 → _udd_ep_3dl_reg_SetAddress）
     *   ★★★ 与 p7 侧的 4b4 不同：这里 which=1 → 写 +0x0c，which=2 → +0x10
     *       我们的数据一律放 LUT0 ⇒ which=1 ---- */
    b[R_LUT0 / 4] = (unsigned)phys;

    /* ---- 步骤 10：SelLUT（+0x004 bits[5:4]）★ 注意这里不是 bits[1:0] ---- */
    v = b[R_CFG / 4];
    v &= ~0x30UL;                         /* 清bits[5:4] */
    v |= ((unsigned)(sel & 3)) << 4;      /* sel → bits[5:4] */
    b[R_CFG / 4] = v;

    /* ---- 步骤 11：rw_Start(1) —— ★★★ 发起硬件 DMA 搬运
     *   libudd5 反汇编：GetReg(+8)|=0x100 → SetReg → &=~0x100 → SetReg
     *   这是 write-1-clear 脉冲，硬件在下降沿执行搬运。           */
    v = b[R_PULSE / 4];
    v |= 0x100UL;                         /* 置bit8 */
    b[R_PULSE / 4] = v;
    v &= ~0x100UL;                        /* ★ 清bit8 = 触发 */
    b[R_PULSE / 4] = v;

    /* ---- 步骤 12（读侧清理，来自 p7 FUN_004cf484(1)）---- */
    v = b[R_PULSE / 4];
    v &= ~0x100UL;                /* 二次确保 */
    b[R_PULSE / 4] = v;

    usleep(5000);
    return 0;
}

/* ================================================================
 * ★★★ safe_restore —— 只改指针，【绝不触发 DMA】
 *---------------------------------------------------------------------
 *  【2026-10-06 血的教训】
 *  旧的 restore 走完整 do_write_seq，其中步骤 11 无条件 rw_Start(1)
 *  ⇒ 它把 0x81115200 的内容【又 DMA 灌进硬件】一次
 *  ⇒ ★★ 而 0x81115200 的内容必须由 p7 的 FUN_0009a3e8 先"准备"
 *  ⇒ ★★ 没prepare 就灌 = 把过期/未初始化数据灌进硬件 ⇒ 画面依然偏色
 *⇒ ★★★ 所以"恢复出厂"必须只改指针，让下一次 ISP 重载（半按对焦）
 *      自己从 p7 拿正确数据。绝不主动 DMA。
 * ================================================================ */
static void safe_restore(volatile unsigned *b)
{
    unsigned v;
    printf("\n=== 安全恢复：仅改指针 + 触发 ISP 重载信号 ===\n");
    /* ① 指针指回出厂表地址 */
    b[R_LUT0 / 4] = (unsigned)FACTORY;
    b[R_LUT1 / 4] = (unsigned)FACTORY;
    /* ② 清掉我们写过的通道/格式选择，让 ISP 用自己的默认值 */
    v = b[R_CFG / 4];
    /* ★★ 只清 bits[1:0]（CbCr）与 bits[5:4]（SelLUT）
     * ★★ bit8/bit12 是【色彩格式】★ 不要清★ —— p7 prepare 后 = 0x100，
     *     清掉它会导致偏色（2026-10-06 实测）*/
    v &= ~0x0033UL;
    b[R_CFG / 4] = v;
    /* ③ ★★★ 关键：不写 rw_Start 脉冲！让 p7 在下一次 AF 时自己灌 */
    /*    只清 bit8/bit4 确保没有挂起的 DMA 请求 */
    v = b[R_PULSE / 4];
    v &= ~0x110UL;
    b[R_PULSE / 4] = v;
    printf("  +0x00c = 0x%08x (出厂表)\n", b[R_LUT0 / 4]);
    printf("  +0x004 = 0x%08x (清通道/格式选择)\n", b[R_CFG / 4]);
    printf("  +0x008 = 0x%08x (无 DMA 挂起)\n", b[R_PULSE / 4]);
    printf("\n★ 现在请【半按快门对焦】—— p7 会重新从 0x81115200灌入正确表\n");
    printf("  这一步才是真正的恢复。★\n");
    usleep(5000);
}

static void dump(volatile unsigned *b, const char *tag)
{
    printf("  [%s]\n", tag);
    printf("    +0x000 OnOff = 0x%08x\n", b[R_ONOFF / 4]);
    printf("    +0x004 Cfg   = 0x%08x  (bits[1:0]=CbCr  bits[5:4]=SelLUT)\n", b[R_CFG / 4]);
    printf("    +0x008 Pulse = 0x%08x\n", b[R_PULSE / 4]);
    printf("    +0x00c LUT0  = 0x%08x\n", b[R_LUT0 / 4]);
    printf("    +0x010 LUT1  = 0x%08x\n", b[R_LUT1 / 4]);
}

/* ================================================================
 * ★★★ dump：把硬件 3D LUT 表【读回】CMA 缓冲
 *---------------------------------------------------------------------
 * 这是【定案LUT 格式】的决定性工具。
 *
 * 依据 libudd5 逆向：
 *   sub_3a888 (写)末尾 = SelLUT(sel); rw_Start(1)   ← 1 = 写方向
 *   sub_3a9e0 (读) 末尾 = SelLUT(sel); rw_Start(2)   ← 2 = 读方向 ★
 *  ⇒ 硬件支持把内部表【读出来】到 CMA 缓冲。
 *  ⇒ 直接读出厂表逐字节分析 ⇒ 不用再猜 8/16-bit、单/三通道、级数。
 *
 * ★★ 读法（sub_3a9e0 的对称结构）：
 *   OnOff(1) → Acc(0) → Acc(1)
 *   switch(sel) { case 0/1/2: SetAddress(p[+8] or [+0xc], which) }
 *   SelLUT(sel)
 *   rw_Start(2)                ← bit4 = 读方向
 *
 * 用法: dump [sel] [max_bytes]
 *   sel = 0..3（通道号，逐个试）
 *   max_bytes = 最多读多少（默认 65536）
 *   → 打印到 stdout，同时写 /mnt/mmc/luts/dump_chN.bin
 * ================================================================ */
static int do_dump(int fd_ep, volatile unsigned *b, int sel, unsigned max_bytes, int cbc)
{
    unsigned long phys = (g_phys ? g_phys : CMA_DEFAULT);     /* 读回目标 = 同一块 CMA */
    int fds;
    unsigned char *lp;
    unsigned npages;
    unsigned v;
    unsigned i;
    unsigned long nonzero = 0;
    char path[128];

    printf("\n=== dump SelLUT=%d CbCr=%d：从硬件读回 LUT 表到 0x%08lx ===\n", sel, cbc, phys);

    /* ---- 序列（照sub_3a9e0）---- */
    b[R_ONOFF / 4] |= 1UL;               /* OnOff(1) */
    b[R_PULSE / 4] &= ~1UL;              /* Acc(0)  */
    b[R_PULSE / 4] |= 1UL;               /* Acc(1)  */

    /* SelLUT(sel) → bits[5:4] */
    v = b[R_CFG / 4];
    v &= ~0x30UL;
    v |= ((unsigned)(sel & 3)) << 4;
    /* ★★ 同时设置 SelCbCr_ch（bits[1:0]）—— 用它区分不同色彩通道的表 */
    v &= ~0x3UL;
    v |= ((unsigned)(cbc & 3));
    b[R_CFG / 4] = v;
    b[R_LUT0 / 4] = (unsigned)phys;

    /* rw_Start(2) = 读方向：bit4 */
    v = b[R_PULSE / 4];
    v |= 0x10UL;
    b[R_PULSE / 4] = v;
    v &= ~0x10UL;
    b[R_PULSE / 4] = v;

    usleep(20000);                        /* ★ 读比写慢，多等一会儿 */

    /* ---- 从 CMA 读出 ---- */
    fds = open("/dev/d5_sma", O_RDWR);
    if (fds < 0) { printf("open d5_sma: %s\n", strerror(errno)); return 1; }
    npages = (max_bytes + 4095) & ~4095UL;
    lp = (unsigned char *)mmap(NULL, npages, PROT_READ | PROT_WRITE,
                               MAP_SHARED, fds, (off_t)phys);
    if (lp == MAP_FAILED) {
        printf("mmap CMA: %s\n", strerror(errno));
        close(fds); return 1;
    }

    printf("读回前64 字节: ");
    for (i = 0; i < 64 && i < max_bytes; i++) {
        printf("%02x ", lp[i]);
        if (lp[i]) nonzero++;
    }
    printf("\n");

    /* 找第一个连续零区，估算真实表长 */
    {
        unsigned long last_nonzero = 0;
        for (i = 0; i < max_bytes; i++) {
            if (lp[i]) { last_nonzero = i; nonzero++; }
        }
        printf("非零字节总数: %lu\n", nonzero);
        printf("最后非零偏移  : %lu (0x%lx)\n", last_nonzero, last_nonzero);
        printf("★ 若最后非零 ≈ 4912 ⇒ 4913 字节单通道；若 ≈14738 ⇒ 三通道 8-bit；\n"
               "  若 ≈29477 ⇒ 三通道 16-bit\n");
        printf("\n★ 16-bit 解读（每2 字节一通道值，小端）前 32 个值:\n   ");
        for (i = 0; i < 32 && (i + 1) * 2 <= max_bytes; i++) {
            unsigned short s = (unsigned short)(lp[i*2] | (lp[i*2+1] << 8));
            printf("%04x ", s);
        }
        printf("\n★ 8-bit 解读（每字节一通道值）前 48 个值:\n   ");
        for (i = 0; i < 48 && i < max_bytes; i++) printf("%02x ", lp[i]);
        printf("\n");
    }

    /* 存文件 */
    sprintf(path, "/mnt/mmc/luts/dump_s%d_c%d.bin", sel, cbc);
    {
        FILE *fp = fopen(path, "wb");
        if (fp) { fwrite(lp, 1, max_bytes, fp); fclose(fp);
                  printf("\n已保存: %s (%u 字节)\n", path, max_bytes); }
        else printf("\n★ 无法写 %s\n", path);
    }

    munmap(lp, npages);
    close(fds);
    printf("恢复出厂...\n");
    return 0;
}

/* ================================================================
 * 主流程
 * ================================================================ */
int main(int argc, char **argv)
{
    struct ep_reg_info info;
    unsigned long pa, size, map_len;
    volatile unsigned *b;
    int fd_ep, i, rc = 0;
    unsigned v;

    if (argc < 2) {
        printf("用法:\n");
        printf("  %s import <file.bin>   导入并激活自定义 LUT\n", argv[0]);
        printf("  %s preset <0|1|2|3>切到预置档\n", argv[0]);
        printf("  %s restore            恢复出厂基线\n", argv[0]);
        printf("  %s read               只读回寄存器\n", argv[0]);
        printf("  %s dump [sel] [n] [cbc]★从硬件读回（sel=SelLUT cbc=SelCbCr_ch）\n", argv[0]);
        printf("\n预置档: 0=标准 1=黑白 2=电影 3=肤色(出厂)\n");
        return 1;
    }

    /* ---- 打开 EP，取权威地址 ---- */
    fd_ep = open("/dev/drime5_ep", O_RDWR);
    if (fd_ep < 0) { printf("open /dev/drime5_ep: %s\n", strerror(errno)); return 2; }
    if (ioctl(fd_ep, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl GET_PHYS_REG_INFO: %s\n", strerror(errno));
        printf("★ 若 ioctl 号错：改用 0x80506864（_IOR('h',100,...)）字面量\n");
        return 3;
    }
    /* ★ 3DLUT = 官方结构体第 9 块（reg_base_3dlut，index 8）*/
    pa  = EP_3DLUT(info).reg_start_addr;
    size = EP_3DLUT(info).reg_size;
    if (pa == 0 || size == 0) {
        printf("EP 3dlut 块地址无效 pa=%lx size=%lx\n", pa, size);
        printf("  ★ 打印全部 10 块诊断：\n");
        for (i = 0; i < 10; i++)
            printf("    [%d] 0x%08x  size 0x%08x\n", i,
                   blk(&info, i)->reg_start_addr, blk(&info, i)->reg_size);
        return 4;
    }
    map_len = (size + 4095) & ~4095UL;
    b = (volatile unsigned *)mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd_ep, (off_t)pa);
    if (b == MAP_FAILED) { printf("mmap EP fail: %s\n", strerror(errno)); return 5; }

    printf("3DLUT @0x%08lx  size=%lu  %p\n", pa, size, (void *)b);
    printf("\n--- 写入前 ---\n");
    dump(b, "before");

    /* ---- 分支 ---- */
    if (strcmp(argv[1], "settle") == 0) {
        /*★★★★★★★★★★ A 方案核心：只读轮询，不写任何寄存器 ★★★★★★★★★★
         * 依据（静态分析）：CBackend_3dlut_View::_run @0x11e3b4
         *   mov r0, #4 ; bl 0x80524664   ← r0=4 ⇒ 不等 DMA
         * 而 Still::_run 会等到 'load Done' ⇒ 照片正常（P2 实测）
         * ⇒★ 取景器花屏是【时序竞态】：DMA 未搬完它就开始读
         * ⇒★ 本命令【什么都不写】，只等待 + 读回状态，让 DMA 有时间完成
         */
        int rounds = (argc > 2) ? atoi(argv[2]) : 20;
        int i;
        printf("=== settle：等待 3D LUT DMA 完成（纯只读，不写寄存器）===\n");
        for (i = 0; i < rounds; i++) {
            volatile unsigned *bb = b;
            unsigned pulse = bb[R_PULSE / 4];
            unsigned cfg   = bb[R_CFG / 4];
            unsigned lut0  = bb[R_LUT0 / 4];
            printf("  [%2d] Pulse=0x%08x bit8=%d  Cfg=0x%08x  LUT0=0x%08x\n",
                   i, pulse, (pulse >> 8) & 1, cfg, lut0);
            /* bit8 = rw_Start 触发位；硬件 DMA 期间通常保持 1，清零表示完成 */
            if (((pulse >> 8) & 1) == 0) {
                printf("★★ bit8 已清零 ⇒ DMA 完成（第 %d 轮）\n", i);
                printf("★ 可安全让取景器读表了\n");
                rc = 0;
                break;
            }
            usleep(300000);      /* 300 ms */
        }
        if (i >= rounds) {
            printf("★ 等了 %d 轮仍未见 bit8 清零（可能 DMA 已完成，位已复用）\n", rounds);
            printf("★ 不影响：表已在 CMA 中，p7 会自行读取\n");
        }
    }
    else if (strcmp(argv[1], "poke") == 0) {
        /* ★★★【最安全】只往 CMA 物理内存写数据，绝不碰任何 EP 寄存器。
         *   用途：刷 p7 指针前，先把一张已知表放到目标地址。
         *   ⇒ 不触发 DMA、不写寄存器 ⇒ 不可能花屏/卡死。           */
        unsigned long phys;
        unsigned long np2;
        void *pp;
        FILE *fp;
        long fsz2;
        unsigned char *b2;
        int fds2;
        size_t got2;

        phys = (argc > 2) ? strtoul(argv[2], NULL, 0) : 0;
        if (phys == 0 || printf("用法: %s poke <phys_addr> <file>\n", argv[0]), 0) { }
        if (phys == 0) { printf("用法: %s poke <phys_addr> <file>\n", argv[0]); rc = 1; goto out; }
        if (argc < 4) { printf("缺少文件参数\n"); rc = 1; goto out; }

        fp = fopen(argv[3], "rb");
        if (!fp) { printf("打不开 %s\n", argv[3]); rc = 1; goto out; }
        fseek(fp, 0, SEEK_END); fsz2 = ftell(fp); fseek(fp, 0, SEEK_SET);
        printf("文件 %s = %ld 字节\n", argv[3], fsz2);
        if (fsz2 <= 0 || fsz2 > 65536) { printf("大小不合法\n"); fclose(fp); rc = 1; goto out; }
        b2 = (unsigned char *)malloc(fsz2);
        got2 = fread(b2, 1, fsz2, fp);
        fclose(fp);
        if ((long)got2 != fsz2) { printf("读取不完整\n"); free(b2); rc = 1; goto out; }

        fds2 = open("/dev/d5_sma", O_RDWR);
        if (fds2 < 0) { printf("打不开 /dev/d5_sma\n"); free(b2); rc = 1; goto out; }
        np2 = (fsz2 + 4095) & ~4095UL;
        pp = mmap(NULL, np2, PROT_READ | PROT_WRITE, MAP_SHARED, fds2, (off_t)phys);
        if (pp == MAP_FAILED) {
            printf("mmap 0x%08lx 失败\n", phys);
            close(fds2); free(b2); rc = 1; goto out;
        }
        {
            unsigned int real = verify_phys(fds2, pp);
            printf("VIRT_TO_PHYS => 0x%08x  (期望 0x%08lx) %s\n", real, phys,
                   real == phys ? "★ 匹配" : "★ 不匹配");
            if (real != phys) {
                printf("⇒ 地址对不上，中止（不写任何数据）\n");
                munmap(pp, np2); close(fds2); free(b2); rc = 3; goto out;
            }
        }
        memcpy(pp, b2, fsz2);
        printf("已写入 %ld 字节，回读校验: %s\n", fsz2,
               memcmp(pp, b2, fsz2) == 0 ? "★ 一致" : "★ 不一致");
        printf("★ 未触碰任何 EP 寄存器（未触发 DMA）\n");
        /*★★★★★★ A 方案核心：表【必须留在 CMA 里】供 p7 读取
         *   之前 imp﻿ort 的"用完即还"会清零落点 ⇒ p7 读到全零 ⇒ 花屏
         *   ⇒★ 此处只解除映射，绝不清零内容。*/
        printf("★★ 落点内容【保留不清零】，供 p7 读取（2026-10-06 A 方案）\n");
        munmap(pp, np2); close(fds2); free(b2);
    }
    else if (strcmp(argv[1], "dump") == 0) {
        /* ★ 从硬件读回 LUT 表 —— 格式定案工具 */
        int sel = (argc > 2) ? atoi(argv[2]) : 0;
        unsigned nb = (argc > 3) ? (unsigned)atoi(argv[3]) : 65536UL;
        int cbc = (argc > 4) ? atoi(argv[4]) : 0;
        if (sel < 0 || sel > 3) { printf("SelLUT 需 0..3\n"); rc = 1; }
        else {
            printf("=== dump 前置状态 ===\n");
            dump(b, "before");
            do_dump(fd_ep, b, sel, nb, cbc);
            printf("\n=== dump 后寄存器 ===\n");
            dump(b, "after");
            /* ★★★ dump 后只改指针，让 p7 自己重载（★ 旧代码在这里错误地触发了 DMA）*/
            printf("\n>>> 安全恢复（仅改指针，请半按快门对焦完成恢复）<<<\n");
            safe_restore(b);
            dump(b, "restored");
        }
    }
    else if (strcmp(argv[1], "read") == 0) {
        /* 只读模式 */
        unsigned long cur = b[R_LUT0 / 4];
        int i;
        printf("\n当前 LUT0 地址 = 0x%08lx\n", cur);
        for (i = 0; i < 4; i++) {
            if (cur == PRE[i]) { printf("==> 匹配预置档[%d] %s\n", i, PN[i]); return 0; }
        }
        printf("==> 非预置地址（可能是自定义 CMA LUT）\n");
        return 0;
    }
    else if (strcmp(argv[1], "restore") == 0) {
        printf("\n=== 恢复出厂基线 %s（安全版）===\n", PN[3]);
        safe_restore(b);
        dump(b, "after");
        printf("\n★ 已改指针。请【半按快门对焦】让 p7 重新灌入正确表。\n");
    }
    else if (strcmp(argv[1], "preset") == 0) {
        int s = (argc > 2) ? atoi(argv[2]) : 3;
        if (s < 0 || s > 3) { printf("档位需0..3\n"); rc = 1; }
        else {
            printf("\n=== 切到预置档[%d] %s (0x%08x) ===\n", s, PN[s], PRE[s]);
            printf("★★★ 安全模式：只改指针，让 p7 自己从该地址灌入\n");
            printf("    （★ 不主动 DMA —— 那会把未准备好的缓冲灌进硬件）\n");
            b[R_LUT0 / 4] = (unsigned)PRE[s];
            b[R_LUT1 / 4] = (unsigned)PRE[s];
            {
                unsigned vv = b[R_CFG / 4];
                vv &= ~0x0033UL;       /* ★ 只清 CbCr+SelLUT，不清 bit8 格式位 */
                b[R_CFG / 4] = vv;
                vv = b[R_PULSE / 4];
                vv &= ~0x110UL;          /* ★ 不置bit8/bit4 = 不触发 DMA */
                b[R_PULSE / 4] = vv;
            }
            dump(b, "after");
            printf("\n★ 请【半按快门对焦】触发 p7 重新灌表。\n");
        }
    }
    else if (strcmp(argv[1], "import") == 0) {
        int fds;
        unsigned char *lp;
        FILE *fp;
        long fsz;
        unsigned char *buf;
        size_t got;
        unsigned long phys;      /* ★★★ 必须在参数解析【之后】赋值（19:04 bug）*/
        unsigned long npages;

        /* ★★ 第 3 参数 = fmt：显式设置 bit8(LUT0 格式)
         *   用法: import <file> [fmt]   fmt: 0 / 1 / 缺省(不改)
         *   ★ p7 出厂态 bit8=1；此前我一律写 0 ⇒ 粉红偏色（18:47 实测）*/
        if (argc > 3) g_fmt = atoi(argv[3]);
        if (argc > 4) g_cbcr_ch = atoi(argv[4]);
        /* ★★ 第 5 参数 = CMA 物理落点（★ 必须用 cmapick.arm 实时探测）
         *   用法: import <file> [fmt] [cbcr] [phys]
         *   ★ 铁律 61：不要用默认值 0x94000000，那块已被 ISP 占用！*/
        if (argc > 5) g_phys = strtoul(argv[5], NULL, 0);
        /* ★★★ 关键：参数解析完成后才决定落点（★ 19:04 修复的 bug）
         *   之前 phys 在声明时就用 g_phys 求值，那时g_phys 还是 0
         *   ⇒ 打印说用了新地址，实际仍用旧的（已占用）地址。*/
        phys = g_phys ? g_phys : CMA_DEFAULT;
        printf("import: fmt=%d cbcr=%d phys=0x%08lx %s\n",
               g_fmt, g_cbcr_ch, phys,
               g_phys ? "(指定)" : "★默认（可能已被占用，建议用 cmapick 指定）");
        printf("import 参数: fmt=%d (bit8=%s)  cbcr=%d\n",
               g_fmt, (g_fmt < 0 ? "不变" : (g_fmt & 1 ? "1" : "0")), g_cbcr_ch);

        if (argc < 3) { printf("需要文件名\n"); rc = 1; goto out; }
        fp = fopen(argv[2], "rb");
        if (!fp) { printf("打开 %s: %s\n", argv[2], strerror(errno)); rc = 1; goto out; }
        fseek(fp, 0, SEEK_END); fsz = ftell(fp); fseek(fp, 0, SEEK_SET);
        if (fsz <= 0 || fsz > (long)CMA_MAX) {
            printf("文件大小 %ld 不合法（需 1..%lu 字节）\n", fsz, CMA_MAX);
            printf("  参考：单通道 17 级 8-bit = 4913B / 16-bit = 9826B\n");
            printf("        三通道 17 级 8-bit = 14739B / 16-bit = 29478B\n");
            fclose(fp); rc = 1; goto out;
        }
        if (fsz < 512) {
            printf("★ 文件仅 %ld 字节 —— 可能不是完整 LUT。\n", fsz);
            printf("  单通道 17 级 8-bit 应为 4913 字节。\n");
            printf("  太小会让硬件读到越界数据 ⇒ 花屏。\n");
            fclose(fp); rc = 1; goto out;
        }
        buf = (unsigned char *)malloc(fsz);
        got = fread(buf, 1, fsz, fp);
        fclose(fp);
        if (got != (size_t)fsz) { printf("读取不完整 %lu/%ld\n", (unsigned long)got, fsz); free(buf); rc = 1; goto out; }

        printf("\n=== 步骤 0：LUT 数据 → CMA 0x%08lx (%ld 字节) ===\n", phys, fsz);
        fds = open("/dev/d5_sma", O_RDWR);
        if (fds < 0) { printf("open /dev/d5_sma: %s\n", strerror(errno)); free(buf); rc = 1; goto out; }
        npages = ((unsigned long)fsz + 4095) & ~4095UL;
        lp = (unsigned char *)mmap(NULL, npages, PROT_READ | PROT_WRITE,
                                   MAP_SHARED, fds, (off_t)phys);
        if (lp == MAP_FAILED) {
            printf("★ mmap CMA 失败: %s\n", strerror(errno));
            printf("  ⇒ CMA 地址 0x%08lx 可能不合法。\n", phys);
            printf("  ⇒ 需要先探测一个可用的 CMA 物理地址。\n");
            free(buf); close(fds); rc = 1; goto out;
        }
        /* ★★ 新增：用官方 VIRT_TO_PHYS 核对物理地址（铁律 61 落实）
         *   mmap 成功只说明虚拟映射建了；这一条才证明物理地址对得上 */
        {
            unsigned int real = verify_phys(fds, lp);
            printf("  VIRT_TO_PHYS => 0x%08x  (期望 0x%08lx) %s\n",
                   real, phys,
                   real == phys ? "★ 匹配" : "★ 不匹配（可能是普通内存）");
            if (real != phys) {
                printf("  ⇒★★ 物理地址对不上，硬件 DMA 会读到错误数据。\n");
                printf("      建议改用 lutload.arm 提供的其它落点，或先探测。\n");
                free(buf); munmap(lp, npages); close(fds); rc = 3; goto out;
            }
        }
        memcpy(lp, buf, fsz);
        /* ★ 回读校验（铁律：写入必须回读） */
        if (memcmp(lp, buf, fsz) != 0) {
            printf("★ 回读校验不一致！CMA 写入可能失败\n");
        } else {
            printf("  回读校验一致 ✔\n");
        }
        printf("  前 16 字节: ");
        { int k; for (k = 0; k < 16 && k < fsz; k++) printf("%02x ", lp[k]); }
        printf("\n");
        munmap(lp, npages);
        close(fds);
        free(buf);

        /* ---- 步骤 1~11：完整写入序列（含 rw_Start DMA 脉冲）---- */
        printf("\n=== 步骤 1-11：11 步写入序列（含 rw_Start DMA 脉冲）===\n");
        do_write_seq(b, phys, 0, 0);
        dump(b, "after");
        printf("\n★★★ 请看取景器！\n");

        /* ★★★ 纪律 2（铁律 61）：DMA 完成后【立即清零并释放】
         *   卡死的直接原因 = 硬件长期引用我写入的内存，
         *   而那块内存同时被 ISP 需要 ⇒ 冲突。
         *   ⇒ "用完即还"把冲突窗口压到最小。
         *   ★ 注意：清零不会影响已灌入硬件的内容（DMA 是异步的，
         *     do_write_seq 内部已usleep 等它完成）。*/
        {
            int fds2 = open("/dev/d5_sma", O_RDWR);
            if (fds2 >= 0) {
                unsigned long np2 = (fsz + 4095) & ~4095UL;
                void *rel = mmap(NULL, np2, PROT_READ | PROT_WRITE,
                                 MAP_SHARED, fds2, (off_t)phys);
                if (rel != MAP_FAILED) {
                    memset(rel, 0, fsz);
                    printf("\n★ 已清零落点 0x%08lx（%ld 字节）并即将释放\n",
                           phys, fsz);
                    munmap(rel, np2);
                } else {
                    printf("\n★ 重新mmap 失败，无法清零（0x%08lx）\n", phys);
                }
                close(fds2);
            }
        }
        printf("    恢复出厂: %s restore（★ 只改指针，请半按快门对焦）\n", argv[0]);
    }
    else {
        printf("未知命令: %s\n", argv[1]);
        rc = 1;
    }

out:
    munmap((void *)b, map_len);
    close(fd_ep);
    return rc;
}