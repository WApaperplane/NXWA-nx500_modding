/* ui_pages_render.c —— D2 五页离线预渲染（**降级绘制版**：evas rect + text）
 *
 * 为什么是"降级绘制"：
 *   真实 elm 控件（elm_list / elm_slider / elm_radio …）需要 elementary 的 engine 初始化，
 *   在**离线 chroot（无显示服务）**里 elm_init 会阻塞或崩（本轮已在 WSL 实测到挂死）。
 *   ⇒ 按 D2 的验收口径（"五页各一张 PNG + 布局/中文无 tofu"），
 *     这里用 **evas_object_rectangle_add（面板/行/滑块槽）+ evas_object_text_add（全部文字）**
 *     手工复现五页的**信息结构**；报告里明确标注哪些是"降级绘制"。
 *
 * ★ 字体：与 nxfilmui v4 / nxlabel_probe 完全同款三项常量（SDIC_GP_US / 26px），
 *   每处文本都显式调用 font_source_set + font_set（否则 0×0 不画 —— 已离线实测）。
 *
 * 用法: ui_pages_render <outdir> [w h]
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <unistd.h>

typedef void Ecore_Evas;
typedef void Evas;
typedef void Evas_Object;

extern Ecore_Evas  *ecore_evas_buffer_new(int w, int h);
extern int          ecore_evas_init(void);
extern int          ecore_init(void);
extern int          evas_init(void);
extern Evas        *ecore_evas_get(const Ecore_Evas *ee);
extern void         ecore_evas_manual_render_set(Ecore_Evas *ee, int manual_render);
extern void         ecore_evas_manual_render(Ecore_Evas *ee);
extern void        *ecore_evas_buffer_pixels_get(Ecore_Evas *ee);

extern Evas_Object *evas_object_rectangle_add(Evas *e);
extern Evas_Object *evas_object_text_add(Evas *e);
extern void         evas_object_text_font_source_set(Evas_Object *o, const char *path);
extern void         evas_object_text_font_set(Evas_Object *o, const char *font, int size);
extern void         evas_object_text_text_set(Evas_Object *o, const char *text);
extern void         evas_object_color_set(Evas_Object *o, int r, int g, int b, int a);
extern void         evas_object_move(Evas_Object *o, int x, int y);
extern void         evas_object_resize(Evas_Object *o, int w, int h);
extern void         evas_object_show(Evas_Object *o);

#define FONT_FILE "/usr/share/fonts/SDIC_GP_US_20120720.ttf"
#define FONT_FAM  "SDIC_GP_US"
#define FSZ       26

static Evas *EV;
static int   g_font_n = 0, g_rect_n = 0, g_page = 0;
static const char *g_log = NULL;

static void logf_(const char *fmt, ...)
{
    va_list ap; FILE *f;
    va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap);
    if (g_log) { f = fopen(g_log, "a"); if (f) { va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap); fclose(f); } }
}

/* ---------- 自写 PNG（同 nxlabel_probe / cjk_render，零依赖） ---------- */
static uint32_t crc_table[256];
static void crc_init(void){ uint32_t c; int n,k; for(n=0;n<256;n++){c=(uint32_t)n;for(k=0;k<8;k++)c=(c&1)?(0xedb88320u^(c>>1)):(c>>1);crc_table[n]=c;} }
static uint32_t crc32_buf(const uint8_t*b,size_t n){uint32_t c=0xffffffffu;size_t i;for(i=0;i<n;i++)c=crc_table[(c^b[i])&0xff]^(c>>8);return c^0xffffffffu;}
static void be32(uint8_t*p,uint32_t v){p[0]=(uint8_t)(v>>24);p[1]=(uint8_t)(v>>16);p[2]=(uint8_t)(v>>8);p[3]=(uint8_t)v;}
static void png_chunk(FILE*f,const char*t,const uint8_t*d,uint32_t len)
{
    uint8_t h[8],c4[4]; uint32_t crc; uint8_t *b=(uint8_t*)malloc(len+4);
    be32(h,len); fwrite(h,1,4,f); fwrite(t,1,4,f); if(len) fwrite(d,1,len,f);
    memcpy(b,t,4); if(len) memcpy(b+4,d,len);
    crc=crc32_buf(b,len+4); be32(c4,crc); fwrite(c4,1,4,f); free(b);
}
static int write_png(const char*path,int w,int h,const uint8_t*rgb)
{
    FILE*f=fopen(path,"wb"); uint8_t sig[8]={0x89,'P','N','G','\r','\n',0x1a,'\n'},ih[13];
    size_t rawlen=(size_t)h*(1+(size_t)w*3), zlen, off, i, pos=0;
    uint8_t *raw,*z; uint32_t a=1,b=0;
    if(!f) return -1;
    fwrite(sig,1,8,f);
    be32(ih,(uint32_t)w); be32(ih+4,(uint32_t)h); ih[8]=8; ih[9]=2; ih[10]=0; ih[11]=0; ih[12]=0;
    png_chunk(f,"IHDR",ih,13);
    raw=(uint8_t*)malloc(rawlen);
    for(i=0;i<(size_t)h;i++){ raw[i*(1+(size_t)w*3)]=0; memcpy(raw+i*(1+(size_t)w*3)+1, rgb+i*(size_t)w*3, (size_t)w*3); }
    zlen=2+rawlen+(rawlen/65535+1)*5+4; z=(uint8_t*)malloc(zlen);
    z[pos++]=0x78; z[pos++]=0x01; off=0;
    while(off<rawlen){ size_t n=rawlen-off; int fin; if(n>65535)n=65535; fin=(off+n>=rawlen);
        z[pos++]=(uint8_t)(fin?1:0); z[pos++]=(uint8_t)(n&0xff); z[pos++]=(uint8_t)((n>>8)&0xff);
        z[pos++]=(uint8_t)(~n&0xff); z[pos++]=(uint8_t)((~n>>8)&0xff);
        memcpy(z+pos,raw+off,n); pos+=n; off+=n; }
    for(i=0;i<rawlen;i++){ a=(a+raw[i])%65521; b=(b+a)%65521; }
    be32(z+pos,(b<<16)|a); pos+=4;
    png_chunk(f,"IDAT",z,(uint32_t)pos); png_chunk(f,"IEND",NULL,0);
    fclose(f); free(raw); free(z); return 0;
}

/* ---------- 绘图原语 ---------- */
static void rect(int x,int y,int w,int h,int r,int g,int b,int a)
{
    Evas_Object*o=evas_object_rectangle_add(EV);
    evas_object_color_set(o,r,g,b,a); evas_object_move(o,x,y); evas_object_resize(o,w,h);
    evas_object_show(o); g_rect_n++;
}
static void text(int x,int y,const char*s,int sz,int r,int g,int b)
{
    Evas_Object*t=evas_object_text_add(EV);
    evas_object_text_font_source_set(t,FONT_FILE);
    evas_object_text_font_set(t,FONT_FAM,sz);
    evas_object_text_text_set(t,s);
    evas_object_color_set(t,r,g,b,255);
    evas_object_move(t,x,y); evas_object_show(t); g_font_n++;
}
static void bg(int W,int H){ rect(0,0,W,H,12,14,20,255); }
static void header(const char*cn,const char*en)
{
    rect(0,0,720,40,26,30,44,255);
    text(10,6,cn,26,235,235,240);
    text(300,10,en,20,150,160,185);
}
static void statusbar(const char*s)
{
    rect(0,444,720,36,20,24,34,255);
    text(10,449,s,20,120,255,160);
}
/* 列表行：色块 + 标签 */
static void list_row(int i,int y,const char*label,const char*sub,int sel,int cr,int cg,int cb)
{
    rect(10,y,700,42, sel?38:26, sel?44:30, sel?56:44, 255);
    rect(16,y+6,30,30,cr,cg,cb,255);                 /* 色块预览（降级替代 elm icon）*/
    text(56,y+8,label,22, sel?255:210, sel?220:210, sel?120:210);
    text(430,y+10,sub,18,150,150,170);
    if(sel) text(660,y+8,"<",22,255,200,80);
}
/* 滑块（降级替代 elm_slider）*/
static void slider(int y,const char*name,int v,int vmax)
{
    char buf[64];
    rect(10,y,700,36,26,30,44,255);
    text(20,y+6,name,20,215,215,225);
    rect(180,y+14,380,10,60,66,86,255);              /* 槽 */
    rect(180,y+14,(int)(380.0*v/(vmax?vmax:1)),10,90,170,240,255); /* 已填 */
    snprintf(buf,sizeof(buf),"%d",v);
    text(580,y+6,buf,20,255,215,120);
}

/* ---------- 五页 ---------- */
static void page1(void)   /* P1 配方库 */
{
    static const char*L[8]={"Portra 400","Velvia 50","TriX 400","Kodak Ektachrome",
                            "HP5 Plus","Superia X-TRA400","MonoWarm 暖调黑白","Ektachrome Cyan 冷调反转"};
    int i;
    header("配方库","Recipes");
    for(i=0;i<8;i++){
        int col=i%2, row=i/2;
        int x=10+col*356, y=48+row*48;
        rect(x,y,344,44, i==2?38:26, i==2?44:30, i==2?56:44,255);
        rect(x+6,y+7,28,28, 120+i*10, 90+i*8, 70+i*6, 255);
        text(x+44,y+10,L[i],20, i==2?255:210, i==2?220:210, i==2?120:210);
        if(i==2) text(x+320,y+10,"<",20,255,200,80);
    }
    statusbar("[3/8] trix400   胶片仿真 · 选中即应用（不关窗）");
}
static void page2(void)   /* P2 PW 七维滑块 */
{
    static const char*N[7]={"R 红","G 绿","B 蓝","HUE 色调","SAT 饱和","SHARP 锐度","CON 对比"};
    static const int  V[7]={106,100,93,11,9,9,8};
    int i;
    header("参数调整","Picture Wizard · 7 axes");
    for(i=0;i<7;i++) slider(48+i*52,N[i],V[i],30);
    statusbar("实时写入 prefman + ISP 重读 · 长按回默认");
}
static void page3(void)   /* P3 3D LUT 管理 */
{
    header("3D LUT 管理","3D LUT");
    text(14,52,"SD 卡 LUT（/mnt/mmc/luts/*.cube）",20,150,160,185);
    list_row(0,80,"Portra400.cube","SD  33³",1,180,120,90);
    list_row(1,126,"Velvia50.cube","SD  33³",0,120,140,180);
    text(14,186,"机身内置 4 档",20,150,160,185);
    list_row(2,214,"内置 1  identity","内置",0,128,128,128);
    list_row(3,260,"内置 2  暖肤色","内置",0,190,150,120);
    list_row(4,306,"内置 3  风格化","内置",0,140,120,190);
    rect(10,360,344,44,40,46,60,255);  text(120,368,"写入所选 LUT",22,220,220,230);
    rect(366,360,344,44,60,36,36,255); text(470,368,"恢复出厂",22,255,180,180);
    statusbar("写入前提示：会改变当前画质 · 可一键恢复出厂");
}
static void page4(void)   /* P4 内置色彩 4 档 */
{
    static const char*N[4]={"identity（直出）","暖肤色 Warm Skin","风格化 Stylized","同 1（保留）"};
    int i;
    header("内置色彩","Built-in Color · 4 slots");
    for(i=0;i<4;i++){
        int y=70+i*70;
        rect(10,y,700,58, i==1?38:26, i==1?44:30, i==1?56:44,255);
        rect(24,y+17,24,24, i==1?90:60, i==1?170:66, i==1?240:86,255);
        text(62,y+16,N[i],24, i==1?255:215, i==1?220:215, i==1?130:215);
        if(i==1) text(640,y+16,"● 已选",20,255,200,80);
    }
    statusbar("单选 · 切换即写入 LUT 选择寄存器 +0x0c");
}
static void page5(void)   /* P5 诊断 / 高危 */
{
    header("诊断","Diagnostics · High-risk");
    text(14,52,"p7 固件状态",20,150,160,185);
    list_row(0,78,"p7 md5  5fc4824f…","与官方一致",0,90,200,120);
    list_row(1,124,"分区备份  11/11","md5 全部匹配",0,90,200,120);
    list_row(2,170,"p8 rtos_data","★ 0 非零字节 · 未解释",0,230,180,90);
    text(14,228,"高危操作（默认禁用）",20,255,140,140);
    rect(10,256,344,44,60,36,36,255);
    text(70,264,"刷写固件（需确认串）",22,255,190,190);
    rect(366,256,344,44,34,38,50,255);
    text(430,264,"备份校验（只读）",22,200,200,210);
    rect(10,316,700,52,44,30,30,255);
    text(20,326,"二次确认：请输入 CONFIRM-FLASH 后才可提交",20,255,200,160);
    text(20,352,"★ 单分区写错 = 可能变砖；boot0/boot1 绝不碰",18,200,170,170);
    statusbar("诊断页只读；写操作需二次确认门控");
}

int main(int argc,char**argv)
{
    const char*outdir=(argc>1)?argv[1]:"/tmp";
    int W=(argc>2)?atoi(argv[2]):720, H=(argc>3)?atoi(argv[3]):480;
    int p;
    crc_init();
    g_log=getenv("UI_LOG");
    logf_("== ui_pages_render start pid=%d outdir=%s %dx%d\n",(int)getpid(),outdir,W,H);
    logf_("   font exist=%d (%s)\n", access(FONT_FILE,R_OK)==0, FONT_FILE);
    if(access(FONT_FILE,R_OK)!=0){ logf_("FATAL font\n"); return 2; }
    logf_("   evas=%d ecore=%d ecore_evas=%d\n", evas_init(), ecore_init(), ecore_evas_init());

    for(p=0;p<5;p++){
        char path[512]; uint8_t*rgb; void*px; int x,y;
        Ecore_Evas*ee=ecore_evas_buffer_new(W,H);
        if(!ee){ logf_("FATAL buffer_new page %d\n",p+1); return 3; }
        EV=ecore_evas_get(ee);
        if(!EV){ logf_("FATAL evas NULL page %d\n",p+1); return 4; }
        g_page=p+1; g_rect_n=0;

        bg(W,H);
        switch(p){
            case 0: page1(); break;
            case 1: page2(); break;
            case 2: page3(); break;
            case 3: page4(); break;
            default: page5(); break;
        }
        ecore_evas_manual_render_set(ee,1);
        ecore_evas_manual_render(ee);
        px=ecore_evas_buffer_pixels_get(ee);
        if(!px){ logf_("FATAL pixels page %d\n",p+1); return 5; }
        rgb=(uint8_t*)malloc((size_t)W*H*3);
        {
            const uint8_t*q=(const uint8_t*)px;
            for(y=0;y<H;y++) for(x=0;x<W;x++){
                const uint8_t*c=q+((size_t)y*W+x)*4;
                rgb[((size_t)y*W+x)*3+0]=c[3]?c[2]:0;
                rgb[((size_t)y*W+x)*3+1]=c[3]?c[1]:0;
                rgb[((size_t)y*W+x)*3+2]=c[3]?c[0]:0;
            }
        }
        snprintf(path,sizeof(path),"%s/ui_page_p%d.png",outdir,p+1);
        if(write_png(path,W,H,rgb)!=0){ logf_("FATAL png page %d\n",p+1); return 6; }
        {
            int ink=0;
            for(y=0;y<H;y++) for(x=0;x<W;x++){
                const uint8_t*c=rgb+((size_t)y*W+x)*3;
                if(c[0]>90||c[1]>90||c[2]>90) ink++;
            }
            logf_("   PAGE %d -> %s  rect_n=%d ink=%d\n",p+1,path,g_rect_n,ink);
        }
        free(rgb);
    }
    logf_("== done, total font_set calls = %d\n", g_font_n);
    return 0;
}
