# 分享文案 / Sharing Copy

> 三份成品，按平台分开，可直接复制使用。  
> Three ready-to-use pieces, split by platform.
>
> - **A** = Reddit（技术社区，r/nx500、r/linux、r/photography）
> - **B** = 小红书（视觉优先，面向更宽受众）
> - **C** = 通用短版（Twitter / X / 微博 / 论坛签名）

---

---

# A. Reddit 版

## A1. 标题候选（选一个）

> 三个选项，按社区调性选：
>
> 1. `I bypassed the "handle wall" on my Samsung NX500 — EP registers are fully mmap-able from Linux`
> 2. `NX500 reverse engineering: IPCC is an empty shell, but the 3D LUT registers are readable (and contain an identity LUT)`
> 3. `Two days of NX500 ISP reverse engineering: 10 hypotheses killed, 3 framework errors found, and a read-only window into the image pipeline`

**建议**：标题 1 最抓人。技术社区对"bypass"和具体寄存器地址敏感度高。


## A2. 正文（详版，适合 r/nx500 或 r/linux）

````markdown
Two days of poking at my Samsung NX500's ISP. Posting the results because
most of it contradicts what I (and apparently the community docs) assumed.

**TL;DR** — The "3D LUT is unreachable" conclusion I started with was **wrong**.
The hardware registers are mmap-able from root on Linux, and the 3D LUT
contains a **baked-in identity LUT**. We are writing to the camera from the
device side, not through the vendor library.

---

### What I thought at first

The vendor library (`libudd5.so`) gates every 3D LUT entry point behind a
runtime object:

```c
d5_ep_3dlut_op_init(handle, ...);   // internally checks handle + 0x0c == 1
````

I'd written this off as the "handle wall" — a hard block that root cannot pass.  
Two days ago I also wrote that `d5_ipcc` was the main inter-core channel and  
that the 3D LUT hardware was never initialised. **All three were wrong.**

### What the hardware actually says

Step 1 — ask the kernel for the register block map:

```c
/* /dev/drime5_ep, _IOR('h', 100, struct ep_reg_info) = 0x80506864 */
struct ep_reg_info { unsigned long start[10]; unsigned long size[10]; };
ioctl(fd_ep, 0x80506864UL, &reg);   /* r=0, 10/10 sub-blocks non-zero */
```

Step 2 — map the physical addresses read-only:

```c
off_t pa_off = addr & ~(pg - 1);          /* offset MUST be page-aligned */
off_t offs   = addr - pa_off;
void *p = mmap(NULL, len + offs, PROT_READ, MAP_SHARED, fd_mem, pa_off);
```

The 3D LUT block is at **`0x2082b000`** (4 KB). A full window dump:

```
[0x0000] 0x00000001  0x00000100  0x00000000  0x81115200
...
[0x00f0] 0x00000000  0x00000000  0x00000000  0x13020619
[0x00f4] 0x13020619  0x13020619  0x13020619  0x13020619
[0x00f8] 0x13020619  0x13020619  0x13020619  0x13020619
[0x00fc] 0x13020619
```

- `+0x00 = 0x00000001` → the enable bit **is set**. The 3D LUT is powered on.
- `+0x0c = 0x81115200` → textbook Samsung ISP config bitfield (`0x81` = 8-bit)
- tail `0x00f0..0x00fc` = **`0x13020619` × 8**. Bytes = `19 / 2 / 6 / 25` — the  
  **standard 4-bit-packed identity LUT** for 8-bit RGB.

That last line is the whole finding in one row. The camera ships with a  
**real, enabled, identity 3D LUT** sitting in its registers. This is exactly  
what you'd expect from a factory-fresh body with no film effect applied.

I verified the measurement method before trusting the target read (read the  
liveview framebuffer at `0xbbaea500` → `0xebebebeb`, normal 24bpp pixels), and  
two independent processes produced **byte-identical** dumps.

### So what is the "handle wall"?

|        |                                                                                       |
| ------ | ------------------------------------------------------------------------------------- |
| Not    | file permissions, root, ioctl permission bits                                         |
| Not    | "the register doesn't exist" or "the hardware was never initialised"                  |
| It is  | an **invariant check on a userspace handle object** built by the vendor library       |
| Bypass | **map the hardware directly, never enter the vendor library** — then no handle exists |

It only ever blocked *callers of the vendor API*. It never guarded the silicon.

### What I am NOT going to do

**Write the EP registers.** Not as a style preference — as a hard constraint:

- the write is non-interruptible
- the EP is **actively driven** by the ISP firmware (`DSP_NX500GLU0APC1_SR1`)
- changing the 3D LUT during liveview means the ISP reads it concurrently → bitfield corruption
- and `di-camera-app` **cannot be killed** (`launchpad_preloading_preinitializing_daemon`  
  respawns it) → the only recovery is a **battery pull**

So the honest phrasing is: **the bypass buys observability, not writability.**  
But that's still worth something — it turns the imaging path from a black box  
into a read-only dashboard.

### Two bonus findings

**`d5_ipcc` is a shell.** Every query ioctl returns `r=0` but never fills the  
mailbox fields (a `0xA5A5A5A5` sentinel survives untouched; only `buf[0]`  
echoes the `core_id` you passed in). Worse, the encoding matters:  
`_IOWR('t',nr,4)` is safe, `_IOWR('t',nr,8)` **raises SIGILL and kills the  
process** — not `ENOTTY`, termination. The NX1 GPL headers define that struct  
as 8 bytes. Copying them verbatim gets you killed.

**`d5_sma` is real:** a 144 MB shared region at `0x94000000`. And `drime5_ep`  
logged **1,490,995 interrupts** — the highest-frequency source in the whole  
system, which is what you'd expect if it's the actual image path.

### The part that cost me the most time

Four consecutive SIGILLs, all showing "near the ioctl" in the stack. I blamed  
printf varargs, stdio buffering, stack overflow, the ioctl dispatch path, the  
`/dev/null` vs `/dev/d5_sma` distinction, and at one point an inlined `svc 0`.  
**All wrong.** The actual cause: a hand-written `IOC` macro — `(2)<<30`  
overflows a signed 32-bit int, and zig 0.13's ARM backend at `-O0` emits an  
**illegal instruction** for that path. What finally located it was converting  
the crash offset (`main + 0x84`) back to a source line, which showed the  
crash was in **the code printing the ioctl encoding** — it never entered the  
kernel at all. Even `/dev/null` ioctls "crashed", which is what finally  
proved the kernel wasn't the culprit.

The general form of that lesson: **if an "external cause" hypothesis must  
explain every observation, and one observation contradicts it, the hypothesis  
is wrong and the bug is yours.** My tell was "even `/dev/null` crashes" — that  
can't be explained by any kernel/firmware story.

### 10 hypotheses I killed with my own experiments

The freeze investigation (only the delete key wedges entering playback, dial  
won't power off, battery pull required) **did not get root-caused.** But the  
10 dead ends are recorded, and all 10 share one error: **treating  
"happened at the same time" as "caused it."** Highlights:

- **`ipcc_ioctl` deadlock chain** — it also stalls when perfectly healthy after  
  a reboot. A static snapshot describes state; it does not explain mechanism.
- **The entire thumbnail hypothesis is refuted.** A month of prewarm  
  configurations → never froze. Factory reset with zero thumbnails → never  
  froze. Both "missing" and "corrupt" are wrong.
- **Watchdog mis-fire as the strongest remaining candidate** — a guard script  
  probing `st cap iqr` every 13 s, measured **5:1 false-alarm rate**, whose  
  firing kills the app. And "the app got killed" is *indistinguishable* from  
  "froze entering playback" from the user's side. Deleted it as a net liability.

The single most valuable thing I learned: **dissect the qualifiers in the bug  
report literally.** "Only the delete key freezes" is not "deleting a photo  
fails" — only the delete key touches the thumbnail path. I burned three  
rounds in the ISP layer because I misparsed that one clause.

### Repo

Full write-up, all raw captures, and the ARM probe toolchain:  
**`WApaperplane/nx500_nx1_modding`** (branch `nx-ks2`, `docs/CONSOLIDATED_REPORT_2026-10-05.md`).

Happy to answer questions. Corrections welcome — I've been wrong three times in  
two days, all listed above.

**Caveats:** single-core Cortex-A9, 3.5.0 PREEMPT, Tizen 2.2.0. All measurements  
on one unit, firmware 1.12. Absolute register addresses may differ on other  
revisions.

````

## A3. 正文（短版，适合 r/nx500 或首帖）

```markdown
**TL;DR** — Two days of NX500 ISP reverse engineering. The "3D LUT is
unreachable" conclusion everyone (including me) had was **wrong**: the
registers are mmap-able from root, and the 3D LUT contains a **baked-in
identity LUT** (`0x13020619` × 8 at `0x2082b000`).

The "handle wall" is just an invariant check on a userspace pointer object
inside `libudd5.so` — it blocks *callers of the vendor API*, never the
silicon. Map `/dev/mem` yourself and there's no handle to check.

Bonus: **`d5_ipcc` is a shell** (returns 0, fills nothing, and the 8-byte
encoding raises SIGILL — the NX1 GPL headers get you killed), and
**`drime5_ep` logged 1.49M interrupts** — that's the real image path.

I did *not* write the registers and won't: non-interruptible write + live
ISP driver + an app that can't be killed = battery pull. The bypass buys
**observability**, not writability.

Also: 10 hypotheses killed by my own experiments, 3 of them framework-level
errors. All 10 shared one mistake — treating co-occurrence as causation.

Full write-up + all raw captures: `WApaperplane/nx500_nx1_modding`,
branch `nx-ks2`.
````

## A4. Reddit 配图建议

Reddit 图文帖建议 **1:1 或 4:3**，文字放在图里（Reddit 不给图片做 SEO）。

| 图            | 内容                                                            | 建议尺寸     |
| ------------ | ------------------------------------------------------------- | -------- |
| 1（首图，决定点不点开） | 3DLUT 寄存器 dump 截图，突出 `0x13020619` 那一行 + 标注 "identity LUT, 8×" | 1200×900 |
| 2            | EP 十个子块基址表（终端截图，`ep3_full` 输出）                                | 1200×900 |
| 3            | 两条路径对照图（厂商 API 被拦 vs 直接 mmap 通）                               | 1200×675 |
| 4            | 修正对照表（旧结论 ❌ / 新结论 ✅）                                          | 1200×900 |

> **图 1 是全部重点。** 如果只做一张，做那张。

---

---

# B. 小红书版

> 小红书的读者不在逆向社区。**重点从"我怎么做到的"移到"这东西能干什么 + 我踩了多少坑"**。  
> 术语一律翻译成大白话，专业名词只保留必要的（3D LUT、ISO、RAW 这些数码爱好者认）。  
> 标题带情绪钩子，正文短段落，emoji 分段，结尾给讨论问题。

## B1. 标题候选（选一个，≤20 字最佳）

1. `我把三星 NX500 的相机"色轮"拆开了`  ← 推荐，悬念 + 具象
2. `修了两天相机，发现三星藏了一个开关`
3. `NX500 的隐藏真相：它一直在"假装"没有胶片功能`
4. `相机厂商的秘密，被我用一行代码翻出来了`

**建议**：标题 1。技术圈外的读者对"色轮/胶片"有直觉兴趣，但"拆开"制造悬念。  
**绝对避免**"逆向""固件""寄存器"这类词做标题——小红书会直接归到技术不推荐。

## B2. 正文（可直接复制）

```
历时两天，我把三星 NX500 里的东西翻了个底朝天。

先说结果 👇

很多人（包括一周前的我）都以为这台相机没法做胶片调色。
我信了，然后我错了。

📌 它其实一直藏着一个完整的 3D 调色引擎
而且是"开着机"的状态

相机芯片里有一块区域，专门负责"给照片上色"。
我把它读出来一看，里面存着一份标准的"原色映射表"
—— 就是"照片颜色 = 场景颜色"的那种恒等变换。

打个比方：这就像你去扒一台专业调色台，
结果发现它里面本来就装着一张"原图 → 原图"的转场卡。
硬件完全支持，只是没接上控制面板。

我做了什么：
✅ 找到那块区域的物理地址（0x2082b000）
✅ 用最基础的内存读取接口，把里面 4KB 全导出来
✅ 一份一份对照，确认那真的是恒等表，不是垃圾数据

（对照组我做了：先读相机预览画面的像素，
 拿到正常的颜色值，确认我的读取方法没毛病，
 才敢信目标数据。这个顺序不能反。）

——————————

🚫 但我明确不会去"写入"这块区域

很多人会问：能读不能写，那有啥用？

原因很硬：
· 这个写入动作一旦发出就中断不了
· 相机的主控程序此刻正在实时使用这块区域
· 两者撞上 = 数据错乱
· 而且相机 APP 杀不掉（系统会立刻重新拉起）
· 唯一的恢复办法 = 拔电池等它自己重启

所以准确的说法是：
这个方法给了我"看得见"的能力，不是"改得了"的能力。

但这已经很有意思了 ——
相当于把原本一个黑盒的成像链路，
变成了可以随时抽查的仪表盘。

——————————

顺便挖到两个意外收获

1️⃣ 厂商留了一条"看起来能用其实完全没用"的接口
   它的说明书上写着能用，实际上调它什么都不会发生，
   而且参数填错的话会直接把程序搞崩。
   照着别人整理的文档抄代码 = 直接翻车

2️⃣ 我自己推翻了自己 10 次

这个我想专门说 🫠

修 bug 的两天里，我提出了 10 个"我认为是原因"的方向，
然后每一个都被我自己的下一个实验推翻。

最离谱的一个：
我一开始怀疑相机的缩略图缓存坏了
→ 我把整个缓存删光
→ 还是死
→ 我甚至恢复了出厂设置（缓存全空）
→ 还是死

最 后发现最可能的原因是：
我自己写的一个"看门狗"脚本在误报警，
报警之后它把相机主程序杀了
—— 而"主程序被杀"和"进相册死机"，
在人的感受上根本分不出来。

这 10 次错误有个共同的点：
我都在把"两件事同时发生"当成"一件事导致另一件事"。

顺便说个坑：
相机死机只能拔电池
所以做实验必须一次只改一个变量
不然出了问题你都不知道是哪一步弄坏的

——————————

如果你也在折腾老相机 / 老设备
评论区聊聊你踩过最离谱的坑 👇

#数码 #相机 #摄影 #三星 #NX500 #胶片模拟 #数码摄影
#程序员日常 #技术分享 #硬件 #摄影技巧 #复古数码
```

## B3. 小红书配图清单（**这版图比文重要**）

小红书是**首图决定点不点开**的平台。建议 6-9 张，做成轮播。

| # | 图                | 怎么画                       | 关键要求                                |
| - | ---------------- | ------------------------- | ----------------------------------- |
| 1 | **首图：手持机身 + 大字** | 照片/渲染背景 + 粗黑字             | 文字占比最大，**≤12 字**："我扒开了 NX500 的调色引擎" |
| 2 | 那块区域的地址表格        | 手机截图风格的终端输出               | **加红框圈出那行恒等表的数值**，配文"这里藏着原色映射"      |
| 3 | 打个比方的示意图         | 简单手绘/图标：`照片 → [转换卡] → 照片` | 越朴素越好，别太技术                          |
| 4 | "能读不能写"的红绿灯      | 绿色✅读 / 红色🚫写 两栏对比         | 这页是全篇转发的关键                          |
| 5 | 我推翻自己 10 次       | 手写风格清单，或者聊天截图感            | **要有"我错了"的字样**，共情点                  |
| 6 | 缩略图缓存那次乌龙        | 前后对比：删光缓存 / 还是死           | 越朴素越好                               |
| 7 | 恢复出厂还是死          | 同上，第二张打脸图                 | 幽默感                                 |
| 8 | "同时发生 ≠ 导致"      | 一句话大字 + 留白                | 这页是全篇最有价值的一句                        |
| 9 | 结尾提问页            | "你踩过最离谱的坑是什么？"            | **必须留提问，评论区才动起来**                   |

> **排版铁律**：手机端每屏只讲一件事，字要大，正文别塞进图里。  
> 小红书用户是"划"的，不是"读"的。

## B4. 小红书文案的两个可选开头

**开头 A（悬念型）**：

> 很多人以为这台相机做不到胶片调色。我信了。然后我错了。

**开头 B（共鸣型）**：

> 修相机两天，我推翻了自己 10 次。这篇讲最离谱的那几个。

> **建议**：小红书用 **B**（共鸣），Reddit 用 **A**（悬念）。小红书读者先要" relatable"，  
> 再决定要不要看技术。

---

---

# C. 通用短版

> 适合 Twitter/X、微博、Discord 签名、论坛签名档。控制在 300 字内。

## C1. 中文

```
NX500 逆向两日成果（长文）：

① 推翻三个框架级错误判断 —— 最重要的是：
   "3D LUT 不可达"是错的。寄存器在 Linux 侧 mmap 可读，
   里面装着一份现成的 identity LUT（0x13020619 × 8 @ 0x2082b000）。

② handle 墙的真实性质：厂商库的用户态不变量检查，
   只拦调用 API 的人，从不拦硬件。

③ 但我明确不写寄存器 ——
   不可中断写入 + 并发读风险 + APP 杀不掉 = 只能拔电池。
   准确的说法是：绕道换来的是「可观测」，不是「可写」。
   （补充：早先我写"EP 由 ISP 固件实时驱动"，后来发现**没有证据** ——
     冷启动日志里 `request_firmware`/`uImage` 全零命中，libudd5 503 个符号零 ISP 引用。
     EP 其实走标准 UDD 模型，ioctl + 用户态自己 mmap，由 Linux 用户态直接驱动。）

④ 附带：d5_ipcc 是空壳（size=8 编码直接 SIGILL，
   照 NX1 GPL 头文件写代码会被杀）；d5_sma 144MB 共享区；
   drime5_ep 中断 149 万次 = 真正的图像通路。

⑤ 彩蛋：eMMC 未挂载分区里扫出两个 uImage（load==entry==0x86008000，
   说明是同一内核的主/备份两份），另有一个**裸 ARM 镜像**——
   没有 Linux 特征、开头是 relocation 表，很可能就是 ISP 固件本体。

⑤ 死机调查未找到根因，但 10 个假设全部被自己的实验推翻，
   错法完全一致：把「同时发生」当成「导致」。

全程 197 个原始采集文件 + ARM 探针工具链已开源。
https://github.com/WApaperplane/nx500_nx1_modding (branch nx-ks2)
```

## C2. English

```
Two days of NX500 ISP reverse engineering — the long version:

1. Three framework-level corrections. Biggest: "3D LUT is unreachable"
   is WRONG. The registers are mmap-able from Linux and contain a
   ready-made identity LUT (0x13020619 ×8 at 0x2082b000).

2. The "handle wall" is an invariant check on a userspace pointer
   object in libudd5.so. It blocks API callers, never the silicon.

3. I will NOT write those registers: non-interruptible write + live
   ISP driver + an unkillable app = battery pull only. The bypass
   buys observability, not writability.

4. Bonus: d5_ipcc is an empty shell (the 8-byte encoding raises
   SIGILL — copying the NX1 GPL headers gets you killed); d5_sma
   exposes 144 MB; drime5_ep logged 1.49M interrupts = the real
   image path.

5. The freeze investigation has no root cause, but 10 hypotheses
   were killed by my own experiments — all with the identical error:
   treating co-occurrence as causation.

197 raw captures + the ARM probe toolchain are open source.
https://github.com/WApaperplane/nx500_nx1_modding (branch nx-ks2)
```



---

---

## D. 跨平台通用注意事项

| 项                  | 建议                                                                               |
| ------------------ | -------------------------------------------------------------------------------- |
| **不要写"破解"**        | Reddit 有读者会反感；改成 `bypass` / `read-only map` / `expose`。技术事实一样，措辞不招敌              |
| **务必主动标注局限**       | 单一台设备、固件 1.12、绝对地址可能随版本变。**主动说局限比被人问出来强十倍**                                      |
| **不要隐瞒"不能写"**      | 只讲能读不讲不能写 = 标题党，且会招来"那有屁用"的评论。**主动说清反而显得可信**                                     |
| **保留失败记录**         | 「10 次推翻」是小众技术帖最容易获得共鸣的部分，reddit 和小红书都吃这个                                         |
| **tag 用平台本地语言**    | reddit：`#nx500` `#samsung` `#reverseengineering` `#linux` `#photography`；小红书见 B2 |
| **不要说"无人做过"**      | 说了会被要求举证。改成"我没找到社区做过"或直接不提——**克制反而更可信**                                          |
| **commit 前确认敏感信息** | 相机内网 IP 属于个人网络信息，**正文里一律用 `192.168.0.x` 代替**                                     |
