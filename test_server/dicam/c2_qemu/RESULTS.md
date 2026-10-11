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
