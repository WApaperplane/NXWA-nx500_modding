/* epinfo.c — NX-KS2 步骤 2a：EP 块物理地址权威查询（只读，零风险）
 *
 * ★★★ 这是整个魔灯路线的钥匙：
 *   内核提供 EP_IOCTL_GET_PHYS_REG_INFO，一次 ioctl 就能拿到全部 10 个
 *   EP 子块的**权威物理地址 + 大小**。再也不用猜地址、不用解析 ELF、
 *   不用跨进程读指针、不用 /dev/mem。
 *
 * 源码依据（NX500 opensource 2015-03-04）：
 *   linux-3.5/drivers/media/video/drime5/ep/d5_ep_ioctl.c
 *     case EP_IOCTL_GET_PHYS_REG_INFO:
 *       ep_get_reg_info(&ep_reg_info);          // memcpy(&reg_info, 80)
 *       copy_to_user(arg, &ep_reg_info, size);
 *   linux-3.5/drivers/media/video/drime5/ep/d5_ep.c
 *     int d5_ep_open(...)  { filp->private_data = g_ep; d5_kdd_open(KDD_EP); }
 *         ★ 零硬件初始化：没有 request_irq / ioremap / 时钟配置
 *     int d5_ep_mmap(...)  { io_remap_pfn_range(vma, vm_start, vm_pgoff, size, ...); }
 *         ★ vm_pgoff 直接就是物理页帧号
 *
 * ★ 本步骤只做【读】：open + ioctl(GET_PHYS_REG_INFO) + 打印。
 *   不 mmap、不写任何寄存器。
 *
 * 结构体定义来自官方用户态头（与内核源码同源，勿手抄）：
 *   #include <media/drime5/ep/d5_ep_ioctl.h>
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

/* 块名表：顺序必须与 struct ep_reg_info 严格一致 */
static const char *NAMES[] = {
    "top  ", "ldc  ", "mc   ", "rsz  ", "lvr  ",
    "bblt ", "fd   ", "jpeg ", "3dlut", "nog  "
};

#define NBLK ((int)(sizeof(NAMES) / sizeof(NAMES[0])))

/* 取第 i 块：结构体是数组式排列，直接按指针算 */
static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

int main(void)
{
    struct ep_reg_info info;
    int fd, i, ret;

    printf("=== NX-KS2 EP 块物理地址权威查询（只读）===\n\n");

    /* ---- (1) 打开 EP 设备 ---- */
    fd = open("/dev/drime5_ep", O_RDONLY);
    if (fd < 0) {
        printf("open(/dev/drime5_ep) 失败: %s\n", strerror(errno));
        printf("  · 节点应该存在（char 10:126），若失败检查权限/驱动\n");
        return 2;
    }
    printf("open(/dev/drime5_ep) = fd %d  ★成功\n", fd);
    printf("  源码保证：open 只做 d5_kdd_open(KDD_EP) 电源计数，**零硬件初始化**\n\n");

    /* ---- (2) 一次 ioctl 拿到 10 个块的地址 ---- */
    memset(&info, 0, sizeof(info));
    printf("ioctl(_IOR('h',100, struct ep_reg_info))...\n");
    printf("  请求号 = 0x%08x  sizeof(struct ep_reg_info) = %d\n\n",
           (unsigned)EP_IOCTL_GET_PHYS_REG_INFO, (int)sizeof(info));

    ret = ioctl(fd, EP_IOCTL_GET_PHYS_REG_INFO, &info);
    if (ret < 0) {
        printf("ioctl 失败: %s\n", strerror(errno));
        printf("  · errno=%d  若是 ENOTTY(25)/ENODEV(19) => 驱动未绑定或号不对\n", errno);
        close(fd);
        return 3;
    }
    printf("ioctl 成功 ★★\n\n");

    /* ---- (3) 打印 10 个块 ---- */
    printf("--- EP 10 个子块（内核权威）---\n");
    printf("%-7s %-12s %-10s %-10s\n", "block", "phys_start", "size", "end");
    for (i = 0; i < NBLK; i++) {
        struct ep_reg_phys_info *b = blk(&info, i);
        printf("%-7s 0x%08x   0x%08x   0x%08x\n",
               NAMES[i], b->reg_start_addr, b->reg_size,
               b->reg_start_addr + b->reg_size);
    }

    /* ---- (4) 与此前 /dev/mem 实测值交叉验证 ---- */
    printf("\n--- 与 /dev/mem 读侧历史实测交叉验证 ---\n");
    {
        static const unsigned expect[NBLK] = {
            0x20820000, 0x20823000, 0x20824000, 0x20826000, 0x20827000,
            0x20828000, 0x20829000, 0x2082a000, 0x2082b000, 0x20821c00
        };
        int ok = 0;
        for (i = 0; i < NBLK; i++) {
            struct ep_reg_phys_info *b = blk(&info, i);
            int match = (b->reg_start_addr == expect[i]);
            printf("  %-7s kernel=0x%08x  mem侧=0x%08x  %s\n",
                   NAMES[i], b->reg_start_addr, expect[i],
                   match ? "✓ 一致" : "✗ 不一致");
            if (match) ok++;
        }
        printf("\n  => %d/%d 一致\n", ok, NBLK);
        if (ok == NBLK)
            printf("  ★★★ 内核与 /dev/mem 双向闭环成立，地址权威可信\n");
    }

    /* ---- (5) 3DLUT 块详情（魔灯目标）---- */
    {
        struct ep_reg_phys_info *b = blk(&info, 8);   /* reg_base_3dlut */
        printf("\n--- 3DLUT 块（魔灯目标）---\n");
        printf("  phys_start = 0x%08x\n", b->reg_start_addr);
        printf("  size       = 0x%08x (%d bytes)\n", b->reg_size, b->reg_size);
        if (b->reg_size == 0) {
            printf("  ⚠ size 为 0！块未启用或probe 未跑\n");
        } else {
            printf("\n  下一步（步骤 2b，只读 mmap 验证）将用：\n");
            printf("    fd  = open(\"/dev/drime5_ep\", O_RDONLY);\n");
            printf("    p   = mmap(NULL, 0x%x, PROT_READ, MAP_SHARED, fd, 0x%x);\n",
                   b->reg_size, b->reg_start_addr >> 12);
            printf("  ★ offset = reg_start_addr >> 12（页帧号）\n");
            printf("  ★ 只需 PROT_READ 先 dump 现有值，零风险\n");
        }
    }

    close(fd);
    printf("\n=== 结束：只做 open+ioctl+读，未 mmap，未写任何寄存器 ===\n");
    return 0;
}