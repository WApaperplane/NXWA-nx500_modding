# 固件升级校验链（D3 · libfirmware-upgrade.so 逆向 · ★ 全解）

> 日期：2026-10-08 ｜ 全程离线：只读 rootfs（`/opt/nxks2/rootfs-112`）+ 官方固件（`.uploads/fw/nx500_v1.13.bin`），**未触碰任何真机**。
> 对象：`usr/lib/libfirmware-upgrade.so`（BuildID `sha1=3e4e067db514b5ed25487c658900ade1c24cf429`，43,684 B，ARM Thumb-2，来自 1.12 rootfs）
> 原始证据：`raw8/fw/upgrade_chain/`（反汇编、strings、符号表、调用者切片、复算脚本）
> 交付问题：①升级对 SLP 做了哪些校验 ②校验调用点清单 ③重打包 SLP 会不会被拒、拒在哪一步

---

## 0. 一句话结论

> **官方 SLP 升级链里只有「容器级结构校验 + 逐段 JAMCRC」这一套，没有任何签名/证书校验；机型校验是一个 16 字节的 project 字符串比对（`NX500`），版本校验发生在 App/dfmsd 层、且只拦「降级」不拦「同版本」。**
> ⇒ **「只改内容 + 重算该段 JAMCRC + 保持 len/offset/flags/project 不变」的重打包 SLP，在 SLP 校验层不会被拒**；
> 唯一需要按入口区分的是 **CRC 到底算不算**：**相机 UI 的实刷回调用 flag=1，会真正逐段校验 CRC**（所以你改了内容就必须把该段 CRC 算对）；
> 而 `st firmware up` / `fw_upgrade_start` 只走 `fw_start_upgrade`（内部 flag=0，**不算 CRC**）。**只要 CRC 算对、project 保持 `NX500`，两条路都能过。**
> 另：dfmsd（云通道）额外要求「与当前版本不同」，同版本重刷经 dfmsd 不会触发；相机 UI 只拦“降级”。

---

## 1. 校验调用点清单（函数地址 / 符号 + 做了什么 + 失败行为）

> 地址均为 `libfirmware-upgrade.so` 中**实际反汇编得到**的地址（Thumb 符号值低位为 1，下表用 objdump 的 `@@Base` 基址）。

### 1.1 库内（`libfirmware-upgrade.so`）

| # | 符号 @ 地址 | 该点做了什么 | 失败时行为 | 证据 |
|---|---|---|---|---|
| C1 | `fw_validate` @ `0x31d4`（size `0x3b0`） | SLP **结构级校验**总入口（见 §2 逐条） | 返回 `-1` 并 `fprintf(stderr,...)` 打印具体原因；调用方放弃升级 | 反汇编 `annotated_key_functions.txt` |
| C2 | `fw_upgrade_crc32` @ `0x4700`（`0xbc`） | 从当前文件位置读 `len` 字节并算 **JAMCRC**（初值 `0xFFFFFFFF`，查表 CRC-32，**不做最终异或**） | 读失败 `fwrite("cannot read input file")` | `annotated_key_functions.txt` :1028 |
| C3 | `fw_crc32` @ `0x46d0`（`0x30`），表 `fw_crc32_table` @ `0x7f80`（`0x400`） | 反射 CRC-32 内核（`crc=table[(b^crc)&0xff] ^ (crc>>8)`，无最终异或） | —— | 同上 :1005 |
| C4 | `fw_start_upgrade` @ `0x359d`（`0x190`） | 升级主序列：`fw_validate(path, get_project_name(), 0)` → `fw_get_info` → `fw_init_proc_plugin` → `fw_flash_upgrader` → `sync()` → `system("reboot -f")` | 任一子步骤 `<0` ⇒ 打印 `firmware(%s) is not valid !!` / 对应错误并返回 `-1`（**不刷、不重启**） | `annotated_key_functions.txt` :1498 |
| C5 | `fw_merge_check_hw` @ `0x381d`（`0xe4`） | 读 **`/mnt/mmc/soft.pl`**（SD 卡上的文件，**不是 SLP**），把其内容与 `fw_get_str_bd_version()`（`fw_get_bd_version` 经 `/dev/mem` mmap 物理 `0x85180000` 读板级版本，@`0x4e55`）`strcmp` | 不等 ⇒ 返回 `-1`；打不开 soft.pl 打印 `soft.pl does not exist!` | `annotated_key_functions.txt` :362 |
| C6 | `fw_cmp_bl_version` @ `0x4d24`（`0x130`） | 仅当实参 == `"bootloader.bin"` 时：读 `/etc/version.info`（`fgets` 5 次，取最后一行）与期望串 `strncmp`；打不开打印 `Version information file does NOT exist!` / `can't open version-info file.` | 与期望不符 ⇒ 返回非 0 | 同上 :443 |
| C7 | `fw_cmp_ss_version` @ `0x4f00`（`0x9c`） | 读 `/etc/bd.conf` 首个整数（`strtol`）与 `fw_get_bd_version()` 比较，打印 `Body Boardversion` / `F/W Snapshot Img. Boardversion` | 不等 ⇒ 返回 1 | 同上 :572 |
| C8 | `fw_emmc_mkfs_preproc` @ `0x5eb5` | **不是闸门**：在每个镜像名（`bootloader`/`vImage`/`pref`/`snapshot`/`pcache`/`devicem4`…）间分发，只有 `bootloader` 会调 C6；`[%s] same version!`（`0x8d4c`）在此打印，用于**决定是否跳过重刷 bootloader** | 仅为优化判断 | `find_ref.py` 命中 0x5fe4；`annotated_all_rest.txt` |

> **C6/C7/C8 都不是“拒绝整包”的闸门**：它们只影响 bootloader/板级信息是否需要重刷，与 SLP 是否被接受无关（C7 甚至在库内**无任何调用者**，仅导出）。

### 1.2 库外（升级入口 / 调用者）

| # | 调用者 @ 地址 | 调用 | flag | 说明 / 证据 |
|---|---|---|---|---|
| E1 | 相机 App `di-camera-app` · `UI_Check_Body_Fw_Available` @ `0x10889c` | `fw_validate(path, get_project_name(), 0)` @ `0x1089cc` | **0** | 仅做头/机型/flags（**不算 CRC**），供 UI 显示与“是否有更新”判断；路径 = `/mnt/mmc/<GetProjectName_small()>.bin`。证据 `callers/dica_UI_Check_Body_Fw_Available.txt` |
| E2 | `di-camera-app` · `UI_Start_Body_Fw_Upgrade` 的 idle 回调 @ `0x109258` | `fw_validate(path, get_project_name(), 1)` @ `0x1092d4` | **1** | ★ **正式升级路径：flag=1 ⇒ 逐段 JAMCRC 被真正校验**（同时起进度线程）。证据 `callers/dica_UI_Start_Body_Fw_Upgrade_and_cb.txt` |
| E3 | `di-camera-app` @ `0x108080`（匿名函数 `__us_cmode_db_info_print+0x3734`，位于 E2 回调链下游） | `fw_start_upgrade(path)` | (内部 0) | 实刷入口：先 `snprintf(path, GetProjectName_small())` + `UI_SysCtrl_Delay(2000)` 再刷。证据 `callers/dica_UI_Start_Body_Fw_Upgrade_and_cb.txt` |
| E4 | `dfmsd`（DFMS 云升级守护）@ `0x1cc2c` | `fw_validate(path, get_project_name(), r8)`，`r8 = strcasecmp(...) != 0`（**非 0**） | **非 0** | ⇒ 走 CRC 校验；随后 `strcmp(get_fw_version_short(), SLP 版本字段)`，**只有版本“不同”才** @ `0x1cf1c` 调 `fw_start_upgrade`。证据 `callers/dfmsd_fw_validate_upgrade.txt` |
| E5 | `libshell-command.so` · `shell_firmware` @ `0xb734`（`st firmware` 命令） | “up” 处理器 @ `0xb074` → `fw_start_upgrade()` @ `0xb168` | (内部 0) | 拼 `/sdcard/<小写project>.bin`，`access(R_OK)` 存在性检查后直接 `fw_start_upgrade`；**无 CRC、无版本比较**。证据 `callers/lsc_shell_firmware_cmdhandlers.txt`、`strings_libshell-command.so.txt`（`usage: st firmware`、`/sdcard/%s.bin`、`Firmware File does NOT exist in SDCARD!`） |
| E6 | `fw_upgrade_start`（CLI）main @ `0x85e8` | `fw_start_upgrade(argv[1])` @ `0x85dc` | (内部 0) | `argc==2` 且路径长度 1..1024 才放行。证据 `callers/disasm_fw_upgrade_start.txt` |
| E7 | `fw_upgrade` / `fw_upgrade_recovery` | `fw_flash_upgrader()`（更底层，恢复用） | — | 不走 `fw_validate` |
| E8 | `ap-setting-app` · `CAPPNetworkFirmwareNotice::checkSdcardFirmwareAvailable` @ `0x33188` | `fw_validate(path, get_project_name(), 0)` | **0** | 设置 App 的“检查 SD 卡固件”提示，仅 flag=0 预检；无 `fw_start_upgrade`。证据：全树 grep + `/tmp/aps.txt`（可按 §5 复现） |

> **全树调用者汇总（`grep -rlI` 于整个 `rootfs-112`）**：
> - `fw_validate` ← `dfmsd`、`di-camera-app`、`ap-setting-app`（后两者仅在“可用性预检”处用 flag=0）
> - `fw_start_upgrade` ← `dfmsd`、`fw_upgrade_start`、`libshell-command.so`、`di-camera-app`
> - `fw_merge_check_hw` ← `di-camera-app`（+ 库内自用）

---

## 2. 逐项判定（机型 / 版本 / 签名）

### 2.1 ★ 机型串比对 —— **有**（硬证据）

`fw_validate`（@`0x31d4`）在读完 64 B 头后：

```
0x32f4  cmp sb, #0            ; sb = 第 2 实参 = 期望 project 串
0x32f8  beq 0x330c            ; 为空则跳过
0x32fa  mov r0, sb
0x32fe  add r1, sp, #0x590    ; = 头缓冲区 + 0x0c  ← project 字段(16B)
0x3302  movs r2, #0x10        ; 比较 16 字节
0x3306  blx strncmp
0x3308  bne 0x3494            ; 不等 → 打 "[PROJECT] Set: %s, Fw: %s" 并返回 -1
```

- 比对的是 **SLP 头偏移 `0x0c` 处的 16 字节 `project`** 与**实参期望串**。
- 实参期望串来自 `get_project_name()`（`libversion-info.so` 导出，@`0x1668`，内部 `CVersionInformation::GetProjectName`）。`CVersionInformation` 构造器（`libversion-info.so` @`0x17dc`）读取 **`/etc/version.info`** 逐行填入（`Project : %s` 日志；`find_ref2.py` 命中 0x183c/0x1f04 等）。
- 实测：`/opt/nxks2/rootfs-112/etc/version.info` = `1.12` / **`NX500`** / `NX500GLU0APC1` / `DSP_NX500GLU0APC1_SR1` / `BABF43A`；官方 SLP 头 `project = "NX500"`（hexdump 实测）。⇒ 官方包与设备同名 ⇒ 通过。

**判定：有“机型/项目串”校验，但是 16 字节字符串 `strncmp`，且要过很简单（保持 `NX500` 即可）。**

### 2.2 版本比对 —— **不在 SLP 校验层；在 App/dfmsd 层，且只拦降级**（硬证据 + 1 处推断）

**（a）`libfirmware-upgrade.so` 内：`fw_validate` / `fw_start_upgrade` 全程不比较版本。** 反汇编逐条看，只有 4 个判断：magic、`num_image` 范围、project（§2.1）、flags 与 JAMCRC（§2.3）。没有任何“版本必须更高/必须不同”的分支。

**（b）相机 App 层（数值比较，非字符串）**：`UI_Check_Body_Fw_Available` @`0x108bc8` 后：
```
UI_Get_Firmware_Info(4, bufA, 100);  UI_Get_Firmware_Info(5, bufB, 100);
r7 = strtol(bufA);   sl = strtol(bufA+2);   // 设备版本 major/minor
r8 = strtol(bufB);   r9 = strtol(bufB+2);   // 文件版本 major/minor
0x108df0  cmp r7, r8 ; movhi r4,#0           // 设备主版本 > 文件主版本 → 不可用
0x108dfc  cmp sl, r9 ; movhi r4,#0 ; movls r4,#1   // 相等 → 可用=1
```
⇒ **只在“文件版本 < 设备版本”时拒绝（拦降级）；同版本返回 1（允许）。**

**（c）dfmsd 层**：`0x1cc58` `get_fw_version_short()` → `0x1cc64` `strcmp(设备版本串, meta+0x1c)`（`meta` = `fw_get_info` 读出的 64B SLP 头；`+0x1c` 即 `version_date` 字段）→ `0x1cc6c` **`bne` 才升级**（相等 ⇒ 不上报/不升级）。字段语义（是否就是 `version_date`）为推断。

**（d）旧结论“版本校验是纯字符串比较”**：对应的是 `fw_cmp_bl_version`（C6，`strncmp`）与 `fw_cmp_ss_version`（C7，`strtol`/整数）；二者只用于 bootloader/板级重刷判断，**不是整包闸门**。
> 推断（非硬证据）：`UI_Get_Firmware_Info` 的 type 4 / type 5 哪个是“设备”、哪个是“文件”未逐字节确认；但两分支合起来必然表达“文件≥设备才可用”，因为反方向（文件>设备→拒绝）在语义上不成立。

### 2.3 容器内逐段校验（除 JAMCRC 外，还有 **flags 魔数** 与 magic/计数）—— **有**（硬证据，且已复算通过）

`fw_validate` 实际做的全套容器校验（`annotated_key_functions.txt` 全文）：

```
读 64B 头（= 48B SLP 头 + 16B 标签）
num = *(u32*)(hdr+0x2c)                         // num_image
if (num-1 > 14)                  → "num image invalid (%d)"        返回 -1   // 1..15
if (!(hdr[0..3]=="SLP\0")) {
    if (strncmp(hdr,"DRM5",4)!=0) → "[MAGIC] Set: SLP, Fw: %s"      返回 -1   // 备选 magic
}
if (期望project!=NULL && strncmp(期望project, hdr+0x0c,16)!=0)
                                 → "[PROJECT] Set: %s, Fw: %s"     返回 -1
读 24*num 字节记录表到栈(360B 上限)
if (record[0].flags != 0xffffffff) → "[IMG-MAGIC] ..."             返回 -1
for i in 0..num-1:
    if (flag==1) c = fw_upgrade_crc32(fp, record[i].len)
    else         fseek(fp, record[i].len, SEEK_CUR)      // flag==0 不校验 CRC
    if (flag==1 && c != record[i].crc) → "%d: [IMG-CRC32] Set: 0x%x, Fw: 0x%x"  返回 -1
    if (record[i].flags != MASK(i))    → "%d: [IMG-MAGIC] Set: 0x%x, Fw: 0x%x"  返回 -1
    // MASK(i) = (0xffffffff >> (4*(i%8))) | (0x87654321 << (4*(i%8)))   取模 2^32
返回 0
```

- **记录步长 24**：`record[i]` 由 `r0 = rectab + (3*i)*8 = rectab + 24*i` 计算（`0x3378`–`0x338a`），字段：`+0x00 len`、`+0x04 crc`、`+0x0c flags`。**`offset`(@+0x08) 未参与校验**（用 `SEEK_CUR` 顺序跳过/读取）。
- **flags 是魔数而非自由位**：`MASK(i)` 由常数 `0xFFFFFFFF` 与 `0x87654321` 做半字节旋转得到。用该公式对官方 v1.13 逐条复算，**10/10 命中**（见 §5 复算输出）。
- **JAMCRC**：`fw_upgrade_crc32` = 初值 `0xFFFFFFFF`、查表反射 CRC-32、**无最终异或** ⇒ 等价 `zlib.crc32(seg) ^ 0xFFFFFFFF`。对官方 v1.13 逐段复算，**10/10 命中**。

### 2.4 签名 / 证书校验 —— **无**（硬证据）

1. `libfirmware-upgrade.so` 的全部导入（81 个 UND 符号）里**没有任何密码学函数**（无 openssl/crypto/sha/rsa/aes/hmac），只有 `libc/libpthread/librt/libgcc/liblogutil/libdlog/libversion-info`。
2. `libfirmware-upgrade.so` 全字符串中**无 sign / cert / hash / rsa / aes / sha / hmac / public key** 相关串（唯一含 “hash” 的是 ELF 段名 `.hash`）。
3. SLP 容器**无签名块**（前序文档 `SLP_CONTAINER_FORMAT_2026-10-08.md` §5：文件末尾与最后一段严格重合，无尾部摘要/证书区）——本轮 `fw_validate` 反汇编**独立印证**：它只读头 64B 与记录表，从不读文件尾部。
4. 同目录 `libsecfw.so` 与固件无关（是 URL 评级 / `TCS/TWP` 内容过滤），非签名库。
5. 升级路径上的 `di-camera-app` 虽链接 `libssl/libcrypto`，但那是网络/NFC 用；固件校验路径（E1/E2/E4）不触碰。

**判定：无签名、无证书、无整包哈希。**

---

## 3. 对“重打包 SLP 能否过”的结论与依据

**问题**：只改内容、重算 JAMCRC、`len`/`offset` 不变。

### 3.1 结论

> **不会被拒（可过）** —— 前提是：① 段的 JAMCRC 算对并回填到记录 `+0x04`；② `flags`(@+0x0c) 保持不动；③ 头里 `project` 保持 `NX500`、`num_image` 不变。
> 满足这三条时，`fw_validate` 的**每一条**判断都是原值/自洽的 ⇒ 返回 0。
>
> **唯一需要按入口区分的行为**：
> - 相机 UI 正式升级（E2, flag=1）与 dfmsd（E4, flag≠0）：**逐段 JAMCRC 会被真正计算**（必须算对）。
> - UI 的可用性预检（E1, flag=0）与 `fw_start_upgrade` 内部那次（flag=0）：**不算 CRC**（只查头/机型/flags）——即便 CRC 没改也能过这一关，但这只是“又一次”调用；正式刷新前 E2 已经算过。
> - dfmsd 额外要求“版本与当前不同”（§2.2c）：**同版本重刷经 dfmsd 不会触发**（但 dfmsd 是云通道；SD 卡通道不走它）。
> - `st firmware up`（E5）与 `fw_upgrade_start`（E6）只走 `fw_start_upgrade`（内部 flag=0）⇒ **连 CRC 都不校验**，同版本/降级都放行。

**拒的场景（若发生，拒在哪一步）**：
| 触发原因 | 拒绝点 | 表现 |
|---|---|---|
| CRC 没重算或算错 | `fw_validate` 第 i 条 → `0x34d6` | `%d: [IMG-CRC32] Set: 0x…, Fw: 0x…`，返回 −1 |
| flags 被改动 | `fw_validate` → `0x33ac`（或 `0x351e`） | `[IMG-MAGIC] Set: 0x…, Fw: 0x…`，返回 −1 |
| project 被改（≠`NX500`） | `fw_validate` → `0x3494` | `[PROJECT] Set: …`，返回 −1 |
| magic/num_image 被破坏 | `fw_validate` | `[MAGIC]…` / `num image invalid (%d)`，返回 −1 |

注：入口层还可能先拒——UI 侧 `UI_Check_Body_Fw_Available` 在“文件版本 < 设备版本”时返回 0（**降级被拦**）；dfmsd 在“版本相同”时不升级。**这两条与“是否重打包”无关，只与版本号相对大小有关。**

### 3.2 依据（两条独立证据）

1. **反汇编**：`fw_validate` 的判定分支只有 §2.3 所列 6 类；无签名、无版本、无整包哈希（本报告 §1–2）。
2. **复算**：用从反汇编归纳出的规则（magic / num / project / flags 魔数 / JAMCRC），对官方 `nx500_v1.13.bin` 复算 ⇒ **全表 PASS**（§5）。两组证据一致 ⇒ 规则正确，且“保持原值即自洽”成立。

---

## 4. 未决与风险

| 级别 | 事项 | 说明 |
|---|---|---|
| 中 | **flag（第 3 实参）语义未完全定名** | 已确证 flag≠0 ⇒ 起进度线程 + 逐段 CRC；flag==0 ⇒ `fseek` 跳过。命名（“verify/thread”）属推断；不影响结论。 |
| 中 | **`get_project_name()` 的确切取值链路** | 已证 `CVersionInformation` 读 `/etc/version.info`（构造器 @`0x17dc`，命中 `/etc/version.info` @`libversion-info.so:0x183c`），且文件第 2 行 = `NX500`；“第 2 行→project 字段”是**推断**（日志 `Project : %s` 存在，但未逐行断言哪一行绑定哪个成员）。若 NX-KS2 改过 `/etc/version.info`，需确认 project 仍为 `NX500`。 |
| 中 | **`UI_Get_Firmware_Info` type 4/5 的方向** | 推断为“设备”和“文件”；未逐字节确认哪一 type 是哪一方。 |
| 低 | **`fw_validate` 的 CRC 是否覆盖“表/头”** | 实测：只覆盖 `[offset,offset+len)` 的段体、逐段独立、不含头/表（与容器文档一致）。 |
| 低 | **`DRM5` 备选 magic 的适用范围** | `fw_validate` 接受 `"SLP\0"` 或 `"DRM5"`（4B 比较）；NX500 用前者。 |
| 低 | **`fw_cmp_ss_version` 无内部调用者** | 仅导出；外部（本 rootfs 内）未见引用 ⇒ 疑似遗留接口。 |
| — | **真机未验证** | 按纪律全程离线，未触碰 192.168.0.105/103；“能被接受”的最终确认仍需机上一次。 |

---

## 5. 复现步骤

```bash
# WSL(NXKS2) 内。Git Bash 调用需 MSYS_NO_PATHCONV=1 且路径用 /mnt/d/...
EV=/mnt/d/download/NX-KS2-88/raw8/fw/upgrade_chain

# 1) 取二进制与反汇编
cp /opt/nxks2/rootfs-112/usr/lib/libfirmware-upgrade.so $EV/
arm-linux-gnueabihf-strings -a -t x $EV/libfirmware-upgrade.so > $EV/strings_libfirmware-upgrade.txt
arm-linux-gnueabihf-objdump -d $EV/libfirmware-upgrade.so        > $EV/disasm_full_libfirmware-upgrade.txt

# 2) 关键函数“带字符串注解”的反汇编（Windows python，仓库根目录执行）
python raw8/fw/upgrade_chain/annotate.py fw_validate fw_upgrade_crc32 fw_crc32 fw_start_upgrade \
      fw_merge_check_hw fw_cmp_bl_version fw_cmp_ss_version fw_get_meta_header fw_get_info \
      fw_emmc_mkfs_preproc  > raw8/fw/upgrade_chain/annotated_key_functions.txt

# 3) 定位“某字符串被哪个函数引用”（会逐函数反汇编，避免字面量池失步）
python raw8/fw/upgrade_chain/find_ref.py 0x75bc 0x75dc 0x75f8 0x7620 0x8d4c 0x8d60

# 4) 用反汇编归纳的规则复算官方 SLP（★ 交叉验证）
python raw8/fw/upgrade_chain/verify_slp.py .uploads/fw/nx500_v1.13.bin

# 5) 调用者切片
arm-linux-gnueabihf-objdump -d --start-address=0x10889c --stop-address=0x109560 \
    /opt/nxks2/rootfs-112/usr/apps/com.samsung.di-camera-app/bin/di-camera-app
arm-linux-gnueabihf-objdump -d --start-address=0x1cb90 --stop-address=0x1cf60 \
    /opt/nxks2/rootfs-112/usr/bin/dfmsd
```

**复算输出**（`verify_slp_output.txt`，规则全部来自本报告 §2——若规则有误则不可能全中）：

```
file : .uploads/fw/nx500_v1.13.bin  size=352121435
magic: b'SLP\x00' OK    num_image: 10 OK    project: b'NX500'
idx  len         off          flags(check)   crc(check)
 0   6160624     0x00000130  0xffffffff OK 0x48f3183b OK
 1   56289       0x005e0220  0x7fffffff OK 0x19d433b2 OK
 2   3176040     0x005ede01  0x65ffffff OK 0xd8719107 OK
 3   6169816     0x008f5469  0x543fffff OK 0x2180947f OK
 4   117184      0x00ed7941  0x4321ffff OK 0x8785210e OK
 5   12075648    0x00ef4301  0x32100fff OK 0xdf679d3b OK
 6   280505658   0x01a78581  0x210000ff OK 0xbda66ec1 OK
 7   5022551     0x125fb2bb  0x1000000f OK 0x41191fb5 OK
 8   28672       0x12ac5612  0xffffffff OK 0xef2256df OK
 9   38808649    0x12acc612  0x7fffffff OK 0xb5082de3 OK
ALL CHECKS: PASS
```

---

## 6. 证据文件清单（`raw8/fw/upgrade_chain/`）

```
libfirmware-upgrade.so                     被测 .so 原件
disasm_full_libfirmware-upgrade.txt        全量反汇编
strings_libfirmware-upgrade.txt / dynsym_… 字符串 / 动态符号
annotated_key_functions.txt                fw_validate 等关键函数“带字符串注解”反汇编（★ 主证据）
annotated_flash_and_merge.txt              刷写/合并函数注解
annotated_all_rest.txt                     其余函数注解
scanned_func_strings.txt                   函数→字符串 扫描（辅助）
libversion-info.so / disasm / strings / dynsym
annotate.py  find_ref.py  find_ref2.py  verify_slp.py          分析脚本
verify_slp_output.txt                      §5 复算输出
collect_callers.sh / collect_evidence2.sh  证据收集脚本
callers/
  di-camera-app 依赖级 dynsym?              （见 dica_*.txt 切片）
  dica_UI_Check_Body_Fw_Available.txt      E1 反汇编切片 + fw_validate@0x1089cc(flag0)
  dica_UI_Start_Body_Fw_Upgrade_and_cb.txt E2/E3 反汇编切片 + fw_validate@0x1092d4(flag1)
  dica_flash_idle_cb.txt                   实刷回调续接
  apsetting_checkSdcardFirmwareAvailable.txt  E8 反汇编切片
  dfmsd_fw_validate_upgrade.txt            E4 反汇编切片
  libshell-command.so（+ disasm/strings/dynsym）
  lsc_shell_firmware_cmdhandlers.txt       E5 反汇编切片（st firmware）
  fw_upgrade_start / fw_upgrade / fw_upgrade_recovery（+ disasm/strings/dynsym）
```

---

*生成：2026-10-08 · 全程离线（只读 rootfs 与官方固件），未触碰真机。地址/偏移均来自本轮实际反汇编与实测，未凭记忆填写。*
