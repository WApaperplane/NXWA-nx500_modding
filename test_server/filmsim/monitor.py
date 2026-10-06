# -*- coding: utf-8 -*-
"""
DCIM 监控 + 原子写回 (原型)
流程：轮询 DCIM 目录发现新 JPEG
  -> 原图移入 <dir>/.original/ 保留副本（防重复处理：备份已存在则跳过）
  -> 处理到同目录临时文件
  -> os.replace 原子写回原名（防半写损坏）
用法：
  python monitor.py <dcim_dir> --recipe portra400 [--once] [--watch-sec 0.5]
"""
import argparse
import os
import shutil
import time

from engine import load_recipe, process_file

_ORIGINAL_DIR = ".original"
_TMP_PREFIX = ".filmsim_tmp_"
IMAGE_EXTS = (".jpg", ".jpeg", ".JPG", ".JPEG")


def _is_image(name):
    return name.endswith(IMAGE_EXTS)


def _is_stable(path, interval=0.4):
    """文件是否已写完（大小两次采样一致）。"""
    try:
        s1 = os.path.getsize(path)
        time.sleep(interval)
        s2 = os.path.getsize(path)
        return s1 == s2 and s2 > 0
    except OSError:
        return False


def process_new_file(dcim_dir, path, recipe):
    """单文件全流程：保留原图 -> 原子写回。"""
    basename = os.path.basename(path)
    orig_dir = os.path.join(dcim_dir, _ORIGINAL_DIR)
    backup = os.path.join(orig_dir, basename)

    # 防重复处理：.original 已有同名备份说明该文件已处理过
    if os.path.exists(backup):
        print(f"[filmsim] {basename}: 已处理过(备份已存在)，跳过", flush=True)
        return

    # 1) 保留原图副本（同分区 move = rename，不触发删除）
    os.makedirs(orig_dir, exist_ok=True)
    shutil.move(path, backup)
    # 2) 处理到临时文件（放同目录保证原子 rename）
    tmp = os.path.join(dcim_dir, _TMP_PREFIX + basename + ".tmp.jpg")
    try:
        process_file(backup, tmp, recipe)
        # 3) 原子写回原名（目标此时不存在，os.replace = rename，无删除）
        os.replace(tmp, path)
    except Exception as e:
        # 失败：清理临时文件，原图从备份挪回（可后悔）
        if os.path.exists(tmp):
            os.remove(tmp)
        if os.path.exists(backup) and not os.path.exists(path):
            shutil.move(backup, path)
        raise
    print(f"[filmsim] {basename}: 已套用「{recipe['name']}」，原图保留在 {_ORIGINAL_DIR}/", flush=True)


def scan(dcim_dir, recipe, once=False, watch_sec=0.5, already_seen=None):
    """轮询 DCIM 目录处理新 JPEG。返回已处理文件名集合。"""
    if already_seen is None:
        already_seen = set()
    while True:
        try:
            entries = sorted(os.listdir(dcim_dir))
        except FileNotFoundError:
            print(f"[filmsim] 目录不存在: {dcim_dir}", flush=True)
            return already_seen
        for name in entries:
            if not _is_image(name):
                continue
            full = os.path.join(dcim_dir, name)
            if os.path.isdir(full):
                continue
            if name in already_seen:
                continue
            if not _is_stable(full):
                continue
            already_seen.add(name)
            try:
                process_new_file(dcim_dir, full, recipe)
            except Exception as e:
                print(f"[filmsim] 处理失败 {name}: {e}", flush=True)
        if once:
            return already_seen
        time.sleep(watch_sec)


def main():
    ap = argparse.ArgumentParser(description="胶片仿真引擎：DCIM 监控 + 原子写回")
    ap.add_argument("dcim_dir", help="DCIM 目录路径")
    ap.add_argument("--recipe", default="portra400", help="配方 id 或 json 路径")
    ap.add_argument("--once", action="store_true", help="处理完现有文件即退出（测试用）")
    ap.add_argument("--watch-sec", type=float, default=0.5, help="轮询间隔")
    args = ap.parse_args()

    recipe = load_recipe(args.recipe)
    print(f"[filmsim] 配方: {recipe['name']} | 监控: {args.dcim_dir}", flush=True)
    scan(args.dcim_dir, recipe, once=args.once, watch_sec=args.watch_sec)


if __name__ == "__main__":
    main()
