# st 全表 × MCB 协议 × di-camera-app 全量反编译（2026-10-08）

> 承接 [`ST_RE_AND_REPRO_2026-10-08.md`](ST_RE_AND_REPRO_2026-10-08.md)。本篇 = 三项深化：
> **① di-camera-app 全量反编译 ② st top_cmd_list 全表（运行时真值） ③ MCB 消息协议档案**。
> 原始数据：`raw8/repro/{st_cmd_table_runtime.txt, mcb_command_dict_raw.txt, mcb_exports_raw.txt, mcb_strings.txt, sysv_msg_capture.txt}`
> Ghidra 导出：`E:\ghidra_out\{di-camera-app.arm_dump, libmulticore-bridge.so_dump, libshell-command.so_dump, mcbtest.arm_dump}`

---

## 1. st 命令表（运行时真值 · 28 条全解 ✅）

**方法**：`qemu-arm-static -g` + `gdb-multiarch`，断在 st `main`(0x8810)，**经 st 自身 GOT 槽位(0x10c94)直取 `top_cmd_list` 运行时地址**（绕开 .so 基址难题）。
基址：libshell-command.so = `0x4084C000`；表 @ `0x4086a33c`；`process_option` @ `0x4086a2cc`。

**结构**：每条 8 字节 `{char* name; void* handler}`，"end" 哨兵；**27 条命令全部有 handler**（此前"多数为 0"是文件态误读）。

**分流逻辑**（st main → 查表 → `process_option[i]`）：

| 路径 | 条件 | 行为 |
|---|---|---|
| A 本地执行 | option=0 | `shell_exec(argc, argv, list)` → `handler(argc-1, argv+4)` |
| B 消息派发 | option=1 | `shell_sndmsg(argc, argv, 0x8828)` → **SysV 消息队列** |
| C 未实现 | handler==0 | `"%s : not implement command !!!"`（当前无命令命中此路径） |

- **B 路径 = log / util / app / leak 四条**（其余 23 条走本地）
- 完整表：见 `raw8/repro/st_cmd_table_runtime.txt`（含每条 handler 偏移 ↔ 符号名映射）
- ★ **cap = `shell_capture`(+0x8984)**，内部：`mcb_init → mcb_register_handler(0xB6, ack) → mcb_send(0xB6, 0, len, "st <args>") → 等 ack（10s 超时）→ 失败打印 "Cann't execute capture command over MCB!"`（`shell_capture.cpp:0x130`）——与 qemu 实测输出逐字吻合

**28 命令行为对照（chroot 实跑，全 27 条响应）**：help/readl/writel/dump/gpio/hdmi/lcd/pmu/clk/key/firmware/devman/stlcd/bat/rtc/tbm/micom/misc/oic/dvfs/adc → 各自 usage 正常打印；thread → 启动线程；**log/util/app/leak → 走 SysV（见 §2）**；cap → MCB 报错（>6s 慢失败）。

## 2. SysV 消息体系（key 0x8828）—— ★ 离线拦截成功

- `shell_sndmsg(argc, argv, 0x8828)`：`sem_open(...)` + `msgget(0x8828, IPC_CREAT|0666)`
- **拦截实验**：WSL 宿主侧自写 C 程序 `msgget(34856=0x8828, IPC_CREAT|0666)`（与 chroot 共享内核 IPC 命名空间），chroot 里跑 `st log` → **捕获到完整消息**！
- **捕获内容（208 字节）**：
  ```
  u32: 0x00000002 | "/usr/bin/st\0" | "log\0" | 参数区(补零)
  ```
  ⇒ 消息格式 = `{u32 类型/flags; char exec_path[]; char command[]; args...}`，即**"谁 + 命令 + 参数"的远程执行请求**（相机上由常驻服务端接受执行）。st log 随后阻塞等回执（超时被我们杀掉）。
- 原理解锁：`0x8828` 不是代码地址，是**消息队列 key**（=34856）——此前反编译误读为函数指针实参，已纠正。

## 3. MCB 消息协议档案（libmulticore-bridge.so）

### 3.1 栈图（全部功能）

```
业务 (shell_capture / mcbtest / …)
  │  mcb_send(u16 cmd, u16 sub, u16 len, u8* data)     ← 公开 C API（26 个 mcb_/Icm_ 导出）
  ▼
CSender::createFrame(cmd, sub, len, data)
  │   堆分配 CFrame(16B 对象)；stFrameHeader 栈构: {u16 cat=2; u8; u16 cmd; u16 sub; u16 len}
  ▼
CFrame::Build(hdr, data)      // 缓冲 = len + 12B 前缀; 拷贝: buf[0..5]←hdr[2..7]; payload@buf+6
  ▼
CSender::send(CFrame)         // 入 CFrameQueue；Category()==0x10 走优先道；满则 "[CSender] Queue is full."
  ▼
Sender 线程 (activate: FThread.Create(0x18ef0, 0x6000) + eventflag)
  ▼
CIPCCDriverIf::Send(buf, size)
  │   校验: size 不得超过 0x18C (396B) — "ERROR: INVALID Size"
  ▼
ipcc_write_pkt(buf, destCpuID(), size)   ← libudd5.so 提供（内联 IPCC UDD 设备层）
  ▼
内核 IPCC 驱动（失败即 "IPCC UDD open is failed!!"，字符串归属 = libudd5.so 实证）
```

### 3.2 关键事实

- **接收**：IPCC 中断 → `CIPCCDriverIf::OnInterrupt` → 监听回调 → `CReceiver`（`Subscribe(cmd, handler)`）→ 按 **u16 命令号**分派到 `mcb_register_handler(cmd, fn)` 注册者，handler 签名 `int fn(int, u8*)`
- **公开 API**（26 个）：`mcb_init/terminate`、`mcb_send/mcb_raw_send`、`mcb_register_handler/unregister`、`mcb_register_raw_int_handler`、`mcb_lock/unlock/history`、`mcb_get_destAlive`、`mcb_set_ignore_init_checking`、`mcb_debug_set_command_name_function / attribute_name_function`（供调试名解析）
- **互通锁**：`CIntercoreMutex`（Icm_lock/unlock + eventflag）
- **帧最大载荷**：396B/包（0x18C）；帧头 category 常量 = 2（另有 0x10 优先类）
- 源码路径泄漏：`src/sender/Sender.cpp`、`source/shell_capture.cpp`（→ 相机内部分层命名）

### 3.3 ★ 命令 ID 字典（mcbtest 内 `capture_command_string`，1868B 大 switch）

ID 空间规律：**高字节=域，低字节=命令**；已提取 40+ 条骨架（完整表见 `mcb_command_dict_raw.txt`）：

| 域 | 范围 | 实例 |
|---|---|---|
| SYS_ | 0x1xx | 0x101 CIS_CLEANING / 0x102 CONTROL_STROBE / 0x104 CHANGE_MODE / 0x106 POWER_SAVE / 0x107 POWER_OFF |
| STILL_ | 0x2xx | 0x201 START_CAPTURE / 0x204 LOCK_AEAF / 0x205 LOCK3A / 0x208 TOUCH_AF / 0x20e SET_AEL_BV |
| LV_ | 0x3xx | 0x301 START / 0x302 STOP / 0x304 SCENE_DETECTION / 0x30c ZEBRA_CTRL / 0x30d PANORAMA_DISPLAY |
| MOVIE_ | 0x4xx | 0x401 START_RECORDING / 0x402 STOP_RECORDING / 0x404 TOUCH_AF |
| LENS_ | 0x5xx | 0x501 POWER_ZOOM / 0x502 SET_OIS / 0x505 FW_UPDATE / 0x509 SET_MF_POSITION |
| QUICKPB_ | 0x6xx | 0x601 CHECK_IMAGE / 0x602 PB_REQUEST / 0x604 DELETE_FILE |
| FLASH_ | 0x7xx | 0x701 EXT_HSS_ONOFF / 0x703 MULTI_ONOFF |
| PRD_（生产） | 0xaaXX | CAPTURE_RAW_PP / CAPTURE_RAW_SSIF / WRITE_LOG_TO_NAND / SET_FOCUS_POSITION … |

- 现场观测的活跃命令号：**0xB0**（cap log on）、**0xB1**（cap log off）、**0xB6**（cap 命令行下发）
- `mcbtest`（584KB，1312 函数反编译）= 完整用法参照：注册 0x10/0x21/0x23/0x31/0x80–0x83/0xA2–0xA4/0xB0/0xB1/0xE0/0xF1/0xF5 等 handler

## 4. di-camera-app 全量反编译（完成 ✅）

| 项 | 数值 |
|---|---|
| 函数清单 | **9,258** |
| 字符串 | **29,264** |
| **反编译全文** | **7,073 函数 / 11.6 MB**（`04_decompiled.c`） |
| 位置 | `E:\ghidra_out\di-camera-app.arm_dump\`（另存 400 函数截断版 `_cap400` 作对照） |
| 工具 | `test_server/isp/ghidra/DumpELF.java`（上限参数 20000 全量） |

## 5. 手法速记（新，可复用）

1. **gdb 直取运行时装**：`qemu-arm-static -g <port>` + `gdb-multiarch`（`set sysroot <rootfs>` 本地读符号）→ 断 main → 经**程序自身 GOT 槽位**（`readelf -r` 查）读目标符号运行地址 → 解码数据结构。**绕开 .so 基址/ASLR 一切麻烦**。
2. **SysV 消息拦截**：写 C 用 `msgget(key, IPC_CREAT|0666)` 抢占队列 + `msgrcv` 抓包；chroot 与宿主共享 IPC 命名空间。
3. chroot 复现三件套：`/proc` 需挂、`/dev/shm` 需在（否则 sem_open→sem_init 段错误）、投文件到**存在的**目录。

## 6. 资产与下一步

- 新增：`raw8/repro/` 5 份原始数据；`E:\ghidra_out\*_dump\` 4 套反编译
- 下一步候选：① di-camera-app 全量伪代码上检索（复用 p7 的 ps_scan 模式）② 0xB6/0xB0 完整链路在真机 telnet 侧验证（铁律 90）③ mcbtest 在 chroot 内运行（离线复现 MCB 测试场景，需补 /dev/ipcc 类设备环境）
