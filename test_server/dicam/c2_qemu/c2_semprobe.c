/* c2_semprobe.c — 最小 semaphore 探针（找出 chroot 里 sem_open/sem_init 失败的真因） */
#include <stdio.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <semaphore.h>
#include <sys/mman.h>
#include <unistd.h>

int main(void)
{
    int fd;
    sem_t *s;
    int r;

    setvbuf(stdout, NULL, _IONBF, 0);

    /* 0) 裸 open 测试 /dev/shm */
    errno = 0;
    fd = open("/dev/shm/probe_file", O_RDWR | O_CREAT, 0660);
    printf("open(/dev/shm/probe_file) = %d errno=%d (%s)\n", fd, errno, strerror(errno));
    if (fd >= 0) close(fd);

    /* 1) 复刻 shell_sndmsg 的调用：flags=0x40(O_CREAT) mode=0660 */
    errno = 0;
    s = sem_open("/probe_sem", 0x40, 0660, 0);
    printf("sem_open('/probe_sem', O_CREAT, 0660, 0) -> %p errno=%d (%s)\n",
           (void *)s, errno, strerror(errno));
    if (s == SEM_FAILED) {
        printf("  SEM_FAILED, skip sem_init\n");
        return 0;
    }

    errno = 0;
    r = sem_init(s, 1, 0);
    printf("sem_init(s,1,0) -> %d errno=%d (%s)\n", r, errno, strerror(errno));

    errno = 0;
    r = sem_post(s);
    printf("sem_post -> %d errno=%d (%s)\n", r, errno, strerror(errno));
    return 0;
}
