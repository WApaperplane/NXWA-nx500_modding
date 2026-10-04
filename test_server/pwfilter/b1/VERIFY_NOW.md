# ★ 请木一看取景器：验证 PW 参数实时生效

## 当前相机状态（脚本已写好，等你确认画面）

```
slot 12（CUSTOM_4）已写入：R=120 G=90 B=200  ← 明显偏蓝紫
PW_TYPE = PW_CUSTOM4 (0x14000c)               ← 已实时切换
prefman set 已执行，但**没有 save**
```

## 请看取景器，回答一个问题

### 问题：画面有没有明显偏蓝紫？

| 观察结果 | 说明 | 含义 |
|---|---|---|
| **明显偏蓝紫** | ✅ `prefman set` 是实时生效的 | 配方切换可以**免重启** |
| **完全没变化** | ❌ 只改了 prefman 内存，ISP 未采用 | 必须 `save` + 重启 |
| **轻微变化** | ⚠️ 部分生效 | 需要查 ISP 何时读 prefman |

预期：如果生效，画面会明显偏冷/偏紫（蓝通道 200 vs 红 120，绿被压到 90）。

## 三种情况的应对

### 如果生效（最好）
配方切换 = `prefman set`（7维）+ `setusr PW_TYPE`（切槽），**免重启、免写 eMMC**。
→ 可以做「Web 配方台 + 秒切」，体验最好。
→ 需要把 `filmlab-apply.sh` 里的 `prefman save` 改成可选。

### 如果没变化
那 `prefman set` 只是改了 prefman 自己的缓存，ISP 用的是 eMMC 里的值。
→ 配方切换必须 `save`（写 eMMC，有磨损，但一天几十次完全不是问题）
→ 或者需要重启相机才生效（体验差，需要换思路）

### 如果轻微变化
说明 ISP 在某个时刻读了 prefman 内存，但缓存没刷新。
→ 试 `prefman load -a 0`（从 eMMC 重载，会覆盖内存值）—— 不可用
→ 试 `prefman save` + `load -a 0`（已验证有效，但需 save）

## 恢复步骤（任何情况都能回滚）

```sh
sh /mnt/mmc/_pwtest/filmlab-apply.sh apply velvia50   # 切回一个已知配方
# 或
sh /mnt/mmc/_pwtest/filmlab-apply.sh reset            # 恢复出厂中性
```

slot 12 当前是实验值（120/90/200），`filmlab-apply.sh apply ektachrome` 会用
e=96/105/108 覆盖它（该配方用 slot 12）。
