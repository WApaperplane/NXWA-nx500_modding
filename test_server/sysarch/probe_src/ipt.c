/* IPCC ABI 逐格探测：每次只调一个 ioctl，调完立刻 write 落盘+退出，
   崩溃了也知道崩在哪一格（前一格的结果已经落盘）。 */
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/ioctl.h>
static int n_; static char ob_[1024];
static void fl_(void){ if(n_){ write(1,ob_,n_); n_=0; } }
static void p_(const char*s){ while(*s){ if(n_>=(int)sizeof(ob_))fl_(); ob_[n_++]=*s++; } }
static void pc_(char c){ if(n_>=(int)sizeof(ob_))fl_(); ob_[n_++]=c; }
static void de_(int v){ char b[16]; int m=0,i; unsigned u; if(v<0){pc_('-');u=(unsigned)(-v);}else u=v;
  if(!u)pc_('0'); else { while(u){b[m++]=(char)('0'+u%10);u/=10;} for(i=0;i<m;i++)pc_(b[i]); } }
static void hx_(unsigned v,int w){ static const char H[]="0123456789abcdef";
  char b[16]; int m=0,i; if(!v){for(i=0;i<w;i++)pc_('0');return;}
  while(v){b[m++]=H[v%16u];v/=16u;} for(i=w;i>m;i--)pc_('0');
  for(i=0;i<m;i++)pc_(b[m-1-i]); }

static const unsigned long IP4[16]={0xc0047400UL,0xc0047401UL,0xc0047402UL,0xc0047403UL,0xc0047404UL,0xc0047405UL,0xc0047406UL,0xc0047407UL,0xc0047408UL,0xc0047409UL,0xc004740aUL,0xc004740bUL,0xc004740cUL,0xc004740dUL,0xc004740eUL,0xc004740fUL};
static const unsigned long IP8[16]={0xc0087400UL,0xc0087401UL,0xc0087402UL,0xc0087403UL,0xc0087404UL,0xc0087405UL,0xc0087406UL,0xc0087407UL,0xc0087408UL,0xc0087409UL,0xc008740aUL,0xc008740bUL,0xc008740cUL,0xc008740dUL,0xc008740eUL,0xc008740fUL};

int main(int argc,char**argv){
    int nr = (argc>1)?atoi(argv[1]):0;
    int fd,r,i;
    unsigned int b16[8];
    p_("IPCC probe nr="); de_(nr); p_("\n"); fl_();
    fd=open("/dev/d5_ipcc",O_RDWR);
    if(fd<0){ p_("open fail\n"); fl_(); return 1; }
    /* 传 32 字节缓冲（大于任何候选 size），逐格看内核写了什么 */
    memset(b16,0xAA,sizeof(b16));
    p_("cmd=");
    if(nr&16) hx_((unsigned)IP8[nr&15],8); else hx_((unsigned)IP4[nr&15],8);
    p_("\n"); fl_();
    r = (nr&16) ? ioctl(fd, IP8[nr&15], b16) : ioctl(fd, IP4[nr&15], b16);
    p_("r="); de_(r); p_(" errno="); de_(errno); p_("\nbuf=");
    for(i=0;i<8;i++){ hx_(b16[i],8); pc_(' '); }
    p_("\n"); fl_();
    close(fd);
    p_("SURVIVED\n"); fl_();
    return 0;
}
