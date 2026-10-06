#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/ioctl.h>
static int n; static char ob[2048];
static void fl(void){ if(n){ write(1,ob,n); n=0; } }
static void s_(const char*p){ while(*p){ if(n>=(int)sizeof(ob))fl(); ob[n++]=*p++; } }
static void hx(unsigned v,int w){ char t[16]; int i,j=w; for(i=0;i<w;i++)t[i]='0';
    while(v&&j>0){ t[--j]="0123456789abcdef"[v&0xf]; v>>=4; } for(i=0;i<w;i++) s_(t+i); }
static void de(int v){ char t[16]; int i=0; unsigned u; if(v<0){ s_("-"); u=(unsigned)(-v);} else u=v;
    if(!u){ s_("0"); return;} while(u){ t[i++]= '0'+u%10; u/=10;} while(i>0) s_(t+--i); }
#define IOC(d,t,nr,sz) (((d)<<30)|((sz)<<16)|((t)<<8)|(nr))

int main(int argc, char**argv){
    int fd, r; unsigned int v=0;
    s_("T2 start\n"); fl();
    fd = open("/dev/d5_sma", O_RDONLY);
    s_("fd="); de(fd); s_(" errno_if_neg="); de(errno); s_("\n"); fl();
    if(fd<0) return 1;

    /* A: 完全未知的 magic，看 ioctl 派发是否本身就崩 */
    r = ioctl(fd, IOC(2,'Z',77,4), &v);
    s_("A IOR('Z',77,4) r="); de(r); s_(" errno="); de(errno); s_("\n"); fl();

    /* B: 正确的 magic 但错的 nr（比已知 nr 大很多） */
    r = ioctl(fd, IOC(2,'s',200,4), &v);
    s_("B IOR('s',200,4) r="); de(r); s_(" errno="); de(errno); s_("\n"); fl();

    /* C: 正确 magic 's'，nr=1（GET_REGION_SIZE），但 size 给 0 */
    r = ioctl(fd, IOC(2,'s',1,0), &v);
    s_("C IOR('s',1,0) r="); de(r); s_(" errno="); de(errno); s_("\n"); fl();

    /* D: 真正的 GET_REGION_SIZE */
    r = ioctl(fd, IOC(2,'s',1,4), &v);
    s_("D IOR('s',1,4) r="); de(r); s_(" errno="); de(errno);
    s_(" v=0x"); hx(v,8); s_("\n"); fl();

    close(fd); s_("T2 done\n"); fl();
    return 0;
}
