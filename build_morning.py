# -*- coding: utf-8 -*-
import json, datetime, re, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "aihot_daily.json")
OUT = os.path.join(HERE, "aihot_morning.html")

CANON = [
    ("模型发布/更新", "ai-models",  "#2563eb"),
    ("产品发布/更新", "ai-products", "#0ea5e9"),
    ("行业动态",     "industry",    "#f59e0b"),
    ("论文研究",     "paper",       "#10b981"),
    ("技巧与观点",   "tip",         "#8b5cf6"),
]

WD = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]

def bj_dt(iso):
    """UTC iso -> Beijing datetime (UTC+8)."""
    dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    dt = dt + datetime.timedelta(hours=8)
    return dt

def bj_hm(dt):
    return f"{dt.month}月{dt.day}日 {dt.hour:02d}:{dt.minute:02d}"

def trunc_cn(s, n):
    a = list(s or "")
    return s if len(a) <= n else "".join(a[:n]) + "…"

def build_overview(sections_out, date_label):
    """生成『每日重点新闻概述』——结构化对象，便于卡片化渲染、快速抓重点。
    只覆盖 产品/模型/行业 三大版块；每块取 Top N 条（标题加粗 + 摘要支撑），
    并产出一句『今日导语』（主线 + 最受关注单条）。"""
    want = {"模型发布/更新": 2, "产品发布/更新": 3, "行业动态": 1}
    theme = {"模型发布/更新": "模型层面", "产品发布/更新": "产品侧", "行业动态": "行业方面"}
    color_of = {"模型发布/更新": "#2563eb", "产品发布/更新": "#0ea5e9", "行业动态": "#f59e0b"}
    weight = {"模型发布/更新": 3, "产品发布/更新": 2, "行业动态": 1}

    blocks = []
    for sec in sections_out:
        if sec["label"] not in want:      # 只保留 产品/模型/行业 三块
            continue
        if sec["count"] == 0:
            continue
        items = sec["items"][: want.get(sec["label"], 1)]
        blocks.append({
            "label": sec["label"],
            "theme": theme.get(sec["label"], "其他"),
            "color": color_of.get(sec["label"], "#8b5cf6"),
            "items": [{"title": it["title"],
                       "summary": (it.get("summary") or "").strip().rstrip("。；")}
                      for it in items],
        })
    if not blocks:
        return {"takeaway": f"{date_label}，今日暂无重点新闻更新。", "blocks": []}

    # 今日导语：以权重最高的版块为主线，点出其中最受关注的单条
    dom = max(blocks, key=lambda b: weight.get(b["label"], 0))
    top = dom["items"][0]["title"]
    takeaway = f"今日 AI 动态以「{dom['theme']}」为主线，最受关注的是：{top}。"
    return {"takeaway": takeaway, "blocks": blocks}

def build_cs_insight(model_items, product_items, industry_items):
    """结合当日的『模型动态 + 产品动态』（辅以行业动态），合成『AI智能客服的新机会』。
    数据驱动：用关键词把真实新闻条目映射到具体客服落地场景；每条给出『是否可落地(可行性分级)
    + 如何应用(说明)』，并按可行性排序，方便快速识别优先验证项。同一新闻只引用一次。"""
    # (应用方向, 具体说明, 可行性分级, 关键词, 业务优先级)
    # 业务优先级高(数字大)的规则先挑条目，确保强相关方向优先占用最匹配的新闻，避免错配
    rules = [
        ("自主任务执行",
         "模型对智能体与自动化的优化，使客服从『问答』走向『代办』，可自主操作软件、查询订单、发起退款、更新工单并回执进展。",
         "可落地", "Agent|智能体|自动化|工作流|代办|操作软件|操作电脑|浏览器操作|Computer Use|执行任务", 5),
        ("全渠道与多终端覆盖",
         "借助对移动端、电脑端、网页端等多终端的覆盖能力，客服可延伸到用户所在的任意设备与场景，实现随身式服务。",
         "可试点", "终端|多端|跨端|移动端|电脑端|网页端|眼镜|手机|开放平台|跨平台|全渠道", 4),
        ("私有化与数据合规",
         "端侧/开放权重的模型可在企业内网或私有环境部署，客户对话与工单数据不出域，满足金融、政务等强合规场景要求。",
         "可试点", "本地|私有化|私有|常驻|开放权重|开源|端侧|本地部署|内网", 3),
        ("多模态客服",
         "用户直接发送产品截图、故障照片或聊天记录，模型图文混合理解意图，自动定位问题并给处理建议，减少多轮来回确认。",
         "可落地", "多模态|multimodal|图像|视觉|截图|图片|图文", 2),
        ("智能会话路由",
         "把动态路由用于客服，按问题复杂度与用户价值自动分流到机器人或对应坐席，提升首次解决率(FCR)。",
         "可落地", "路由|router|调度|分配|分流", 1),
        ("规模化降本",
         "底层推理与算力基础设施的持续投入拉低单位调用成本，让 7x24 全量智能客服在大规模用户下仍具经济性。",
         "趋势", "成本|降本|算力|芯片|数据中心|推理基础设施|单位调用", 0),
    ]
    pools = [("模型", model_items), ("产品", product_items), ("行业", industry_items)]
    flat = [{"src": src, "title": it.get("title", ""), "summary": it.get("summary", ""),
             "url": it.get("url", ""), "blob": it.get("title", "") + " " + it.get("summary", "")}
            for src, items in pools for it in items]

    used = set()      # 已占用的新闻标题（同一新闻只引用一次）
    points = []
    for title, desc, level, kw, _pri in sorted(rules, key=lambda r: -r[4]):
        best = None; best_score = 0
        for it in flat:
            if it["title"] in used:
                continue
            score = len(re.findall(kw, it["blob"]))
            if score > best_score:
                best_score = score; best = it
        if best:
            used.add(best["title"])
            points.append({"title": title, "sourceLabel": best["src"],
                           "sourceTitle": best["title"], "sourceUrl": best["url"],
                           "desc": desc, "level": level})

    n_m, n_p = len(model_items), len(product_items)
    k = len(points)
    if not points:
        names = [it["title"] for it in (model_items + product_items)][:3]
        verdict = (f"结合今日 {n_m} 条模型动态与 {n_p} 条产品动态"
                   f"（{('、'.join(names)) or '暂无'}），暂未匹配到明确的智能客服落点，建议持续跟踪。")
        return {"verdict": verdict, "points": []}

    rank = {"可落地": 0, "可试点": 1, "需评估": 2, "趋势": 3}
    pts_sorted = sorted(points, key=lambda p: rank.get(p["level"], 9))
    top2 = "、".join("「" + p["title"] + "」" for p in pts_sorted[:2])
    verdict = (f"结合今日 {n_m} 条模型动态与 {n_p} 条产品动态，其中 {k} 个方向与 AI 智能客服强相关。"
               f"建议优先从 {top2} 切入验证。")
    # 展示按可行性排序（可落地优先），便于快速识别优先级
    return {"verdict": verdict, "points": pts_sorted}

d = json.load(open(SRC))
sec_map = {s["label"]: s["items"] for s in d.get("sections", [])}

# ----- date / time labels (Beijing, human readable) -----
yy, mm, dd = (int(x) for x in d["date"].split("-"))
date_obj = datetime.date(yy, mm, dd)
date_label = f"{yy}年{mm}月{dd}日 {WD[date_obj.weekday()]}"

gen = bj_dt(d["generatedAt"])
gen_label = f"{gen.year}年{gen.month}月{gen.day}日 {gen.hour:02d}:{gen.minute:02d}（北京时间）"

ws = bj_dt(d["windowStart"]); we = bj_dt(d["windowEnd"])
window_label = f"{bj_hm(ws)} – {bj_hm(we)}（北京时间）"

# ----- map into 5 canonical sections with global numbering -----
global_idx = 0
sections_out = []
for label, slug, color in CANON:
    items = sec_map.get(label, [])
    cards = []
    for it in items:
        global_idx += 1
        url = it.get("sourceUrl") or it.get("permalink") or ""
        cards.append({
            "n": global_idx,
            "title": it.get("title", "") or "（无标题）",
            "source": it.get("sourceName", "") or "未知来源",
            "summary": it.get("summary", "") or "",
            "url": url,
        })
    sections_out.append({
        "label": label, "slug": slug, "color": color,
        "count": len(cards), "items": cards,
    })

total = global_idx
src = d.get("attribution", {})
canonical = src.get("canonical", "https://aihot.virxact.com")
source_name = src.get("source", "AIHOT")

overview = build_overview(sections_out, date_label)

def _items_of(label):
    return next(s["items"] for s in sections_out if s["label"] == label)
cs_insight = build_cs_insight(
    _items_of("模型发布/更新"),
    _items_of("产品发布/更新"),
    _items_of("行业动态"),
)

DATA = {
    "dateLabel": date_label,
    "genLabel": gen_label,
    "windowLabel": window_label,
    "total": total,
    "overviewObj": overview,
    "csObj": cs_insight,
    "sourceName": source_name,
    "canonical": canonical,
    "sections": sections_out,
}

# ------------------------------------------------------------------
HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI HOT 每日晨报</title>
<style>
  :root{
    --bg:#f4f6fb; --card:#ffffff; --ink:#1f2533; --muted:#6b7280;
    --line:#e7eaf2; --shadow:0 1px 2px rgba(16,24,40,.04),0 8px 24px rgba(16,24,40,.06);
    --radius:16px;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html{scroll-behavior:smooth}
  body{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    background:var(--bg); color:var(--ink); line-height:1.6; -webkit-font-smoothing:antialiased;
  }
  a{color:inherit}

  /* HERO */
  .hero{
    background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 55%,#9333ea 100%);
    color:#fff; padding:46px 22px 38px; text-align:center; position:relative; overflow:hidden;
  }
  .hero::after{content:"";position:absolute;inset:0;background:
    radial-gradient(600px 200px at 15% -10%,rgba(255,255,255,.18),transparent),
    radial-gradient(500px 220px at 90% 0%,rgba(255,255,255,.12),transparent);pointer-events:none}
  .kicker{font-size:13px;letter-spacing:.28em;text-transform:uppercase;opacity:.85;font-weight:600}
  .hero h1{font-size:clamp(26px,5vw,40px);margin:10px 0 6px;font-weight:800;letter-spacing:.5px}
  .hero .meta{font-size:13px;opacity:.9;max-width:680px;margin:0 auto}
  .hero .total{margin:18px 0 22px;font-size:15px}
  .hero .total b{font-size:30px;font-weight:800;vertical-align:-2px;margin:0 6px}
  .stats{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;max-width:760px;margin:0 auto}
  .stat{
    background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);
    backdrop-filter:blur(6px);border-radius:999px;padding:7px 15px;font-size:13px;font-weight:600;
    display:flex;align-items:center;gap:7px;
  }
  .stat .dot{width:9px;height:9px;border-radius:50%}
  .stat b{font-size:15px}

  /* OVERVIEW (今日要点) */
  .overview{max-width:1080px;margin:22px auto 0;padding:0 18px}
  .overview .box{
    background:linear-gradient(180deg,#ffffff,#fbfcff);
    border:1px solid var(--line);border-left:4px solid #7c3aed;
    border-radius:14px;padding:18px 20px;box-shadow:var(--shadow);
  }
  .overview .o-head{display:flex;align-items:center;gap:9px;margin-bottom:9px}
  .overview .o-head .tag{
    font-size:11px;font-weight:700;color:#7c3aed;background:#f1ecfe;
    border-radius:6px;padding:2px 9px;letter-spacing:.04em;
  }
  .overview .o-head h2{font-size:16px;font-weight:800;color:var(--ink)}
  /* 今日导语（一句话主线） */
  .overview .takeaway{
    font-size:15.5px;font-weight:700;color:#1f2533;line-height:1.6;
    margin:2px 0 14px;padding:11px 14px;background:#f5f3ff;
    border-radius:10px;border-left:3px solid #7c3aed;
  }
  .overview .box.cs .takeaway{background:#eafaf8;border-left-color:#0d948b;color:#0f3b37}
  /* 今日要点：分块 + 加粗标题，便于扫读 */
  .ov-block{display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--line)}
  .ov-block:first-of-type{border-top:none}
  .ov-block-label{
    flex:0 0 60px;font-size:12.5px;font-weight:800;color:var(--c);
    position:relative;padding-left:11px;line-height:1.5;
  }
  .ov-block-label::before{
    content:"";position:absolute;left:0;top:2px;bottom:2px;width:3px;
    border-radius:2px;background:var(--c);
  }
  .ov-list{list-style:none;flex:1}
  .ov-list li{margin-bottom:9px;line-height:1.66}
  .ov-list li:last-child{margin-bottom:0}
  .ov-t{font-size:14px;font-weight:700;color:#1f2533}
  .ov-s{font-size:13.5px;color:#4b5563;margin-left:1px}
  @media (max-width:520px){
    .overview{padding:0 12px}
    .ov-block{flex-direction:column;gap:3px}
    .ov-block-label{flex:none}
  }
  /* 第二个块：AI 智能客服的新机会（不同强调色） */
  .overview .box.cs{border-left-color:#0d948b}
  .overview .o-head .tag.cs{color:#0d948b;background:#e6f7f4}
  /* 客服机会：按可行性分级的卡片网格 */
  .cs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(278px,1fr));gap:12px;margin-top:4px}
  .cs-card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 15px;box-shadow:var(--shadow)}
  .cs-card-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}
  .cs-title{font-size:14.5px;font-weight:800;color:#0f3b37}
  .cs-level{font-size:11px;font-weight:700;border-radius:999px;padding:2px 9px;white-space:nowrap}
  .lv-high{color:#047857;background:#d1fae5}
  .lv-mid{color:#0369a1;background:#e0f2fe}
  .lv-low{color:#b45309;background:#fef3c7}
  .lv-trend{color:#6b7280;background:#f3f4f6}
  .cs-src{font-size:12px;color:var(--muted);margin-bottom:7px}
  .cs-src a{color:#0d948b;font-weight:600;text-decoration:none}
  .cs-src a:hover{text-decoration:underline}
  .cs-desc{font-size:13.5px;color:#374151;line-height:1.66}
  @media (max-width:520px){ .cs-grid{grid-template-columns:1fr} }

  /* NAV */
  .nav{
    position:sticky;top:0;z-index:20;background:rgba(255,255,255,.92);
    backdrop-filter:blur(10px);border-bottom:1px solid var(--line);
    display:flex;flex-wrap:wrap;gap:6px;justify-content:center;padding:10px 14px;
  }
  .nav a{
    text-decoration:none;font-size:13px;color:var(--ink);font-weight:600;
    padding:6px 12px;border-radius:999px;display:flex;align-items:center;gap:6px;transition:.15s;
    border:1px solid transparent;
  }
  .nav a:hover{background:#eef1fb;border-color:#d9defb}
  .nav a.top{background:#1f2533;color:#fff}
  .nav a b{font-size:12px;background:rgba(0,0,0,.07);border-radius:999px;padding:0 7px;min-width:20px;text-align:center}
  .nav a.top b{background:rgba(255,255,255,.25)}

  /* SECTIONS */
  .wrap{max-width:1080px;margin:0 auto;padding:30px 18px 10px}
  section{margin-bottom:38px;scroll-margin-top:64px}
  .sec-head{display:flex;align-items:center;gap:11px;margin-bottom:16px}
  .sec-head .dot{width:13px;height:13px;border-radius:4px}
  .sec-head h2{font-size:20px;font-weight:800}
  .sec-head .count{
    font-size:12px;font-weight:700;color:var(--muted);background:#eef1f7;
    border-radius:999px;padding:2px 10px;
  }
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
  .card{
    background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
    padding:18px 18px 16px;box-shadow:var(--shadow);display:flex;flex-direction:column;
    transition:transform .15s ease,box-shadow .15s ease;
  }
  .card:hover{transform:translateY(-3px);box-shadow:0 10px 30px rgba(16,24,40,.12)}
  .card-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}
  .num{
    font-size:13px;font-weight:800;color:#fff;border-radius:8px;
    min-width:30px;height:26px;display:inline-flex;align-items:center;justify-content:center;padding:0 8px;
  }
  .chip{
    font-size:12px;font-weight:600;color:var(--muted);background:#f1f3f9;
    border-radius:999px;padding:3px 10px;max-width:60%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  }
  .card h3{font-size:16px;font-weight:700;line-height:1.45;margin-bottom:8px}
  .summary{font-size:14px;color:#3c4456;flex:1;margin-bottom:14px}
  .more{
    align-self:flex-start;text-decoration:none;font-size:13px;font-weight:700;
    color:#4f46e5;display:inline-flex;align-items:center;gap:4px;transition:.15s;
  }
  .more:hover{gap:8px;color:#7c3aed}
  .empty{
    grid-column:1/-1;background:#fff;border:1px dashed var(--line);border-radius:var(--radius);
    padding:26px;text-align:center;color:var(--muted);font-size:14px;
  }

  /* FOOTER */
  footer{
    text-align:center;color:var(--muted);font-size:13px;padding:26px 18px 46px;
    border-top:1px solid var(--line);margin-top:10px;
  }
  footer a{color:#4f46e5;font-weight:600;text-decoration:none}
  footer a:hover{text-decoration:underline}
  footer .big{font-size:15px;color:var(--ink);font-weight:700}
  @media (max-width:520px){
    .hero{padding:36px 14px 30px}
    .wrap{padding:22px 12px 6px}
    .grid{grid-template-columns:1fr}
  }
</style>
</head>
<body>
  <header class="hero" id="top">
    <div class="kicker">AI HOT · 每日晨报</div>
    <h1 id="dateLabel"></h1>
    <div class="meta" id="meta"></div>
    <div class="total">今日精选 <b id="totalBig"></b> 条</div>
    <div class="stats" id="stats"></div>
  </header>

  <section class="overview" id="overview">
    <div class="box">
      <div class="o-head">
        <span class="tag">每日重点新闻概述</span>
        <h2>今日要点</h2>
      </div>
      <p class="takeaway" id="ovTakeaway"></p>
      <div class="ov-blocks" id="ovBlocks"></div>
    </div>
    <div class="box cs" style="margin-top:14px">
      <div class="o-head">
        <span class="tag cs">AI 智能客服 · 新机会</span>
        <h2>AI智能客服的新机会</h2>
      </div>
      <p class="takeaway cs-take" id="csVerdict"></p>
      <div class="cs-grid" id="csGrid"></div>
    </div>
  </section>

  <nav class="nav" id="nav"></nav>

  <main class="wrap" id="content"></main>

  <footer>
    <div class="big">本日报共 <span id="footTotal"></span> 条</div>
    <div style="margin-top:6px">数据来源：<a id="srcLink" target="_blank" rel="noopener noreferrer"></a>（aihot.virxact.com）</div>
  </footer>

<script>
const DATA = __DATA__;

function trunc(s, n){
  const a = Array.from(s || "");
  return a.length <= n ? s : a.slice(0, n).join("") + "…";
}

document.getElementById("dateLabel").textContent = DATA.dateLabel;
document.getElementById("meta").textContent = "报告生成：" + DATA.genLabel + " · 覆盖 " + DATA.windowLabel;
document.getElementById("totalBig").textContent = DATA.total;
document.getElementById("footTotal").textContent = DATA.total;

const srcLink = document.getElementById("srcLink");
srcLink.textContent = DATA.sourceName;
srcLink.href = DATA.canonical;

// ---- 今日要点：导语 + 分块加粗列表 ----
const ov = DATA.overviewObj || {takeaway:"", blocks:[]};
document.getElementById("ovTakeaway").textContent = ov.takeaway;
const ovBlocks = document.getElementById("ovBlocks");
(ov.blocks || []).forEach(b=>{
  const block = document.createElement("div");
  block.className = "ov-block";
  block.style.setProperty("--c", b.color);
  const lab = document.createElement("div");
  lab.className = "ov-block-label";
  lab.textContent = b.theme;
  const ul = document.createElement("ul");
  ul.className = "ov-list";
  (b.items || []).forEach(it=>{
    const li = document.createElement("li");
    const t = document.createElement("b");
    t.className = "ov-t"; t.textContent = it.title;
    li.appendChild(t);
    if(it.summary){
      const s = document.createElement("span");
      s.className = "ov-s"; s.textContent = "：" + it.summary;
      li.appendChild(s);
    }
    ul.appendChild(li);
  });
  block.appendChild(lab);
  block.appendChild(ul);
  ovBlocks.appendChild(block);
});

// ---- AI智能客服的新机会：结论 + 按可行性分级的卡片 ----
const cs = DATA.csObj || {verdict:"", points:[]};
document.getElementById("csVerdict").textContent = cs.verdict;
const csGrid = document.getElementById("csGrid");
const lvClass = {"可落地":"lv-high","可试点":"lv-mid","需评估":"lv-low","趋势":"lv-trend"};
(cs.points || []).forEach(p=>{
  const card = document.createElement("div");
  card.className = "cs-card";
  const top = document.createElement("div");
  top.className = "cs-card-top";
  const title = document.createElement("span");
  title.className = "cs-title"; title.textContent = p.title;
  const lv = document.createElement("span");
  lv.className = "cs-level " + (lvClass[p.level] || "lv-mid");
  lv.textContent = p.level;
  top.appendChild(title); top.appendChild(lv);
  const src = document.createElement("div");
  src.className = "cs-src";
  src.appendChild(document.createTextNode("源自 " + p.sourceLabel + "动态 · "));
  if(p.sourceUrl){
    const a = document.createElement("a");
    a.href = p.sourceUrl; a.target = "_blank"; a.rel = "noopener noreferrer";
    a.textContent = p.sourceTitle;
    src.appendChild(a);
  } else {
    src.appendChild(document.createTextNode(p.sourceTitle));
  }
  const desc = document.createElement("p");
  desc.className = "cs-desc"; desc.textContent = p.desc;
  card.appendChild(top); card.appendChild(src); card.appendChild(desc);
  csGrid.appendChild(card);
});

// stats chips
const statsEl = document.getElementById("stats");
DATA.sections.forEach(sec=>{
  const el = document.createElement("div");
  el.className = "stat";
  el.innerHTML = '<span class="dot" style="background:'+sec.color+'"></span>'+sec.label+' <b>'+sec.count+'</b>';
  statsEl.appendChild(el);
});

// nav
const navEl = document.getElementById("nav");
const topA = document.createElement("a");
topA.href = "#top"; topA.className = "top"; topA.innerHTML = "顶部 <b>↑</b>";
navEl.appendChild(topA);
DATA.sections.forEach(sec=>{
  const a = document.createElement("a");
  a.href = "#sec-"+sec.slug;
  a.innerHTML = sec.label + " <b>"+sec.count+"</b>";
  navEl.appendChild(a);
});

// sections + cards
const content = document.getElementById("content");
DATA.sections.forEach(sec=>{
  const secEl = document.createElement("section");
  secEl.id = "sec-"+sec.slug;
  const head = document.createElement("div");
  head.className = "sec-head";
  head.innerHTML = '<span class="dot" style="background:'+sec.color+'"></span>'
    + '<h2>'+sec.label+'</h2><span class="count">'+sec.count+' 条</span>';
  secEl.appendChild(head);

  const grid = document.createElement("div");
  grid.className = "grid";

  if(sec.items.length === 0){
    const e = document.createElement("div");
    e.className = "empty";
    e.textContent = "今日该版块暂无精选内容";
    grid.appendChild(e);
  } else {
    sec.items.forEach(it=>{
      const card = document.createElement("article");
      card.className = "card";
      const numStr = String(it.n).padStart(2,"0");
      card.innerHTML =
        '<div class="card-top">'
        + '<span class="num" style="background:'+sec.color+'">'+numStr+'</span>'
        + '<span class="chip" title="'+it.source.replace(/"/g,"&quot;")+'">'+it.source+'</span>'
        + '</div>'
        + '<h3>'+it.title+'</h3>'
        + '<p class="summary">'+trunc(it.summary,60)+'</p>'
        + '<a class="more" href="'+it.url+'" target="_blank" rel="noopener noreferrer">阅读原文 →</a>';
      grid.appendChild(card);
    });
  }
  secEl.appendChild(grid);
  content.appendChild(secEl);
});
</script>
</body>
</html>
"""

html = HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False))
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print("WROTE:", OUT)
print("total items:", total)
for s in sections_out:
    print(f"  {s['label']}: {s['count']}")
print("dateLabel:", date_label)
print("genLabel:", gen_label)
print("windowLabel:", window_label)
