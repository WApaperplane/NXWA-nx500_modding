#include <sys/ioctl.h>
static int n; static char ob[1024];
static void fl(void){ if(n){ write(1,ob,n); n=0; } }
static void s_(const char*p){ while(*p){ if(n>=(int)sizeof(ob))fl(); ob[n++]=*p++; } }
int main(void){ s_("x\n"); fl(); return 0; }
