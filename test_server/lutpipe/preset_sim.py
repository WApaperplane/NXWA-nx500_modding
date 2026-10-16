#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preset_sim.py — T2「统一预设与适配器协议」模拟后端（离线验证 · 2026-10-16）

对应文档：docs/current/T2_PRESET_PROTOCOL_2026-10-16.md
职责：用可注入故障的 mock 适配器 + 控制器，跑通状态机全部关键场景并输出轨迹。
  S1 全成功 / S2 部分失败 / S3 取消 / S4 外部改参 / S5 固件缺失 / S6 关闭语义（不得写 identity）

用法:
  python preset_sim.py --all
  python preset_sim.py --scene S2
"""
import argparse
import copy
import json
import sys

# ---------------------------------------------------------------- 状态
IDLE = "idle"
SELECTED = "selected"
APPLYING = "applying"
APPLIED = "applied"
PARTIAL = "partial"
PREVIEW_ONLY = "preview_only"
STILL_VERIFIED = "still_verified"
EXTERNAL_MODIFIED = "external_modified"
ROLLED_BACK = "rolled_back"


class ApplyResult:
    def __init__(self, name, level, detail=None):
        self.name = name
        self.level = level          # full | partial | failed | skipped
        self.detail = detail or {}

    def __repr__(self):
        return f"<{self.name}:{self.level}>"


# ---------------------------------------------------------------- 预设
def preset_basic():
    """portra400：PW + LUT，成片走 postproc（当前 LUT 直灌为负结论）"""
    return {
        "schema": "nxwa.preset/1",
        "id": "portra400",
        "display_name": "Portra 400",
        "capability": {
            "pw": True, "lut": True, "preview": True, "still": "postproc",
            "still_verified": False, "requires_firmware": "A2",
        },
        "pw": {"R": 106, "G": 100, "B": 93, "HUE": 11, "SAT": 9, "SHARP": 9, "CON": 8},
        "lut": {"file": "portra400.bin", "sha256": "ab" * 32,
                "format": "nx17q4", "purpose": "style",
                "input_color": {"gamut": "sRGB", "verified": False}},
    }


# ---------------------------------------------------------------- 适配器 mock
class PwMock:
    name = "pw"

    def __init__(self, ctx):
        self.ctx = ctx

    def probe(self, preset):
        fw = preset["capability"].get("requires_firmware")
        ok = (fw is None) or self.ctx.get("firmware_ok", True)
        return {"available": ok, "reason": None if ok else f"缺固件 {fw}（直推段将不生效）"}

    def apply(self, preset):
        if self.ctx.get("pw_fail"):
            return ApplyResult(self.name, "failed", {"err": "直推段拒收/超时"})
        if not self.probe(preset)["available"]:
            # 固件缺失：不写，如实标注「不生效」（不是 failed，是未达成）
            return ApplyResult(self.name, "skipped", {"reason": "firmware_missing"})
        self.ctx["pw_snapshot"] = copy.deepcopy(preset["pw"])
        self.ctx["pw_committed"] = True
        return ApplyResult(self.name, "full", {"values": preset["pw"]})

    def rollback(self, preset):
        snap = self.ctx.get("pw_snapshot")
        self.ctx["pw_committed"] = False
        return ApplyResult(self.name, "full", {"restored": snap})


class LutMock:
    name = "lut"

    def __init__(self, ctx):
        self.ctx = ctx

    def probe(self, preset):
        if not preset["capability"].get("lut"):
            return {"available": False, "reason": "preset 无 LUT"}
        if self.ctx.get("lut_missing"):
            return {"available": False, "reason": "表文件缺失"}
        return {"available": True, "reason": None,
                "precondition": "需前置抢回态（对焦一次）"}

    def apply(self, preset):
        if self.ctx.get("lut_fail"):
            return ApplyResult(self.name, "failed", {"err": "落点/四查被拒"})
        if self.ctx.get("cancelled"):
            # 取消：不再提交新的适配器（已提交的步骤不回滚——取消≠回滚）
            return ApplyResult(self.name, "failed", {"err": "cancelled_before_commit"})
        self.ctx["lut_committed"] = True
        self.ctx["lut_channel"] = 1                       # sel=1（LUT1）
        return ApplyResult(self.name, "full", {"sel": 1, "guard": True})

    def rollback(self, preset):
        """★ 关闭 = 停止守护 + 恢复确认过的原厂选表/配置；**不写 identity**"""
        self.ctx["lut_committed"] = False
        self.ctx["lut_channel"] = 0
        self.ctx["guard"] = False
        self.ctx["rollback_path"] = "restore_factory(sel=0 + lutload restore)"
        return ApplyResult(self.name, "full", {"path": self.ctx["rollback_path"],
                                               "identity_used": False})


# ---------------------------------------------------------------- 控制器
class Controller:
    def __init__(self, ctx=None, order=("pw", "lut")):
        self.ctx = ctx or {}
        self.order = order
        self.state = IDLE
        self.trace = []
        self.preset = None
        self.results = {}
        self.value_snapshot = None

    def _log(self, *msg):
        line = " ".join(str(m) for m in msg)
        self.trace.append(line)
        print("   " + line)

    def set_state(self, s):
        self.state = s
        self._log(f"[state] -> {s}")

    # -- 交互
    def select(self, preset):
        self.preset = preset
        self.set_state(SELECTED)

    def confirm(self):
        if self.state == APPLYING:
            self._log("[busy] 重复确认被拒绝（applying 中）")
            return
        self.set_state(APPLYING)
        adapters = {"pw": PwMock(self.ctx), "lut": LutMock(self.ctx)}
        self.results = {}
        for name in self.order:
            if self.ctx.get("cancelled"):
                self._log(f"[apply:{name}] 取消标志已置——本适配器不提交")
            r = adapters[name].apply(self.preset)
            self.results[name] = r
            self._log(f"[apply:{name}] -> {r.level} {r.detail}")
        self._settle()

    def _settle(self):
        levels = {k: v.level for k, v in self.results.items()}
        full = [k for k, v in levels.items() if v == "full"]
        bad = [k for k, v in levels.items() if v in ("failed", "skipped")]
        if not bad:
            self.set_state(APPLIED)
            self._post_applied()
        elif full:
            self.set_state(PARTIAL)
            self._log(f"[partial] 成功={full} 未达成={bad}（如实显示；不做原子化包装）")
        else:
            self.set_state(PARTIAL)
            self._log(f"[partial] 全部失败/未达成={bad}")

    def _post_applied(self):
        cap = self.preset["capability"]
        if cap.get("still") == "native" and cap.get("still_verified"):
            self.set_state(STILL_VERIFIED)
        else:
            self.set_state(PREVIEW_ONLY)
            note = ("机制=native 但**未实机验收**" if cap.get("still") == "native"
                    else f"成片={cap.get('still')}")
            self._log(f"[cap] {note} ⇒ 仅预览生效（如实标注）")

    def cancel(self):
        self.ctx["cancelled"] = True
        self._log("[cancel] 置取消标志（已提交步骤不回滚；取消≠回滚）")

    def retry_failed(self):
        self._log("[retry] 重试未达成部分")
        self.confirm()

    def external_change(self, what="factory_menu"):
        if self.state in (APPLIED, PREVIEW_ONLY, STILL_VERIFIED):
            self.set_state(EXTERNAL_MODIFIED)
            self._log(f"[external] 检测到原厂改参（{what}）⇒ 不再宣称精确匹配")

    def rollback(self):
        self._log("[rollback] 回滚（逐适配器）")
        PwMock(self.ctx).rollback(self.preset)
        LutMock(self.ctx).rollback(self.preset)
        self.set_state(ROLLED_BACK)

    def close_lut(self):
        """关闭 LUT：走恢复原厂路径（不得写 identity）"""
        self._log("[close_lut] 停止守护 + 恢复确认过的原厂选表/配置")
        r = LutMock(self.ctx).rollback(self.preset)
        self._log(f"[close_lut] path={r.detail['path']} identity_used={r.detail['identity_used']}")
        self.set_state(ROLLED_BACK)


# ---------------------------------------------------------------- 场景
def scene_S1():
    print("== S1 全成功 ==")
    c = Controller()
    c.select(preset_basic())
    c.confirm()
    assert c.state == PREVIEW_ONLY, c.state
    assert c.ctx["pw_committed"] and c.ctx["lut_committed"]
    return c


def scene_S2():
    print("== S2 部分失败（PW 成功 / LUT 失败）==")
    c = Controller(ctx={"lut_fail": True})
    c.select(preset_basic())
    c.confirm()
    assert c.state == PARTIAL
    assert c.results["pw"].level == "full" and c.results["lut"].level == "failed"
    print("   -- retry（清除故障后）--")
    c.ctx["lut_fail"] = False
    c.retry_failed()
    assert c.state == PREVIEW_ONLY
    return c


def scene_S3():
    print("== S3 取消（apply 中途）==")
    c = Controller(ctx={})
    c.select(preset_basic())
    c.set_state(APPLYING)
    # 模拟：pw 已提交后用户取消 ⇒ lut 不提交
    PwMock(c.ctx).apply(c.preset)
    c.cancel()
    r = LutMock(c.ctx).apply(c.preset)
    c.results = {"pw": ApplyResult("pw", "full"), "lut": r}
    c._log(f"[apply:lut] -> {r.level} {r.detail}")
    c._settle()
    assert c.state == PARTIAL
    assert c.ctx.get("pw_committed") and not c.ctx.get("lut_committed")
    print("   -- 显式回滚 --")
    c.rollback()
    assert c.state == ROLLED_BACK
    return c


def scene_S4():
    print("== S4 外部改参 ==")
    c = scene_S1()
    c.external_change("原厂菜单改了 PW 值")
    assert c.state == EXTERNAL_MODIFIED
    return c


def scene_S5():
    print("== S5 固件缺失（requires_firmware=A2）==")
    c = Controller(ctx={"firmware_ok": False})
    c.select(preset_basic())
    c.confirm()
    assert c.results["pw"].level == "skipped", c.results["pw"].level
    assert c.state == PARTIAL
    print("   ⇒ pw=skipped 如实标注（不是 failed，也不是成功）")
    return c


def scene_S6():
    print("== S6 关闭语义（不得写 identity）==")
    c = scene_S1()
    c.close_lut()
    assert c.ctx["rollback_path"].startswith("restore_factory")
    assert c.ctx["lut_channel"] == 0 and not c.ctx["guard"]
    return c


SCENES = {"S1": scene_S1, "S2": scene_S2, "S3": scene_S3,
          "S4": scene_S4, "S5": scene_S5, "S6": scene_S6}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--scene", default=None)
    a = ap.parse_args()
    names = list(SCENES) if (a.all or not a.scene) else [a.scene]
    ok = 0
    for n in names:
        print()
        try:
            SCENES[n]()
            print(f"   ✅ {n} PASS")
            ok += 1
        except AssertionError as e:
            print(f"   ❌ {n} FAIL: {e}")
    print(f"\n== 汇总：{ok}/{len(names)} 场景 PASS ==")
    return 0 if ok == len(names) else 2


if __name__ == "__main__":
    sys.exit(main())
