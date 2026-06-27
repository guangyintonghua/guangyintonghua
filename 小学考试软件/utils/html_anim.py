"""
Generate a self-contained animated HTML page from solution steps.
Opens in the system default browser — no extra packages required.
"""

import json
import os
import tempfile

# ── HTML template ──────────────────────────────────────────────────────────
# Dynamic injection points use HTML-comment markers so they never collide
# with CSS/JS braces.
#   <!--STEPS_JSON-->      JSON array of step objects
#   <!--KP-->              knowledge point chip text
#   <!--QUESTION-->        question content (HTML-escaped)
#   <!--ANSWER-->          correct answer  (HTML-escaped)
# ──────────────────────────────────────────────────────────────────────────

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>解题动画讲解</title>
<style>
:root {
  --primary:#4B7BEC; --success:#52B788; --warning:#FD9644;
  --danger:#FC5C65;  --teal:#2BCBBA;    --purple:#8854D0;
  --bg:#F5F7FA; --card:#FFFFFF; --border:#E8ECF0;
  --text:#2D3436; --hint:#B2BEC3;
}
*{margin:0;padding:0;box-sizing:border-box}
body{
  font-family:"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif;
  background:var(--bg); min-height:100vh;
  display:flex; flex-direction:column; align-items:center;
  padding:28px 16px 40px;
}
.wrap{width:100%;max-width:740px}

/* ── header ── */
.page-title{
  font-size:22px;font-weight:bold;color:var(--primary);
  text-align:center;margin-bottom:20px;letter-spacing:1px;
}

/* ── question card ── */
.q-card{
  background:var(--card);border-radius:14px;
  padding:18px 22px;margin-bottom:22px;
  border:1px solid var(--border);
  box-shadow:0 2px 8px rgba(0,0,0,.05);
}
.kp-chip{
  display:inline-block;background:#EBF0FF;color:var(--primary);
  border-radius:4px;padding:2px 10px;font-size:12px;font-weight:bold;
  margin-bottom:10px;
}
.q-text{font-size:15px;line-height:1.8;color:var(--text)}
.q-answer{
  margin-top:10px;font-size:13px;font-weight:bold;
  color:var(--success);
}

/* ── progress dots ── */
.dots{display:flex;justify-content:center;gap:10px;margin-bottom:18px}
.dot{
  width:13px;height:13px;border-radius:50%;
  background:#DDE1E7;cursor:pointer;
  transition:background .3s,transform .3s;border:none;
}
.dot.active{transform:scale(1.35)}
.dot.done{background:var(--hint)}

/* ── step wrapper + cards ── */
.step-wrap{position:relative;overflow:hidden;margin-bottom:14px}
.step-card{
  background:var(--card);border-radius:14px;
  border:1px solid var(--border);
  border-left-width:5px;
  padding:22px 24px;
  box-shadow:0 2px 12px rgba(0,0,0,.06);
  /* default: off-screen right */
  position:absolute;top:0;left:0;width:100%;
  transform:translateX(105%);opacity:0;
  transition:transform .42s cubic-bezier(.25,.46,.45,.94),opacity .35s ease;
  pointer-events:none;
}
.step-card.active{
  position:relative;
  transform:translateX(0);opacity:1;
  pointer-events:auto;
}
.step-card.exit-left {transform:translateX(-105%);opacity:0;position:absolute}
.step-card.exit-right{transform:translateX( 105%);opacity:0;position:absolute}
.step-card.from-right{transform:translateX( 105%);opacity:0}
.step-card.from-left {transform:translateX(-105%);opacity:0}

/* ── card internals ── */
.sh{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.sbadge{
  width:36px;height:36px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-size:15px;font-weight:bold;color:#fff;flex-shrink:0;
}
.stitle{font-size:17px;font-weight:bold;flex:1}
.sprog{font-size:12px;color:var(--hint)}
.sdiv{height:1px;background:var(--border);margin-bottom:14px}
.scontent{
  font-size:15px;line-height:1.85;color:var(--text);
  min-height:56px;word-break:break-all;
}
.cursor{
  display:inline-block;width:2px;height:1.1em;
  vertical-align:text-bottom;margin-left:1px;
  animation:blink .65s step-end infinite;
}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
.kpoint{
  margin-top:12px;padding:9px 14px;border-radius:8px;
  font-size:13px;font-weight:bold;display:none;
  animation:popIn .35s cubic-bezier(.34,1.56,.64,1);
}
.kpoint.show{display:block}
@keyframes popIn{from{opacity:0;transform:translateY(6px) scale(.97)}to{opacity:1;transform:none}}

/* ── progress bar ── */
.pbar-wrap{height:5px;background:var(--border);border-radius:3px;margin-bottom:10px;overflow:hidden}
.pbar-fill{
  height:100%;border-radius:3px;
  background:linear-gradient(90deg,var(--primary),#74a1f5);
  transition:width 2.8s linear;
}

/* ── controls ── */
.controls{
  display:flex;justify-content:center;align-items:center;
  gap:10px;flex-wrap:wrap;margin-bottom:12px;
}
.btn{
  padding:10px 22px;border:none;border-radius:9px;
  font-size:14px;font-family:inherit;cursor:pointer;
  font-weight:bold;transition:all .2s;
}
.btn:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(0,0,0,.12)}
.btn:active{transform:translateY(0)}
.btn:disabled{opacity:.38;cursor:not-allowed;transform:none;box-shadow:none}
.btn-primary{background:linear-gradient(135deg,#5B8DEF,#3867D6);color:#fff}
.btn-secondary{background:#fff;color:#636E72;border:1px solid var(--border)}

.step-counter{text-align:center;font-size:12px;color:var(--hint)}
.footer{
  text-align:center;margin-top:28px;
  font-size:12px;color:var(--hint);
}
</style>
</head>
<body>
<div class="wrap">
  <div class="page-title">🔢 解题动画讲解</div>

  <div class="q-card">
    <div class="kp-chip"><!--KP--></div>
    <div class="q-text"><!--QUESTION--></div>
    <div class="q-answer">✓ 正确答案：<!--ANSWER--></div>
  </div>

  <div class="dots" id="dots"></div>
  <div class="step-wrap" id="stepWrap"></div>

  <div class="pbar-wrap"><div class="pbar-fill" id="pbarFill" style="width:0%"></div></div>

  <div class="controls">
    <button class="btn btn-secondary" id="btnPrev" onclick="doPrev()" disabled>◀ 上一步</button>
    <button class="btn btn-primary"   id="btnPlay" onclick="togglePlay()">▶ 自动播放</button>
    <button class="btn btn-secondary" id="btnNext" onclick="doNext()">下一步 ▶</button>
  </div>
  <div class="step-counter" id="counter"></div>
  <div class="footer">数学练习 · 解题动画 · 按 F5 重新播放</div>
</div>

<script>
"use strict";
const STEPS = <!--STEPS_JSON-->;

// Per-step colour palette
const PAL=[
  {bg:"#4B7BEC",light:"#EBF0FF"},
  {bg:"#52B788",light:"#E8F5EF"},
  {bg:"#FD9644",light:"#FEF3E8"},
  {bg:"#FC5C65",light:"#FDEDED"},
  {bg:"#2BCBBA",light:"#E4F9F8"},
  {bg:"#8854D0",light:"#F0EBFF"},
];

let cur=0, playing=false, typeId=null, autoId=null;

/* ── Build DOM ── */
const dotsEl   = document.getElementById("dots");
const wrapEl   = document.getElementById("stepWrap");

STEPS.forEach((s,i)=>{
  // dot
  const d=document.createElement("button");
  d.className="dot"+(i===0?" active":"");
  d.id="dot"+i;
  d.onclick=()=>{stopAuto();showStep(i)};
  dotsEl.appendChild(d);

  // card
  const c=PAL[i%PAL.length];
  const card=document.createElement("div");
  card.className="step-card"+(i===0?" active":"");
  card.id="card"+i;
  card.style.borderLeftColor=c.bg;
  card.innerHTML=
    '<div class="sh">'+
      '<div class="sbadge" style="background:'+c.bg+'">'+(i+1)+'</div>'+
      '<div class="stitle" style="color:'+c.bg+'">'+esc(s.title)+'</div>'+
      '<div class="sprog">'+(i+1)+' / '+STEPS.length+'</div>'+
    '</div>'+
    '<div class="sdiv"></div>'+
    '<div class="scontent" id="ct'+i+'"></div>'+
    (s.key_point
      ? '<div class="kpoint" id="kp'+i+'" style="background:'+c.light+';color:'+c.bg+'">💡 '+esc(s.key_point)+'</div>'
      : '');
  wrapEl.appendChild(card);
});

/* ── Utilities ── */
function esc(t){
  return String(t).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function updateDots(idx){
  STEPS.forEach((_,i)=>{
    const d=document.getElementById("dot"+i);
    const c=PAL[i%PAL.length];
    d.style.background= i===idx ? c.bg : i<idx ? "#B2BEC3" : "#DDE1E7";
    d.className="dot"+(i===idx?" active":i<idx?" done":"");
  });
}

function updateUI(){
  document.getElementById("counter").textContent="步骤 "+(cur+1)+" / "+STEPS.length;
  document.getElementById("btnPrev").disabled = cur===0;
  document.getElementById("btnNext").disabled = cur===STEPS.length-1;
}

function setPbar(idx,animate){
  const fill=document.getElementById("pbarFill");
  const pct=Math.round((idx+1)/STEPS.length*100);
  if(!animate){fill.style.transition="none";fill.style.width=pct+"%";fill.offsetHeight;fill.style.transition="";}
  else{fill.style.transition="width 2.8s linear";fill.style.width=pct+"%";}
}

/* ── Typewriter ── */
function startType(idx,onDone){
  clearTimeout(typeId);
  const el=document.getElementById("ct"+idx);
  const txt=STEPS[idx].content||"";
  let i=0;
  el.innerHTML='<span class="cursor" style="background:'+PAL[idx%PAL.length].bg+'"></span>';
  function tick(){
    if(i<txt.length){
      i++;
      el.innerHTML=esc(txt.slice(0,i))+'<span class="cursor" style="background:'+PAL[idx%PAL.length].bg+'"></span>';
      typeId=setTimeout(tick,20);
    } else {
      el.textContent=txt;
      const kp=document.getElementById("kp"+idx);
      if(kp) kp.classList.add("show");
      if(onDone) onDone();
    }
  }
  tick();
}

function finishType(idx){
  clearTimeout(typeId);
  const el=document.getElementById("ct"+idx);
  el.textContent=STEPS[idx].content||"";
  const kp=document.getElementById("kp"+idx);
  if(kp) kp.classList.add("show");
}

function onTypeDone(){
  setPbar(cur,true);
  if(playing){
    autoId=setTimeout(()=>{
      if(cur<STEPS.length-1) showStep(cur+1,1);
      else stopAuto();
    },2200);
  }
}

/* ── Card slide ── */
function showStep(idx, dir){
  if(idx<0||idx>=STEPS.length||idx===cur&&document.getElementById("card"+cur).classList.contains("active")) return;

  const direction = dir!==undefined ? dir : (idx>cur?1:-1);
  finishType(cur);

  const oldCard=document.getElementById("card"+cur);
  const newCard=document.getElementById("card"+idx);

  // lock wrapper height to prevent jump
  wrapEl.style.height=wrapEl.offsetHeight+"px";

  // exit old
  oldCard.classList.remove("active");
  oldCard.classList.add(direction>0?"exit-left":"exit-right");

  // prepare new off-screen
  newCard.style.transition="none";
  newCard.classList.remove("active","exit-left","exit-right","from-right","from-left");
  newCard.classList.add(direction>0?"from-right":"from-left");
  newCard.offsetHeight; // reflow
  newCard.style.transition="";
  newCard.classList.remove("from-right","from-left");
  newCard.classList.add("active");

  // cleanup after transition
  setTimeout(()=>{
    oldCard.classList.remove("exit-left","exit-right");
    wrapEl.style.height="";
  },480);

  cur=idx;
  updateDots(idx);
  updateUI();
  setPbar(idx,false);

  setTimeout(()=>startType(idx,onTypeDone),60);
}

/* ── Navigation ── */
function doNext(){
  clearTimeout(autoId);
  const el=document.getElementById("ct"+cur);
  if(el.querySelector(".cursor")){finishType(cur);onTypeDone();return;}
  if(cur<STEPS.length-1) showStep(cur+1,1);
}

function doPrev(){
  clearTimeout(autoId);
  if(cur>0) showStep(cur-1,-1);
}

function togglePlay(){
  playing=!playing;
  document.getElementById("btnPlay").textContent=playing?"⏸ 暂停":"▶ 自动播放";
  if(playing){
    // if already done typing, start auto timer
    const el=document.getElementById("ct"+cur);
    if(!el.querySelector(".cursor")) onTypeDone();
  } else {
    clearTimeout(autoId);
  }
}

function stopAuto(){
  playing=false;
  clearTimeout(autoId);
  document.getElementById("btnPlay").textContent="▶ 自动播放";
}

/* ── Init ── */
showStep(0);
updateUI();

// F5 restarts
document.addEventListener("keydown",e=>{
  if(e.key==="F5"){e.preventDefault();location.reload();}
  if(e.key==="ArrowRight") doNext();
  if(e.key==="ArrowLeft")  doPrev();
  if(e.key===" "){e.preventDefault();togglePlay();}
});
</script>
</body>
</html>
"""


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_solution_html(question: dict, steps: list[dict]) -> str:
    """Fill the template with question data and steps, return complete HTML string."""
    steps_json = json.dumps(steps, ensure_ascii=False)
    html = _TEMPLATE
    html = html.replace("<!--STEPS_JSON-->", steps_json)
    html = html.replace("<!--KP-->",       _esc(question.get("knowledge_point", "")))
    html = html.replace("<!--QUESTION-->", _esc(question.get("content", "")))
    html = html.replace("<!--ANSWER-->",   _esc(str(question.get("answer", ""))))
    return html


def open_in_browser(question: dict, steps: list[dict]) -> str:
    """Generate HTML, write to a temp file, and open in the default browser.
    Returns the temp file path (caller may delete it later if desired)."""
    html = generate_solution_html(question, steps)
    fd, path = tempfile.mkstemp(suffix=".html", prefix="math_anim_")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    os.startfile(path)
    return path
