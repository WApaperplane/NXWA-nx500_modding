#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/syscall.h>
static int n; static char ob[4096];
static void fl(void){ if(n){ write(1,ob,n); n=0; } }
static void s_(const char*p){ while(*p){ if(n>=(int)sizeof(ob))fl(); ob[n++]=*p++; } }
static void hx(unsigned v,int w){ char t[16]; int i,j=w; for(i=0;i<w;i++)t[i]='0';
    while(v&&j>0){ t[--j]="0123456789abcdef"[v&0xf]; v>>=4; } for(i=0;i<w;i++) s_(t+i); }
static void de(int v){ char t[16]; int i=0; unsigned u; if(v<0){ s_("-"); u=(unsigned)(-v);} else u=v;
    if(!u){ s_("0"); return;} while(u){ t[i++]= '0'+u%10; u/=10;} while(i>0) s_(t+--i); }
#define IOC(d,t,nr,sz) (((d)<<30)|((sz)<<16)|((t)<<8)|(nr))

/* ★ 直接用内联 syscall 调 ioctl，绕开 libc 的 variadic 包装 */
static int my_ioctl(int fd, unsigned long cmd, void *arg){
    register long r7 __asm__("r7") = (long)SYS_ioctl;
    register long r0 __asm__("r0") = fd;
    register long r1 __asm__("r1") = (long)cmd;
    register long r2 __asm__("r2") = (long)arg;
    __asm__ volatile ("svc 0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2) : "memory");
    return (int)r0;
}

static void one(const char*path){
    int fd, r; unsigned int v=0;
    fd = open(path, O_RDONLY);
    s_("dev "); s_(path); s_(" open="); de(fd);
    if(fd<0){ s_(" (none)\n"); fl(); return; }
    s_(" -> syscall ioctl..."); fl();
    r = my_ioctl(fd, IOC(2,'Z',77,4), &v);
    s_(" SURVIVED r="); de(r); s_(" errno="); de(errno); s_("\n"); fl();
    close(fd);
}

int main(void){
    s_("T4 start (inline syscall ioctl)\n"); fl();
    one("/dev/null");
    one("/dev/urandom");
    one("/dev/d5_sma");
    one("/dev/d5_ipcc");
    one("/dev/drime5_ep");
    s_("T4 done\n"); fl();
    return 0;
}
