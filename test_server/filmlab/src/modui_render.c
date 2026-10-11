/* modui_render.c —— NX-WA mod 原生 UI「全功能」离线预渲染（降级绘制版：evas rect + text）
 *
 * 与 ui_pages_render.c 的关系：
 *   ui_pages_render.c  = D2 五页（配方库 / PW 七维 / 3D LUT / 内置色彩 / 诊断）
 *   modui_render.c（本文件）= **扩展版：覆盖 mod 当前全部功能**，共 10 页（P1..P10）。
 *   两者共用同一套"降级绘制"纪律与自写 PNG 写入器。
 *
 * 为什么是"降级绘制"（沿用 D2 结论）：
 *   真实 elm 控件（elm_list/elm_slider/elm_radio/elm_entry）需要 elementary 的 engine 初始化，
 *   在**离线 chroot（无显示服务）**里 elm_init 会阻塞或崩。
 *   ⇒ 用 evas_object_rectangle_add（面板/行/槽/进度条）+ evas_object_text_add（全部文字）
 *     手工复现各页的**信息结构与布局**。可判「布局是否合理 / 中文是否出字 / 信息是否齐全」，
 *     **不可**判「真实控件在机身长什么样」。
 *
 * ★ 字体：SDIC_GP_US / 26px 基线，每处文本都显式 font_source_set + font_set
 *   （不设则几何 0x0 不画 —— 已离线实测）。
 *
 * 用法: modui_render <outdir> [w h]
 * 环境: UI_LOG=<日志文件>   （gate G3 依赖日志里的 PAGE 行与 font_set 计数）
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <unistd.h>

/* ---- libevas / libecore / libecore_evas（无 EFL 头，直接用 extern 声明） ---- */
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

/* 主题色（与 D2 一致） */
#define C_BG       12,14,20
#define C_PANEL    26,30,44
#define C_PANEL_S  38,44,56
#define C_TEXT   235,235,240
#define C_TEXT2  210,210,215
#define C_DIM    150,160,185
#define C_HL     255,200, 80
#define C_OK     120,255,160
#define C_WARN   255,170, 90
#define C_DANGER 255,150,150
#define C_ACCENT  90,170,240

static Evas *EV;
static int   g_font_n = 0, g_rect_n = 0;
static const char *g_log = NULL;

static void logf_(const char *fmt, ...)
{
    va_list ap; FILE *f;
    va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap);
    if (g_log) { f = fopen(g_log, "a"); if (f) { va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap); fclose(f); } }
}

/* ---------- 自写 PNG（同 D2 渲染器：**零依赖**；可选接相机 zlib 压缩） ----------
 * 默认用 DEFLATE "stored" 块（不压缩，但完全零依赖）⇒ 720x480 每张约 1.0MB。
 * 定义 -DUSE_ZLIB 则改用相机自带 libz 的 compress2（zlib 流，PNG IDAT 直接可用）
 * ⇒ 每张降到几十 KB（UI 大面积纯色，压缩率极高），便于入库留证。
 */
#ifdef USE_ZLIB
/* 相机 /lib/libz.so.1（zlib 1.2.5）导出；无头文件所以自己声明 */
extern int compress2(unsigned char *dest, unsigned long *destLen,
                     const unsigned char *source, unsigned long sourceLen, int level);
#endif

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
#ifdef USE_ZLIB
    {
        unsigned long clen = (unsigned long)(rawlen + rawlen/1000 + 64);
        z = (uint8_t*)malloc(clen);
        if (compress2(z, &clen, raw, (unsigned long)rawlen, 6) != 0) { free(z); z=NULL; }
        if (z) { png_chunk(f,"IDAT",z,(uint32_t)clen); free(z); }
    }
    if (!z) { free(raw); fclose(f); return -1; }
#else
    zlen=2+rawlen+(rawlen/65535+1)*5+4; z=(uint8_t*)malloc(zlen);
    z[pos++]=0x78; z[pos++]=0x01; off=0;
    while(off<rawlen){ size_t n=rawlen-off; int fin; if(n>65535)n=65535; fin=(off+n>=rawlen);
        z[pos++]=(uint8_t)(fin?1:0); z[pos++]=(uint8_t)(n&0xff); z[pos++]=(uint8_t)((n>>8)&0xff);
        z[pos++]=(uint8_t)(~n&0xff); z[pos++]=(uint8_t)((~n>>8)&0xff);
        memcpy(z+pos,raw+off,n); pos+=n; off+=n; }
    for(i=0;i<rawlen;i++){ a=(a+raw[i])%65521; b=(b+a)%65521; }
    be32(z+pos,(b<<16)|a); pos+=4;
    png_chunk(f,"IDAT",z,(uint32_t)pos); free(z);
#endif
    png_chunk(f,"IEND",NULL,0);
    fclose(f); free(raw); return 0;
}

/* ---------- 绘图原语 ---------- */
static void rect(int x,int y,int w,int h,int r,int g,int b,int a)
{
    Evas_Object*o=evas_object_rectangle_add(EV);
    evas_object_color_set(o,r,g,b,a); evas_object_move(o,x,y); evas_object_resize(o,w,h);
    evas_object_show(o); g_rect_n++;
}
/* 取整、限幅，防负数与溢出把 evas 搞崩 */
static int clampi(int v,int lo,int hi){ return v<lo?lo:(v>hi?hi:v); }
static void text(int x,int y,const char*s,int sz,int r,int g,int b)
{
    Evas_Object*t=evas_object_text_add(EV);
    evas_object_text_font_source_set(t,FONT_FILE);
    evas_object_text_font_set(t,FONT_FAM,sz);
    evas_object_text_text_set(t,s);
    evas_object_color_set(t,r,g,b,255);
    evas_object_move(t,x,y); evas_object_show(t); g_font_n++;
}
static void bg(int W,int H){ rect(0,0,W,H,C_BG,255); }
static void header(const char*cn,const char*en,const char*right)
{
    rect(0,0,720,40,26,30,44,255);
    text(10,6,cn,26,C_TEXT);
    text(230,10,en,20,C_DIM);
    if(right) text(560,12,right,18,C_HL);
}
static void statusbar(const char*s)
{
    rect(0,444,720,36,20,24,34,255);
    text(10,449,s,20,C_OK);
}
/* 列表行：色块 + 主标签 + 右侧副文本 + 选中标记 */
static void row(int y,const char*label,const char*sub,int sel,int cr,int cg,int cb,int h)
{
    rect(10,y,700,h, sel?38:26, sel?44:30, sel?56:44, 255);
    rect(16,y+(h-30)/2,30,30,cr,cg,cb,255);
    text(56,y+(h-22)/2,label,22, sel?255:210, sel?220:210, sel?120:210);
    if(sub) text(430,y+(h-19)/2,sub,18,C_DIM);
    if(sel)  text(660,y+(h-22)/2,"<",22,C_HL);
}
/* 滑块行：名字 + 槽 + 已填 + 数值 */
static void slider(int y,const char*name,int v,int vmax,const char*tag)
{
    char buf[64];
    rect(10,y,700,36,26,30,44,255);
    text(20,y+6,name,20,215,215,225);
    rect(190,y+14,340,10,60,66,86,255);
    rect(190,y+14,clampi((int)(340.0*v/(vmax?vmax:1)),0,340),10,90,170,240,255);
    snprintf(buf,sizeof(buf),"%d",v);
    text(548,y+6,buf,20,255,215,120);
    if(tag) text(600,y+7,tag,18,C_OK);
}
/* 键值行（诊断/状态页） */
static void kv(int y,const char*k,const char*v,int vr,int vg,int vb)
{
    rect(10,y,700,30,22,26,38,255);
    text(20,y+4,k,20,C_TEXT2);
    text(420,y+4,v,20,vr,vg,vb);
}
/* 小徽标 */
static void badge(int x,int y,const char*s,int r,int g,int b)
{
    rect(x,y,96,26,r/3,g/3,b/3,255);
    text(x+8,y+2,s,18,r,g,b);
}
/* 进度条 */
static void bar(int x,int y,int w,const char*label,int pct,int r,int g,int b)
{
    char buf[32];
    text(x,y-4,label,18,C_DIM);
    rect(x,y+22,w,12,50,56,74,255);
    rect(x,y+22,clampi(w*pct/100,0,w),12,r,g,b,255);
    snprintf(buf,sizeof(buf),"%d%%",pct);
    text(x+w+8,y+16,buf,18,C_TEXT2);
}
/* 分区小标题 */
static void sect(int y,const char*s,int r,int g,int b)
{
    rect(10,y,4,20,r,g,b,255);
    text(22,y-2,s,20,r,g,b);
}

/* ============================ P1 配方库 ============================ */
static void page1(void)
{
    static const char*FAM[5]={"负片 Negative","反转 Reversal","黑白 B&W","电影 Cinema","风格 Stylized"};
    static const char*L[6]={"Portra 400","Velvia 50","TriX 400","Ektar 100","Superia X-TRA400","HP5 Plus"};
    static const char*S[6]={"负片 100/93/88","反转 112/104/96","黑白 103/101/99","负片 108/96/86","负片 105/98/92","黑白 100/100/100"};
    int i;
    header("配方库","Recipes","95 条 / 6 页");
    text(14,48,"族：负片 32 · 反转 18 · 黑白 15 · 电影 14 · 风格 16",18,C_DIM);
    for(i=0;i<6;i++) row(74+i*44,L[i],S[i], i==2, 120+i*12, 96+i*9, 74+i*7, 40);
    text(14,352,"[3/6 页]  trix400",20,C_HL);
    rect(10,382,170,44,40,46,60,255);  text(40,392,"上一页",22,C_TEXT2);
    rect(190,382,170,44,40,46,60,255); text(220,392,"下一页",22,C_TEXT2);
    rect(370,382,170,44,40,46,60,255); text(400,392,"应用所选",22,C_OK);
    rect(550,382,160,44,60,36,36,255); text(580,392,"返回",22,C_DANGER);
    statusbar("波轮翻页 · 点击应用（不关窗）· 配方源：SD 卡 filmlab/recipes.json");
}

/* ============================ P2 配方详情 ============================ */
static void page2(void)
{
    static const char*N[7]={"R 红","G 绿","B 蓝","HUE 色调","SAT 饱和","SHARP 锐度","CON 对比"};
    static const int  V[7]={106,100,93,11,9,9,8};
    int i;
    header("配方详情","Recipe · portra400","已装入槽 3");
    rect(10,46,340,86,26,30,44,255);
    rect(24,58,62,62,180,110,80,255);
    text(100,58,"Portra 400",24,C_TEXT);
    text(100,88,"Kodak · 负片 · 100/93/88",18,C_DIM);
    rect(366,46,344,86,26,30,44,255);
    text(378,54,"引擎：ksfilm.arm",19,C_TEXT2);
    text(378,78,".cube：portra400.cube",19,C_TEXT2);
    text(378,102,"来源：SD /mnt/mmc/luts",19,C_DIM);
    sect(142,"七维参数",C_HL);
    for(i=0;i<7;i++) kv(168+i*28,N[i], (i<3)?"外部可直推(A1前不可)":"外部直推 ✓", 90,170,240);
    { char b[64]; snprintf(b,sizeof(b),"%d / %d / %d",V[0],V[1],V[2]); text(420,168,b,20,150,160,185); }
    text(420,196,"11",20,150,160,185);
    text(420,224,"9 / 9 / 8",20,150,160,185);
    rect(10,382,170,44,40,46,60,255); text(30,392,"应用 (--fast)",21,C_OK);
    rect(190,382,170,44,40,46,60,255); text(212,392,"写槽不切",21,C_TEXT2);
    rect(370,382,170,44,40,46,60,255); text(392,392,"对比原图",21,C_TEXT2);
    rect(550,382,160,44,60,36,36,255); text(574,392,"删除",21,C_DANGER);
    statusbar("三维即时生效 · R/G/B/HUE 需 A1(p7 patch) 或机身『自定义1』");
}

/* ============================ P3 PW 七维 ============================ */
static void page3(void)
{
    static const char*N[7]={"R 红","G 绿","B 蓝","HUE 色调","SAT 饱和","SHARP 锐度","CON 对比"};
    static const int  V[7]={106,100,93,11,9,9,8};
    static const char*T[7]={"需A1","需A1","需A1","需A1","直推✓","直推✓","直推✓"};
    int i;
    header("参数调整","Picture Wizard · 7 axes","槽 3 / 14");
    for(i=0;i<7;i++) slider(46+i*52,N[i],V[i],30,T[i]);
    rect(10,412,222,26,22,26,38,255);  text(20,414,"长按 = 回默认",18,C_DIM);
    rect(242,412,222,26,22,26,38,255); text(252,414,"写入 prefman + ISP 重读",18,C_DIM);
    rect(474,412,236,26,22,26,38,255); text(484,414,"判定：filmlab.sh check",18,C_DIM);
    statusbar("值变了 ≠ 被消费 —— 一律以 check/iqr 客观判据为准");
}

/* ============================ P4 3D LUT 管理 ============================ */
static void page4(void)
{
    header("3D LUT 管理","3D LUT","预览直灌 / 成片后处理");
    text(14,48,"SD 卡 LUT   /mnt/mmc/luts/*.cube",19,C_DIM);
    row(72, "Portra400.cube","SD 33³", 1,180,120, 90,42);
    row(118,"Velvia50.cube","SD 33³",  0,120,140,180,42);
    row(164,"TriX400.cube","SD 33³",   0,140,140,140,42);
    text(14,212,"机身内置 4 档",19,C_DIM);
    row(236,"内置 1  identity","内置", 0,128,128,128,40);
    row(280,"内置 2  暖肤色","内置",   0,190,150,120,40);
    row(324,"内置 3  风格化","内置",   0,140,120,190,40);
    rect(10,372,220,40,40,46,60,255);  text(38,380,"写入所选 LUT",21,C_TEXT2);
    rect(240,372,220,40,40,46,60,255); text(268,380,"重新扫描 SD",21,C_TEXT2);
    rect(470,372,240,40,60,36,36,255); text(506,380,"恢复出厂表",21,C_DANGER);
    statusbar("写入走 LUT1 + lutsentinel 守护 · 只影响预览，不改 p7");
}

/* ============================ P5 引擎与判据 ============================ */
static void page5(void)
{
    header("FilmLab 引擎","Engine & Verdict","判据基准");
    kv(50, "引擎 ksfilm.arm",   "v2 / ARM softfp -O0", 120,255,160);
    kv(84, "配方库 recipes.json","95 条 · 21216 B",     210,210,215);
    kv(118,"配套 .cube",         "17 个内置 + SD 可选",  210,210,215);
    sect(156,"apply --fast 判据（只读回读）",C_HL);
    kv(182,"SAT   期望 9  实测 9","命中", 120,255,160);
    kv(216,"SHARP 期望 9  实测 9","命中", 120,255,160);
    kv(250,"CON   期望 8  实测 8","命中", 120,255,160);
    kv(284,"HUE   期望 11 实测 11","命中", 120,255,160);
    rect(10,322,700,74,22,26,38,255);
    text(20,330,"判据命令：sh /opt/usr/nx-ks/filmlab.sh check",19,C_TEXT2);
    text(20,354,"回读 ISP 手上那 7 维并与配方槽位比对（只读 / 零风险）",19,C_DIM);
    rect(10,404,340,32,40,46,60,255); text(30,408,"导入配方（SD→相机）",20,C_TEXT2);
    rect(360,404,350,32,40,46,60,255); text(380,408,"导出配方（相机→SD）",20,C_TEXT2);
    statusbar("『值变了』≠『被消费』—— 这一条是全项目的判据基准");
}

/* ============================ P6 Web 遥控与相册 ============================ */
static void page6(void)
{
    header("Web 遥控 / 相册","nx-rc · Album","80 / 8080");
    kv(50, "遥控服务 (80)",      "运行中",       120,255,160);
    kv(84, "相册实时目录 dirlist","每次 readdir",  120,255,160);
    kv(118,"缩略图 CGI thumb",    "缓存命中 92%", 120,255,160);
    kv(152,"WiFi push",          "在线",         120,255,160);
    rect(10,190,700,26,22,26,38,255);
    text(20,192,"缩略图预热（nice -n 19，不影响拍摄）",19,C_TEXT2);
    bar(20,232,540,"网格 320px · 最新 300 张", 68, 90,170,240);
    bar(20,286,540,"灯箱 1024px · 最新 60 张", 35, 90,200,140);
    rect(10,340,700,72,22,26,38,255);
    text(20,346,"相册模型：折叠目录（目录倒序、默认只展开最新）",19,C_TEXT2);
    text(20,372,"根治单核 CPU 上『目录多 ⇒ 首屏卡顿』；新拍照片立即可见",19,C_DIM);
    rect(10,418,340,22,40,46,60,255); text(30,418,"开关遥控",19,C_TEXT2);
    rect(360,418,350,22,40,46,60,255); text(380,418,"打开相册页面",19,C_TEXT2);
    statusbar("80 端口 daemon 的目录列表是启动快照 ⇒ 必须走 8080 dirlist 实时接口");
}

/* ============================ P7 网络与连接 ============================ */
static void page7(void)
{
    header("网络与连接","Network","WiFi");
    kv(50, "IP 地址",        "192.168.0.105", 255,200,80);
    kv(84, "Telnet (23)",    "开 · root",     120,255,160);
    kv(118,"FTP (21)",       "开 · root 空密码",120,255,160);
    kv(152,"SSH (dropbear)", "开 · 需 -i nx500_key",120,255,160);
    kv(186,"HTTP (80 / 8080)","开",            120,255,160);
    sect(224,"8080 服务群（busybox httpd）",C_HL);
    row(250,"thumb   缩略图","DCT 缩放 + SD 缓存",0, 90,170,240,40);
    row(294,"dirlist 实时目录","每次 readdir",     0, 90,200,140,40);
    row(338,"prewarm 预热进度","前端进度条",        0,200,180, 90,40);
    row(382,"push    WiFi 推送","免拔卡部署",       0,180,140,200,40);
    statusbar("点主菜单首行即可开/关 Telnet+FTP；不再用 EV+WiFi 组合键");
}

/* ============================ P8 拍摄参数与键位 ============================ */
static void page8(void)
{
    header("拍摄参数 / 键位","Capture · Keys","原 NX-KS 模块");
    kv(50, "拍摄参数 Web API", "capdtm setusr/getusr", 120,255,160);
    kv(84, "WB 模式 / 色调两轴","可用",                120,255,160);
    kv(118,"键位映射 EV_*.sh",  "13 个按键脚本",        210,210,215);
    kv(152,"码率 / 黑场",       "br_*.sh · blackout",   210,210,215);
    kv(186,"全量装载/保存",     "FullLoad / FullSave",  210,210,215);
    sect(224,"常用键位",C_HL);
    row(250,"EV + AEL","★ 打开 FilmLab 配方菜单",1, 255,200, 80,40);
    row(294,"EV + UP / DOWN","亮度 ±",      0, 90,170,240,40);
    row(338,"EV + LEFT / RIGHT","对焦栈切换",0, 90,170,240,40);
    row(382,"长按 OK","自定义按钮 (cButton)",0, 90,170,240,40);
    statusbar("键位脚本位于 /opt/usr/nx-ks/scripts/ · 可在 SD 卡上改");
}

/* ============================ P9 同步与安装 ============================ */
static void page9(void)
{
    header("同步与安装","Sync & Install","智能引导器");
    kv(50, "固件版本",   "/etc/version.info = 1.12", 255,200, 80);
    kv(84, "mod 落点",   "/opt/usr/nx-ks/ (= p14)",  120,255,160);
    kv(118,"引导链",     "info.tg → nx_cs.adj → install.sh",120,255,160);
    kv(152,"安装模式",   "未装=全量 / 已装=增量同步", 210,210,215);
    kv(186,"卸载",       "相机菜单 uninstall.sh",     210,210,215);
    rect(10,222,700,70,22,26,38,255);
    text(20,228,"★ 插卡即自动执行，不需要按键；『安装完成』后手动开一次蓝牙以初始化 mod",19,C_TEXT2);
    text(20,254,"★ 增量同步只覆盖不删除、永不误卸载；SD 上 scripts/ 母本保留",19,C_DIM);
    sect(306,"部署通道",C_HL);
    row(332,"SD 卡插入","离线 / 无需网络",       0, 90,170,240,40);
    row(376,"WiFi push","8080 /push · 免拔卡",    0, 90,200,140,40);
    statusbar("刷固件不碰 mod：/opt/usr = p14，不在 SLP 10 段内");
}

/* ============================ P10 诊断与高危 ============================ */
static void page10(void)
{
    header("诊断 / 高危","Diagnostics","只读优先");
    sect(48,"固件与备份状态",C_HL);
    kv(74, "p7 md5    5fc4824f…","与官方一致",     120,255,160);
    kv(108,"分区备份  11/11",     "md5 全部匹配",   120,255,160);
    kv(142,"p12 pcache","已回纯净 0x00",          120,255,160);
    kv(176,"A1 p7 patch","未刷（slp_…v116 待刷）", 255,200, 80);
    sect(214,"高危操作（默认禁用 · 二次确认）",C_DANGER);
    rect(10,240,340,44,60,36,36,255); text(46,248,"刷写固件（需确认串）",21,255,190,190);
    rect(360,240,350,44,34,38,50,255); text(396,248,"备份校验（只读）",21,200,200,210);
    rect(10,296,700,54,44,30,30,255);
    text(20,302,"二次确认：输入 CONFIRM-FLASH 后才可提交",19,255,200,160);
    text(20,328,"★ 单分区写错可能变砖；boot0 / boot1 绝不碰",19,200,170,170);
    rect(10,362,700,34,22,26,38,255);
    text(20,366,"门控：python test_server/tools/gate_flow.py（六门全绿才允许 L4）",18,C_DIM);
    rect(10,404,220,32,40,46,60,255); text(30,408,"导出诊断日志",19,C_TEXT2);
    rect(240,404,220,32,40,46,60,255); text(260,408,"校验备份 md5",19,C_TEXT2);
    rect(470,404,240,32,40,46,60,255); text(500,408,"回到取景",19,C_TEXT2);
    statusbar("诊断页只读；所有写操作须经门控 + 二次确认");
}

/* ============================ main ============================ */
typedef void (*pagefn)(void);
static pagefn PAGES[] = { page1,page2,page3,page4,page5,page6,page7,page8,page9,page10 };
static const char*PNAME[] = {
    "配方库 Recipes","配方详情 Recipe","PW 七维 Picture Wizard","3D LUT 管理","引擎与判据 Engine & Verdict",
    "Web 遥控/相册 nx-rc","网络与连接 Network","拍摄参数/键位 Capture & Keys","同步与安装 Sync & Install","诊断/高危 Diagnostics"
};
#define NPAGES ((int)(sizeof(PAGES)/sizeof(PAGES[0])))

int main(int argc,char**argv)
{
    const char*outdir=(argc>1)?argv[1]:"/tmp";
    int W=(argc>2)?atoi(argv[2]):720, H=(argc>3)?atoi(argv[3]):480;
    int p;
    crc_init();
    g_log=getenv("UI_LOG");
    logf_("== modui_render start pid=%d outdir=%s %dx%d pages=%d\n",(int)getpid(),outdir,W,H,NPAGES);
    logf_("   font exist=%d (%s)\n", access(FONT_FILE,R_OK)==0, FONT_FILE);
    if(access(FONT_FILE,R_OK)!=0){ logf_("FATAL font\n"); return 2; }
    logf_("   evas=%d ecore=%d ecore_evas=%d\n", evas_init(), ecore_init(), ecore_evas_init());

    for(p=0;p<NPAGES;p++){
        char path[512]; uint8_t*rgb; void*px; int x,y;
        Ecore_Evas*ee=ecore_evas_buffer_new(W,H);
        if(!ee){ logf_("FATAL buffer_new page %d\n",p+1); return 3; }
        EV=ecore_evas_get(ee);
        if(!EV){ logf_("FATAL evas NULL page %d\n",p+1); return 4; }
        g_rect_n=0;

        bg(W,H);
        PAGES[p]();
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
            logf_("PAGE %d -> %s  name=%s rect_n=%d ink=%d\n",p+1,path,PNAME[p],g_rect_n,ink);
        }
        free(rgb);
    }
    logf_("== done, total font_set calls = %d\n", g_font_n);
    return 0;
}
