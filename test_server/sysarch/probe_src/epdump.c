/* epdump.arm -- dump EP 3DLUT / NOG 寄存器窗口（只读，逐行立即落盘）
   用法: epdump <addr_hex> <words>
   ★ PROT_READ only，绝不写任何寄存器。 */
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/mman.h>
#include <stdlib.h>
static int on; static char ob[8192];
static void fl(void){ if(on){ write(1,ob,on); on=0; } }
static void p_(const char*s){ while(*s){ if(on>=(int)sizeof(ob))fl(); ob[on++]=*s++; } }
static void pc_(char c){ if(on>=(int)sizeof(ob))fl(); ob[on++]=c; }
static void pnl(void){ pc_('\n'); }
static void de_(int v){ char b[16]; int m=0,i; unsigned u;
  if(v<0){pc_('-');u=(unsigned)(-v);}else u=(unsigned)v;
  if(!u){pc_('0');return;} while(u){b[m++]=(char)('0'+u%10);u/=10;}
  for(i=m;i>0;i--)pc_(b[i-1]); }
static void hx_(unsigned v,int w){ static const char H[]="0123456789abcdef";
  char b[16]; int m=0,i; if(!v){for(i=0;i<w;i++)pc_('0');return;}
  while(v){b[m++]=H[v%16u];v/=16u;} for(i=w;i>m;i--)pc_('0');
  for(i=0;i<m;i++)pc_(b[m-1-i]); }
int main(int argc,char**argv){
    unsigned addr, nw, pg, i, j;
    off_t pa; unsigned offs;
    int fd; void *p; unsigned *q;
    if(argc<3){ p_("usage: epdump <addr_hex> <words>\n"); fl(); return 1; }
    addr=(unsigned)strtoul(argv[1],0,16);
    nw  =(unsigned)strtoul(argv[2],0,16);
    pg  =(unsigned)sysconf(_SC_PAGE_SIZE);
    fd=open("/dev/mem",O_RDONLY);
    if(fd<0){ p_("/dev/mem FAILED: "); p_(strerror(errno)); pnl(); fl(); return 1; }
    pa=(off_t)(addr & ~(pg-1)); offs=addr-(unsigned)pa;
    p_("dump addr=0x"); hx_(addr,8); p_(" words="); de_((int)nw); pnl(); fl();
    p=mmap((void*)0,(size_t)(nw*4+offs),PROT_READ,MAP_SHARED,fd,pa);
    if(p==MAP_FAILED){ p_("mmap FAILED: "); p_(strerror(errno)); pnl(); fl(); return 1; }
    q=(unsigned*)((char*)p+offs);
    for(i=0;i<nw;i++){
        p_("  [0x"); hx_(i*4,4); p_("] 0x"); hx_(q[i],8);
        /* 全行16 列 */
        for(j=1;j<4 && i+j<nw;j++){ p_("  0x"); hx_(q[i+j],8); }
        pnl(); fl();
    }
    munmap(p,(size_t)(nw*4+offs)); close(fd);
    p_("OK\n"); fl();
    return 0;
}
