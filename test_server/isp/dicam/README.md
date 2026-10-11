# dicam — di-camera-app 静态分析小工具组（2026-10-11）

四个独立小脚本，全部离线（Windows Python + 目标二进制即可）。
工作目录约定：`E:/tmp/dicam_strings/`（提取物落这里；脚本内路径按需改）。

| 脚本 | 作用 |
|---|---|
| `dicam_strings.py` | 提取二进制全部 ASCII/UTF-16 字符串（带 file 偏移）→ `all.txt` |
| `dicam_xref.py` | 内置目标表：对字符串 vaddr 扫描全文件 LE32 引用（区分 .text/.rodata/.data 区域） |
| `dicam_findref.py` | 通用：命令行传任意 vaddr，打印引用点及前后各 1 词的字符串注解 |
| `dicam_dump.py` | .data/.rodata/.text 按 4B 转储 + 指针自动注解为字符串（连续零词折叠） |

典型用法：

```bash
# 1) 全量字符串表（后续三个脚本的注解依赖它）
python dicam_strings.py

# 2) 内置目标（PW 菜单/图标一族）的引用扫描
python dicam_xref.py

# 3) 任意地址的引用扫描（例：uscom 名串 + uscom handler）
python dicam_findref.py 0x36d6dc 0xca3a8

# 4) 表区转储（例：App 命令表 @0x439d28）
python dicam_dump.py 0x439d28 0x439e40
```

地址映射（本目标，NX500 v1.12 `di-camera-app`，readelf -l 确认）：

- `file < 0x4384ac`  ⇒ `vaddr = file + 0x8000`
- `file ≥ 0x4384ac`  ⇒ `vaddr = file + 0x10000`

主设计文档：`docs/current/DICAM_MOD_DESIGN_2026-10-11.md`（全部结论 + 关键地址速查）。
