#ifndef FILMSIM_CORE_H_
#define FILMSIM_CORE_H_
#include "recipes_gen.h"

/* 对整幅 RGB 图像（w*h*3，行连续）应用胶片配方。
 * 顺序：矩阵 -> 饱和度 -> 曲线 LUT -> 颗粒（与 engine.py 一致） */
void filmsim_apply(unsigned char *rgb, int w, int h, const FilmRecipe *r);

/* 按 id 查找配方，找不到返回 NULL */
const FilmRecipe *filmsim_find(const char *id);

#endif /* FILMSIM_CORE_H_ */
