/* eplut7.c — NX-KS2 步骤 7：最小路径写入 CMA（★ 已验证 /dev/d5_sma 可写）
 *
 * ★★★ mmtest.arm 已实测：
 *     open("/dev/d5_sma", O_RDWR) + mmap(PROT_WRITE, offset=phys)
 *     ⇒ 写入成功（O_SYNC 与否都行）
 *   ⇒★★ **CMA 内存可写！** 之前的 SIGSEGV 是别的原因。
 *
 * ★ 与 eplut6 的差异：eplut6 先 mmap 了 EP 块再 mmap CMA，然后崩。
 *   本探针★严格按 mmtest 的顺序：先只做 CMA 的读+写，不碰 EP。
 *   分两步跑：write（只写 CMA，打印校验）→ 然后再跑 attach（挂到 3DLUT）。
 *
 * 用法:
 *   eplut7 write <phys> <mode>   分配+写入 LUT（不碰 EP）
 *   eplut7 attach <phys>         把该地址挂到 3DLUT 16 槽 + 发脉冲
 *   eplut7 restore               恢复
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

#define R_START     0x08
#define R_LUT0_ADDR 0x0c
#define NSLOT       16
#define SLOTSZ      0x100
#define ORIG_LUT    0x81115200UL

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

static void gen_lut(unsigned char *buf, int mode)
{
    int i;
    memset(buf, 0, 32);
    for (i = 0; i < 11; i++) {
        unsigned char r, g, bl;
        switch (mode) {
        case 0:  r = g = bl = (unsigned char)i; break;
        case 1:  r = g = bl = (unsigned char)(i + 51); break;
        case 2:  r = g = bl = (unsigned char)(i > 51 ? i - 51 : 0); break;
        case 3:  r = (unsigned char)i; g = (unsigned char)(255 - i); bl = 0; break;
        case 4:  { int y = (i * 77) / 255; r = g = bl = (unsigned char)y; } break;
        default: r = g = bl = (unsigned char)i; break;
        }
        buf[i * 3 + 0] = r;
        buf[i * 3 + 1] = g;
        buf[i * 3 + 2] = bl;
    }
}

int main(int argc, char **argv)
{
    unsigned long target;
    int fd, i;

    if (argc < 3) {
        printf("用法: %s write <phys> <mode> | attach <phys> | restore\n", argv[0]);
        return 1;
    }
    target = strtoul(argv[2], NULL, 0);

    /* ================= write：只碰 CMA ================= */
    if (strcmp(argv[1], "write") == 0) {
        int mode = (argc > 3) ? atoi(argv[3]) : 0;
        unsigned char tmp[SLOTSZ];
        unsigned char *p;
        int bad;

        fd = open("/dev/d5_sma", O_RDWR);
        if (fd < 0) { printf("open: %s\n", strerror(errno)); return 2; }
        printf("open(/dev/d5_sma, O_RDWR) = %d\n", fd);

        /* 先只读确认 */
        p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, (off_t)target);
        if (p == MAP_FAILED) { printf("mmap RO fail: %s\n", strerror(errno)); return 3; }
        printf("mmap RO  = %p  read[0..3]: %08x %08x %08x %08x\n",
               (void *)p, p[0], p[1], p[2], p[3]);
        munmap((void *)p, 4096);

        /* 再可写 */
        p = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd, (off_t)target);
        if (p == MAP_FAILED) { printf("mmap RW fail: %s\n", strerror(errno)); return 4; }
        printf("mmap RW  = %p  ★\n", (void *)p);

        gen_lut(tmp, mode);
        printf("写入 256 字节 (mode=%d)...\n", mode);
        memcpy((void *)p, tmp, SLOTSZ);
        bad = memcmp((void *)p, tmp, SLOTSZ);
        printf("读回校验: %s\n", bad ? "★不一致" : "一致 ✓");
        printf("前 24 字节: ");
        for (i = 0; i < 24; i++) printf("%02x ", p[i]);
        printf("\n");
        munmap((void *)p, 4096);
        close(fd);
        printf("\n★ CMA 写入完成（还没挂到 3DLUT，画面应无变化）\n");
        return 0;
    }

    /* ================= attach / restore：只碰 EP ================= */
    {
        struct ep_reg_info info;
        unsigned long pa, size, map_len;
        volatile unsigned *b;
        unsigned char *mb;
        int fd_ep = open("/dev/drime5_ep", O_RDWR);
        if (fd_ep < 0) { printf("open EP: %s\n", strerror(errno)); return 5; }
        if (ioctl(fd_ep, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
            printf("ioctl: %s\n", strerror(errno)); return 6;
        }
        pa = blk(&info, 8)->reg_start_addr;
        size = blk(&info, 8)->reg_size;
        map_len = (size + 4095) & ~4095UL;
        mb = mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd_ep, (off_t)pa);
        if (mb == MAP_FAILED) { printf("mmap EP fail\n"); return 7; }
        b = (volatile unsigned *)mb;
        printf("3dlut @0x%08lx = %p\n", pa, (void *)mb);

        if (strcmp(argv[1], "restore") == 0) {
            printf("恢复 16 槽 +0x0c <- 0x%08lx\n", ORIG_LUT);
            for (i = 0; i < NSLOT; i++)
                b[(i * SLOTSZ + R_LUT0_ADDR) / 4] = (unsigned)ORIG_LUT;
            b[R_START / 4] = 0x100;
            usleep(2000);
            printf("读回 slot0 = 0x%08x\n", b[R_LUT0_ADDR / 4]);
        } else {   /* attach */
            printf("\n--- 16 槽 +0x0c <- 0x%08lx ---\n", target);
            for (i = 0; i < NSLOT; i++)
                b[(i * SLOTSZ + R_LUT0_ADDR) / 4] = (unsigned)target;
            printf("读回 slot0 = 0x%08x\n", b[R_LUT0_ADDR / 4]);
            printf("\n--- 启动脉冲 ---\n");
            b[R_START / 4] = 0x100;
            usleep(3000);
            printf("+0x08 = 0x%08x\n", b[R_START / 4]);
            printf("\n★★★ 请看取景器！\n");
            printf("    恢复：%s restore 0x81115200\n", argv[0]);
        }
        munmap(mb, map_len);
        close(fd_ep);
    }
    return 0;
}