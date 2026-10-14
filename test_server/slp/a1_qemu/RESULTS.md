# A1 p7 补丁「包级真字节」QEMU 行为验证（2026-10-14）

> **目标**：上机（真机刷写）之前，把 **A1 成品包内将实际刷入的 p7 字节**（SLP idx5）
> 载入 QEMU 执行**完整归一化器调用链**，对 orig（官方）/ step1 / full 三版本做全用例差分
> —— 排除"包打错 / 逻辑编码错 / 跳转目标解算错"一类问题。
> **结论**：A/B/C/D 全项 PASS ＋ 反例演练 3/3 全被抓住（套件有区分能力）。
>
> 与既有 `qemu_test_logic.sh`（12 例、"重新汇编的等价逻辑"）的关系：那是设计期单测；
> **本套件是上机前包级验证** —— 真字节、真入口、真拒收 handler、真日志调用点、64 例差分。

---

## 1. 测试对象（成品包 → 真字节）

| 版本 | 来源 | idx5 md5 |
|---|---|---|
| orig | `NX500_v1.12.bin`（官方） | `5fc4824f…` |
| step1 | `slp_a1_p7_g_step1_v116.bin`（绕行档） | `1e0be7df…` |
| full | `slp_a1_p7_g_v116.bin`（特判块档） | `2ee98811…` |

提取由 `extract_variants.py` 完成（`slp_tool.parse` 定位 idx5 + md5 自证）；
被测区段（0x350）/ 特判块（0x18）再从三份 idx5 中切出，`harness.s` 以 `.incbin` 嵌入。
提取自检：三版本 seg_norm 差异**仅限 0x510b0 指令内 3 字节**；seg_blk 三形态（零 / 单 b / 24B 块）与设计一致。✅

## 2. 方法（载具工作方式）

`harness.s`（ARM 汇编，无 libc，裸 svc）：

1. `mmap2(0x80000000, 0x80000, RWX, FIXED|PRIVATE|ANON)` 铺出 p7 地址空间；
2. 拷入真字节：norm 区 → `0x80051090`，特判块 → `0x80011504`；
   另放一个 **日志桩** → `0x80046484`（拒收 handler 里 `bl` 的日志函数；桩在 `0x80070000` 计数后返回，
   不改返回值——`bx lr` 后紧接 `mvn r0,#0`）；
3. 遍历 **64 用例**，`blx 0x80051090`（**真实 VA 的归一化器入口**，全链真字节执行：
   域检查 → 跳转表分发 / 重定向 → 特判块/绕行 → 拒收 或 共享收尾）；
   逐例记录 `{id, ret, conv}`；
4. `write()` 输出 64×12B + 尾部 u32（日志桩计数）。

> 载具与被测的寄存器契约：被调链（0x80051090 全链，含 handler/收尾/拒收）只用 r0–r3；
> harness 状态驻 r4/r5/r6/r8；日志桩用 `movw/movt` 内嵌常量（位置无关，任意地址执行等价）。

## 3. 结果（A/B/C/D 全绿）

| # | 判定 | 结果 |
|---|---|---|
| **A** | orig 基线 = 设计表（45 映射 + 0x119/0x11a 拒收 + 域外 17 拒收） | ✅ **64/64** |
| **B** | **step1 ≡ orig**：全 64 例 `{ret, conv}` 逐字段 | ✅ 零行为变化 |
| **C** | **full**：除 0x130..0x133 外 ≡ orig；目标四维 → `(ret=0, conv=id)` | ✅ |
| **D** | 拒收路径日志计数：orig=19 / step1=19 / full=15（每拒收恰一次） | ✅ |

关键个案（差分总表节选）：

```
0x130 | orig -1/0xff | step1 -1/0xff | full 0/0x130  ★目标
0x131 | orig -1/0xff | step1 -1/0xff | full 0/0x131  ★目标
0x132 | orig -1/0xff | step1 -1/0xff | full 0/0x132  ★目标
0x133 | orig -1/0xff | step1 -1/0xff | full 0/0x133  ★目标
0x12f | 三版本一致 -1/0xff（相邻越界仍拒）
0x110 | 三版本一致 0/0x10f（SAT 回归不变）
```

全表 64 行见 `logs/check_report.txt`；三份原始输出 `logs/out_*.bin`。

## 4. ★ 反例演练（mutation：证明套件不是"怎么测都绿"）

| # | 反例构造 | 结果 |
|---|---|---|
| M1 | full 的 blk 区清零（模拟"特判块未刷入"） | ✅ 被抓住（full 17 例全异常） |
| M2 | orig 跳转表首项 0x80051388→0x80051394（模拟"表被破坏"） | ✅ 被抓住（A/B/C 连锁 FAIL） |
| M3 | orig 的 norm + full 的块（模拟"0x510b0 未重定向"） | ✅ 被抓住（目标四维未放行） |

判定日志：`logs/mut_check_m{1,2,3}.txt`。M1 的抓取细节值得一提：blk 清零后 0x130 走全零区"跑飞"，
最终借道日志桩返回、`r0` 未清零 ⇒ 判定仍识别为异常（`ret=304, conv=0xdeadbeef`）——
说明判定条件（`ret` 与 `conv` 双匹配）足够严格，不放过任何一类偏差。

## 5. 覆盖边界（重要）

| 项 | 状态 |
|---|---|
| 补丁逻辑真字节行为（重定向链路 / 全 47 项表 / 边界 / 拒收 / 日志路径） | ✅ 本套件覆盖 |
| **0x11504 零区在 p7 启动+运行时是否被覆写** | ❌ 不覆盖 —— 仍由 **A1 Step1 刷后回读 + 零区存活探针**裁决（V5b） |
| p7 启动初始化、其余代码、外设交互 | ❌ 不覆盖（仅归一化器调用链） |
| cache / MMU / 段保护等运行期属性 | ❌ 不覆盖 |

⇒ 本套件把"**逻辑层错误**"在上机前清零；"**运行期存活**"仍是 Step1 灰度法的唯一目的。

## 6. 复现

```bash
# Windows 侧（前台，输出可见）：
MSYS_NO_PATHCONV=1 wsl -d NXKS2 -- bash /mnt/e/tmp/NXWA-nx500_modding/test_server/slp/a1_qemu/build_a1_qemu.sh
# 反例演练（可选，证明套件灵敏度）：
MSYS_NO_PATHCONV=1 wsl -d NXKS2 -- bash /mnt/e/tmp/NXWA-nx500_modding/test_server/slp/a1_qemu/selftest_mutation.sh
```

依赖：WSL NXKS2（`arm-linux-gnueabihf-as/ld`、`qemu-arm-static`、`python3`）。

## 7. 产物清单

| 文件 | 说明 |
|---|---|
| `extract_variants.py` | 成品包 → idx5 + 区段（md5 自证） |
| `harness.s` | QEMU 载具（真字节 + 真 VA + 日志桩） |
| `check_a1_qemu.py` | 三版本 64 例差分判定（A/B/C/D + 总表） |
| `build_a1_qemu.sh` | 提取 → 构建 → 运行 → 判定（一键） |
| `selftest_mutation.sh` | 反例演练（M1/M2/M3） |
| `logs/out_{orig,step1,full}.bin` | 三版本原始输出（64×12B + 计数） |
| `logs/check_report.txt` | 判定报告（全 64 行差分表） |
| `logs/mut_check_m{1,2,3}.txt` | 反例判定日志 |
| `logs/h_{orig,step1,full}.elf` | 构建产物（可复跑） |

---
*生成：2026-10-14 夜 · 分支 `nxwa` · 全部离线（wsl NXKS2 + qemu-arm-static 8.2.2），未动相机*
