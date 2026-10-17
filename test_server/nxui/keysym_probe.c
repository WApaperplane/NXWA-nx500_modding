/* keysym_probe.c —— 相机 X11 键/滚轮事件诊断（临时工具，不参与生产）
 * 打开 720x192 override-redirect 窗口并抢焦点，把 Key/Button 事件写到 /mnt/mmc/nxui-keys.log
 * 用法（相机端）: DISPLAY=:0 setsid ./keysym_probe.arm &
 * 结束: killall keysym_probe.arm
 */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(void)
{
    Display *d = XOpenDisplay(NULL);
    if (!d) { fprintf(stderr, "no display\n"); return 2; }
    int scr = DefaultScreen(d);
    XSetWindowAttributes attr;
    memset(&attr, 0, sizeof attr);
    attr.override_redirect = True;
    attr.background_pixel = BlackPixel(d, scr);
    attr.event_mask = ExposureMask | KeyPressMask | KeyReleaseMask |
                      ButtonPressMask | ButtonReleaseMask | StructureNotifyMask;
    Window w = XCreateWindow(d, RootWindow(d, scr), 0, 0, 1, 1, 0,
                             DefaultDepth(d, scr), InputOutput, DefaultVisual(d, scr),
                             CWOverrideRedirect | CWBackPixel | CWEventMask, &attr);
    XStoreName(d, w, "NXWA-KEYS");
    XMapRaised(d, w);
    XSetInputFocus(d, w, RevertToPointerRoot, CurrentTime);
    XSync(d, False);
    alarm(120); /* 自动退出兜底：防忘关/防遮挡 */

    FILE *f = fopen("/mnt/mmc/nxui-keys.log", "a");
    if (f) { fprintf(f, "=== probe start ===\n"); fflush(f); }

    for (;;) {
        XEvent e;
        XNextEvent(d, &e);
        if (e.type == KeyPress || e.type == KeyRelease) {
            KeySym ks = XLookupKeysym(&e.xkey, 0);
            const char *nm = XKeysymToString(ks);
            if (!f) continue;
            fprintf(f, "key %s keycode=%u keysym=0x%lx name=%s state=0x%x\n",
                    e.type == KeyPress ? "press" : "release",
                    e.xkey.keycode, (unsigned long)ks, nm ? nm : "?", e.xkey.state);
        } else if (e.type == ButtonPress || e.type == ButtonRelease) {
            if (!f) continue;
            fprintf(f, "btn %s button=%u x=%d y=%d state=0x%x\n",
                    e.type == ButtonPress ? "press" : "release",
                    e.xbutton.button, e.xbutton.x, e.xbutton.y, e.xbutton.state);
        } else {
            continue;
        }
        fflush(f);
    }
}
