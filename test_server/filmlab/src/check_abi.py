"""把 nxfilmui.c 里引用的每个 EFL 符号，逐个到 mod_gui + di-camera-app 的
.dynsym 未定义符号集合里查证。

为什么要这个脚本
----------------
EFL 头文件本地没有，只能手写 ABI 声明。手写声明的失败模式是**链接期才发现**，
那时已经把板子折腾上了。改成链接前静态查证：
    「这个符号有没有在真机上被跑通过的二进制用到过？」
用到过 ⇒ 真机那个库里必然有 ⇒ 链接能过、运行能解析。

白名单来源（都是真机上实际跑过的 ARM ELF）
    scripts/mod_gui            14KB，EFL 客户端，最小依赖集
    test_server/appprobe/di-camera-app  4.7MB，EFL 重度用户，230 个 elementary 符号
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent.parent  # -> 仓库根

PROVIDERS = [ROOT / "scripts" / "mod_gui",
             ROOT / "test_server" / "appprobe" / "di-camera-app",
             # ★ 2026-10-08（工作流 D7）：第三个白名单来源 ——
             #   离线 CJK 光栅化程序，已在相机 rootfs（chroot + qemu-arm-static）里
             #   跑通出图，是 **evas 纯文本 API（evas_object_text_*）的第一手等价证据**。
             #   没有它，nxfilmui v4 新加的字体调用会被误判为"无真机证据"。
             ROOT / "test_server" / "filmlab" / "src" / "out" / "cjk_render.arm"]

SRC = HERE / "nxfilmui.c"


def main() -> int:
    sys.path.insert(0, str(HERE))
    from dynsym import dynsym

    known = set()
    for p in PROVIDERS:
        if not p.is_file():
            print("!! 缺 provider: %s" % p)
            continue
        _, undef = dynsym(p)
        known |= set(undef)
        print("已加载白名单 %-16s 未定义符号 %d" % (p.name, len(undef)))

    src = SRC.read_text(encoding="utf-8")

    # 抓出所有裸函数调用（形如 ident(...) ）+ typedef 行后的声明名
    called = set(re.findall(r"\b([a-z_][a-z0-9_]{2,})\s*\(", src))

    PREFIX = ("elm_", "evas_", "ecore_", "eina_", "edje_", "efl_")
    used = sorted(n for n in called if n.startswith(PREFIX))

    print("\n" + "=" * 72)
    print("nxfilmui.c 引用的 EFL 符号 %d 个，逐个查证：" % len(used))
    print("=" * 72)

    ok, missing = [], []
    for n in used:
        hit = n in known
        (ok if hit else missing).append(n)
        print("  %s  %s" % ("OK  " if hit else "MISS", n))

    print("\n有真机证据 %d/%d" % (len(ok), len(used)))
    if missing:
        print("\n★ 无真机证据的符号（可能被两个 provider 都没用到，不代表不存在）:")
        for n in missing:
            print("  - %s" % n)

    print("\n=== 反向检查：这两个是我担心真机没有的，确认一下 ===")
    for probe in ("elm_gengrid_page_size_set", "elm_win_fullscreen_set",
                  "elm_label_alignment_set", "elm_gengrid_reorder",
                  "elm_object_text_color_set", "evas_object_size_hint_weight_set",
                  "ecore_event_handler_add", "elm_object_size_hint_min_set"):
        print("  %-36s %s" % (probe, "有真机证据" if probe in known else "★ 无证据"))

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
