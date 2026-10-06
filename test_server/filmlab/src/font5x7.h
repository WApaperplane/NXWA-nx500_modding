#ifndef FONT5X7_H
#define FONT5X7_H

/* 取 5x7 字模（5 字节，每字节一列，bit0=最上一行） */
const unsigned char *font5x7_get(int ch);

/* 字符前进宽度 / 行高（含1 点间隔） */
int font5x7_width(int scale);
int font5x7_height(int scale);

#endif
