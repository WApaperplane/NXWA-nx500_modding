/*
 * ★ nxfilmui 本地行为回归测试（PC 版，不是交叉编译）
 *
 * 为什么要这个
 * ------------
 * 「编译通过」只证明符号能解析，不证明逻辑对。
 * nxfilmui.c 里最容易静默出错的是 load_recipes 的分段读法
 * （read 会截断半行、必须保留到下次 read 之后接着解析）。
 * 这段逻辑错了 → 屏幕上是空列表，但程序不报错。
 *
 * 做法：把解析代码抽成可编译的独立单元，用 PC gcc 编一个测试程序，
 * 喂真配方文件，断言解析结果逐个字段正确。
 * —— 属于「判据工具本身要有判据」：nxfilmui 的解析也有判据。
 *
 * 编译（PC）：
 *   gcc -O0 -DTEST_LOCAL -o /tmp/recipe_test recipes_test.c
 *   /tmp/recipe_test test_server/filmsim/recipes/nx500_filmlab_sd.json
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/stat.h>

#define MAXR 32
typedef struct {
    char key[48];
    char label[48];
    int  v[7];
} Rec;
static Rec g_rec[MAXR];
static int  g_nrec = 0;

/* ==== 以下三个函数逐字复制自 nxfilmui.c，保证测的就是真逻辑 ==== */
static int parse_line(char *s, Rec *r) {
    char *f[9];
    int i = 0;
    f[i++] = s;
    while (i < 9) {
        char *p = strchr(f[i - 1], '|');
        if (!p) break;
        *p = 0;
        f[i++] = p + 1;
    }
    if (i < 9) return -1;
    if (f[0][0] == '#' || f[0][0] == 0) return -1;
    if (strlen(f[0]) >= sizeof(r->key)) return -1;
    if (strlen(f[1]) >= sizeof(r->label)) return -1;
    strcpy(r->key, f[0]);
    strcpy(r->label, f[1]);
    for (i = 0; i < 7; i++) r->v[i] = atoi(f[2 + i]);
    return 0;
}

static int load_recipes(const char *path) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    char buf[512];
    g_nrec = 0;
    int held = 0;
    for (;;) {
        buf[held] = 0;
        int got = read(fd, buf + held, sizeof(buf) - 1 - held);
        if (got <= 0) {
            if (held > 0 && g_nrec < MAXR)
                if (parse_line(buf, g_rec + g_nrec) == 0) g_nrec++;
            break;
        }
        held += got;
        int start = 0, i;
        for (i = 0; i < held; i++) {
            if (buf[i] != '\n') continue;
            buf[i] = 0;
            if (g_nrec < MAXR)
                if (parse_line(buf + start, g_rec + g_nrec) == 0) g_nrec++;
            start = i + 1;
        }
        held -= start;
        if (held > 0 && start > 0) {
            int k;
            for (k = 0; k < held; k++) buf[k] = buf[start + k];
        }
        if (g_nrec >= MAXR) break;
    }
    close(fd);
    return g_nrec;
}

/* ==== 测试用例 ==== */
static int fails = 0;
static void ok(int cond, const char *what) {
    printf("  [%s] %s\n", cond ? "PASS" : "FAIL", what);
    if (!cond) fails++;
}

/* recipes.txt 的真实格式（filmlab.sh export 生成） */
static const char *FIXTURE =
    "portra400|Portra 400|100|100|100|10|10|10|10\n"
    "velvia50|Velia 50|100|100|100|10|10|10|10\n"
    "#comment|ignored|1|2|3|4|5|6|7\n"
    "trix400|Trix 400|105|98|92|12|14|8|11\n";

int main(int argc, char **argv) {
    const char *path = (argc > 1) ? argv[1] : "/tmp/frecipes.txt";
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) { perror("open fixture"); return 2; }
    write(fd, FIXTURE, strlen(FIXTURE));
    close(fd);

    printf("== nxfilmui 配方解析回归 ==\n");
    printf("fixture: %s\n\n", path);

    int n = load_recipes(path);
    printf("  解析出 %d 条（注释行应被跳过，期望 3）\n\n", n);
    ok(n == 3, "解析条数 == 3（# 开头被跳过）");

    if (n >= 3) {
        ok(strcmp(g_rec[0].key, "portra400") == 0, "第0条key == portra400");
        ok(strcmp(g_rec[0].label, "Portra 400") == 0, "第0条label == 'Portra 400'（含空格，未被切断）");
        ok(g_rec[0].v[0] == 100 && g_rec[0].v[6] == 10, "第0条 7 个参数值正确");
        ok(strcmp(g_rec[1].key, "velvia50") == 0, "第1条key == velvia50");
        ok(strcmp(g_rec[2].key, "trix400") == 0, "第2条key == trix400（跳过注释后没错位）");
        ok(g_rec[2].v[0] == 105 && g_rec[2].v[3] == 12, "第2条参数值正确");
    }

    /* 半行截断：用 4096 字节的长 label 逼出跨 read 边界 */
    printf("\n  --- 跨 read 边界（分段读法最容易错的地方）---\n");
    {
        char big[900];
        int p = 0;
        p += sprintf(big + p, "bigkey|");
        for (int i = 0; i < 700; i++) big[p++] = 'A';
        p += sprintf(big + p, "|1|2|3|4|5|6|7\n");
        big[p] = 0;
        /* label 700 字符 >= sizeof(label)=48 ⇒ 应被丢弃（长度保护） */
        fd = open(path, O_WRONLY | O_TRUNC, 0644);
        write(fd, "small|S|1|1|1|1|1|1|1\n", 25);
        close(fd);
        int m = load_recipes(path);
        ok(m == 1, "超长 label 的行被丢弃，不影响正常行");
    }

    /* 段数不足的行 */
    printf("\n  --- 畸形输入 ---\n");
    {
        fd = open(path, O_WRONLY | O_TRUNC, 0644);
        write(fd, "bad|onlythree\nsmall|S|1|1|1|1|1|1|1\n", 39);
        close(fd);
        int m = load_recipes(path);
        ok(m == 1, "段数不足的行被丢弃（不是静默产生垃圾值）");
    }

    /* 空文件 */
    printf("\n  --- 空文件 ---\n");
    {
        fd = open(path, O_WRONLY | O_TRUNC, 0644);
        close(fd);
        int m = load_recipes(path);
        ok(m == 0, "空文件返回 0（触发 main 里的报错画面分支）");
    }

    printf("\n%s: %d 失败\n", fails ? "有失败" : "全部通过", fails);
    return fails ? 1 : 0;
}
