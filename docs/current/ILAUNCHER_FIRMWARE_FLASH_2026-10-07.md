# iLauncher 固件刷写机制逆向 + 本地文件刷写可行性评估

> 日期：2026-10-07 ｜ 对象：`E:\iLauncher`（Samsung i-Launcher，2014-10 版）
> 证据脚本：`test_server/ilauncher/{fna_trace,fna_strings,fna_xref,fna_reloc}.py`
> 证据输出：`test_server/ilauncher/FNA_FLOW_EVIDENCE.txt`、`devinfo_table.txt`
> 结论一句话：**iLauncher 的刷机链路是「联网查版本 → 下载 ZIP → 解压 → 拷到相机 SD 卡」，它本来就不是「PC 直刷相机」—— 而这条链路的断点只有两个：① 版本查询服务器已死 ② ZIP 只能从 URL 下。好消息是「拷贝到 SD 卡」这一段是在 PC 上对相机的大容量存储卷做的纯文件拷贝，因此 100% 可以本地化。**

---

## 0. 结论表（先看这个）

| 问题 | 结论 | 证据 |
|---|---|---|
| iLauncher 是直刷相机固件吗？ | **不是**。它把固件包**拷到相机的 SD 卡**，由相机自己升级 | `Creating thread to copy the firmware to SD Card` / `SD Card Has Space.` / `CopyFileEx` |
| 联网模式为什么失效？ | 2 个 Samsung 版本查询 URL 已下线（samsungimaging.com / samsung.com） | `downloadUrlList.do?prd_mdl_name=%s` 两处 |
| USB 检测为什么失败？ | 走 SetupAPI 枚举 `USB\VID_xxxx&PID_xxxx`，按 devinfo 表匹配；**NX500 不在表里**（表最新到 NX1 04E8:140B） | iLauncher.exe 导入 SETUPAPI；158 条 devinfo |
| 能否改成「本地文件刷写」？ | **能，而且不需要改二进制** | 见 §4：整条链路可用「假 device.xml + 本地 ZIP 托管 + SD 卡卷」串起来 |
| 最省力的落地方式？ | **完全绕开 iLauncher**：直接把固件文件按规范拷到相机 SD 卡的 `/SYSTEM/` 目录 | 见 §4.3 方案 B（推荐） |

---

## 1. 组件构成（谁干什么）

`E:\iLauncher\` 下的 EXE/DLL 分两类：**主程序（编排）** vs **子工具（各自独立小工具）**。

| 文件 | 大小 | 角色 | 说明 |
|---|---|---|---|
| `iLauncher.exe` | 1,254,400 B | ★ 主编排器 | 唯一导入 **SETUPAPI**（USB 枚举）的模块；负责找相机、准备 `X:\SYSTEM\`、拉起子进程 |
| `upgrader.exe` | 565,248 B | 下载器 | 命名空间 `MS_Upgrader`；导入 urlmon+WININET |
| `firmwareUpgrader/firmwareUpgrader.exe` | 605,184 B | ★ 刷机 UI + 拷贝 | 真正执行「下载/解压/拷到相机 SD」；导入 WININET+SHLWAPI |
| `firmwareUpgrader/FnA.dll` | 574,976 B | ★★ 核心动作库 | 5 个导出；`do_modal_firmware_up_dlg` = 整个刷机流程 |
| `COMMON/COMMONDL.exe`、`SMC/SMCDL.exe` | ~13 万 B | 通用下载器 | DL = Download，纯 urlmon，无 USB 代码 |
| `DNG/DNGDL.exe`、`PAB/PABDL.exe`、`WDM/WigDownloadManager.exe`、`frontLCDAnim/lcdanim.exe`、`lightroom/lightroom.exe` | — | 各功能下载器 | 与刷机无关 |
| `setMaunal/setManual.exe` | — | **目录不存在** | 该功能已被阉割 |

★ **关键判据**：只有 `iLauncher.exe` 导入 USB 相关 API（`SetupDiGetClassDevsW` / `SetupDiEnumDeviceInterfaces` / `CM_Get_Device_IDW`）。**FnA.dll 里一行 USB 代码都没有** —— 它只认「路径」。

---

## 2. 刷机主流程（反汇编还原）

### 2.1 FnA.dll 导出函数签名

```
FnA.dll  5 个导出：
  0x10005ef0  create_lcd_anim_window
  0x10006040  do_modal_lcd_anim_notice_dlg_if_needed
  0x10006140  do_modal_firmware_up_dlg   ★ 刷机主流程
  0x10005ce0  set_language
  0x100065f0  isLatestVersionAvailable
```

`do_modal_firmware_up_dlg` 的真实签名（从 `[ebp+8]` 起，逐参数打日志还原）：

```cpp
int do_modal_firmware_up_dlg(
    CString model_name,             // [ebp+8]   日志 "arg: model_name: "
    CString device_xml_path,        // [ebp+0xc] 日志 "arg: device_xml_path: "
    CString firmware_copy_dir,      // [ebp+0x10]日志 "arg: firmware_copy_dir: "   ★ 目标目录
    CString urlType,                // [ebp+0x14]日志 "arg: urlType: "
    CString showCameraModelName);   // [ebp+0x18]日志 "arg: showCameraModelName: "
```

★ **注意 `firmware_copy_dir` 是「拷到哪里」，不是「从哪里读」** —— 它必须存在。

### 2.2 执行流水线

```
do_modal_firmware_up_dlg(model, device_xml_path, firmware_copy_dir, urlType, show)
│
├─ 逐参数打日志（0x6196…0x63bc）
├─ "Device xml full path: " + device_xml_path
│
├─ 0x6721  PathFileExistsW(device_xml_path)
│     ├─ 存在 → "Path Exists, Executing CurrentInfo Function"
│     │          → 解析 device.xml：/SDP/Device/BaseModelName、
│     │            FirmwareUpdate/CurrentVersion、ProductionPlace…
│     │          → "Getting Msg Maps"、"Lens latest FW availability"
│     └─ ★ 不存在 → 0x6ba1 → `xor al,al; ret`  直接返回失败，无任何回退
│
├─ 联网查版本（URL 来自上面解析结果）：
│     http://www.samsungimaging.com/common/support/firmware/downloadUrlList.do?prd_mdl_name=%s&loc=%s
│     http://www.samsung.com/%s/support/firmware/downloadUrlList.do?prd_mdl_name=%s
│     → 返回 XML，取 /FirmwareInfo/* 里的 DownloadURL 字段
│
├─ "Downloading..." URL: …  To: …（下载到临时文件）   log "downloadToFile:"
├─ "Download Complete.. Trying to unzip (%s) to (%s)"
├─ 0x28a90 = Unzipper::extract  →  "Unzip success"
│
├─ "Firmware Copy dir: " + firmware_copy_dir
├─ 0xef99  GetDiskFreeSpaceExW(firmware_copy_dir …)
├─ 0xefa7  比较 可用空间 vs 解压后总大小（ebx+0xac）
│     ├─ 够 → "SD Card Has Space."      置 [ebp-0x121]=1
│     └─ 不够→ "SD Card doesn't has Space."
│
├─ "Creating thread to copy the firmware to SD Card"   ← ★ 关键：开线程拷贝
│     thread:  "Trying to create directory " + 目录
│              "Trying to copy file (%s) - (%s)"
│              CopyFileExW 逐文件复制
│              "CopyFileEx result= %d, lastErr= %d"
│              → "Firmware Copy successful" / "Firmware Copy not successful"
│
└─ "Download Successful"
```

关键调用点（图）：
- `0x1004d174` = `KERNEL32!GetDiskFreeSpaceExW`
- `0x1004d39c` = `SHLWAPI!PathFileExistsW`
- `0x1004d2d4` = `MSVCR100!free`（CString 析构）

### 2.3 device.xml 解析的 XPath（完整）

```
/SDP/Device/BaseModelName/@value
/SDP/Device/FirmwareUpdate/CurrentVersion/@value
/SDP/Device/FirmwareUpdate/ProductionPlace/@value
/SDP/Device/LensFirmwareUpdate/@value                 (="TRUE")
/SDP/Device/LensFirmwareUpdate/LensModelName/@value
/SDP/Device/LensFirmwareUpdate/LensFWVersion/@value
/SDP/Device/LensFirmwareUpdate/LensFWName/@value
/SDP/Device/LensFirmwareUpdate/LensProductionPlace/@value
/SDP/Device/LensFirmwareUpdate/LENSProductionPlace/@value
/FirmwareInfo/*            → 取子节点 FWVersion / DownloadURL / Description / DescriptionKor
```

---

## 3. iLauncher.exe 的 USB / 卷定位逻辑

从字符串（UTF-16）可见：

```
"USB\VID_%4X&PID_%4X"     ← 用 SetupAPI 枚举匹配设备实例 ID
"\\?\%c:"                 ← 卷设备路径
"%c:\SYSTEM\device.xml"   ← 相机大容量存储上的 device.xml
"%c:\SYSTEM\system.bin"   ← 相机大容量存储上的固件本体
" firmwareUpgrader.exe"   ← 子进程命令（前导空格 = 拼接命令串）
" firmwareUpgrader\"      ← 子进程工作目录
"Please attach a SAMSUNG Camera to update firmware"
```

**推断的 iLauncher 主逻辑**：

```
1. SetupDiGetClassDevs + SetupDiEnumDeviceInterfaces 枚举设备
2. 用 devinfo 表匹配 USB\VID_%4X&PID_%4X
3. 拿到相机的盘符 X:
   （NX 相机 USB 模式暴露为大容量存储 / MSC）
4. 检查 X:\SYSTEM\device.xml 是否存在
5. 拉起 firmwareUpgrader\firmwareUpgrader.exe（工作目录 firmwareUpgrader\）
   → 后者 LoadLibrary FnA.dll 并调用 do_modal_firmware_up_dlg(...)
```

**NX500 为什么检测不到**：`iLauncher.exe` 内嵌 158 条 `<devinfo>` 表，NX 系列 16 款，**没有 NX500**（表里最新是 NX1 `04E8:140B`）。NX500 于 2015 年发布，本 iLauncher 是 2014-10 版，早于它。

已导出全表：`test_server/ilauncher/devinfo_table.txt`。

---

## 4. ★ 本地文件刷写可行性评估

### 4.1 断点定位（哪一步断了）

| 步骤 | 状态 | 能否本地化 |
|---|---|---|
| ① 设备枚举（USB VID/PID） | 断（表里无 NX500） | 可绕过（手工定位盘符） |
| ② `X:\SYSTEM\device.xml` 存在性检查 | 可用 | 可自造 |
| ③ 版本查询 HTTP | **死**（服务器下线） | 可本地伪造（改 hosts / 自建 HTTP） |
| ④ 下载 ZIP | 依赖 ③ | **可完全跳过**（本地放 ZIP） |
| ⑤ 解压 | 可用（自带 Unzipper，zlib 1.01） | 本地 |
| ⑥ 拷到 `firmware_copy_dir` | 可用 | 本地 |

★ 结论：**只有 ③④ 断，而 ③④ 恰好都能用本地文件替代。**

### 4.2 方案 A：喂 FnA.dll 一个「本地化」调用（可行，需少量胶水）

`do_modal_firmware_up_dlg` 的 `firmware_copy_dir` 是**目标目录**（相机 SD 卡卷），
不是源。因此**不能直接“把本地 ZIP 传进去”** —— 源必须靠 ③ 的返回 XML 给出。

改造点：让 `downloadUrlList.do?prd_mdl_name=NX500&loc=...` 指向**本地 HTTP**，
返回一个 XML：

```xml
<FirmwareInfo>
  <FWVersion>1.12</FWVersion>
  <DownloadURL>http://127.0.0.1:8080/NX500_FW.zip</DownloadURL>
  <Description>local</Description>
</FirmwareInfo>
```

做法（任选）：
- **改 hosts**：把 `www.samsungimaging.com` / `www.samsung.com` 指向 `127.0.0.1`，本地起 80 端口 HTTP 服务（需管理员+改 hosts）。★ 注意 URL 是 **http（非 https）**，无证书校验，极易劫持。
- **直接写一个替身 EXE**：用 FnA.dll 导出的 `do_modal_firmware_up_dlg` 自己写调用者（MSVC，32 位），
  传 `firmware_copy_dir = "X:\"`，然后靠 hosts 重定向喂本地 ZIP。★ 这是最干净的「改写为本地文件」形态。

★ 风险/代价：需要 MSVC 32 位工具链 + 写少量 C++ + 一个本地 HTTP 服务 + 改 hosts。
★★ 但**这一步没必要**，因为——

### 4.3 ★★★★★ 方案 B（推荐）：彻底绕开 iLauncher，直接向 SD 卡投放

**这是本报告最重要的结论。** 整条 iLauncher 链路的**终点只是一个文件拷贝**：把解压后的固件文件，
按规范放进相机 SD 卡（或相机 MSC 卷）的目录里。既然如此，用普通文件操作即可完成，无需 iLauncher 任何组件。

依据：
1. `firmwareUpgrader.exe` 的拷贝目标就是 `%c:` 卷上的目录，动作是 `CopyFileExW`（纯文件复制）。
2. 相机端升级靠**读 SD 卡上的固件文件**（社区 NX-KS/NX-KS2 一直这么做，本仓库即证据）。
3. `"For an NX camera, "Body Firmware" should be selected in the firmware update menu of the device to start firmware upgrade."` —— **升级是相机自己发起的**，PC 只负责“投文件”。

**操作步骤（NX500）**：
```
1. 取官方固件升级文件（.zip 内含 .bin/.srf 等，视版本而定）
2. 解压
3. 按官方目录规范拷入 SD 卡：
     <SD>:\ 根目录或官方指定目录（NX 系列通常是根目录放 *.bin）
   或（若走相机 MSC）  X:\SYSTEM\  —— 与 iLauncher 的 %c:\SYSTEM\ 一致
4. 插卡 → 开机 → 菜单里选 Body Firmware → 升级
```

★ 需要确认的一点（待实测）：**NX500 官方升级文件的放置路径与文件名规范**。
这可以从**官方 NX500 固件包**（三星官网/社区镜像下载的 .zip）里直接读到 —— 里面有 `device.xml` 或说明文件，
或者直接观察 iLauncher 解压后拷贝的目录结构（`Trying to create directory %s` 的那个路径）。

### 4.4 方案 C：纯离线「版本伪装」（若坚持用原 UI）

把 `X:\SYSTEM\device.xml` 手工放到相机 MSC 卷上，`CurrentVersion` 填一个低版本，
则 iLauncher 会认为“需要升级”。但 ③ 仍是死的 ⇒ 依旧需要 4.2 的 hosts 劫持。**不推荐。**

---

## 5. 对我们的 NX-KS2 项目的意义

| 结论 | 对项目的用处 |
|---|---|
| iLauncher 不直刷相机 | ⇒ 我们**不必**去逆向任何 USB 刷机协议 / DRIMe 刷写器 —— **那条路不存在** |
| 升级 = 相机读 SD 卡文件 | ⇒ 与我们现在的 SD 卡部署（`nx-ks2` 脚本 + push.sh）**完全同构**，已验证可行 |
| 官方升级文件可本地投递 | ⇒ 若将来需要**回滚/刷官方固件**，只需 SD 卡放文件，无需 iLauncher |
| `device.xml` 结构已解出 | ⇒ 可用于**伪装/绕过版本检查**（如让相机认为已有更高版本，或做研究） |
| 版本查询 URL 已死且为 http | ⇒ 若做研究，本地 hosts 劫持无证书障碍 |

★ **一句话**：`E:\iLauncher` 对我们的价值是**参考文档**而非工具 —— 它反证了「NX 系刷机不需要 PC 直连协议」，
从而**关闭了一条本可能被误开启的逆向方向**（省下大量时间）。

---

## 6. 待办 / 验证清单

- [ ] 找一份官方 **NX500 固件 .zip**，读出其内部目录结构与文件名规范（决定方案 B 的落地细节）
- [ ] 确认相机 MSC 模式下暴露的卷是否可写 `X:\SYSTEM\`（有的机型只读）
- [ ] （可选）验证 `PathFileExistsW` 分支：手工造一个 `device.xml` 看 iLauncher 是否走到下一步
- [ ] （可选）用 FnA.dll 自写调用者 + hosts 劫持，做「方案 A」POC
