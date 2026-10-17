#include "nxui_model.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int nx_key_valid(const char *s) {
    size_t n = 0;
    if (!s || !*s) return 0;
    for (; *s; s++, n++)
        if (!((*s >= 'a' && *s <= 'z') || (*s >= '0' && *s <= '9') || *s == '_')) return 0;
    return n < sizeof(((struct nx_recipe *)0)->key);
}
static int line_read(FILE *f, char *line, size_t size) {
    size_t n;
    if (!fgets(line, (int)size, f)) return 0;
    n = strlen(line);
    if (n && line[n-1] != '\n' && !feof(f)) return -1;
    line[strcspn(line, "\r\n")] = 0;
    return 1;
}
int nx_load_recipes(const char *path, struct nx_recipe *out, int max) {
    FILE *f = fopen(path, "r");
    char line[1024]; int n = 0, rc, i, j;
    if (!f) return -1;
    while ((rc = line_read(f, line, sizeof line)) > 0) {
        char *part[9], *p = line, *end;
        struct nx_recipe r;
        if (!*line || *line == '#') continue;
        for (i = 0; i < 9; i++) {
            part[i] = p;
            p = strchr(p, '|');
            if (i < 8) { if (!p) break; *p++ = 0; }
            else if (p) break;
        }
        if (i != 9 || !nx_key_valid(part[0]) || !*part[1] ||
            strlen(part[1]) >= sizeof r.label || n >= max) goto bad;
        for (j = 0; j < n; j++) if (!strcmp(out[j].key, part[0])) goto bad;
        memset(&r, 0, sizeof r);
        strcpy(r.key, part[0]); strcpy(r.label, part[1]);
        for (i = 0; i < 7; i++) {
            long v;
            if (!*part[i+2]) goto bad;
            v = strtol(part[i+2], &end, 10);
            if (*end || v < 0 || v > (i < 3 ? 200 : 20)) goto bad;
            r.value[i] = (int)v;
        }
        out[n++] = r;
    }
    if (rc < 0 || ferror(f)) goto bad;
    fclose(f); return n;
bad:
    fclose(f); return -1;
}
int nx_load_menu(const char *path, struct nx_item *out, int max) {
    FILE *f = fopen(path, "r"); char line[1024]; int n = 0, rc;
    if (!f) return -1;
    while ((rc = line_read(f, line, sizeof line)) > 0) {
        char *label, *command; int check;
        if (!*line || *line == '#') continue;
        if (!strncmp(line, "button|", 7)) { check = 0; label = line + 7; }
        else if (!strncmp(line, "checkbox|", 9)) { check = 1; label = line + 9; }
        else goto bad;
        command = strchr(label, '|');
        if (!command || n >= max) goto bad;
        *command++ = 0;
        if (strlen(label) >= sizeof out[n].label || strlen(command) >= sizeof out[n].command) goto bad;
        out[n].checkbox = check;
        strcpy(out[n].label, label); strcpy(out[n++].command, command);
    }
    if (rc < 0 || ferror(f)) goto bad;
    fclose(f); return n;
bad:
    fclose(f); return -1;
}
/* Menus can reference only files directly inside the installed scripts folder. */
int nx_menu_path(const char *root, const char *source, char *out, size_t size) {
    const char *p = source; int n;
    if (*p == '@') p++;
    if (!strncmp(p, "/tmp/gui_", 9)) {
        if (strchr(p + 5, '/') || strstr(p, "..")) return 0;
        n = snprintf(out, size, "%s", p);
        return n > 0 && (size_t)n < size;
    }
    if (!strncmp(p, "/opt/usr/nx-ks/", 15)) p += 15;
    if (!*p || strchr(p, '/') || strstr(p, "..") || strchr(p, '\\')) return 0;
    n = snprintf(out, size, "%s/%s", root, p);
    return n > 0 && (size_t)n < size;
}
void nx_queue_init(struct nx_queue *q) {
    memset(q, 0, sizeof *q); q->desired = q->running = q->applied = -1;
}
void nx_queue_select(struct nx_queue *q, int index, long long now) {
    q->desired = index; q->due = now + NXUI_DEBOUNCE_MS;
}
int nx_queue_take(struct nx_queue *q, long long now) {
    if (q->running >= 0 || q->desired < 0 || now < q->due ||
        (q->desired == q->applied && !q->commit_requested)) return -1;
    q->running = q->desired;
    q->committing = q->commit_requested;
    q->commit_requested = 0;
    return q->running;
}
void nx_queue_done(struct nx_queue *q, int success) {
    if (success) q->applied = q->running;
    else if (q->desired == q->running) q->desired = -1; /* explicit retry only */
    q->running = -1;
}
