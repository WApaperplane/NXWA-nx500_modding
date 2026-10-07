# 历史归档 / Archive

> ⚠ **这些文档的结论可能已被后续调查推翻。**
> 取结论前，请先对照 [`../current/ERROR_CORRECTIONS_2026-10-07.md`](../current/ERROR_CORRECTIONS_2026-10-07.md)
> 与 [`../current/HANDOVER_2026-10-07.md`](../current/HANDOVER_2026-10-07.md)。
> 归档：2026-10-07

## 为什么保留

这些是 2026-10-05 / 10-06 的阶段性成果与调查报告，**记录了当时的推理过程**，
对理解"为什么走过某些弯路"仍有价值。但**其中若干结论是错的**，例如：

| 文档里的旧结论 | 实际情况 | 修正出处 |
|---|---|---|
| mod_gui `key_down_callback` 只认 **13 键** | 实为 **4 keysym**（Super_L/Super_R/Menu/XF86PowerOff）| ERROR_CORRECTIONS C1/C2 |
| `p6`/`p13` 是**主/备份同一内核** | 实为**两个不同构建**（#7 vs #1183），运行 p6 | ERROR_CORRECTIONS C6 |
| p7 里**没有任何 EP 物理基址字面量** | 实有 **342 个 EP 寄存器访问** | ERROR_CORRECTIONS C3 |
| p13（`rImage`）= 内核备份 | — | ERROR_CORRECTIONS C6 |
| "1.13 固件"是新版本 | v1.13 == v1.12，仅版本字符串差 1 字节 | ERROR_CORRECTIONS C8 |

## 内容清单

- `2026-10-05` 系列：固件层框架、p7 分析、SLP、SMA、BC 路径挖掘、魔灯可行性、综合报告
- `2026-10-06` 系列：3D LUT 写入通路打通、EP 驱动状态、libudd5 API 图、功能设计与矩阵、各类工作/评估报告
- `_2026-10-06_purged/`：2026-10-06 当晚即已作废的 3D LUT 探索文档（更早一轮的已否证结论）

## 完整历史

如需当时的完整上下文，见 git 历史（归档前的路径均为 `docs/<文件名>`）。
