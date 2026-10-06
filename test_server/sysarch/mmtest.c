/*验证 O_SYNC 是否能拿到可写映射 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <errno.h>
int main(int argc, char **argv){
    unsigned long target = strtoul(argv[1], NULL, 0);
    int i;
    for (i = 0; i < 2; i++) {
        int fl = i ? (O_RDWR|O_SYNC) : (O_RDWR);
        const char *nm = i ? "O_RDWR|O_SYNC" : "O_RDWR";
        int fd = open("/dev/d5_sma", fl);
        volatile unsigned *p;
        unsigned long pa = (unsigned long)target & ~4095UL;
        if (fd < 0) { printf("%-14s open fail %s\n", nm, strerror(errno)); continue; }
        p = mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_SHARED, fd, (off_t)pa);
        if (p == MAP_FAILED) { printf("%-14s mmap fail: %s\n", nm, strerror(errno)); close(fd); continue; }
        printf("%-14s mmap=%p  read[0]=%08x  ", nm, (void*)p, p[0]);
        fflush(stdout);
        p[0] = 0x12345678;   /* ★ 试写 */
        printf("write OK -> %08x\n", p[0]);
        p[0] = 0;            /* 还原 */
        munmap((void*)p, 4096);
        close(fd);
    }
    return 0;
}
