/* epmc.c — Q3 极轻量探针：只读 mc 块，不压死相机
 *
 * ★★★ 为什么单独写这个文件（两次压死相机换来的教训）
 *
 *   epgamma.arm 首版一次跑完 10 块扫描 + 全量十六进制 dump，
 *   在单核 NX500 上把相机压到重启两次（12:06、12:20）。
 *   ⇒ 读 EP 寄存器本身不重（28KB），重的是【长时间不 sleep 的连续读 + 大量 printf】。
 *   ⇒ ★★ 单核相机铁律的真正含义不是"nice -n 19"，
 *      而是【任何循环都必须周期性让出，且总量必须小】。
 *
 * ★★★ 本文件的全部设计围绕一件事：让进程【尽快退出】
 *   ·只读 1 个块（默认 mc）
 *   · 只读 N 个寄存器（默认 64，可选）
 *   · 每读 16 个 usleep(2000)
 *   · 输出极简：只有 hex 行，没有长表格
 *   · 正常路径 3 段以内结束 ⇒ 实测应在 1 秒内退出
 *
 * 用法（★ 一次只跑一条，别堆叠）：
 *   epmc                读 mc 块前 64 个寄存器
 *   epmc 2 32           读 idx=2(mc) 的前 32 个
 *   epmc 9 64           读 idx=9(nog) 的前 64 个
 *   epmc 8 4            读 3dlut 前 4 个（自证用，最轻）
 *
 * ★★★ v2 新增：nzonly 模式（★ 本项目最关键的一个优化）
 *   事故链：256 regs ✅ → 768 regs ✅ → 1024 regs ✘ 压死相机（12:28、12:36 两次）
 *   ⇒ 复盘结论：**危险的不是读了多少字节，是 stdout 输出了多少行**
 *     （铁律 88：危险 ∝ 循环长度 × 输出量，∝ 数据量几乎无关）
 *   ⇒ 正确解法不是"读得更小心"，而是【把输出压到最小】：
 *     nzonly 只打印非零寄存器及其偏移 ⇒ 8KB 全块预计只几十行
 *   ⇒ 这样一次上机就能扫完整块，输出量降一到两个数量级。
 *
 *   ★ nzonly用法：
 *   epmc 2 2048 nz           只列非零寄存器 + 偏移（可扫全 8KB）
 *   epmc 2 2048 nz 0x400     只列非零 + 只看 ≥0x400 的部分
 *
 * ★ 判读：
 *   mc 块非零 ⇒它是活跃参数面，gamma/color【可能】在里面（H1 部分成立）
 *   mc 块全零 ⇒ 参数不在 EP 可见面（H2 增强）⇒ 固件层应关闭
 *   nog 只有 256B ⇒ 它能装的东西极少，NOG 参数大概率不在寄存器里
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>

#include <media/drime5/ep/d5_ep_ioctl.h>

int main(int argc, char **argv)
{
    struct ep_reg_info info;
    struct ep_reg_phys_info *rp;
    unsigned long pa, size, msize, mbase;
    volatile unsigned *p, *b;
    int idx =2, nreg = 64, i, fd;
    int nzonly = 0;                /* ★ v2：只打印非零 */
    unsigned long from = 0;         /* ★ v2：起始偏移（字节）*/

    if (argc > 1 && argv[1][0] >= '0' && argv[1][0] <= '9') idx  = atoi(argv[1]);
    if (argc > 2 && argv[2][0] >= '0' && argv[2][0] <= '9') nreg = atoi(argv[2]);
    if (argc > 3 && !strcmp(argv[3], "nz")) {
        nzonly = 1;
        if (argc > 4) from = strtoul(argv[4], NULL, 0);
    }
    if (idx < 0 || idx > 9) { printf("idx 0..9\n"); return 1; }
    if (nreg < 1 || nreg > 2048) { printf("nreg 1..2048\n"); return 1; }

    nice(19);

    fd = open("/dev/drime5_ep", O_RDONLY);   /* ★ 只读 */
    if (fd < 0) { printf("open fail %s\n", strerror(errno)); return 2; }

    memset(&info, 0, sizeof(info));
    if (ioctl(fd, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl fail %s\n", strerror(errno));
        return 3;
    }
    rp = (struct ep_reg_phys_info *)((char *)&info + idx * 8);
    pa = rp->reg_start_addr;
    size = rp->reg_size;
    printf("idx=%d phys=0x%08lx size=0x%04lx nreg=%d%s from=0x%04lx\n",
           idx, pa, size, nreg, nzonly ? " NZONLY" : "", from);
    fflush(stdout);

    if (size == 0) { printf("size=0\n"); close(fd); return 4; }

    msize = (size + 4095) & ~4095UL;
    mbase = pa & ~4095UL;
    p = (volatile unsigned *)mmap(NULL, msize, PROT_READ, MAP_SHARED,
                                  fd, (off_t)mbase);
    if (p == MAP_FAILED) {
        printf("mmap fail %s\n", strerror(errno));
        close(fd);
        return 5;
    }
    b = p + ((pa - mbase) / 4);

    /* ★★★ v2 nzonly：只输出非零，输出量降一到两个数量级
     *   ⇒ 这是让"一次扫完整块"变得可行的关键（不是读得更小心，是输得更少）*/
    if (nzonly) {
        int nz = 0;
        int start = (int)(from / 4);
        if (start < 0) start = 0;
        for (i = start; i < nreg; i++) {
            if (b[i]) {
                printf("  +0x%04x = 0x%08x\n", (unsigned)(i * 4), b[i]);
                nz++;
            }
            if ((i & 0x3f) == 0x3f) usleep(1000);   /* ★ 每 64 regs 让出 1ms */
        }
        printf("NZ nonzero %d/%d (from 0x%04lx)\n", nz, nreg - start, from);
    } else {
        /* 极简输出：每行 4 个寄存器 */
        int nz = 0;
        for (i = 0; i < nreg; i++) {
            if (i % 4 == 0) printf("  +0x%03x:", (unsigned)(i * 4));
            printf(" %08x", b[i]);
            if (b[i]) nz++;
            if (i % 4 == 3) { printf("\n"); fflush(stdout); usleep(2000); }
        }
        if (i % 4) printf("\n");
        printf("nonzero %d/%d\n", nz, nreg);
    }

    munmap((void *)p, msize);
    close(fd);
    return 0;
}
