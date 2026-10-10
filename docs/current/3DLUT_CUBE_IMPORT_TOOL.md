# 3D LUT .cube 导入工具（`nx3dlut.py`）

> 更新：2026-10-08 · 工具：`test_server/isp/nx3dlut.py`（约 720 行，纯标准库）
> 依据：表格式来自 [`3DLUT_TABLE_FORMAT_2026-10-08.md`](3DLUT_TABLE_FORMAT_2026-10-08.md)（已多表自证）
> 纪律：**只产文件，不碰相机**。`patch` 产物一律视同 `DO-NOT-FLASH`，除非另行验收。

---

## 0. 一句话

把标准 Adobe `.cube`（任意 N³ 或 1D 曲线）**按硬件真实采样格点**重采样成 NX500 原生
17³×4B 表；也能反向导出、预览、并按 VA 打进 `p7_full.bin` 的**副本**里。

---

## 1. 目标表格式速查（写死，不再从零推）

| 项 | 值 |
|---|---|
| 表长 | `4913 × 4B = 19652 B`，项 = `{R, G, B, pad=0}` |
| 索引 | `((B*17 + G)*17 + R) * 4` —— **R 变化最快** |
| 槽步长 | `0x4D00 = 19712`（表 19652 + 填充 60B） |
| 尾部填充 | 末项×3（12B）+ 48×`0x00` |
| 采样格点 | **非均匀**：level i ↔ 8-bit `G_i = min(i*16, 255)` ⇒ `{0,16,…,240,255}` |

> ★ 格点非均匀是本工具与旧工具（`filmsim/cube2nx17.py`）的**根本差别**。
> 旧工具产 `29478B`（`4913×6`，u16×3）—— 那是**被否掉的格式**；本工具仍能读入并自动降转。

---

## 2. 命令速查

```bash
PY="C:/Users/31623/.workbuddy/binaries/python/versions/3.13.12/python.exe"   # 或 E:/nxks2-re/Scripts/python.exe

# —— 导入（核心）——
python test_server/isp/nx3dlut.py import  in.cube [out.bin] [--slot] [--order auto|rgb|…] [--verify ref.bin]

# —— 导出 / 构造 ——
python test_server/isp/nx3dlut.py export  in.bin  out.cube [--n 17|33] [--title T]
python test_server/isp/nx3dlut.py identity out.bin [--slot]

# —— 查看 / 目视 ——
python test_server/isp/nx3dlut.py info    in.{cube,bin}
python test_server/isp/nx3dlut.py preview in.{cube,bin} out.ppm [--n 33]

# —— 打进 p7 副本（干跑，产物 DO-NOT-FLASH）——
python test_server/isp/nx3dlut.py patch   in.{cube,bin} p7_full.bin out.bin --va 0x80897BC0

# —— 回归 ——
python test_server/isp/nx3dlut.py selftest
```

| 命令 | 输入 | 输出 | 说明 |
|---|---|---|---|
| `import` | `.cube`（3D 或 1D） | `19652 B` 或 `19712 B`（`--slot`） | 主入口；`--verify` 给对照表算最大偏差 |
| `export` | 原生 `.bin` | `.cube`（默认 17³） | 非均匀格点→均匀格点重采样 |
| `identity` | — | 原生 identity | 灌进去画面**不变**（用于验证线路通不通） |
| `info` | `.cube` / `.bin` | stdout | 3D 报轴序/角点；1D 报三条曲线；`.bin` 报三轴 ramp + 对角 + 与 identity 偏差 |
| `preview` | `.cube` / `.bin` | `256×256 PPM` | 上半灰阶楔 + 下半 RG 色平面；目视验收色偏 |
| `patch` | `.cube` / `.bin` + `p7_full.bin` | patched p7 副本 | 按 VA 覆盖一槽；**先校验该处是合法槽**（pad 全 0）否则拒写 |
| `selftest` | 内置 84 表 | stdout | T1–T6，0 失败为绿 |

---

## 3. 三处关键设计决策

### 3.1 必须按硬件格点采样（否则 level15 错一格）

硬件 level 15 对应输入 **240**（不是均匀格的 239）。工具对 `.cube` 做三线性插值时，
取样位置固定用 `hw_grid_f() = {0,16,…,240,255}/255`。

- 自测 **T2 负对照**：若改用均匀格点 `i*255/16`，最大偏差 = 1，且 `level15: 239 vs 240` ⇒ 判据有效。
- 实证 **T3**：84 个内置表中 `level15==240` 有 **21** 个，`==239` **0** 个。

### 3.2 轴序自动纠正（本仓存在非规范 cube）

`.cube` 规范要求 **R 最快**（索引 `r + g*n + b*n²`）。仓内
`test_server/filmsim/_luttest/identity33.cube` 实为 **B 最快（`bgr`）**，按规范读会得到全零。

工具默认 `--order auto`：对 6 种轴序排列算「可分离性打分」（通道 c 应只依赖第 c 轴），取最低者；
判错时用 `--order rgb|rbg|grb|…` 强制。实测纠正后与构造身份表**字节级一致（偏差 0）**。

### 3.3 只产文件 + 槽合法性双保险

`patch` 打开 `p7_full.bin` 后先检查目标 VA 处 **4913 个 pad 字节是否全 0**，
不是合法槽就拒绝覆盖；`import --slot` 的输出自动补 `末项×3 + 48×0` 尾部指纹。

---

## 4. 工作流

```
  .cube  ──import──►  19652B 原生表  ──patch --va <槽VA>──►  p7 副本
     ▲                    │                                    │
     │                    └────export────► .cube（往返/校验）    └─► 上机验收后才有意义
     └── filmsim 产出的 .cube（Kodak Portra 400 等）
```

- **离线**：`import` → `info`/`preview` 看得住色偏；`export` 往返偏差量化格式正确性。
- **上机**：拿 Block A/B 内置表当模板（见表格式文档 §3），选空槽 VA 用 `patch` 造副本，
  走**线路 E**（`3DLUT_APPLY_PATHS_2026-10-08.md`）灌入验证。
- 现成输入：`test_server/filmsim/luts/Kodak Portra 400.cube`（33³ 规范）。

---

## 5. 自测清单（`selftest`）

| 项 | 内容 | 通过判据 | 现状 |
|---|---|---|---|
| T1 | `identity cube(17/33/65) → 原生` | 偏差 = 0 | ✅ 0/0/0 |
| T2 | 负对照：均匀格点必须失败 | 偏差 ≥ 1 且落在 level15 | ✅ 1（239 vs 240）|
| T3 | 内置表 level15 落点 | `==240 ≥4` 且 `==239 ==0` | ✅ 21 / 0 |
| T4 | 索引顺序角落断言 | R/G/B 角映射正确 | ✅ |
| T5 | 槽长 19712 + tail 指纹 | 末项×3(12B)+48×0 | ✅ |
| T6 | 84 内置表 `export→import` 往返 | 单调族 ≤4 | ✅ 单调族 42 表 min1 中位1 max2 |

> T6 里**非单调族 42 表**（疑 `+0x400` 移位伪读）偏差 min15 max38 —— 这是**抽取侧**的问题，
> 不是本工具逻辑错误；已在表格式文档记录为待查项。

---

## 6. 已知限制 / 遗留

1. **`patch` 只对槽区域负责**，不判断该 VA 属于 Block A/B 还是散点区；错 VA 会拒写但不报"这槽是谁"。
2. **1D cube** 会展开成逐通道曲线再采样（数学上 = 逐通道线性插值），**不做** 3D 交叉项。
3. `export` 从非均匀格点重采样到均匀格点会有 ≤1 量化损失（T6 已量化），**不是**往返无损。
4. 工具**不接触相机**：无 telnet/FTP/EP 调用；上机注入由 `cam.py` / 线路 E 另行完成。
5. 尚未接 `DOMAIN_MIN/MAX` 之外的非标准头（如 `LUT_3D_INPUT_RANGE`），遇到会忽略并继续。

---

## 7. 相关文件

| 路径 | 内容 |
|---|---|
| `test_server/isp/nx3dlut.py` | 本工具 |
| `docs/current/3DLUT_TABLE_FORMAT_2026-10-08.md` | 表格式与表池（本工具的依据）|
| `docs/current/3DLUT_APPLY_PATHS_2026-10-08.md` | 5 条线路 + 寄存器语义（上机灌表用）|
| `docs/current/3DLUT_VIEW_STILL_ISOLATION_2026-10-08.md` | View/Still 隔离性 + save_lut dump 通道 |
| `raw8/p7/lut_format/tab_*.bin` | 84 个内置表抽取产物（19652B 各）|
| `test_server/filmsim/cube2nx17.py` | 旧工具（产 29478B 被否格式），仅供对照 |
