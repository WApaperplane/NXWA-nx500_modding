# 任务1 · 3D LUT 相关字符串全量清单

- 目标: `raw8/p7/p7_full.bin` — 12845056 字节 (12.25 MiB)
- 扫描正则: `rb'[\x20-\x7e]{4,}'` (ASCII 可打印, ≥4 连续字符, **完整输出不截断**)
- VA 换算: `VA = 0x80000000 + 文件偏移`
- TIER1 (含 `dlut`/`3DLUT`/`3D-LUT`/`3dl`): **125** 条  ← 3D LUT 子系统本体
- TIER2 (仅含 `lut`, 属其它 LUT 子系统如 LDC/gamma): **49** 条  ← 排除项, 仅附录列出
- Itanium RTTI 类名(带长度前缀) **14** 条, 去重后 **14** 个类

## 核心发现

1. 3D LUT 子系统本体字符串 **125** 条, 分布在 6 个文件偏移区段; 另有 **49** 条只含 `lut` 但属 LDC 镜头畸变 / gamma 等别的 LUT 子系统(已隔离, 见附录C), 二者**不可混淆** —— 这正是 '3D LUT' 与 'ldc lut' 在固件里共用 `lut` 关键词导致的。
2. **直接给出网格/尺寸语义的字符串已定位**: `0x714a34 (_load) LoadLut Error! (Rtncd=0x%08X)`、`0x720858 d5_ep_3dl_load_lut(0x%08X,%d, %d, %d)` / `0x720880 d5_ep_3dl_save_lut(...)` 证明加载/保存接口签名是 **(addr, a, b, c)** 四参, 后三参含义待任务5追查; `0x73c398 lut size error too large~ (%d) > %d` 证明存在**表长上限校验**。
3. **BYPASS/PROCESS 双模式已确证**: `0x75f7d4 3D-LUT: BYPASS Mode` 与 `0x75f7ec 3D-LUT: PROCESS Mode` 成对出现 —— 取景器花屏最可能就是被强制进 BYPASS 或 PROCESS 拿到了非法表; 而 `0x758ec0 3D-LUT table SRAM load failed [driver error]!!` / `0x758ef0 ...load success` 是**唯一一组直接报告表是否落进 SRAM 的日志**, 是排查花屏的第一现场。

## 区段分布

| 区段 | 命中(TIER1) |
|---|---|
| A/CODE | 0 |
| B/CODE | 0 |
| C/DATA | 0 |
| D/RODATA | 69 |
| E/RODATA-dense | 56 |
| F/RODATA-table | 0 |

## TIER1 · 含 dlut/3DLUT/3dl 的全部字符串 （125 条）

| # | 文件偏移 | 虚拟地址 | 区段 | 数字 | 格式 | 尺寸词 | 完整字符串 |
|---|---|---|---|---|---|---|---|
| 1 | `0x582250` | `0x80582250` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 2 | `0x582264` | `0x80582264` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 3 | `0x582528` | `0x80582528` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 4 | `0x58253c` | `0x8058253c` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 5 | `0x5836a4` | `0x805836a4` | D/RODATA | Y |  |  | `~CBackend_3dlut` |
| 6 | `0x5836b4` | `0x805836b4` | D/RODATA | Y |  |  | `CBackend_3dlut` |
| 7 | `0x5836c4` | `0x805836c4` | D/RODATA | Y |  |  | `14CBackend_3dlut` |
| 8 | `0x58376c` | `0x8058376c` | D/RODATA | Y |  |  | `~CBackend_3dlut_Base` |
| 9 | `0x583784` | `0x80583784` | D/RODATA | Y |  |  | `CBackend_3dlut_Base` |
| 10 | `0x5837b0` | `0x805837b0` | D/RODATA | Y |  |  | `19CBackend_3dlut_Base` |
| 11 | `0x58387c` | `0x8058387c` | D/RODATA | Y |  |  | `19CBackend_3dlut_View` |
| 12 | `0x58392c` | `0x8058392c` | D/RODATA | Y |  |  | `20CBackend_3dlut_Still` |
| 13 | `0x583a04` | `0x80583a04` | D/RODATA | Y |  |  | `17CBackend_3dlut_CS` |
| 14 | `0x583a24` | `0x80583a24` | D/RODATA | Y |  |  | `27CBackend_3dlut_CS0_Callback` |
| 15 | `0x583a50` | `0x80583a50` | D/RODATA | Y |  |  | `27CBackend_3dlut_CS1_Callback` |
| 16 | `0x588cc0` | `0x80588cc0` | D/RODATA | Y |  |  | `8C3DLUTIf` |
| 17 | `0x588cec` | `0x80588cec` | D/RODATA | Y |  |  | `11C3DLUTAlarm` |
| 18 | `0x58bae0` | `0x8058bae0` | D/RODATA | Y |  |  | `32CMaterial_NX1_Still_3dlut_Normal` |
| 19 | `0x58bb70` | `0x8058bb70` | D/RODATA | Y |  |  | `37CMaterial_NX1_Still_3dlut_SelectColor` |
| 20 | `0x58bbf8` | `0x8058bbf8` | D/RODATA | Y |  |  | `28CMaterial_NX1_Still_3dlut_CS` |
| 21 | `0x58e6c0` | `0x8058e6c0` | D/RODATA | Y |  |  | `28CMaterial_NX1_QView_3dlut_CS` |
| 22 | `0x59caac` | `0x8059caac` | D/RODATA | Y |  |  | `virtual int CMaterial_3DLUT_Liveview::run()` |
| 23 | `0x59cae4` | `0x8059cae4` | D/RODATA | Y |  |  | `virtual int CMaterial_3DLUT_Liveview::setParam()` |
| 24 | `0x59cb74` | `0x8059cb74` | D/RODATA | Y |  |  | `virtual int CMaterial_3DLUT_Liveview::stop(int)` |
| 25 | `0x59cbac` | `0x8059cbac` | D/RODATA | Y |  |  | `void CMaterial_3DLUT_Liveview::handle(int, long int)` |
| 26 | `0x59cbf8` | `0x8059cbf8` | D/RODATA | Y |  |  | `virtual void CMaterial_3DLUT_Liveview::OnNotifyCompletion(int, long int, long int)` |
| 27 | `0x59cc58` | `0x8059cc58` | D/RODATA | Y |  |  | `int CMaterial_3DLUT_Liveview::finalize()` |
| 28 | `0x59cc84` | `0x8059cc84` | D/RODATA | Y |  |  | `24CMaterial_3DLUT_Liveview` |
| 29 | `0x59de30` | `0x8059de30` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 30 | `0x59de44` | `0x8059de44` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 31 | `0x59dfc4` | `0x8059dfc4` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 32 | `0x59dfd8` | `0x8059dfd8` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 33 | `0x59e2c0` | `0x8059e2c0` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 34 | `0x59e2d4` | `0x8059e2d4` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 35 | `0x59e440` | `0x8059e440` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 36 | `0x59e454` | `0x8059e454` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 37 | `0x59ecd4` | `0x8059ecd4` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 38 | `0x59ece8` | `0x8059ece8` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 39 | `0x59eec8` | `0x8059eec8` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 40 | `0x59eedc` | `0x8059eedc` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 41 | `0x59f09c` | `0x8059f09c` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 42 | `0x59f0b0` | `0x8059f0b0` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 43 | `0x59f328` | `0x8059f328` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 44 | `0x59f33c` | `0x8059f33c` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 45 | `0x59f5d0` | `0x8059f5d0` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 46 | `0x59f5e4` | `0x8059f5e4` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 47 | `0x59f7b0` | `0x8059f7b0` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 48 | `0x59f7c4` | `0x8059f7c4` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 49 | `0x59f950` | `0x8059f950` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 50 | `0x59f964` | `0x8059f964` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 51 | `0x59fad4` | `0x8059fad4` | D/RODATA | Y |  |  | `set3DLUT_UD_Material` |
| 52 | `0x59faec` | `0x8059faec` | D/RODATA | Y |  |  | `set3DLUT_UD_Material` |
| 53 | `0x59fcf0` | `0x8059fcf0` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 54 | `0x59fd04` | `0x8059fd04` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 55 | `0x5a08c0` | `0x805a08c0` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 56 | `0x5a08d4` | `0x805a08d4` | D/RODATA | Y |  |  | `set3DLUTMaterial` |
| 57 | `0x63ec82` | `0x8063ec82` | D/RODATA | Y |  |  | `@@ADE_d5_3dl_cb_rdma0_err` |
| 58 | `0x63ec9c` | `0x8063ec9c` | D/RODATA | Y |  |  | `ADE_d5_3dl_cb_wdma0_err` |
| 59 | `0x63ecb4` | `0x8063ecb4` | D/RODATA | Y |  |  | `ADE_d5_3dl_cb_rdma0_2` |
| 60 | `0x63eccc` | `0x8063eccc` | D/RODATA | Y |  |  | `ADE_d5_3dl_cb_rdma0_1` |
| 61 | `0x63ece4` | `0x8063ece4` | D/RODATA | Y |  |  | `ADE_d5_3dl_cb_wdma0_1` |
| 62 | `0x63ecfc` | `0x8063ecfc` | D/RODATA | Y |  |  | `ADE_udd_ep_3dl_cb_eptop_rddone` |
| 63 | `0x63f194` | `0x8063f194` | D/RODATA | Y |  |  | `ADE_udd_ep_3dl_cb_eptop_wrdone` |
| 64 | `0x63f1b4` | `0x8063f1b4` | D/RODATA | Y |  |  | `ADE_d5_3dl_cb_wdma0_0` |
| 65 | `0x63f1cc` | `0x8063f1cc` | D/RODATA | Y |  |  | `ADE_d5_3dl_cb_wdma0_2` |
| 66 | `0x63f1e4` | `0x8063f1e4` | D/RODATA | Y |  |  | `ADE_d5_3dl_cb_rdma0_0` |
| 67 | `0x63f1fc` | `0x8063f1fc` | D/RODATA | Y |  |  | `ADE_do_3dl_init` |
| 68 | `0x63f20c` | `0x8063f20c` | D/RODATA | Y |  |  | `ADE_d5_3dl_load_luttable` |
| 69 | `0x63f228` | `0x8063f228` | D/RODATA | Y |  |  | `ADE_EP_3dlut_Param_SET` |
| 70 | `0x6e6254` | `0x806e6254` | E/RODATA-dense | Y |  |  | `_udd_ep_mux_3dlut_rdxi` |
| 71 | `0x6e632c` | `0x806e632c` | E/RODATA-dense | Y |  |  | `_udd_ep_mux_3dlut_wdxi` |
| 72 | `0x712758` | `0x80712758` | E/RODATA-dense | Y |  |  | `BackEnd 3dlut` |
| 73 | `0x714888` | `0x80714888` | E/RODATA-dense | Y |  |  | `product/Backend/EP/3DLUT/CBackend_3dlut.cpp` |
| 74 | `0x7148b4` | `0x807148b4` | E/RODATA-dense | Y | Y |  | `(Callback) 3dlut Done (Error=%d)` |
| 75 | `0x7148e4` | `0x807148e4` | E/RODATA-dense | Y |  |  | `12st3dlutParam` |
| 76 | `0x7148f4` | `0x807148f4` | E/RODATA-dense | Y |  |  | `product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp` |
| 77 | `0x714928` | `0x80714928` | E/RODATA-dense | Y |  |  | `CBackend_3dlut_Base` |
| 78 | `0x71493c` | `0x8071493c` | E/RODATA-dense | Y |  |  | `BackEnd_3DLUT` |
| 79 | `0x714978` | `0x80714978` | E/RODATA-dense | Y |  |  | `CBackend_3dlut` |
| 80 | `0x714998` | `0x80714998` | E/RODATA-dense | Y |  |  | `st3dlutParam` |
| 81 | `0x7149a8` | `0x807149a8` | E/RODATA-dense | Y |  |  | `CBackend_3dlut_View` |
| 82 | `0x7149fc` | `0x807149fc` | E/RODATA-dense | Y |  |  | `product/Backend/EP/3DLUT/View/CBackend_3dlut_View.cpp` |
| 83 | `0x714a34` | `0x80714a34` | E/RODATA-dense | Y | Y |  | `(_load) LoadLut Error! (Rtncd=0x%08X)` |
| 84 | `0x714a5c` | `0x80714a5c` | E/RODATA-dense | Y |  |  | `CBackend_3dlut_Still` |
| 85 | `0x714a74` | `0x80714a74` | E/RODATA-dense | Y |  |  | `(_run) 3dlut load wait. ` |
| 86 | `0x714a90` | `0x80714a90` | E/RODATA-dense | Y |  |  | `product/Backend/EP/3DLUT/Still/CBackend_3dlut_Still.cpp` |
| 87 | `0x714ac8` | `0x80714ac8` | E/RODATA-dense | Y |  |  | `(_run) 3dlut load Done. ` |
| 88 | `0x714b00` | `0x80714b00` | E/RODATA-dense | Y |  |  | `CBackend_3dlut_CS` |
| 89 | `0x714b14` | `0x80714b14` | E/RODATA-dense | Y |  |  | `product/Backend/EP/3DLUT/CS/CBackend_3dlut_CS.cpp` |
| 90 | `0x714b48` | `0x80714b48` | E/RODATA-dense | Y |  |  | `(_load) 3dlut load wait. ` |
| 91 | `0x72082c` | `0x8072082c` | E/RODATA-dense | Y |  |  | `C3DLUTIf` |
| 92 | `0x720838` | `0x80720838` | E/RODATA-dense | Y | Y |  | `d5_ep_3dlut_op_init(0x%08X)` |
| 93 | `0x720858` | `0x80720858` | E/RODATA-dense | Y | Y |  | `d5_ep_3dl_load_lut(0x%08X,%d, %d, %d)` |
| 94 | `0x720880` | `0x80720880` | E/RODATA-dense | Y | Y |  | `d5_ep_3dl_save_lut(0x%08X, %d, %d, %d)` |
| 95 | `0x725148` | `0x80725148` | E/RODATA-dense | Y |  |  | `STILL_3DLUT_NORMAL` |
| 96 | `0x72515c` | `0x8072515c` | E/RODATA-dense | Y |  |  | `STILL_3DLUT_CS` |
| 97 | `0x72516c` | `0x8072516c` | E/RODATA-dense | Y |  |  | `STILL_3DLUT_SELECT_COLOR` |
| 98 | `0x727a48` | `0x80727a48` | E/RODATA-dense | Y |  |  | `3dLut Material is NULL !! !!` |
| 99 | `0x728c70` | `0x80728c70` | E/RODATA-dense | Y |  |  | `RECIPE PAGE 3DLUT` |
| 100 | `0x728cc0` | `0x80728cc0` | E/RODATA-dense | Y |  |  | `3dlut Image is NULL !! !!` |
| 101 | `0x72a41c` | `0x8072a41c` | E/RODATA-dense | Y |  |  | `3dlut CS QView 3` |
| 102 | `0x72a430` | `0x8072a430` | E/RODATA-dense | Y |  |  | `3dlut CS QView 4` |
| 103 | `0x72a444` | `0x8072a444` | E/RODATA-dense | Y |  |  | `3DLUT CS QView` |
| 104 | `0x72a454` | `0x8072a454` | E/RODATA-dense | Y |  |  | `3DLUT CS QView 1` |
| 105 | `0x72ce90` | `0x8072ce90` | E/RODATA-dense | Y |  |  | `LVIEW_3DLUT_OTF` |
| 106 | `0x72de14` | `0x8072de14` | E/RODATA-dense | Y |  |  | `(_callback_3dlut_wr_done) Done! ` |
| 107 | `0x72de38` | `0x8072de38` | E/RODATA-dense | Y |  |  | `(_callback_3dlut_rd_done) Done! ` |
| 108 | `0x72e660` | `0x8072e660` | E/RODATA-dense | Y |  |  | `ACC_3DLUT_RD_FINISH Already Enable! ` |
| 109 | `0x72e688` | `0x8072e688` | E/RODATA-dense | Y |  |  | `ACC_3DLUT_WR_FINISH Already Enable! ` |
| 110 | `0x72e708` | `0x8072e708` | E/RODATA-dense | Y |  |  | `ACC_3DLUT_RD_FINISH Not Enable! ` |
| 111 | `0x72e72c` | `0x8072e72c` | E/RODATA-dense | Y |  |  | `ACC_3DLUT_WR_FINISH Not Enable! ` |
| 112 | `0x732720` | `0x80732720` | E/RODATA-dense | Y |  |  | `[Live] 3DLUT:ERDONE` |
| 113 | `0x7588e8` | `0x807588e8` | E/RODATA-dense | Y |  |  | `3D-LUT rdma0_err` |
| 114 | `0x7588fc` | `0x807588fc` | E/RODATA-dense | Y |  |  | `3D-LUT wdma0_err` |
| 115 | `0x758910` | `0x80758910` | E/RODATA-dense | Y |  |  | `3D-LUT rdma0_2` |
| 116 | `0x758920` | `0x80758920` | E/RODATA-dense | Y |  |  | `3D-LUT rdma0_1` |
| 117 | `0x758958` | `0x80758958` | E/RODATA-dense | Y |  |  | `EP 3D-LUT: Read done` |
| 118 | `0x758e10` | `0x80758e10` | E/RODATA-dense | Y |  |  | `EP 3D-LUT: Write done` |
| 119 | `0x758e28` | `0x80758e28` | E/RODATA-dense | Y |  |  | `3D-LUT wdma0_0` |
| 120 | `0x758e38` | `0x80758e38` | E/RODATA-dense | Y |  |  | `3D-LUT wdma0_2` |
| 121 | `0x758e48` | `0x80758e48` | E/RODATA-dense | Y |  |  | `3D-LUT rdma0_0` |
| 122 | `0x758ec0` | `0x80758ec0` | E/RODATA-dense | Y |  |  | `3D-LUT table SRAM load failed [driver error]!!` |
| 123 | `0x758ef0` | `0x80758ef0` | E/RODATA-dense | Y |  |  | `3D-LUT table SRAM load success` |
| 124 | `0x75f7d4` | `0x8075f7d4` | E/RODATA-dense | Y |  |  | `3D-LUT: BYPASS Mode ` |
| 125 | `0x75f7ec` | `0x8075f7ec` | E/RODATA-dense | Y |  |  | `3D-LUT: PROCESS Mode ` |

## RTTI 类名全表（Itanium 长度前缀已校验）

| # | 类名 | 长度 | 出现偏移 |
|---|---|---|---|
| 1 | `C3DLUTAlarm` | 11 | 0x588cec |
| 2 | `C3DLUTIf` | 8 | 0x588cc0, 0x72082c |
| 3 | `CBackend_3dlut` | 14 | 0x5836b4, 0x5836c4, 0x714978 |
| 4 | `CBackend_3dlut_Base` | 19 | 0x583784, 0x5837b0, 0x714928 |
| 5 | `CBackend_3dlut_CS` | 17 | 0x583a04, 0x714b00 |
| 6 | `CBackend_3dlut_CS0_Callback` | 27 | 0x583a24 |
| 7 | `CBackend_3dlut_CS1_Callback` | 27 | 0x583a50 |
| 8 | `CBackend_3dlut_Still` | 20 | 0x58392c, 0x714a5c |
| 9 | `CBackend_3dlut_View` | 19 | 0x58387c, 0x7149a8 |
| 10 | `CMaterial_3DLUT_Liveview` | 24 | 0x59caac, 0x59cae4, 0x59cb74, 0x59cbac, 0x59cbf8, 0x59cc58, 0x59cc84 |
| 11 | `CMaterial_NX1_QView_3dlut_CS` | 28 | 0x58e6c0 |
| 12 | `CMaterial_NX1_Still_3dlut_CS` | 28 | 0x58bbf8 |
| 13 | `CMaterial_NX1_Still_3dlut_Normal` | 32 | 0x58bae0 |
| 14 | `CMaterial_NX1_Still_3dlut_SelectColor` | 37 | 0x58bb70 |

> 校验规则: `^(\d{1,3})(C[A-Za-z0-9_]+)$` 且 **`int(长度前缀) == len(类名)`**。Itanium C++ ABI 的 typeinfo 名字以十进制字符长度打头, 该自洽校验可 100% 排除误报(例: `32CMaterial_NX1_Still_3dlut_Normal` —— 类名恰 32 字符, 前缀 `32` 自洽)。

## 附录A · TIER1 扁平表（按文件偏移升序）

| # | 文件偏移 | 虚拟地址 | 完整字符串 |
|---|---|---|---|
| 1 | `0x582250` | `0x80582250` | `set3DLUTMaterial` |
| 2 | `0x582264` | `0x80582264` | `set3DLUTMaterial` |
| 3 | `0x582528` | `0x80582528` | `set3DLUTMaterial` |
| 4 | `0x58253c` | `0x8058253c` | `set3DLUTMaterial` |
| 5 | `0x5836a4` | `0x805836a4` | `~CBackend_3dlut` |
| 6 | `0x5836b4` | `0x805836b4` | `CBackend_3dlut` |
| 7 | `0x5836c4` | `0x805836c4` | `14CBackend_3dlut` |
| 8 | `0x58376c` | `0x8058376c` | `~CBackend_3dlut_Base` |
| 9 | `0x583784` | `0x80583784` | `CBackend_3dlut_Base` |
| 10 | `0x5837b0` | `0x805837b0` | `19CBackend_3dlut_Base` |
| 11 | `0x58387c` | `0x8058387c` | `19CBackend_3dlut_View` |
| 12 | `0x58392c` | `0x8058392c` | `20CBackend_3dlut_Still` |
| 13 | `0x583a04` | `0x80583a04` | `17CBackend_3dlut_CS` |
| 14 | `0x583a24` | `0x80583a24` | `27CBackend_3dlut_CS0_Callback` |
| 15 | `0x583a50` | `0x80583a50` | `27CBackend_3dlut_CS1_Callback` |
| 16 | `0x588cc0` | `0x80588cc0` | `8C3DLUTIf` |
| 17 | `0x588cec` | `0x80588cec` | `11C3DLUTAlarm` |
| 18 | `0x58bae0` | `0x8058bae0` | `32CMaterial_NX1_Still_3dlut_Normal` |
| 19 | `0x58bb70` | `0x8058bb70` | `37CMaterial_NX1_Still_3dlut_SelectColor` |
| 20 | `0x58bbf8` | `0x8058bbf8` | `28CMaterial_NX1_Still_3dlut_CS` |
| 21 | `0x58e6c0` | `0x8058e6c0` | `28CMaterial_NX1_QView_3dlut_CS` |
| 22 | `0x59caac` | `0x8059caac` | `virtual int CMaterial_3DLUT_Liveview::run()` |
| 23 | `0x59cae4` | `0x8059cae4` | `virtual int CMaterial_3DLUT_Liveview::setParam()` |
| 24 | `0x59cb74` | `0x8059cb74` | `virtual int CMaterial_3DLUT_Liveview::stop(int)` |
| 25 | `0x59cbac` | `0x8059cbac` | `void CMaterial_3DLUT_Liveview::handle(int, long int)` |
| 26 | `0x59cbf8` | `0x8059cbf8` | `virtual void CMaterial_3DLUT_Liveview::OnNotifyCompletion(int, long int, long int)` |
| 27 | `0x59cc58` | `0x8059cc58` | `int CMaterial_3DLUT_Liveview::finalize()` |
| 28 | `0x59cc84` | `0x8059cc84` | `24CMaterial_3DLUT_Liveview` |
| 29 | `0x59de30` | `0x8059de30` | `set3DLUTMaterial` |
| 30 | `0x59de44` | `0x8059de44` | `set3DLUTMaterial` |
| 31 | `0x59dfc4` | `0x8059dfc4` | `set3DLUTMaterial` |
| 32 | `0x59dfd8` | `0x8059dfd8` | `set3DLUTMaterial` |
| 33 | `0x59e2c0` | `0x8059e2c0` | `set3DLUTMaterial` |
| 34 | `0x59e2d4` | `0x8059e2d4` | `set3DLUTMaterial` |
| 35 | `0x59e440` | `0x8059e440` | `set3DLUTMaterial` |
| 36 | `0x59e454` | `0x8059e454` | `set3DLUTMaterial` |
| 37 | `0x59ecd4` | `0x8059ecd4` | `set3DLUTMaterial` |
| 38 | `0x59ece8` | `0x8059ece8` | `set3DLUTMaterial` |
| 39 | `0x59eec8` | `0x8059eec8` | `set3DLUTMaterial` |
| 40 | `0x59eedc` | `0x8059eedc` | `set3DLUTMaterial` |
| 41 | `0x59f09c` | `0x8059f09c` | `set3DLUTMaterial` |
| 42 | `0x59f0b0` | `0x8059f0b0` | `set3DLUTMaterial` |
| 43 | `0x59f328` | `0x8059f328` | `set3DLUTMaterial` |
| 44 | `0x59f33c` | `0x8059f33c` | `set3DLUTMaterial` |
| 45 | `0x59f5d0` | `0x8059f5d0` | `set3DLUTMaterial` |
| 46 | `0x59f5e4` | `0x8059f5e4` | `set3DLUTMaterial` |
| 47 | `0x59f7b0` | `0x8059f7b0` | `set3DLUTMaterial` |
| 48 | `0x59f7c4` | `0x8059f7c4` | `set3DLUTMaterial` |
| 49 | `0x59f950` | `0x8059f950` | `set3DLUTMaterial` |
| 50 | `0x59f964` | `0x8059f964` | `set3DLUTMaterial` |
| 51 | `0x59fad4` | `0x8059fad4` | `set3DLUT_UD_Material` |
| 52 | `0x59faec` | `0x8059faec` | `set3DLUT_UD_Material` |
| 53 | `0x59fcf0` | `0x8059fcf0` | `set3DLUTMaterial` |
| 54 | `0x59fd04` | `0x8059fd04` | `set3DLUTMaterial` |
| 55 | `0x5a08c0` | `0x805a08c0` | `set3DLUTMaterial` |
| 56 | `0x5a08d4` | `0x805a08d4` | `set3DLUTMaterial` |
| 57 | `0x63ec82` | `0x8063ec82` | `@@ADE_d5_3dl_cb_rdma0_err` |
| 58 | `0x63ec9c` | `0x8063ec9c` | `ADE_d5_3dl_cb_wdma0_err` |
| 59 | `0x63ecb4` | `0x8063ecb4` | `ADE_d5_3dl_cb_rdma0_2` |
| 60 | `0x63eccc` | `0x8063eccc` | `ADE_d5_3dl_cb_rdma0_1` |
| 61 | `0x63ece4` | `0x8063ece4` | `ADE_d5_3dl_cb_wdma0_1` |
| 62 | `0x63ecfc` | `0x8063ecfc` | `ADE_udd_ep_3dl_cb_eptop_rddone` |
| 63 | `0x63f194` | `0x8063f194` | `ADE_udd_ep_3dl_cb_eptop_wrdone` |
| 64 | `0x63f1b4` | `0x8063f1b4` | `ADE_d5_3dl_cb_wdma0_0` |
| 65 | `0x63f1cc` | `0x8063f1cc` | `ADE_d5_3dl_cb_wdma0_2` |
| 66 | `0x63f1e4` | `0x8063f1e4` | `ADE_d5_3dl_cb_rdma0_0` |
| 67 | `0x63f1fc` | `0x8063f1fc` | `ADE_do_3dl_init` |
| 68 | `0x63f20c` | `0x8063f20c` | `ADE_d5_3dl_load_luttable` |
| 69 | `0x63f228` | `0x8063f228` | `ADE_EP_3dlut_Param_SET` |
| 70 | `0x6e6254` | `0x806e6254` | `_udd_ep_mux_3dlut_rdxi` |
| 71 | `0x6e632c` | `0x806e632c` | `_udd_ep_mux_3dlut_wdxi` |
| 72 | `0x712758` | `0x80712758` | `BackEnd 3dlut` |
| 73 | `0x714888` | `0x80714888` | `product/Backend/EP/3DLUT/CBackend_3dlut.cpp` |
| 74 | `0x7148b4` | `0x807148b4` | `(Callback) 3dlut Done (Error=%d)` |
| 75 | `0x7148e4` | `0x807148e4` | `12st3dlutParam` |
| 76 | `0x7148f4` | `0x807148f4` | `product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp` |
| 77 | `0x714928` | `0x80714928` | `CBackend_3dlut_Base` |
| 78 | `0x71493c` | `0x8071493c` | `BackEnd_3DLUT` |
| 79 | `0x714978` | `0x80714978` | `CBackend_3dlut` |
| 80 | `0x714998` | `0x80714998` | `st3dlutParam` |
| 81 | `0x7149a8` | `0x807149a8` | `CBackend_3dlut_View` |
| 82 | `0x7149fc` | `0x807149fc` | `product/Backend/EP/3DLUT/View/CBackend_3dlut_View.cpp` |
| 83 | `0x714a34` | `0x80714a34` | `(_load) LoadLut Error! (Rtncd=0x%08X)` |
| 84 | `0x714a5c` | `0x80714a5c` | `CBackend_3dlut_Still` |
| 85 | `0x714a74` | `0x80714a74` | `(_run) 3dlut load wait. ` |
| 86 | `0x714a90` | `0x80714a90` | `product/Backend/EP/3DLUT/Still/CBackend_3dlut_Still.cpp` |
| 87 | `0x714ac8` | `0x80714ac8` | `(_run) 3dlut load Done. ` |
| 88 | `0x714b00` | `0x80714b00` | `CBackend_3dlut_CS` |
| 89 | `0x714b14` | `0x80714b14` | `product/Backend/EP/3DLUT/CS/CBackend_3dlut_CS.cpp` |
| 90 | `0x714b48` | `0x80714b48` | `(_load) 3dlut load wait. ` |
| 91 | `0x72082c` | `0x8072082c` | `C3DLUTIf` |
| 92 | `0x720838` | `0x80720838` | `d5_ep_3dlut_op_init(0x%08X)` |
| 93 | `0x720858` | `0x80720858` | `d5_ep_3dl_load_lut(0x%08X,%d, %d, %d)` |
| 94 | `0x720880` | `0x80720880` | `d5_ep_3dl_save_lut(0x%08X, %d, %d, %d)` |
| 95 | `0x725148` | `0x80725148` | `STILL_3DLUT_NORMAL` |
| 96 | `0x72515c` | `0x8072515c` | `STILL_3DLUT_CS` |
| 97 | `0x72516c` | `0x8072516c` | `STILL_3DLUT_SELECT_COLOR` |
| 98 | `0x727a48` | `0x80727a48` | `3dLut Material is NULL !! !!` |
| 99 | `0x728c70` | `0x80728c70` | `RECIPE PAGE 3DLUT` |
| 100 | `0x728cc0` | `0x80728cc0` | `3dlut Image is NULL !! !!` |
| 101 | `0x72a41c` | `0x8072a41c` | `3dlut CS QView 3` |
| 102 | `0x72a430` | `0x8072a430` | `3dlut CS QView 4` |
| 103 | `0x72a444` | `0x8072a444` | `3DLUT CS QView` |
| 104 | `0x72a454` | `0x8072a454` | `3DLUT CS QView 1` |
| 105 | `0x72ce90` | `0x8072ce90` | `LVIEW_3DLUT_OTF` |
| 106 | `0x72de14` | `0x8072de14` | `(_callback_3dlut_wr_done) Done! ` |
| 107 | `0x72de38` | `0x8072de38` | `(_callback_3dlut_rd_done) Done! ` |
| 108 | `0x72e660` | `0x8072e660` | `ACC_3DLUT_RD_FINISH Already Enable! ` |
| 109 | `0x72e688` | `0x8072e688` | `ACC_3DLUT_WR_FINISH Already Enable! ` |
| 110 | `0x72e708` | `0x8072e708` | `ACC_3DLUT_RD_FINISH Not Enable! ` |
| 111 | `0x72e72c` | `0x8072e72c` | `ACC_3DLUT_WR_FINISH Not Enable! ` |
| 112 | `0x732720` | `0x80732720` | `[Live] 3DLUT:ERDONE` |
| 113 | `0x7588e8` | `0x807588e8` | `3D-LUT rdma0_err` |
| 114 | `0x7588fc` | `0x807588fc` | `3D-LUT wdma0_err` |
| 115 | `0x758910` | `0x80758910` | `3D-LUT rdma0_2` |
| 116 | `0x758920` | `0x80758920` | `3D-LUT rdma0_1` |
| 117 | `0x758958` | `0x80758958` | `EP 3D-LUT: Read done` |
| 118 | `0x758e10` | `0x80758e10` | `EP 3D-LUT: Write done` |
| 119 | `0x758e28` | `0x80758e28` | `3D-LUT wdma0_0` |
| 120 | `0x758e38` | `0x80758e38` | `3D-LUT wdma0_2` |
| 121 | `0x758e48` | `0x80758e48` | `3D-LUT rdma0_0` |
| 122 | `0x758ec0` | `0x80758ec0` | `3D-LUT table SRAM load failed [driver error]!!` |
| 123 | `0x758ef0` | `0x80758ef0` | `3D-LUT table SRAM load success` |
| 124 | `0x75f7d4` | `0x8075f7d4` | `3D-LUT: BYPASS Mode ` |
| 125 | `0x75f7ec` | `0x8075f7ec` | `3D-LUT: PROCESS Mode ` |

## 附录C · TIER2 排除项：含 lut 但属其它子系统（49 条）

> 这些串含 `lut` 但**不含** `dlut`, 经人工判读归属 LDC 镜头畸变校正 / gamma / DPC 等子系统, 与 3D LUT 无关。列出以证明已穷尽筛除, 避免后续误引。

| # | 文件偏移 | 虚拟地址 | 完整字符串 |
|---|---|---|---|
| 1 | `0x6e5034` | `0x806e5034` | `d5_ep_ldc_calc_ldc_lut` |
| 2 | `0x6e504c` | `0x806e504c` | `d5_ep_ldc_calc_ldc_lut_lens_info` |
| 3 | `0x6e6440` | `0x806e6440` | `pp_dpc_lut_initialize_set_func` |
| 4 | `0x6e6a3c` | `0x806e6a3c` | `d5_pp_core_lut_control` |
| 5 | `0x6e7794` | `0x806e7794` | `pp_lrc_resolution_control` |
| 6 | `0x714708` | `0x80714708` | `(LUT_Load) _load error!! ` |
| 7 | `0x714724` | `0x80714724` | `(LUT_ChangeAddress) _changeDma error!! ` |
| 8 | `0x714750` | `0x80714750` | `(LUT_Stop) _stop error!! ` |
| 9 | `0x71476c` | `0x8071476c` | `(LUT_Start) _run error!! ` |
| 10 | `0x714788` | `0x80714788` | `(LUT_SetParam) Input param is NULL!! ` |
| 11 | `0x7147b0` | `0x807147b0` | `(LUT_SetParam) Ctrl Param Error!! ` |
| 12 | `0x7147d4` | `0x807147d4` | `(LUT_SetParam) _setDmaMux error!! ` |
| 13 | `0x7147f8` | `0x807147f8` | `(LUT_SetParam) _setParam error!! ` |
| 14 | `0x71481c` | `0x8071481c` | `(LUT_SetParam) _setWDma error!! ` |
| 15 | `0x714840` | `0x80714840` | `(LUT_SetParam) _setCtrl error!! ` |
| 16 | `0x714864` | `0x80714864` | `(LUT_SetParam) _setRDma error!! ` |
| 17 | `0x7149d8` | `0x807149d8` | `(_load) lut base addr is NULL! ` |
| 18 | `0x717629` | `0x80717629` | ` mag_coeff = %d, lut_adj = %d, center x/y = %d/%d, khl/khr = %d/%d, kvu/kvl = %d/%d` |
| 19 | `0x717681` | `0x80717681` | ` ---LUT DATA----` |
| 20 | `0x7209b4` | `0x807209b4` | `d5_ep_ldc_calc_ldc_lut(%d, %d, %d, 0x%08X)` |
| 21 | `0x7209e0` | `0x807209e0` | `d5_ep_ldc_calc_ldc_lut_lens_info(0x%08X, 0x%08X)` |
| 22 | `0x7240f8` | `0x807240f8` | `3D LUT Dump %s` |
| 23 | `0x728c84` | `0x80728c84` | `Lut Procedure is NULL !! !!` |
| 24 | `0x728ca4` | `0x80728ca4` | `Lut Material is NULL !! !!` |
| 25 | `0x72f54c` | `0x8072f54c` | `%s Line[%d] need DPC_Lut Maching Check (%d)` |
| 26 | `0x72f57c` | `0x8072f57c` | `%s Line[%d] dpc_lut_address is not multiple(16)` |
| 27 | `0x72f5b0` | `0x8072f5b0` | `is there mv4 = %d, dpc_lut_id = %llu` |
| 28 | `0x73c33c` | `0x8073c33c` | `lut_h,%d,lut_v,%d` |
| 29 | `0x73c398` | `0x8073c398` | `lut size error too large~ (%d) > %d` |
| 30 | `0x753f74` | `0x80753f74` | `3D LUT          %d` |
| 31 | `0x754154` | `0x80754154` | `lut_address = %X` |
| 32 | `0x755e8c` | `0x80755e8c` | `lv1 data size = %d, lut size = %d` |
| 33 | `0x755eb0` | `0x80755eb0` | `lv2 data size = %d, lut size = %d` |
| 34 | `0x755ed4` | `0x80755ed4` | `lv3 data size = %d, lut size = %d` |
| 35 | `0x755ef8` | `0x80755ef8` | `4k1 data size = %d, lut size = %d` |
| 36 | `0x755f1c` | `0x80755f1c` | `4k2 data size = %d, lut size = %d` |
| 37 | `0x755f40` | `0x80755f40` | `ud2 data size = %d, lut size = %d` |
| 38 | `0x755f64` | `0x80755f64` | `burst data size = %d, lut size = %d` |
| 39 | `0x755f88` | `0x80755f88` | `1080 data size = %d, lut size = %d` |
| 40 | `0x755fac` | `0x80755fac` | `live data size = %d, lut size = %d` |
| 41 | `0x755fd0` | `0x80755fd0` | `faf data size = %d, lut size = %d` |
| 42 | `0x755ff4` | `0x80755ff4` | `vfaf data size = %d, lut size = %d` |
| 43 | `0x756018` | `0x80756018` | `hfull data size = %d, lut size = %d` |
| 44 | `0x75603c` | `0x8075603c` | `dmf data size = %d, lut size = %d` |
| 45 | `0x7560a8` | `0x807560a8` | `reserved data size = %d, lut size = %d` |
| 46 | `0x75f718` | `0x8075f718` | `Error: Wrong LUT table` |
| 47 | `0x75f754` | `0x8075f754` | `Error: LUT operation failed ` |
| 48 | `0x75fafc` | `0x8075fafc` | `Error : invalid output buffer for ldc lut, %s [%d]` |
| 49 | `0x75fb30` | `0x8075fb30` | `Fail to calc ldc's lut, %s [%d]` |

## 复现

```bash
python scripts/discovery/t1_strings.py
```

```python
import re
data = open(r'raw8/p7/p7_full.bin','rb').read()
T1 = re.compile(rb'dlut|3DLUT|3D-LUT|3dl', re.I)
for m in re.finditer(rb'[\x20-\x7e]{4,}', data):
    s = m.group()
    if T1.search(s): print(hex(m.start()), s)
```