/* kread.c — NX-KS2：读 /dev/mem 指定物理地址并dump（纯只读）
 *
 * ★ 用途：静态核实内核里 drime5_ep_open / drime5_ep_probe 的行为，
 *   用来判断"自己 open /dev/drime5_ep 是否安全"。
 *   ★ 只 O_RDONLY 打开 /dev/mem，只读，绝不写。
 *
 * 用法: kread <phys_addr_hex> <len_hex>
 *   例: kread 0xc02cd30c 0x40
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>

int main(int argc, char **argv)
{
    unsigned long pa, len;
    unsigned char *p;
    int fd;
    size_t pg;
    unsigned long base;

    if (argc < 3) {
        printf("usage: %s <phys_addr_hex> <len_hex>\n", argv[0]);
        printf("  ex : %s 0xc02cd30c 0x40\n", argv[0]);
        return 1;
    }
    pa  = strtoul(argv[1], NULL, 0);
    len = strtoul(argv[2], NULL, 0);
    if (len == 0 || len > 0x100000) {
        printf("bad len\n");
        return 1;
    }

    fd = open("/dev/mem", O_RDONLY | O_SYNC);
    if (fd < 0) { perror("open /dev/mem"); return 2; }
    printf("/dev/mem opened O_RDONLY (O_SYNC)\n");

    pg  = (size_t)sysconf(_SC_PAGESIZE);
    base = pa & ~(pg - 1);
    p = mmap(NULL, pg, PROT_READ, MAP_SHARED, fd, (off_t)base);
    if (p == MAP_FAILED) { perror("mmap"); close(fd); return 3; }
    printf("phys 0x%08lx mapped at %p (page 0x%lx)\n", base, p, (unsigned long)pg);
    printf("read  %lu bytes from +0x%lx\n\n", len, pa - base);

    {
        const unsigned char *q = p + (pa - base);
        unsigned long i;
        for (i = 0; i < len; i += 16) {
            unsigned k;
            printf("%08lx  ", pa + i);
            for (k = 0; k < 16 && i + k < len; k++)
                printf("%02x ", q[i + k]);
            for (; k < 16; k++) printf("   ");
            printf(" |");
            for (k = 0; k < 16 && i + k < len; k++) {
                unsigned char c = q[i + k];
                printf("%c", (c >= 32 && c < 127) ? c : '.');
            }
            printf("|\n");
        }
    }
    printf("\n=== end: pure read, nothing written ===\n");
    munmap(p, pg);
    close(fd);
    return 0;
}