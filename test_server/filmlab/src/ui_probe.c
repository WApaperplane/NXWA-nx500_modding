/* ui_probe.c —— 探针：buffer 引擎下 elementary 控件能不能真离线渲染
 *
 * 目的：cjk_render.c 只证了【裸 evas 对象】能离线出字。本探针回答下一个问题：
 *   ① 不设 ECORE_EVAS_ENGINE，只把 ELM_ENGINE=buffer，elm_init/elm_win_add 是否成功？
 *   ② elm_win 底层是不是一个 ecore_evas_buffer？（用 ecore_evas_ecore_evas_list_get 取回）
 *   ③ 真控件（elm_label/elm_list/elm_slider/...）能不能写进这块 buffer 并光栅化？
 *   ④ 中文标签在【真控件】里是否照样出字（无 tofu）？
 *
 * 用法：ui_probe <out.png> [w h]
 * 退出码 0 成功
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <unistd.h>
#include <signal.h>
#include <ucontext.h>

typedef void Ecore_Evas;
typedef void Evas;
typedef void Evas_Object;
typedef void Elm_Object_Item;
typedef struct _Eina_List Eina_List;
struct _Eina_List { void *data; Eina_List *next; Eina_List *prev; };

/* elementary（符号已用 dynsym 核对 libelementary.so.1.7.99 确有导出） */
extern int          elm_init(int argc, char **argv);
extern void         elm_shutdown(void);
extern Evas_Object *elm_win_util_standard_add(const char *name, const char *title);
extern Evas_Object *elm_win_add(Evas_Object *parent, const char *name, int type);
extern Evas_Object *elm_label_add(Evas_Object *parent);
extern Evas_Object *elm_button_add(Evas_Object *parent);
extern Evas_Object *elm_list_add(Evas_Object *parent);
extern Evas_Object *elm_slider_add(Evas_Object *parent);
extern Evas_Object *elm_radio_add(Evas_Object *parent);
extern Evas_Object *elm_entry_add(Evas_Object *parent);
extern Evas_Object *elm_table_add(Evas_Object *parent);
extern void         elm_object_part_text_set(Evas_Object *o, const char *part, const char *txt);
extern void         elm_object_part_content_set(Evas_Object *o, const char *part, Evas_Object *c);
extern Elm_Object_Item *elm_list_item_append(Evas_Object *o, const char *label, Evas_Object *icon, Evas_Object *end, void *cb, void *data);
extern void         elm_object_item_part_text_set(Elm_Object_Item *it, const char *part, const char *txt);
extern void         elm_list_go(Evas_Object *o);
extern Evas_Object *elm_list_item_object_get(const Elm_Object_Item *it);
extern void         elm_list_item_selected_set(Elm_Object_Item *it, int sel);
extern void         elm_slider_value_set(Evas_Object *o, double v);
extern void         elm_slider_min_max_set(Evas_Object *o, double mn, double mx);
extern void         elm_slider_indicator_show_set(Evas_Object *o, int s);
extern void         elm_table_pack(Evas_Object *o, Evas_Object *c, int cx, int cy, int cw, int ch);
extern void         elm_win_activate(Evas_Object *o);
extern void         elm_win_title_set(Evas_Object *o, const char *t);
extern int          elm_config_engine_set(const char *engine);
extern const char  *elm_config_engine_get(void);
extern int          elm_config_preferred_engine_set(const char *engine);

/* ecore */
extern int          ecore_init(void);
extern int          ecore_main_loop_iterate(void);
extern const Eina_List *ecore_evas_ecore_evas_list_get(void);
extern const char  *ecore_evas_engine_name_get(const Ecore_Evas *ee);
extern void         ecore_evas_manual_render_set(Ecore_Evas *ee, int manual_render);
extern void         ecore_evas_manual_render(Ecore_Evas *ee);
extern void        *ecore_evas_buffer_pixels_get(Ecore_Evas *ee);

/* evas */
extern int          evas_init(void);
extern Evas        *evas_object_evas_get(const Evas_Object *o);
extern Evas_Object *evas_object_rectangle_add(Evas *e);
extern Evas_Object *evas_object_text_add(Evas *e);
extern void         evas_object_text_font_source_set(Evas_Object *o, const char *path);
extern void         evas_object_text_font_set(Evas_Object *o, const char *font, int size);
extern void         evas_object_text_text_set(Evas_Object *o, const char *text);
extern void         evas_object_geometry_get(const Evas_Object *o, int *x, int *y, int *w, int *h);
extern void         evas_object_color_set(Evas_Object *o, int r, int g, int b, int a);
extern void         evas_object_move(Evas_Object *o, int x, int y);
extern void         evas_object_resize(Evas_Object *o, int w, int h);
extern void         evas_object_show(Evas_Object *o);
extern void         evas_object_size_hint_weight_set(Evas_Object *o, double x, double y);

#define FONT_FILE "/usr/share/fonts/SDIC_GP_US_20120720.ttf"
#define FONT_FAM  "SDIC_GP_US"

static const char *g_log = NULL;
static void logf_(const char *fmt, ...)
{
    va_list ap; FILE *f;
    va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap);
    if (g_log) { f = fopen(g_log, "a"); if (f) { va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap); fclose(f); } }
}

/* ★ 自装 SIGSEGV 处理器：① 打印 PC/LR/maps 便于定位；② 干净 _exit
 *   避免默认 core dump 触发 WSL 的 core_pattern(|/wsl-capture-crash) 无限级联。 */
static void segv_handler(int sig, siginfo_t *si, void *ctx)
{
    ucontext_t *uc = (ucontext_t *)ctx;
    FILE *f;
    logf_("!! SIGNAL %d addr=%p pc=%p lr=%p\n", sig, si->si_addr,
          (void *)(uintptr_t)uc->uc_mcontext.arm_pc,
          (void *)(uintptr_t)uc->uc_mcontext.arm_lr);
    f = fopen("/proc/self/maps", "r");
    if (f) {
        char line[512];
        while (fgets(line, sizeof line, f)) {
            if (strstr(line, "libelementary") || strstr(line, "libecore_x") ||
                strstr(line, "libevas") || strstr(line, "libecore_evas") ||
                strstr(line, "ui_probe"))
                logf_("   MAP %s", line);
        }
        fclose(f);
    }
    _exit(42);
}

/* ---- 自写 PNG（stored deflate，零依赖）---- */
static uint32_t crc_table[256];
static void crc_init(void){ uint32_t c; int n,k; for(n=0;n<256;n++){c=(uint32_t)n;for(k=0;k<8;k++)c=(c&1)?(0xedb88320u^(c>>1)):(c>>1);crc_table[n]=c;} }
static uint32_t crc32_buf(const uint8_t*b,size_t n){uint32_t c=0xffffffffu;size_t i;for(i=0;i<n;i++)c=crc_table[(c^b[i])&0xff]^(c>>8);return c^0xffffffffu;}
static void be32(uint8_t*p,uint32_t v){p[0]=(uint8_t)(v>>24);p[1]=(uint8_t)(v>>16);p[2]=(uint8_t)(v>>8);p[3]=(uint8_t)v;}
static void png_chunk(FILE*f,const char*t,const uint8_t*d,uint32_t len)
{
    uint8_t hdr[8],crcb[4]; uint32_t crc; uint8_t*body=(uint8_t*)malloc(len+4);
    be32(hdr,len); fwrite(hdr,1,4,f); fwrite(t,1,4,f); if(len)fwrite(d,1,len,f);
    memcpy(body,t,4); if(len)memcpy(body+4,d,len); crc=crc32_buf(body,len+4); be32(crcb,crc); fwrite(crcb,1,4,f); free(body);
}
static int write_png(const char*path,int w,int h,const uint8_t*rgb)
{
    FILE*f=fopen(path,"wb"); uint8_t sig[8]={0x89,'P','N','G','\r','\n',0x1a,'\n'}; uint8_t ihdr[13];
    size_t rawlen=(size_t)h*(1+(size_t)w*3); uint8_t*raw,*z; size_t zlen,off,i,pos=0; uint32_t a=1,b=0;
    if(!f)return -1; fwrite(sig,1,8,f);
    be32(ihdr,(uint32_t)w); be32(ihdr+4,(uint32_t)h); ihdr[8]=8;ihdr[9]=2;ihdr[10]=0;ihdr[11]=0;ihdr[12]=0;
    png_chunk(f,"IHDR",ihdr,13);
    raw=(uint8_t*)malloc(rawlen);
    for(i=0;i<(size_t)h;i++){raw[i*(1+(size_t)w*3)]=0;memcpy(raw+i*(1+(size_t)w*3)+1,rgb+i*(size_t)w*3,(size_t)w*3);}
    zlen=2+rawlen+(rawlen/65535+1)*5+4; z=(uint8_t*)malloc(zlen); z[pos++]=0x78;z[pos++]=0x01; off=0;
    while(off<rawlen){size_t n=rawlen-off;int fin;if(n>65535)n=65535;fin=(off+n>=rawlen);z[pos++]=(uint8_t)(fin?1:0);z[pos++]=(uint8_t)(n&0xff);z[pos++]=(uint8_t)(n>>8);z[pos++]=(uint8_t)(~n&0xff);z[pos++]=(uint8_t)((~n>>8)&0xff);memcpy(z+pos,raw+off,n);pos+=n;off+=n;}
    for(i=0;i<rawlen;i++){a=(a+raw[i])%65521;b=(b+a)%65521;} be32(z+pos,(b<<16)|a);pos+=4;
    png_chunk(f,"IDAT",z,(uint32_t)pos); png_chunk(f,"IEND",NULL,0); fclose(f); free(raw); free(z); return 0;
}

int main(int argc, char **argv)
{
    const char *out = (argc>1)?argv[1]:"/tmp/ui_probe.png";
    int W=(argc>3)?atoi(argv[2]):720, H=(argc>3)?atoi(argv[3]):480;
    Evas_Object *win, *bg, *tbl, *lbl, *lst, *sld, *btn, *rad, *ent;
    Evas *evas; Ecore_Evas *ee=NULL; void *px; uint8_t *rgb;
    const Eina_List *l; int n_ee=0, i;
    int nonblack=0;

    crc_init(); g_log=getenv("UI_LOG");
    { struct sigaction sa; memset(&sa,0,sizeof sa); sa.sa_sigaction=segv_handler; sa.sa_flags=SA_SIGINFO; sigaction(SIGSEGV,&sa,NULL); sigaction(SIGBUS,&sa,NULL); }
    logf_("== ui_probe start out=%s %dx%d\n", out, W, H);
    logf_("   ELM_ENGINE=%s ECORE_EVAS_ENGINE=%s\n",
          getenv("ELM_ENGINE")?getenv("ELM_ENGINE"):"(unset)",
          getenv("ECORE_EVAS_ENGINE")?getenv("ECORE_EVAS_ENGINE"):"(unset)");
    logf_("   font exists=%d\n", access(FONT_FILE,R_OK)==0);

    logf_("   evas_init=%d\n", evas_init());
    logf_("   ecore_init=%d\n", ecore_init());
    { int r=elm_init(0,NULL); logf_("   elm_init=%d (期望 1)\n", r); if(!r){logf_("FATAL elm_init\n");return 2;} }
    /* ★★ 关键：elementary 默认 engine=NULL ⇒ ecore_evas_new(NULL,...) 选了 software_x11
     *   （上一次探针即崩在 ecore_x_window_root_first_get）。必须在建窗前显式钉成 buffer。 */
    logf_("   engine before set = '%s'\n", elm_config_engine_get()?elm_config_engine_get():"(null)");
    logf_("   elm_config_engine_set(buffer) = %d\n", elm_config_engine_set("buffer"));
    logf_("   elm_config_preferred_engine_set(buffer) = %d\n", elm_config_preferred_engine_set("buffer"));
    logf_("   engine after  set = '%s'\n", elm_config_engine_get()?elm_config_engine_get():"(null)");

    win = elm_win_util_standard_add("nxks2-ui", "NX-KS2 UI");
    logf_("   elm_win_util_standard_add -> %p\n", (void*)win);
    if(!win){ logf_("   retry elm_win_add(ELM_WIN_BASIC=1)\n"); win=elm_win_add(NULL,"nxks2-ui",1); logf_("   elm_win_add -> %p\n",(void*)win); }
    if(!win){ logf_("FATAL no win\n"); return 3; }
    evas = evas_object_evas_get(win);
    logf_("   win evas=%p\n", (void*)evas);
    { const Eina_List *q=ecore_evas_ecore_evas_list_get(); int k=0; for(;q;q=q->next){ k++; logf_("   [pre-resize] ee%d=%p engine='%s'\n", k, q->data, ecore_evas_engine_name_get((Ecore_Evas*)q->data)); } logf_("   [pre-resize] ee count=%d\n", k); }
    logf_("   ... evas_object_resize(win) ...\n");
    evas_object_resize(win, W, H);
    logf_("   ... resize OK ...\n");
    elm_win_title_set(win, "NX-KS2 UI");
    logf_("   ... title OK ...\n");

    bg = evas_object_rectangle_add(evas);
    evas_object_color_set(bg, 18,20,28,255);
    evas_object_move(bg,0,0); evas_object_resize(bg,W,H); evas_object_show(bg);

    tbl = elm_table_add(win);
    logf_("   elm_table_add OK\n");
    evas_object_resize(tbl, W, H); evas_object_show(tbl);

    /* 真控件：label（中文） */
    lbl = elm_label_add(win);
    logf_("   elm_label_add OK\n");
    elm_object_part_text_set(lbl, NULL, "P1 配方库 · 胶片配方 Portra 400 / 中文出字测试");
    evas_object_move(lbl, 16, 12); evas_object_resize(lbl, W-32, 40); evas_object_show(lbl);
    logf_("   elm_label configured\n");

    /* 真控件：list 3 项 */
    lst = elm_list_add(win);
    logf_("   elm_list_add OK\n");
    evas_object_move(lst, 16, 60); evas_object_resize(lst, 420, 130); evas_object_show(lst);
    { const char *it[3]={"配方 01 · Portra 400 柔和肤色","配方 02 · Velvia 50 浓郁风光","配方 03 · Tri-X 400 黑白颗粒"};
      Elm_Object_Item *e; int k;
      for(i=0;i<3;i++){ e=elm_list_item_append(lst, it[i], NULL, NULL, NULL, NULL);
        if(i==1) elm_list_item_selected_set(e, 1);
        { Evas_Object *io=elm_list_item_object_get(e); int gx,gy,gw,gh; evas_object_geometry_get(io,&gx,&gy,&gw,&gh);
          logf_("   list item %d geom=(%d,%d,%dx%d)\n", i, gx,gy,gw,gh); }
      }
      (void)k; elm_list_go(lst); logf_("   elm_list_go OK\n"); }

    /* 真控件：slider */
    sld = elm_slider_add(win);
    logf_("   elm_slider_add OK\n");
    evas_object_move(sld, 16, 210); evas_object_resize(sld, 420, 40); evas_object_show(sld);
    elm_slider_min_max_set(sld, 0, 100); elm_slider_value_set(sld, 62);

    /* 真控件：button / radio / entry */
    btn = elm_button_add(win);
    logf_("   elm_button_add OK\n");
    elm_object_part_text_set(btn, NULL, "应用"); evas_object_move(btn,470,60); evas_object_resize(btn,110,44); evas_object_show(btn);
    rad = elm_radio_add(win);
    logf_("   elm_radio_add OK\n");
    elm_object_part_text_set(rad, NULL, "暖肤色"); evas_object_move(rad,470,120); evas_object_resize(rad,150,40); evas_object_show(rad);
    ent = elm_entry_add(win);
    logf_("   elm_entry_add OK\n");
    elm_object_part_text_set(ent, NULL, "确认串：FLASH-P7"); evas_object_move(ent,470,180); evas_object_resize(ent,230,60); evas_object_show(ent);

    /* 真控件：evas text（对照，显式字体） */
    {
        Evas_Object *t = evas_object_text_add(evas);
        evas_object_text_font_source_set(t, FONT_FILE);
        evas_object_text_font_set(t, FONT_FAM, 20);
        evas_object_text_text_set(t, "EVAS-TEXT 中文对照 · 影调 颗粒");
        evas_object_color_set(t, 255,200,80,255);
        evas_object_move(t,16,300); evas_object_show(t);
        { int tx,ty,tw,th; evas_object_geometry_get(t,&tx,&ty,&tw,&th); logf_("   evas text geom=(%d,%d,%dx%d)\n",tx,ty,tw,th); }
    }

    evas_object_show(win);
    logf_("   win shown, entering main loop iterations\n");

    for(i=0;i<30;i++) ecore_main_loop_iterate();
    logf_("   main loop iterations done\n");

    l = ecore_evas_ecore_evas_list_get();
    for(; l; l=l->next){ n_ee++; logf_("   ee[%d]=%p engine='%s'\n", n_ee, l->data, ecore_evas_engine_name_get((Ecore_Evas*)l->data)); if(!ee) ee=(Ecore_Evas*)l->data; }
    logf_("   ecore_evas count=%d\n", n_ee);
    if(!ee){ logf_("FATAL: no ecore_evas found\n"); return 4; }

    ecore_evas_manual_render_set(ee, 1);
    ecore_evas_manual_render(ee);
    px = ecore_evas_buffer_pixels_get(ee);
    logf_("   pixels=%p\n", px);
    if(!px){ logf_("FATAL: pixels_get NULL (引擎可能不是 buffer)\n"); return 5; }

    rgb=(uint8_t*)malloc((size_t)W*H*3);
    { const uint8_t*p=(const uint8_t*)px; int x,y;
      for(y=0;y<H;y++)for(x=0;x<W;x++){const uint8_t*q=p+((size_t)y*W+x)*4;uint8_t B=q[0],G=q[1],R=q[2],A=q[3];
        rgb[((size_t)y*W+x)*3+0]=A?R:0; rgb[((size_t)y*W+x)*3+1]=A?G:0; rgb[((size_t)y*W+x)*3+2]=A?B:0;
        if(R>90||G>90||B>90)nonblack++; } }
    logf_("   nonblack=%d / %d px\n", nonblack, W*H);
    write_png(out, W, H, rgb);
    logf_("   PNG written: %s\n== ui_probe done\n", out);
    return 0;
}
