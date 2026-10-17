#ifndef NXUI_MODEL_H
#define NXUI_MODEL_H
#include <stddef.h>
#define NXUI_MAX_RECIPES 256
#define NXUI_MAX_ITEMS 64
#define NXUI_PATH 512
#define NXUI_DEBOUNCE_MS 150
struct nx_recipe { char key[64], label[192]; int value[7]; };
struct nx_item { int checkbox; char label[192], command[512]; };
struct nx_queue {
    int desired, running, applied, committing, commit_requested, close_requested;
    long long due;
};
int nx_load_recipes(const char *, struct nx_recipe *, int);
int nx_load_menu(const char *, struct nx_item *, int);
int nx_key_valid(const char *);
int nx_menu_path(const char *root, const char *source, char *out, size_t size);
void nx_queue_init(struct nx_queue *);
void nx_queue_select(struct nx_queue *, int index, long long now);
/* Returns an index once, only when idle and settled; -1 means no work. */
int nx_queue_take(struct nx_queue *, long long now);
void nx_queue_done(struct nx_queue *, int success);
#endif
