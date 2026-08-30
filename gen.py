# -*- coding: utf-8 -*-
"""
GitHub Actions 云端入口：拉取 aihot 最新日报 -> 调用 build_morning.py 生成 HTML -> 复制为 index.html。
纯标准库，无需任何第三方依赖。由 .github/workflows/daily.yml 调用。
"""
import os, sys, json, datetime, urllib.request, subprocess, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
AIHOT = "https://aihot.virxact.com/api/public/daily"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_daily():
    """返回 (data, 使用的日期)。当日无内容则回退到最近有内容的日期（最多往前 10 天）。"""
    today = datetime.date.today()
    for back in range(0, 10):
        d = today - datetime.timedelta(days=back)
        ds = d.isoformat()
        try:
            data = get_json(f"{AIHOT}/{ds}")
        except Exception:
            continue
        total = sum(len(s.get("items", [])) for s in data.get("sections", []))
        if total > 0:
            return data, ds
    return get_json(AIHOT), today.isoformat()


def main():
    data, used = fetch_daily()
    json.dump(data, open(os.path.join(HERE, "aihot_daily.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print("fetched daily for:", used)
    subprocess.run([sys.executable, os.path.join(HERE, "build_morning.py")],
                   check=True, cwd=HERE)
    shutil.copy(os.path.join(HERE, "aihot_morning.html"),
                os.path.join(HERE, "index.html"))
    print("wrote index.html for", used)


if __name__ == "__main__":
    main()
