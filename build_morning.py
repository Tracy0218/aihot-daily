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

# 兜底色：数据源当天若出现 CANON 之外的分类，按出现顺序分配稳定色，保证不丢不漏
FALLBACK_COLORS = ["#14b8a6", "#f97316", "#a855f7", "#ef4444", "#0d948b", "#78716c"]

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

# ---- 做AI智能客服该关注什么 ----
# 从所有分类新闻里，筛出对『AI智能客服业务效果』有影响的条目。
# 关键词覆盖：模型/Agent能力、成本、多模态、终端、私有化、工具调用等能直接或间接
# 提升客服(答得准/回得快/能代办/更便宜/更合规)的能力信号。
CS_LAND = [
    "Agent", "智能体", "自动化", "工作流", "工具调用", "function call", "computer use",
    "多模态", "multimodal", "视觉", "图像", "语音", "端侧", "本地部署", "私有化",
    "开源", "开放权重", "成本", "降价", "推理", "算力", "上下文", "长上下文",
    "RAG", "检索", "路由", "router", "多轮", "对话", "人工", "客服", "客户服务",
    "价格", "token", "API", "调用", "智能编程", "网络防御", "安全",
]
# 趋势词：偏方向性/基础设施/长期，标记为『是趋势』；其余按『可落地』呈现
CS_TREND = [
    "自主", "探索", "环境", "文明", "研究", "开放世界", "数学发现", "网络防御",
    "多智能体", "长期", "规划", "记忆", "评测", "基准",
]

def build_cs_watch(sections_out):
    """生成『做AI智能客服该关注什么』：命中智能客服影响信号的新闻 → 可落地 / 是趋势 两类。
    每类给『简要总结』（来源标题 + 一句话对客服的影响），便于领导快速扫读决策。"""
    # 汇总所有分类的新闻，保留来源分类信息
    flat = []
    for sec in sections_out:
        for it in sec["items"]:
            blob = (it["title"] or "") + " " + (it["summary"] or "")
            flat.append({
                "label": sec["label"], "color": sec["color"],
                "title": it["title"], "summary": it["summary"], "url": it["url"],
                "blob": blob,
            })

    land = []   # 可落地
    trend = []  # 是趋势
    for it in flat:
        hit = any(k.lower() in it["blob"].lower() for k in CS_LAND)
        if not hit:
            continue
        is_trend = any(k.lower() in it["blob"].lower() for k in CS_TREND)
        (trend if is_trend else land).append({
            "label": it["label"], "color": it["color"],
            "title": it["title"], "summary": it["summary"], "url": it["url"],
        })

    return {"land": land, "trend": trend}

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

# ----- map into sections with global numbering -----
# 优先按 CANON 固定顺序渲染已知分类；数据源当天若出现 CANON 之外的新分类，
# 按出现顺序追加渲染（分配兜底色），确保所有分类、所有新闻都不丢不漏。
global_idx = 0
sections_out = []

def _make_section(label, slug, color, items):
    global global_idx
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
    return {"label": label, "slug": slug, "color": color,
            "count": len(cards), "items": cards}

seen_labels = set()
for label, slug, color in CANON:
    if label not in sec_map:
        continue
    seen_labels.add(label)
    sections_out.append(_make_section(label, slug, color, sec_map[label]))

# 追加数据源里 CANON 未覆盖的分类（保证不丢）
_fb = 0
for label, items in sec_map.items():
    if label in seen_labels:
        continue
    slug = "sec-" + str(len(sections_out) + 1)
    color = FALLBACK_COLORS[_fb % len(FALLBACK_COLORS)]
    _fb += 1
    sections_out.append(_make_section(label, slug, color, items))

total = global_idx
src = d.get("attribution", {})
canonical = src.get("canonical", "https://aihot.virxact.com")
source_name = src.get("source", "AIHOT")

overview = build_overview(sections_out, date_label)
cs_watch = build_cs_watch(sections_out)

DATA = {
    "dateLabel": date_label,
    "genLabel": gen_label,
    "windowLabel": window_label,
    "total": total,
    "overviewObj": overview,
    "csWatch": cs_watch,
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

  /* CSWATCH (做AI智能客服该关注什么) */
  .cswatch{max-width:1080px;margin:14px auto 0;padding:0 18px}
  .cswatch .box{border-left-color:#0d948b}
  .cswatch .o-head .tag.cs{color:#0d948b;background:#e6f7f4}
  .cswatch .takeaway.cs-lead{
    font-size:14px;font-weight:600;color:#134e4a;line-height:1.6;
    margin:2px 0 14px;padding:10px 14px;background:#e9f7f5;
    border-radius:10px;border-left:3px solid #0d948b;
  }
  .cs-groups{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  .cs-group{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
  .cs-group-head{display:flex;align-items:center;gap:7px;font-size:14.5px;font-weight:800;margin-bottom:10px}
  .cs-ic{width:9px;height:9px;border-radius:50%;display:inline-block}
  .cs-group-head.land .cs-ic{background:#059669;box-shadow:0 0 0 4px #d1fae5}
  .cs-group-head.trend .cs-ic{background:#0284c7;box-shadow:0 0 0 4px #e0f2fe}
  .cs-list{list-style:none}
  .cs-list li{padding:9px 0;border-top:1px dashed var(--line);line-height:1.55}
  .cs-list li:first-child{border-top:none;padding-top:0}
  .cs-list .cs-lbl{font-size:11px;font-weight:700;color:#0d948b;background:#e6f7f4;border-radius:6px;padding:1px 7px;margin-right:6px}
  .cs-list .cs-t{font-size:13.5px;font-weight:700;color:#1f2533}
  .cs-list .cs-s{display:block;font-size:12.5px;color:#4b5563;margin-top:3px}
  .cs-empty{font-size:13px;color:var(--muted);padding:4px 0}
  @media (max-width:640px){
    .cswatch{padding:0 12px}
    .cs-groups{grid-template-columns:1fr}
  }

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
  </section>

  <section class="cswatch" id="cswatch">
    <div class="box">
      <div class="o-head">
        <span class="tag cs">做 AI 智能客服 · 该关注什么</span>
        <h2>做AI智能客服该关注什么</h2>
      </div>
      <p class="takeaway cs-lead" id="csLead"></p>
      <div class="cs-groups">
        <div class="cs-group">
          <div class="cs-group-head land"><span class="cs-ic"></span>可落地</div>
          <ul class="cs-list" id="csLand"></ul>
        </div>
        <div class="cs-group">
          <div class="cs-group-head trend"><span class="cs-ic"></span>是趋势</div>
          <ul class="cs-list" id="csTrend"></ul>
        </div>
      </div>
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

// ---- 做AI智能客服该关注什么：可落地 / 是趋势 ----
const cw = DATA.csWatch || {land:[], trend:[]};
const totalCs = (cw.land||[]).length + (cw.trend||[]).length;
document.getElementById("csLead").textContent =
  "从今日 " + DATA.total + " 条新闻中，筛选出 " + totalCs
  + " 条对 AI 智能客服业务效果有影响的动态。可落地项可优先评估试点，趋势项建议跟踪储备。";
function renderCs(list, el){
  const ul = document.getElementById(el);
  if(!list.length){
    const li = document.createElement("li");
    li.className = "cs-empty";
    li.textContent = "今日暂无匹配项";
    ul.appendChild(li);
    return;
  }
  list.forEach(it=>{
    const li = document.createElement("li");
    const lbl = document.createElement("span");
    lbl.className = "cs-lbl"; lbl.textContent = it.label;
    const t = document.createElement("span");
    t.className = "cs-t"; t.textContent = it.title;
    li.appendChild(lbl); li.appendChild(t);
    if(it.summary){
      const s = document.createElement("span");
      s.className = "cs-s";
      if(it.url){
        const a = document.createElement("a");
        a.href = it.url; a.target = "_blank"; a.rel = "noopener noreferrer";
        a.style.cssText = "color:#0d948b;text-decoration:none";
        a.textContent = "阅读原文";
        s.textContent = it.summary + "（";
        s.appendChild(a);
        s.appendChild(document.createTextNode("）"));
      } else {
        s.textContent = it.summary;
      }
      li.appendChild(s);
    }
    ul.appendChild(li);
  });
}
renderCs(cw.land, "csLand");
renderCs(cw.trend, "csTrend");

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
// 智能客服关注锚点
const csA = document.createElement("a");
csA.href = "#cswatch";
csA.innerHTML = "智能客服关注 <b>" + totalCs + "</b>";
navEl.appendChild(csA);
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
