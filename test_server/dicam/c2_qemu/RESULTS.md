# C-2 补丁 QEMU 预跑结果（2026-10-11 夜）

> 目标：在上机之前，把 `docs/current/DICAM_MOD_DESIGN_2026-10-11.md` §5-C2 的补丁
> （`uscom→film` + 桩）在 **QEMU（相机 rootfs chroot + qemu-arm-static）** 里全链验证。
> 结论：**T1–T4 全部 PASS ✅**。补丁二进制 md5 `0e1da8b326f49728e9394f98a53ffd35`（源 `ae44293e…`）。

---

## 1. 结果总表

| # | 测试 | 内容 | 结果 | 证据 |
|---|---|---|---|---|
| **T1** | 静态 | 桩反汇编 = 设计（`b` 精确落在 `system@plt`）；全文件仅 2 处差异（16B 桩 + 5B 名字串）；无外部跳转进入桩区 | ✅ PASS | objdump：`ca3a8: cmp r0,#2; ca3ac: bxcc lr; ca3b0: ldr r0,[r1,#4]; ca3b4: b add08 <system@plt>` |
| **T2** | 单测 | **直接调用补丁后真字节**（映射回原 VA 0xca3a8）→ `system(cmd)` 执行 | ✅ PASS | `logs/t2_unit.log`；`/tmp/c2_unit_ok` 生成 |
| **T2b** | 守卫 | `argc=1` 时 `bxlo lr` 直接返回、**不执行** | ✅ PASS | `logs/t2b_guard.log`；`/tmp/c2_guard_ran` 未生成 |
| **T3** | 分派 | **真 libshell-command.so** 的 `shell_exec` 用 App 式表匹配 `"film"` → 桩 → 执行 | ✅ PASS | `logs/t3_dispatch.log`；`/tmp/c2_dispatch_ok` 生成 |
| **T4** | 端到端 | **真 `st app film "touch /tmp/c2e2eok"`** → SysV 队列 0x8828 → 线程 → 注册回调（复刻 ui_shell_command）→ App 式表匹配 → 桩 → 执行 → sem 回执 → `st` rc=0 | ✅ PASS | `logs/t4_server.log`：`[mock app] shell_exec(argc=3, argv[1]=film) -> 0`；`/tmp/c2e2eok` 生成；`st rc=0` |

**T4 链路实测（与设计 §3.1 全链逐段一致）**：

```
st app film "touch /tmp/c2e2eok"
  → shell_sndmsg(argc=4, ["/usr/bin/st","app","film","touch /tmp/c2e2eok"], key=0x8828)
  → [队列] → harness 线程 msgrcv → shell_exec(…, top_cmd_list)
  → 命中 "app" → shell_application → 注册回调（模拟 App 的 ui_shell_command）
  → shell_exec(3, ["app","film","touch …"], App 式表)
  → 命中 "film" → 桩(2, ["film","touch …"]) → ldr r0,[r1,#4] → system("touch /tmp/c2e2eok")
  → sem_post(/sem_app_res) → st 返回 0
```

## 2. ★ chroot 环境三件套（本次实测踩出，缺一即败）

| # | 项 | 说明 |
|---|---|---|
| 1 | `mount -t proc proc <rootfs>/proc` | glibc `sem_open` 会走 `/proc/mounts` 探测 |
| 2 | **`mount -t tmpfs tmpfs <rootfs>/dev/shm`** | ★★ **仅"存在目录"不够**：chroot 的 `/dev/shm` 若只是普通目录（ext4），`statfs` 类型非 tmpfs ⇒ glibc 走挂载表探测失败 ⇒ `sem_open` 返回 NULL + `errno=38(ENOSYS)` ⇒ 随后 `sem_init(-1,…)` **段错误**。给 chroot 挂一个**真 tmpfs** 后：`sem_open→0x40804000 / sem_init→0 / sem_post→0` 全通。（修正 10-08 笔记的"`/dev/shm` 需在"表述——**必须真 tmpfs**） |
| 3 | 临时停用 `<rootfs>/usr/bin/save_crash_info.sh` | 崩溃处理器（`libsys-assert.so`，经 `/etc/ld.so.preload` 全局注入）会执行一串 `st cap …` ⇒ 崩溃时**递归崩溃风暴**。测试期间改名 `.off`，结束还原 |

> 另：`/etc/ld.so.preload` 在 rootfs 里强制加载 `libsys-assert.so`（"CA9 user fault"打印者）——分析环境里记住这个。

## 3. 复现命令

```bash
# 0) 生成补丁（Windows Python）
python test_server/dicam/mk_c2_patch.py            # → E:/tmp/dicam_strings/c2/{di-camera-app.c2, c2_bytepatch.json}

# 1) 构建载体（WSL，相机 ABI：glibc 2.13 直链 + 自备 crt0）
bash test_server/dicam/c2_qemu/build_c2_harness.sh

# 2) 全链验证（自动：挂 proc+tmpfs → T2/T2b/T3/T4 → 清理还原）
bash test_server/dicam/c2_qemu/run_c2_qemu.sh
```

## 4. 补丁内容（回顾）

| # | 位置(file) | old → new |
|---|---|---|
| P1 | 0x3656dc | `uscom\0` → `film\0\0`（全镜像唯一引用） |
| P2 | 0xc23a8 | 原 `FUN_000ca3a8` 头 16B → 桩 4 指令：`E3500002 312FFF1E E5910004 EAFF8E53` |

- 桩语义：`cmp r0,#2; bxcc(lr); ldr r0,[r1,#4]; b system@plt(0xadd08)`（handler 约定 `(argc, argv)`；参数 = `argv[1]`）
- 已知约束（T4 顺带实测）：消息槽定长 20B ⇒ 单参数 ≤19 字符；本次用 18 字符命令。
- 未覆盖（留给上机）：真 App 的 `ui_shell_command` 本体（本测试用语义等价的 20B 复刻）；`system()` 的真实目标为 `/opt/usr/nx-ks` 脚本（将随 C-2 v2 桩拼接）。

## 5. 产物清单

| 文件 | 说明 |
|---|---|
| `c2_harness.c` | 验证载体（unit/guard/dispatch/server 四模式） |
| `c2_harness.arm`(out/) | 相机 ABI 二进制（11KB，GLIBC_2.4） |
| `build_c2_harness.sh` / `run_c2_qemu.sh` | 构建 / 全链驱动（含环境三件套自动处理） |
| `c2_semprobe.c` | 最小 sem 探针（环境问题定界工具） |
| `logs/t2_unit.log` 等 4 份 | 各测试原始输出 |
| `../mk_c2_patch.py` | 补丁生成器（含 bytepatch.json 供回滚） |

*生成：2026-10-11 · 全部在 WSL NXKS2 + chroot(-112) 离线完成，未动相机*

---

## 6. ★ 追加：桩 v2（拼接版）QEMU 全链复跑（2026-10-12）

> 背景：v1 桩执行 `system(argv[1])` **裸命令串**，需要短路径（`/f` 符号链接）或 PATH 依赖，
> 且只能带一个参数。v2 桩把 `"sh /opt/usr/nx-ks/f.sh "` 前缀与 `argv[1..n]` 拼进静态缓冲
> ⇒ `st app film apply 23` 自然可用，**零 PATH 依赖**。
> 设计：`docs/current/MOD_DECISION_P7_APP_2026-10-12.md` D-6。

### 6.1 载体改造（`c2_harness.c`）

| 项 | v1 时代 | 现在 | 原因 |
|---|---|---|---|
| 桩长度 | 硬编码 16B | `STUB_LEN 256` | v2 桩 156B（含 `.ltorg` 字面量池 + 前缀串） |
| 蹦床目标 | 直指 `system` | 指向 **`spy_system`** | 打印 `SYSTEM_CMD[...]` ⇒ v1/v2 行为差异一眼可辨 |
| 新增模式 | — | **`unit2`**（3 参数） | 验证多参数拼接 |

驱动脚本 `run_c2_qemu.sh` 相应支持 `C2BIN=<补丁路径>` 选择 v1/v2，并预置
`/opt/usr/nx-ks/f.sh` 转发器（v2 走 `sh f.sh <args>`、v1 直接执行 cmd ⇒ **同一套判据对两版都成立**）。

### 6.2 结果（★ 全绿）

| # | 测试 | v1（16B 桩） | **v2（156B 拼接桩）** |
|---|---|---|---|
| T2 | 单测 unit | PASS | **PASS** |
| T2b | 守卫 guard | PASS | **PASS** |
| T3 | 分派 dispatch | PASS | **PASS** |
| T4 | 端到端（真 `st` → 队列 0x8828 → 回调 → 桩） | PASS（`st rc=0`） | **PASS**（`st rc=0`） |
| T5 | **v2 拼接（unit2）** | N/A（预期：只执行 argv[1]） | ★ **PASS** |

**决定性证据（v2 T5）**：

```
SYSTEM_CMD[sh /opt/usr/nx-ks/f.sh apply 23 ]
```

`/tmp/fsh_calls` 转发器记录（= 端到端穿透证明）：

```
f.sh called: touch /tmp/c2_unit_ok
f.sh called: touch /tmp/c2_dispatch_ok
f.sh called: touch /tmp/c2e2eok
f.sh called: apply 23          ← ★ 多参数拼接成功
```

v1 对照（T5）：`SYSTEM_CMD[apply]` —— 正是 v1 的"单参数、无前缀"特征。

### 6.3 产物

| 文件 | 说明 |
|---|---|
| `test_server/dicam/stub_v2.s` | v2 桩源码（ARM 汇编，位置相关，无 libc 依赖） |
| `test_server/dicam/build_stub_v2.sh` | 构建 + 自检（校验 `bl 0xadd08`、长度 < 656B） |
| `test_server/dicam/stub_v2.bin` | 机器码 **156 B**（可用空间 656 B） |
| `di-camera-app.c2.v2` | v2 补丁二进制，md5 `697c57394f43e99ed07449ad9cb8a238` |
| `c2_bytepatch.v2.json` | 逐项 old/new（含 156B 覆盖区间） |

- 覆盖区间：**file `0xc23a8..0xc2444`（156 B），其中原非零字节 135 个**（= 原 FUN 遗体代码，非零区；该 FUN 仅 1 处引用=命令表项）。
- 长度余量：156 / 656 B ⇒ 后续若要加逻辑，仍有 ~500B 空间。

### 6.4 仍未覆盖（留给上机）

- 真 App 的 `ui_shell_command` 本体（本测试用语义等价的 20B 复刻）。
- 真机上 `/opt/usr/nx-ks/f.sh` 的实际存在性与权限（**上机前必须落盘该脚本**）。
- I-cache：QEMU 用户态不模拟，真机自改代码需注意（本补丁是**整文件替换**，不涉及运行时自改，故不适用）。

### 6.5 ★ 效果演示（2026-10-12，可复跑）

脚本：`test_server/dicam/c2_qemu/demo_c2_app.sh`（前台跑，输出可见）
```
MSYS_NO_PATHCONV=1 wsl -d NXKS2 -- bash /mnt/e/tmp/NXWA-nx500_modding/test_server/dicam/c2_qemu/demo_c2_app.sh
```

链路（除 App 本体外全部为真）：**真 `st app film …`** → 真 SysV 队列 `0x8828` → 真 `libshell-command.so`
→ 真补丁字节 → `f.sh` → 落盘。

同一句 `st app film apply portra400` 的两版行为对照：

| 桩 | `system()` 实际收到 | 结果 |
|---|---|---|
| **v1** | `SYSTEM_CMD[apply]` | 只在 PATH 找 `apply`：**参数丢失**，且**绕过 mod 脚本** |
| **v2** | `SYSTEM_CMD[sh /opt/usr/nx-ks/f.sh apply portra400 ]` | `f.sh` 收到 `argv[1]=apply argv[2]=portra400` ⇒ **落盘 `applied_recipe.txt = portra400`** |

v2 的 `f.sh` 记录（直接证据）：
```
argv_count=2
  argv[1]=apply
  argv[2]=portra400
[f.sh] 应用配方: portra400
```

> ★ 为什么不用"真 VM"跑：`di-camera-app` 真身依赖 DRIMe5 硬件（EP / SMA / ISP / IPCC），
> 在任何 QEMU 里都无法初始化。故取最真实的可行环境 = **相机 rootfs + `qemu-arm-static`**：
> 真 `st`、真 `libshell`、真队列、真补丁字节，仅 App 用语义等价的 harness 顶替。

### 6.6 ★ 参数净化 + f.sh 验证 + 死锁实验（2026-10-12 续）

#### (1) 桩 v2 修订：参数净化（安全修复）

**实测复现的注入面**：v2 桩把参数拼进命令行交 `system()`（=`/bin/sh -c`）⇒ 入参取得 shell 解释权。
未净化时 `st app film recipe apply bad;name` 的 f.log 记录为 `recipe apply 'bad'` —— **`;` 被解释**。

**修复**：桩内加字符白名单（`a-z A-Z 0-9 . _ + - /`），其余 → `_`。

| 输入 | 修复后 |
|---|---|
| `recipe apply bad;name`（整串单参数） | `DENY: recipe_apply_bad_na` —— 注入阻断 |
| `recipe apply 'bad;name'`（分开传） | 引擎收 `apply bad_name` —— 正常分发、元字符中和 |

- 桩长 **156 B → 248 B**（上限 656 B）；新补丁 md5 **`48d94bd63e4479fc931ae1a1fee4e94b`**。

#### (2) f.sh（App 命令入口）验证 —— A 段全通

`scripts/f.sh`（白名单分发）经 `demo_fsh.sh` 实测：

```
>>> st app film recipe list            → 引擎 stub 收到: list
>>> st app film recipe apply portra400 → 引擎 stub 收到: apply portra400
>>> st app film bogus                  → f.log: DENY: bogus
```
引擎 stub 记录：
```
[stub-engine] argv: list
[stub-engine] argv: apply portra400
[stub-engine] argv: apply fast-400 --fast
[stub-engine] argv: apply bad_name
```

#### (3) ★★ 铁律一实验证实：f.sh 内不能发 `st app`

在 App 线程内执行 `st app mode m` ⇒ 探针输出：
```
[probe] ★ 8s 后 st app 仍在等待 ⇒ 队列无人服务（阻塞/死锁证实）
```
⇒ App 的 shell 线程被 `system(f.sh)` 阻塞期间无法服务队列 0x8828；`f.sh` 只许用 `st cap` / `prefman`。

#### (4) 超时工具的现实约束

相机 rootfs **无独立 `timeout`**；mod 自带 busybox 的 applet 集也需实测。`f.sh` 的 `run_tmo` 探测失败即降级直跑。

*追加：2026-10-12 · 分支 `nxwa` · 上机顺序见 `TASKFLOW_2026-10-12.md` W-4*
