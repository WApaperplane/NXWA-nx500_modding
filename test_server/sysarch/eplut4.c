/* eplut4.c — NX-KS2 步骤 4：用 SMA_ALLOC 分配真正的 CMA 内存并写入 3DLUT
 *
 * ★★★★ 与 eplut3.c 的区别（这是 eplut3 失败的原因）：
 *   eplut3 用 posix_memalign + /dev/mem 硬写 0x81115200 —— 那个地址
 *   ★ 不在 CMA 区（0x0e000000..0x20000000），是固件残留默认值 ⇒ 无效。
 *
 *   本探针用**内核提供的正确接口**：
 *     fd = open("/dev/d5_sma", O_RDWR);
 *     struct SMA_Buffer_Info info = {0, size};
 *     ioctl(fd, SMA_ALLOC, &info);      // ★ 返回 CMA 里的【物理地址】
 *     mmap 那个物理地址 → 写入 LUT 数据
 *     写进 3DLUT 的 +0x0c，然后脉冲
 *
 * ★ SMA ioctl 表（源码 include/media/drime5/sma/d5_sma_ioctl.h）：
 *   SMA_GET_REGION_SIZE       _IOR ('s', 1, uint)
 *   SMA_VIRT_TO_PHYS          _IOWR('s', 2, uint)   ★ 对普通堆内存返回 0
 *   SMA_SET_CACHE             _IOWR('s', 3, int)
 *   SMA_GET_REGION_START_ADDR _IOR ('s', 4, uint)
 *   SMA_ALLOC                 _IOWR('s', 5, SMA_Buffer_Info)   ★★ 本探针用这个
 *   SMA_FREE                  _IOW ('s', 6, uint)   （参数是虚拟地址）
 *   SMA_FREE_PHYS             _IOW ('s', 7, uint)   （参数是物理地址）
 *   SMA_GET_ALLOCATED_SIZE    _IOR ('s', 8, uint)
 *   SMA_CACHE_FLUSH           _IOWR('s', 9, SMA_Buffer_Info)
 *   SMA_CONTROL_PREBUFFER     _IOW ('s',10, uint)
 *   struct SMA_Buffer_Info { unsigned addr; unsigned size; }   ★ 只有 2 个字段
 *
 * 用法:
 *   eplut4 region              只读：查 CMA 区大小与已用量
 *   eplut4 put <mode>          分配 + 写入 + 挂到3DLUT（会改画面）
 *          mode: 0=identity 1=提亮 2=压暗 3=R/G反相 4=灰阶
 *   eplut4 restore            恢复原 +0x0c 值
 *
 * ★ 恢复：进程退出前会把原值打印出来；也可用 restore 子命令。
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
#include <media/drime5/sma/d5_sma_ioctl.h>

#define R_START     0x08
#define R_LUT0_ADDR 0x0c
#define NSLOT       16
#define SLOTSZ      0x100

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

static void gen_lut(unsigned char *buf, int mode)
{
    int i;
    memset(buf, 0, SLOTSZ);
    for (i = 0; i < 256; i++) {
        unsigned char r, g, bl;
        switch (mode) {
        case 0:  r = g = bl = (unsigned char)i; break;
        case 1:  r = g = bl = (unsigned char)(i + 51); break;
        case 2:  r = g = bl = (unsigned char)(i > 51 ? i - 51 : 0); break;
        case 3:  r = (unsigned char)i; g = (unsigned char)(255 - i); bl = 0; break;
        case 4:  { int y = (i * 77) / 255;  r = g = bl = (unsigned char)y; } break;
        default: r = g = bl = (unsigned char)i; break;
        }
        buf[i * 3 + 0] = r;
        buf[i * 3 + 1] = g;
        buf[i * 3 + 2] = bl;
    }
}

int main(int argc, char **argv)
{
    struct ep_reg_info info;
    struct SMA_Buffer_Info binfo;
    unsigned long pa, size;
    volatile unsigned *b;
    unsigned char *map_base;
    unsigned long map_len;
    unsigned v;
    int fd_ep, fd_sma, i;
    const char *cmd;

    if (argc < 2) {
        printf("用法: %s region | put <mode> | restore\n", argv[0]);
        return 1;
    }
    cmd = argv[1];

    fd_sma = open("/dev/d5_sma", O_RDWR);
    if (fd_sma < 0) { printf("open(/dev/d5_sma) 失败: %s\n", strerror(errno)); return 2; }
    fd_ep = open("/dev/drime5_ep", O_RDWR);
    if (fd_ep < 0) { printf("open(EP) 失败: %s\n", strerror(errno)); return 3; }
    printf("open: d5_sma=%d drime5_ep=%d  ★\n", fd_sma, fd_ep);

    if (ioctl(fd_ep, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl(GET_PHYS_REG_INFO) 失败: %s\n", strerror(errno));
        return 4;
    }
    pa = blk(&info, 8)->reg_start_addr;
    size = blk(&info, 8)->reg_size;
    map_len = (size + 4095) & ~4095UL;
    map_base = mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd_ep, (off_t)pa);
    if (map_base == MAP_FAILED) { printf("mmap EP 失败\n"); return 5; }
    b = (volatile unsigned *)map_base;
    printf("3dlut @0x%08lx = %p\n\n", pa, (void *)map_base);

    /* ---------- 只读：CMA 区信息 ---------- */
    if (strcmp(cmd, "region") == 0) {
        unsigned rstart = 0, rsize = 0, used = 0;
        if (ioctl(fd_sma, SMA_GET_REGION_START_ADDR, &rstart) < 0)
            printf("SMA_GET_REGION_START_ADDR 失败: %s\n", strerror(errno));
        if (ioctl(fd_sma, SMA_GET_REGION_SIZE, &rsize) < 0)
            printf("SMA_GET_REGION_SIZE 失败: %s\n", strerror(errno));
        if (ioctl(fd_sma, SMA_GET_ALLOCATED_SIZE, &used) < 0)
            printf("SMA_GET_ALLOCATED_SIZE 失败: %s\n", strerror(errno));
        printf("--- CMA / SMA 区---\n");
        printf("  region start = 0x%08x\n", rstart);
        printf("  region size  = 0x%08x (%u bytes)\n", rsize, rsize);
        printf("  allocated    = 0x%08x (%u bytes)\n", used, used);
        printf("  free         = 0x%08x\n", rsize - used);
        printf("\n  ★ 对比 3DLUT 现有 LUT 地址 0x81115200\n");
        printf("    在区内? %s\n",
               (0x81115200 >= rstart && 0x81115200 < rstart + rsize) ? "是" : "★ 否（证实是残留值）");
        goto out;
    }

    /* ---------- 恢复 ---------- */
    if (strcmp(cmd, "restore") == 0) {
        unsigned orig = (unsigned)strtoul("0x81115200", NULL, 0);
        printf("把 16 个槽的 +0x0c 恢复为 0x%08x\n", orig);
        for (i = 0; i < NSLOT; i++)
            b[(i * SLOTSZ + R_LUT0_ADDR) / 4] = orig;
        b[R_START / 4] = 0x100;
        usleep(2000);
        printf("已恢复并发脉冲\n");
        goto out;
    }

    /* ---------- put ---------- */
    if (strcmp(cmd, "put") == 0) {
        int mode = (argc > 2) ? atoi(argv[2]) : 0;
        unsigned long map_va;
        unsigned char *lut;

        printf("--- 当前 16 槽 +0x0c ---\n");
        for (i = 0; i < 4; i++)
            printf("  slot %2d = 0x%08x\n", i, b[(i * SLOTSZ + R_LUT0_ADDR) / 4]);

        /* ★★★ 关键：用内核分配真正的 CMA 内存 */
        memset(&binfo, 0, sizeof(binfo));
        /* ★ 256 会 EFAULT：d5_cma_alloc 走 cma_alloc，需页对齐/最小块
         *   逐级试探，找出最小可用尺寸 */
        {
            static unsigned tries[] = { 0x100, 0x1000, 0x1000, 0x4000, 0x10000 };
            unsigned t;
            int ok = 0;
            for (t = 0; t < sizeof(tries)/sizeof(tries[0]); t++) {
                memset(&binfo, 0, sizeof(binfo));
                binfo.size = tries[t];
                binfo.addr = 0;
                if (ioctl(fd_sma, SMA_ALLOC, &binfo) == 0) {
                    printf("  SMA_ALLOC(0x%x) 成功 -> phys=0x%08x\n",
                           tries[t], binfo.addr);
                    ok = 1;
                    break;
                }
                printf("  SMA_ALLOC(0x%x) 失败: %s\n", tries[t], strerror(errno));
            }
            if (!ok) { printf("  ★ 所有尺寸都失败\n"); goto out; }
        }
        binfo.addr = 0;
        printf("\nSMA_ALLOC(size=0x%x) ...\n", binfo.size);
        if (ioctl(fd_sma, SMA_ALLOC, &binfo) < 0) {
            printf("  ★ SMA_ALLOC 失败: %s\n", strerror(errno));
            printf("  ⇒ CMA 区可能已耗尽，或需要 CAP_SYS_ADMIN\n");
            goto out;
        }
        printf("  ★ 分配成功: phys=0x%08x size=0x%08x\n", binfo.addr, binfo.size);

        if (binfo.addr == 0 || (binfo.addr & 0xff) != 0) {
            printf("  ⚠ phys 未 256 对齐（0x%08x）—— libudd5 的 load_lut 会拒绝\n", binfo.addr);
        }

        /* 把 CMA 物理地址映射到本进程虚拟空间 */
        map_va = (unsigned long)mmap(NULL, (binfo.size + 4095) & ~4095UL,
                                    PROT_READ | PROT_WRITE, MAP_SHARED,
                                    fd_sma, (off_t)binfo.addr);
        if (map_va == (unsigned long)MAP_FAILED) {
            printf("  mmap CMA 失败: %s\n", strerror(errno));
            printf("  ⇒ 试 fallback：直接往 phys 写（需要 /dev/mem）\n");
            goto out;
        }
        lut = (unsigned char *)map_va;
        printf("  ★ CMA 已映射到 vaddr=0x%08lx\n", map_va);

        gen_lut(lut, mode);
        printf("  LUT 已生成 (mode=%d)\n", mode);

        /* 写进3DLUT 的 16 个槽 */
        printf("\n--- 写入 16 槽 +0x0c = 0x%08x ---\n", binfo.addr);
        for (i = 0; i < NSLOT; i++)
            b[(i * SLOTSZ + R_LUT0_ADDR) / 4] = binfo.addr;
        printf("  读回验证 slot0 = 0x%08x\n", b[R_LUT0_ADDR / 4]);

        printf("\n--- 发启动脉冲 ---\n");
        b[R_START / 4] = 0x100;
        usleep(2000);
        v = b[R_START / 4];
        printf("  +0x08 = 0x%08x %s\n", v, v == 0 ? "(硬件自清)" : "(待清)");

        printf("\n★★请看取景器（mode=%d）：画面有变化吗？\n", mode);
        printf("   恢复：%s restore\n", argv[0]);
        printf("   释放 CMA：ioctl(d5_sma, SMA_FREE_PHYS, 0x%08x)\n", binfo.addr);
    }

out:
    munmap(map_base, map_len);
    close(fd_ep);
    close(fd_sma);
    return 0;
}