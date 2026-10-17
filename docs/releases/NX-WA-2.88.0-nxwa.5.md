# NX-WA 2.88.0-nxwa.5

发布日期：2026-10-17
上一版：2.88.0-nxwa.4（Release id 415716288）

## 一句话

**NXUI 浏览配方的等待从 4.35 秒降到 1.3 秒**（3.3 倍），并修掉"预览会污染内置风格"的缺陷。

## 为什么慢（实测根因）

相机端分段计时（`st cap capdtm` 每次调用走 App 队列）：

| 项 | 耗时 |
|---|---|
| `st cap capdtm getusr 20` | 1.31 s |
| `st cap capdtm setusr 20 …` | 1.23 s |
| 再次 `getusr`（读回自证） | 1.30 s |
| `prefman get` ×7 | 0.17 s |
| `pwsend seq` 启动 | 0.45 s |
| `/bin/true` ×20 | 0.27 s |

单次预览 4.35 s 的构成：档位读-切-验三连 ≈ 2.5~3.9 s + `pwsend` 固定
7×150 ms + 300 ms = 1.35 s + 写槽与备份 0.4 s（预览根本用不到）。

## 改了什么

1. **预览固定以「自定义1」为画布**：A2 的提交位（`0x13B`）本来就把运行时档位切到
   CUSTOM1。固定槽之后预览 **0 次 `st cap`**。
2. **预览不写槽、不备份、不切档**：画面完全由 A2 直推决定；`保存并关闭`
   （`commit`）才写入七维 + `prefman save` + 把档位还回打开面板时那一档。
3. **`pwsend` 条间间隔** 150 ms → 40 ms（预览路径可调，`FILMLAB_PWSLEEP`）。
4. **`pwsend` 收尾 `usleep`** 300 ms → 100 ms（单发与 seq 两处；`svdm` 同步返回，
   队列已投递，收尾只是保险）。
5. `commit` 的档位恢复省掉一次 `getusr`（3 次 `st` → 2 次）。

顺带修掉：以前在「标准」档浏览配方，会把配方七维写进 slot 0（标准风格）且不恢复，
切回"标准"看到的是最后一次预览。现在预览完全不碰任何槽。

## 验收（真机 192.168.0.106）

| 项 | 结果 |
|---|---|
| 单次预览（portra400） | **1.32 s** |
| 单次预览（trix400） | **1.29 s** |
| 单次预览（portra800） | **1.27 s** |
| 七维 ISP 读回 | 三条配方逐维命中（R/G/B 高 16 位、H/S/P/C 的 `0xD80A` 标记位全部对应） |
| 连续三次预览 | 全部 `reload=already pw=direct not-saved`，无丢值 |

## 部署

| 文件 | md5 |
|---|---|
| `/opt/usr/nx-ks/filmlab.sh` | `021a7aff98d724f1eaf6309c04ffcd62` |
| `/opt/usr/nx-ks/pwsend.arm` | `935fead94a9a9e2dac0ae7b42593e5c7` |

机端备份：`filmlab.sh.bak-1017b`（`4ecddd03`）、`pwsend.arm.bak-1017c`（`003e7365`）。

> `pwsend.arm` 本次以二进制常量补丁落地（两处 `usleep` 实参 `0x493e0` → `0x186a0`，
> 仅 6 字节差异），源码 `test_server/pwsend/pwsend.c` 同步改为 `100000`；
> 二者功能等价，重编需 zig 0.13.0 + `-target arm-linux-gnueabi.2.15`。

## 行为变化（需要知道）

- 预览后运行时档位停在「自定义1」。**槽数据没变**，切走再切回即恢复原值；
  不想停留就按 `保存并关闭`（会还档）或手动切回原档位。
- 由于预览不再"跟随当前栏位"，内置 9 档风格（标准/鲜艳/人像……）**不再被预览污染**。

## 回滚

```sh
cp /opt/usr/nx-ks/filmlab.sh.bak-1017b /opt/usr/nx-ks/filmlab.sh
cp /opt/usr/nx-ks/pwsend.arm.bak-1017c /opt/usr/nx-ks/pwsend.arm
sync
```
