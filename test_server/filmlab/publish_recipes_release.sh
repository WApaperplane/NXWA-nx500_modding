#!/usr/bin/env bash
#=====================================================================
# publish_recipes_release.sh —— 发布 FilmLab 配方库 release（含附件）
#---------------------------------------------------------------------
# 背景（2026-10-11）：
#   GitHub 的 release / 附件上传只能走 `api.github.com` / `uploads.github.com`
#   的 **POST**。部分网络环境（本项目实测：出网网关 Caddy）会拦截对
#   api.github.com 的 POST/PUT（返回 403/502，空体），但 `github.com` 正常、
#   `git push` 正常。于是「仓库 commit + tag」能自动化，「建 release」不能。
#
#   本脚本就是补这一步：在 API 可达的机器上跑一次即可。
#
# 前提：已 `git push` 了含 recipes.json 的分支与 tag（tag 默认 filmlab-recipes-v2）。
#
# 用法（二选一）：
#   A) 已 `gh auth login`：
#        bash test_server/filmlab/publish_recipes_release.sh
#   B) 无 gh，用个人令牌：
#        GH_TOKEN=ghp_xxx bash test_server/filmlab/publish_recipes_release.sh
#
# 幂等：release 已存在则补/覆盖附件；附件名固定 recipes.json / recipes.txt。
#=====================================================================
set -euo pipefail

REPO="${REPO:-WApaperplane/NXWA-nx500_modding}"
TAG="${TAG:-filmlab-recipes-v2}"
TITLE="${TITLE:-FilmLab 配方库 v2 — 95 条（+27：经典负片全谱 / 反转片 E-6 / 电影卷）}"

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SRC="$ROOT/scripts/filmlab/recipes.json"
NOTES="${NOTES:-$ROOT/docs/current/RECIPES_BATCH2_2026-10-11.md}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

[ -f "$SRC" ] || { echo "★ 找不到 $SRC"; exit 1; }

# 1) 生成扁平表 recipes.txt（key|label|R|G|B|HUE|SAT|SHARP|CON）
python3 - "$SRC" "$OUT/recipes.txt" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding="utf-8"))
F = ["R_COLOR","G_COLOR","B_COLOR","HUE","SATURATION","SHARPNESS","CONTRAST"]
rows = ["|".join([k, v["label"]] + [str(v[f]) for f in F]) for k, v in d["recipes"].items()]
open(dst, "w", encoding="utf-8", newline="\n").write("\n".join(rows) + "\n")
print("recipes.txt = %d 行" % len(rows))
PY
cp -f "$SRC" "$OUT/recipes.json"
echo "[local] recipes.json md5=$(md5sum "$OUT/recipes.json" | cut -d' ' -f1)"

# 2) 发布
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo "[gh] 创建/更新 release $TAG"
  gh release create "$TAG" \
    --repo "$REPO" --title "$TITLE" \
    --notes-file "$NOTES" \
    "$OUT/recipes.json" "$OUT/recipes.txt" \
    || {
      echo "[gh] release 已存在，改为上传（覆盖）附件"
      gh release upload "$TAG" --repo "$REPO" --clobber \
        "$OUT/recipes.json" "$OUT/recipes.txt"
    }
  gh release view "$TAG" --repo "$REPO"
  exit 0
fi

# 3) 无 gh → 纯 REST（需 GH_TOKEN）
: "${GH_TOKEN:?未设置 GH_TOKEN，且 gh 未登录。见脚本头用法。}"
API="https://api.github.com/repos/$REPO"
AUTH=(-H "Authorization: token $GH_TOKEN" -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28")

python3 - "$NOTES" "$TITLE" "$TAG" "$OUT/payload.json" <<'PY'
import json, sys
notes, title, tag, dst = sys.argv[1:5]
body = open(notes, encoding="utf-8").read()
json.dump({"tag_name": tag, "target_commitish": "nxwa", "name": title,
           "body": body, "draft": False, "prerelease": False},
          open(dst, "w", encoding="utf-8"))
PY

code=$(curl -sS -o "$OUT/rel.json" -w "%{http_code}" -X POST "$API/releases" \
  "${AUTH[@]}" --data-binary "@$OUT/payload.json")
echo "[rest] create release -> HTTP $code"

RID=$(python3 - "$OUT/rel.json" <<'PY'
import json, sys
try:
    print(json.load(open(sys.argv[1], encoding="utf-8"))["id"])
except Exception:
    print("")
PY
)

if [ -z "$RID" ]; then
  echo "★ 创建失败（可能已存在）：手动去 https://github.com/$REPO/releases/new?tag=$TAG"
  echo "  或先 export GH_TOKEN 后重跑。"
  exit 1
fi

for f in recipes.json recipes.txt; do
  ct="application/json"; [ "${f##*.}" = "txt" ] && ct="text/plain"
  c=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
    "https://uploads.github.com/repos/$REPO/releases/$RID/assets?name=$f" \
    "${AUTH[@]}" -H "Content-Type: $ct" --data-binary "@$OUT/$f")
  echo "[rest] upload $f -> HTTP $c"
done
echo "完成：https://github.com/$REPO/releases/tag/$TAG"
