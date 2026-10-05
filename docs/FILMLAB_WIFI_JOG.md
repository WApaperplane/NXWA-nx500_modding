# FilmLab 一键化：WiFi 键直达 + 波轮配方UI

> 2026-10-05。回答「单击 WiFi 键打开 FilmLab UI + 波轮切换 + 触屏」的可行性裁决。
> 全部结论基于静态查证（社区源码 + 真机二进制符号表），**未上实机**。

---

## 结论先给

| 诉求 | 可行性 | 载体 | 触发动作 |
|---|---|---|---|
| 消灭「主菜单→FilmLab→配方」三层 | ✅ **零改动，已解决** | `EV_MOBILE.sh` | 按住 EV + WiFi 键 |
| **真·一键**（零 UI 轮换配方） | ✅ **零改动，已解决** | `MOBILE_MOBILE.sh` | 双击 WiFi 键 |
| 波轮切换配方 | ⚠️ **mod_gui 层无解**，需自写 UI | `nxfilmui.arm` | 见下|
| 单击 WiFi 键 | ❌ **keyscan 二进制无此分支** | — | 需重编译 keyscan |

**波轮 + 触屏的 UI 已经编译出来了**（`nxfilmui.arm`，40KB，ELF32 ARM EXEC，零警告）。
难点不在写代码，在于「本地没有 EFL 库，怎么证明手写 ABI 声明是对的」——已用真机符号表解决（见下）。

---

## 一、单击 WiFi 键：为什么做不到

不是设计取舍，是 `scripts/keyscan` 二进制的硬限制。

从二进制里提取出全部 shell 名构造格式串，**只有三个**：

| 格式串 | 触发条件 | 产出的脚本名 |
|---|---|---|
| `'EV_%s'` | 按住 EV 时按其他已命名键 | `EV_MOBILE.sh` |
| `'%s_%s'` | 双击同一键（间隔 <1000ms） | `MOBILE_MOBILE.sh` |
| `'MODE_SAS'` | 模式盘「松开」特例，无前缀 | `MODE_SAS.sh` |

**没有「无前缀的普通单击」分支。** 而且门槛是 `strlen(shell_name) > 4`——
`MOBILE` 有 6 个字符，纯粹是没有这条分支，不是长度不够。

要实现单击只有一条路：**重新编译 keyscan**，加一个 MOBILE 单击分支。
社区有源码（`ottokiksmaler/nx500_nx1_modding`），但风险明确：

- keyscan 是开机自起的输入守护进程，它挂了相机的物理按键全失效
- 它有 `/tmp/keyscan.pid` + `flock` 防双实例，**stale lock 只能拔电池清**
- 换掉它之后，`xinput test` 社区工具链的按键映射行为也要重新验证

**当前权衡**：双击 WiFi 键（`MOBILE_MOBILE.sh`）在体验上已经接近单击——
单手拇指双击 vs 单击的手感差异，在举起相机时远小于收益差距。
所以先不碰 keyscan。

---

## 二、零改动消灭三层

**关键发现**：从 `scripts/mod_gui` 二进制挖出路径解析逻辑——

```
Usage: %s [path_to_scripts_directory] [debug]
路径格式串： '%s/%s%s'   '%s.%s'   'mod_gui.cfg.'
读 /etc/version.info 取机型
传gui_ini 时：先试 gui_ini.NX500，不通再试 gui_ini
```

⇒ **可以直接指定任意菜单文件当顶层**，不必经过主菜单。

```sh
# scripts/nx-rc/EV_MOBILE.sh 的核心
MENU=$D/gui_filmlab1b
[ -r "$MENU.$SUFFIX" ] && TARGET=$MENU.$SUFFIX || TARGET=$MENU
nice -n +15 $D/mod_gui "$TARGET" >/dev/null 2>&1 &
```

三层 → 一层，改动是**一个新脚本**（覆盖社区原版 `EV_MOBILE.sh`，原版开 telnetd，
本项目已把 telnet 改成主菜单按钮，槽位空闲）。

---

## 三、mod_gui 的两个结构性缺陷

读 `mod_gui.c` 源码查证：

**① 点完就关窗**（这才是"不够一键"的真正根因）

```c
run_command() {
    evas_object_hide(win);
    system("<cmd> &");
    quit_app();      // ★ 立刻退出
}
```

关了就没了 → 想看效果必须重新触发 → 三层。

**② 波轮无解**

`key_down_callback` 只认 13 个键：`F6~F10` / `KP_Home` / `Scroll_Lock` /
`XF86PowerOff` / `Hiragana` / `Muhenkan` / `Control_R` / `Alt_R` /
`Katakana` / `XF86Reload` / `XF86WWW` / `KP_Enter`。

`Up`/`Down`/`Left`/`Right` 与 `JOG1_CW`/`JOG1_CCW` **全部落进 `else → quit_app()`**。

⇒ mod_gui 层「波轮切换」和「点完不关窗」都不可能，必须自己写。

---

## 四、nxfilmui：自写 EFL 版，波轮 + 触屏

### 为什么用 EFL 而不是 X11

| | X11 版（`nxflab.c`，已实机验证） | EFL 版（本程序） |
|---|---|---|
| 栈 | X11 + xcb | EFL/elementary |
| 满屏 720×480 720×480 | **实测吃满单核**，连 `echo` 都执行不完 | 与 `di-camera-app`/`mod_gui` 同一栈，固件自己优化过 |

### 核心难点：本地没有 EFL，怎么证明手写 ABI 声明对

**这是本轮唯一真正的技术障碍**，解法是换一个证据来源。

`sysroot`（`.uploads/nx1_open/rootfs_dev/.../lib`）只有 14 个 `.so`，
**没有 `libelementary` / `libevas` / `libecore`**，也没有头文件。
凭 EFL 版本记忆写声明 = 赌。

**换成从真机上跑通过的二进制反查**：

```bash
# test_server/filmlab/src/dynsym.py
python dynsym.py scripts/mod_gui --libs   # 按前缀把 UNDEF 符号归属到库
```

`mod_gui` 的 `.dynsym` 未定义符号里，直接出现了：

```
--- libecore.so.1 ---
  ecore_event_handler_add     ← ★ 证明该符号存在于真机 libecore.so.1
  ecore_main_loop_iterate
```

⇒ 「本地没有这个库」≠「真机没这个符号」。问题性质从**缺能力**变成**缺文件**。

### 查出并修掉的 3 个真问题

`check_abi.py` 拿 `mod_gui` + `di-camera-app`（4.7MB，230 个 elementary 符号）的
未定义符号做白名单，逐个核对 `nxfilmui.c` 的 25 个 EFL 引用：

| 符号 | 判定 | 处理 |
|---|---|---|
| `elm_box_recalculate` | ❌ **这个 API 根本不存在**（我原先写错了） | 删除，box 在 `pack_end` 后自己重算 |
| `elm_win_fullscreen_set` | ⚠️ 真机查无使用证据 | 改用 mod_gui 的做法：只靠 `elm_win_resize_object_add`绑窗口尺寸 |
| `elm_gengrid_page_size_set` | ⚠️ 真机查无使用证据 | 改用 `evas_object_size_hint_min_set` 定尺寸 + 外层套 `elm_scroller_add` |
| `elm_label_alignment_set` | ⚠️ 无证据 | 不用，颜色走 `evas_object_color_set` |
| `elm_object_text_color_set` | ⚠️ 无证据 | 不用，同上 |
| `elm_gengrid_reorder` | ⚠️ 无证据 | 不用 |

###链接期 stub 库（`efl_stub.c`）

缺库就链接不过，解法是造桩，但要保证**桩函数地址永不进真机**：

1. 桩库只在构建机参与链接，不部署
2. soname 与真机严格一致（`libelementary.so.1` / `libevas.so.1`）
3. 产物的 `DT_NEEDED` 记的就是这两个名字 → 真机 ld-linux 加载**真库**，
   按 ELF 符号解析规则把地址填进 GOT

### `ecore_event_handler_add` 为什么单独走 dlsym

这个符号属于 `libecore.so.1`，而**真机上确实有**（`mod_gui` 依赖它且跑通），
但本地无该库。危险写法是"链接期 stub 占位"——符号被静态解析进二进制，
真机上**调到空函数**：窗口能开、能触摸，但**波轮完全无反应且不报错**。
极难排查。

改成 `dlsym(RTLD_DEFAULT, ...)`，符号留在导入表里，运行时由 ld-linux 解析真函数。
并且 `dlsym` 失败时**显式 `return 1`**（不是静默降级），日志写明原因。

### 编译自证

```bash
bash test_server/filmlab/src/build.sh ui
```

```
out/nxfilmui.arm   40412 bytes   ELF1 32-bit LE  machine=0x28 ARM  type=2 EXEC

DT_NEEDED:
    libelementary.so.1     ← soname 正确
    libevas.so.1
    libpthread.so.0
    libc.so.6
    libdl.so.2

未定义符号: 50 个（无 ecore_*，确认 ecore 走 dlsym）
```

---

## 五、交互设计

| 通道 | 动作 | 行为 |
|---|---|---|
| 波轮 | `JOG1_CW` / `JOG1_CCW` | 上一个 / 下一个，**滚动即实时应用** |
| 触摸 | 点配方块 | 立即应用，**不关窗**（可连续对比多个配方） |
| 按键 | `KP_Enter` / `Return` | 应用并退出 |
| 按键 | `Left` / `Escape` / `XF86PowerOff` | 退出 |

**「滚动即应用」是刻意设计**：单核相机上 `apply` 要走 7 次 `prefman set` +
强制 ISP 重读，约1–2 秒。同步应用的好处是转到哪就生效哪，不用二次确认。

**光标高亮**（`paint_sel`）：波轮在 9 个配方的一屏里是盲操作，
选中项染成琥珀色（255,200,80），其余灰色（200,200,200）。

**退出即应用，不做回滚**——本来就是即时预览语义。

###必须实机确认的项

源码里已标`★`，无法静态判定：

1. **波轮的 keysym 名到底叫什么**。`on_key` 同时匹配 `JOG1_CW` / `Up` / `KP_Up` 三种写法。
   来源是社区文档里 `xinput test 8` 的输出——但那给的是 X11 **keycode**（`JOG1_CW=185`），
   ecore 回调给的是 **keysym 名**，两者不一定同名。三种写法里总有一种命中，
   日志会记下实际是哪个。
2. **触摸回调挂两处的生效情况**：`evas_object_smart_callback_add(it,"clicked",...)` 与
   `elm_gengrid_item_append(..., cb, ...)` 都挂了 `cb_item`。
   mod_gui 没用过 gengrid，「哪个在 1.7.99 上真触发」只有实机知道。挂两个兜底。
3. **零 CJK 字体降级**：实测 `/usr/share/fonts` 只有 9 个 ttf，无中文字体 →
   含中文的标签会渲染成空白。`mk_item` 检测到非 ASCII 就退化成 `"序号. key"`。
   如果 `recipes.json` 里标签是中文，屏幕上显示的是 `1. portra400` 这种。

---

## 六、本地回归测试（`recipes_test.c`）

「编译通过」只证明符号能解析，不证明逻辑对。`load_recipes` 的分段读法
（read 会截断半行，必须留到下次 read 接着解析）错了→ 屏幕空列表但不报错。

把解析代码抽出来用 PC 版编译，喂真配方格式：

```
  [PASS] 解析条数 == 3（# 开头被跳过）
  [PASS] 第0条 label == 'Portra 400'（含空格，未被切断）
  [PASS] 第2条 key == trix400（跳过注释后没错位）
  [PASS] 超长 label 的行被丢弃，不影响正常行
  [PASS] 段数不足的行被丢弃（不是静默产生垃圾值）
  [PASS] 空文件返回 0（触发 main 里的报错画面分支）

全部通过: 0 失败
```

**未覆盖**：`apply_sel` 的写入通道（`set_pw` / `cur_enum` 的 popen 正则）。
PC 上没有 `prefman` 测不了。已做静态核对——`cur_enum` 的 sed 正则与
`filmlab-apply.sh:111-112` **逐字一致**，两条通道同源。

---

## 七、部署

```bash
# 1. 引擎（★ 不在 install.sh 部署链，必须单独 FTP 投递）
#    test_server/filmsim/filmlab-apply.sh → /opt/usr/nx-ks/filmlab.sh
# 2. 触发脚本 + 部署自证
cp scripts/nx-rc/EV_MOBILE.sh  scripts/nx-rc/MOBILE_MOBILE.sh \
   scripts/nx-rc/flab-wifi.sh   /tmp/_xfer/
cp test_server/filmlab/src/out/nxfilmui.arm       /tmp/_xfer/nx-rc/
# 3. 走 SD 卡 install.sh，然后 FTP 补 engine + nxfilmui.arm
# 4. 相机上跑部署自证
/opt/usr/nx-ks/busybox sh /opt/usr/nx-ks/nx-rc/flab-wifi.sh
```

`flab-wifi.sh` 的 6 项检查全部只读，不写 PW：
引擎 / 配方库 / 2 个触发脚本 / EFL UI（可选）/ mod_gui 菜单重建 / 只读状态回显。

---

## 八、文件清单

| 文件 | 状态 | 作用 |
|---|---|---|
| `scripts/nx-rc/EV_MOBILE.sh` | 新建 | EV+WiFi → 打开 FilmLab 页（消灭三层） |
| `scripts/nx-rc/MOBILE_MOBILE.sh` | 新建 | 双击 WiFi → 无 UI 轮换配方 |
| `scripts/nx-rc/flab-wifi.sh` | 新建 | 部署 6 项检查 + 只读自证 |
| `test_server/filmlab/src/nxfilmui.c` | 新建 | EFL 版配方 UI（波轮+触屏+不关窗） |
| `test_server/filmlab/src/efl_stub.c` | 新建 | 链接期 EFL 桩库 |
| `test_server/filmlab/src/build.sh` | 新建 | 构建 + DT_NEEDED/符号自证 |
| `test_server/filmlab/src/check_abi.py` | 新建 | EFL 符号真机证据核对 |
| `test_server/filmlab/src/dynsym.py` | 新建 | ELF32 .dynsym 提取（导出/需外部提供） |
| `test_server/filmlab/src/readelf_needed.py` | 新建 | ELF32 DT_NEEDED 提取 |
| `test_server/filmlab/src/recipes_test.c` | 新建 | 配方解析本地回归（10 断言） |
| `test_server/filmlab/src/out/nxfilmui.arm` | 产物 | 40412 bytes，ELF32 ARM EXEC |

---

## 九、待决

1. **要不要重编译 keyscan 以支持单击 WiFi 键？** 收益 = 少一次双击；
   成本 = 输入守护替换风险 + 需重新验证 xinput 工具链。默认**不做**。
2. **`nxfilmui.arm` 上机验证** —— 3 个必须实机确认项（见第五节），
   尤其波轮 keysym 名。相机离线中。
3. 配方标签若为中文，屏幕上会显示 `1. portra400`。要不要改成
   `filmlab.sh export` 时就把label 转 ASCII？

##相关文档

- `docs/FILMLAB_ONEKEY_VERIFY.md` —— 真一键客观判据（A→E 五阶段）
- `test_server/filmsim/filmlab-apply.sh` —— 引擎本体，`cycle` / `pw_force_reload`
