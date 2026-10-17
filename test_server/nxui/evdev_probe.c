/* evdev_probe.c —— 直读 evdev 原始事件（绕开 X11），找滚轮/方向键键码
 * 事件写 /mnt/mmc/nxui-evdev.log；180 秒自动退出。
 */
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/select.h>
#include <linux/input.h>

int main(void)
{
    const char *devs[3] = {"/dev/input/event0", "/dev/input/event1", "/dev/input/event2"};
    int fd[3] = {-1, -1, -1};
    int i, maxfd = -1;
    FILE *f = fopen("/mnt/mmc/nxui-evdev.log", "a");
    if (!f) return 2;
    fprintf(f, "=== evdev probe start ===\n");
    for (i = 0; i < 3; i++) {
        fd[i] = open(devs[i], O_RDONLY | O_NONBLOCK);
        if (fd[i] >= 0 && fd[i] > maxfd) maxfd = fd[i];
        fprintf(f, "open %s -> %d\n", devs[i], fd[i]);
    }
    fflush(f);
    alarm(180);
    for (;;) {
        fd_set rs;
        int n;
        FD_ZERO(&rs);
        for (i = 0; i < 3; i++) if (fd[i] >= 0) FD_SET(fd[i], &rs);
        n = select(maxfd + 1, &rs, NULL, NULL, NULL);
        if (n <= 0) continue;
        for (i = 0; i < 3; i++) {
            struct input_event ev;
            ssize_t got;
            if (fd[i] < 0 || !FD_ISSET(fd[i], &rs)) continue;
            got = read(fd[i], &ev, sizeof ev);
            if (got != (ssize_t)sizeof ev) continue;
            if (ev.type == EV_SYN || ev.type == EV_MSC) continue;
            if (ev.type == EV_ABS && i == 2) continue; /* 触摸屏坐标量大，忽略；event0/1 的 ABS 可能是滚轮/转盘，要记 */
            fprintf(f, "event%d type=%u code=%u value=%d\n", i, ev.type, ev.code, ev.value);
            fflush(f);
        }
    }
}
