/* eplen.c — NX-KS2：探测 3DLUT LUT 的真实长度与格式
 *
 * ★★★ 现在写入通路已通（画面会变），唯一未知是"该写多少字节、什么格式"。
 *
 * 判据设计（★ 不再盲试，用可观测差异）：
 *   长度不足 ⇒ 硬件读到未初始化数据 ⇒ 花屏
 *   长度正确 + 全 0（identity 等价）⇒ 画面正常
 *   ⇒ 所以"全 0 + 不同长度"就能测出正确长度 —— 画面正常的那个就是。
 *
 * 用法:
 *   eplen dump <phys> <len>    只读 dump 固件预置缓冲（看它原本长什么样）
 *   eplen zero <phys> <len>    把该地址填全0 + 走完整 6 步序列（identity 测试）
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

#define R_ONOFF     0x000
#define R_CFG       0x004
#define R_PULSE     0x008
#define R_LUT0      0x00c
#define BASE_LUT    0x81115200UL

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

int main(int argc, char **argv)
{
    struct ep_reg_info info;
    unsigned long pa, size, map_len, target, len;
    volatile unsigned *b;
    unsigned char *mb, *lp;
    int fd_ep, fd_sma, i, fds;

    if (argc < 4) {
        printf("用法: %s dump <phys> <len> | zero <phys> <len>\n", argv[0]);
        return 1;
    }
    target = strtoul(argv[2], NULL, 0);
    len    = strtoul(argv[3], NULL, 0);
    if (len == 0 || len > 0x10000) { printf("len 越界\n"); return 1; }

    fd_sma = open("/dev/d5_sma", O_RDWR);
    if (fd_sma < 0) { printf("open d5_sma: %s\n", strerror(errno)); return 2; }

    /* ---------- dump：只读看固件预置缓冲 ---------- */
    if (strcmp(argv[1], "dump") == 0) {
        unsigned long off;
        int nz = 0;
        printf("=== dump 0x%08lx  len=%lu ===\n", target, len);
        /* 分段 mmap（每段 4096）*/
        for (off = 0; off < len; off += 4096) {
            unsigned long this_len = len - off;
            unsigned long map_len = (this_len + 4095) & ~4095UL;
            unsigned k;
            if (map_len > 4096) map_len = 4096;
            lp = mmap(NULL, map_len, PROT_READ, MAP_SHARED, fd_sma, (off_t)(target + off));
            if (lp == MAP_FAILED) { printf("  mmap 0x%08lx 失败: %s\n", target + off, strerror(errno)); break; }
            for (k = 0; k < this_len; k++) if (lp[k]) { nz++; break; }
            /* 打印前 64 字节与最后 64 字节 */
            if (off < 64 || (len - off) < 64) {
                printf("  +0x%04lx: ", off);
                for (i = 0; i < 64 && (unsigned long)i < this_len; i++)
                    printf("%02x", lp[i]);
                printf("\n");
            }
            munmap(lp, map_len);
        }
        printf("\n非零页数 = %d / %lu\n", nz, (len + 4095) / 4096);
        close(fd_sma);
        return 0;
    }

    /* ---------- zero：填全 0 + 完整 6 步 ---------- */
    if (strcmp(argv[1], "zero") == 0) {
        unsigned long off;
        printf("=== 填全0 @0x%08lx len=%lu ===\n", target, len);
        for (off = 0; off < len; off += 4096) {
            unsigned long this_len = len - off;
            unsigned long map_len = (this_len + 4095) & ~4095UL;
            if (map_len > 4096) map_len = 4096;
            lp = mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd_sma,
                      (off_t)(target + off));
            if (lp == MAP_FAILED) { printf("  mmap 失败: %s\n", strerror(errno)); break; }
            /* ★ 用逐字节写，避开 memset 在 -O0 下的 SIGSEGV（铁律 51）*/
            for (i = 0; (unsigned long)i < this_len; i++) lp[i] = 0;
            printf("  +0x%04lx ~ +0x%04lx 置零 ✔\n", off, off + this_len - 1);
            munmap(lp, map_len);
        }

        /* EP 侧 6 步 */
        fds = open("/dev/drime5_ep", O_RDWR);
        if (fds < 0) { printf("open EP: %s\n", strerror(errno)); return 3; }
        if (ioctl(fds, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
            printf("ioctl: %s\n", strerror(errno)); return 4;
        }
        pa = blk(&info, 8)->reg_start_addr;
        size = blk(&info, 8)->reg_size;
        map_len = (size + 4095) & ~4095UL;
        mb = mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, fds, (off_t)pa);
        if (mb == MAP_FAILED) { printf("mmap EP fail\n"); return 5; }
        b = (volatile unsigned *)mb;
        printf("\n3dlut @0x%08lx\n", pa);

        /* ① OnOff */
        b[R_ONOFF / 4] |= 1UL;
        /* ② 脉冲清零 */
        b[R_PULSE / 4] &= ~1UL;
        /* ③ 启动 */
        b[R_PULSE / 4] |= 1UL;
        usleep(2000);
        /* ④ SetAddress */
        b[R_LUT0 / 4] = (unsigned)target;
        usleep(2000);
        /* ⑤ 通道 */
        b[R_CFG / 4] = b[R_CFG / 4] & 0xffffffcfUL;
        /* ⑥ 读侧清理 */
        b[R_PULSE / 4] &= ~0x100UL;
        usleep(3000);

        printf("\n--- 最终 ---\n");
        printf("  +0x000 = 0x%08x\n", b[R_ONOFF / 4]);
        printf("  +0x004 = 0x%08x\n", b[R_CFG / 4]);
        printf("  +0x008 = 0x%08x %s\n", b[R_PULSE / 4],
               b[R_PULSE / 4] ? "★保持1（硬件接受了启动）" : "(被清零)");
        printf("  +0x00c = 0x%08x\n", b[R_LUT0 / 4]);
        printf("\n★★★ 请看取景器：画面**正常**（identity 等价）还是**花屏**？\n");
        printf("    恢复正常 ⇒ len=%lu 是正确的（或至少不越界）\n", len);
        printf("    仍花屏 ⇒ 这个长度也不对\n");
        printf("    恢复基线：把 +0x00c 写回 0x%08lx 再走 6 步\n", BASE_LUT);

        munmap(mb, map_len);
        close(fds);
        close(fd_sma);
        return 0;
    }
    close(fd_sma);
    return 0;
}