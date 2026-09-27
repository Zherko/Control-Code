"""Genera dashboard.html: Consumo (tabs desacoplados, grafico 7d fijo) + Recursos + Tareas+calendario. Sin deps."""
import sqlite3, os, json, datetime, html, pathlib, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.expanduser(r"~\.local\share\opencode\opencode.db")
CONF = os.path.expanduser(r"~\.config\opencode\opencode.json")

def fmt_tok(n):
    if n >= 1e9: return f"{n/1e9:.2f}B"
    if n >= 1e6: return f"{n/1e6:.1f}M"
    if n >= 1e3: return f"{n/1e3:.0f}K"
    return str(n)

# --- consumo: opencode.db
con = sqlite3.connect(os.path.expanduser("~/.local/share/opencode/opencode.db"))
cur = con.cursor()
cur.execute("SELECT id, project_id FROM session")
sess2proj = dict(cur.fetchall())
cur.execute("SELECT id, worktree FROM project")
proj2wt = dict(cur.fetchall())
cur.execute("SELECT session_id, time_created, data FROM message")
daily, hourly = {}, {}
tot_t, tot_c, msgs = 0, 0.0, 0
for sid, tc, d in cur.fetchall():
    try: j = json.loads(d)
    except Exception: continue
    if j.get("role") != "assistant": continue
    tok = j.get("tokens") or {}
    t = int(tok.get("total") or 0)
    c = float(j.get("cost") or 0)
    ts = (j.get("time") or {}).get("created") or tc
    try:
        dt = datetime.datetime.fromtimestamp(ts/1000)
        day, hr = dt.strftime("%Y-%m-%d"), dt.strftime("%H")
    except Exception: continue
    msgs += 1; tot_t += t; tot_c += c
    wt = proj2wt.get(sess2proj.get(sid, "?"), "?")
    cwd = ((j.get("path") or {}).get("cwd")) or wt
    short = os.path.basename(cwd.rstrip("/\\")) or cwd
    m = j.get("modelID", "?")
    e = daily.setdefault(day, {"t": 0, "c": 0.0, "k": 0, "proj": {}, "mod": {}})
    e["t"] += t; e["c"] += c; e["k"] += 1
    p = e["proj"].setdefault(short, [0, 0.0, 0]); p[0] += t; p[1] += c; p[2] += 1
    mb = e["mod"].setdefault(m, [0, 0.0, 0]); mb[0] += t; mb[1] += c; mb[2] += 1
    if day == datetime.date.today().strftime("%Y-%m-%d"):
        h = hourly.setdefault(hr, [0, 0.0, 0]); h[0] += t; h[1] += c; h[2] += 1
con.close()

# --- tool & cache (build-time, comité veredicto)
tool_cnt={}
cache_in=cache_read=cache_write=cache_out=0
try:
    con2=sqlite3.connect(os.path.expanduser("~/.local/share/opencode/opencode.db"))
    cur2=con2.cursor()
    cur2.execute("SELECT data FROM part WHERE json_extract(data,'$.type')='tool' LIMIT 20000")
    import collections
    tc=collections.Counter()
    for (d,) in cur2.fetchall():
        try:
            o=json.loads(d)
            t=o.get("tool")
            if t: tc[t]+=1
        except: pass
    tool_cnt=dict(tc.most_common(12))
    cur2.execute("SELECT data FROM message WHERE json_extract(data,'$.role')='assistant'")
    for (d,) in cur2.fetchall():
        try:
            o=json.loads(d)
            tok=o.get("tokens") or {}
            cache_in+=int(tok.get("input") or 0)
            cache_out+=int(tok.get("output") or 0)
            cache_read+=int((tok.get("cache") or {}).get("read") or 0)
            cache_write+=int((tok.get("cache") or {}).get("write") or 0)
        except: pass
    con2.close()
except Exception as e:
    tool_cnt={"err":str(e)[:40]}

today = datetime.date.today()
def agg(days):
    pt, md = {}, {}
    t = c = k = 0
    for d in days:
        e = daily.get(d)
        if not e: continue
        t += e["t"]; c += e["c"]; k += e["k"]
        for n, v in e["proj"].items():
            b = pt.setdefault(n, [0, 0.0, 0]); b[0] += v[0]; b[1] += v[1]; b[2] += v[2]
        for n, v in e["mod"].items():
            b = md.setdefault(n, [0, 0.0, 0]); b[0] += v[0]; b[1] += v[1]; b[2] += v[2]
    return t, c, k, pt, md

all_days = sorted(daily)
d30 = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
d7 = d30[:7]; d1 = [today.strftime("%Y-%m-%d")]
R = {"total": agg(all_days), "d30": agg(d30), "d7": agg(d7), "d1": agg(d1)}
t_today = daily.get(d1[0], {"t": 0, "c": 0.0, "k": 0})

# --- recursos
agents, mcps = [], []
try:
    cfg = json.load(open(CONF, encoding="utf-8"))
    for k, v in (cfg.get("agent") or {}).items():
        agents.append({"id": k, "desc": (v.get("description") or "")[:90], "mode": v.get("mode",""), "tools": ",".join([kk for kk, vv in (v.get("tools") or {}).items() if vv])})
    for k, v in (cfg.get("mcp") or {}).items():
        mcps.append({"id": k, "type": v.get("type",""), "enabled": v.get("enabled", True), "cmd": " ".join(v.get("command") or [])[:60]})
except Exception as e:
    agents = [{"id": f"err {e}", "desc": "", "mode": "", "tools": ""}]

# skills: global + project
def skill_desc(p):
    try:
        md = open(os.path.join(p, "SKILL.md"), encoding="utf-8", errors="ignore").read()
        # primera linea no vacia tras frontmatter
        md = re.sub(r"^---.*?---\s*", "", md, flags=re.S)
        for ln in md.splitlines():
            s = ln.strip()
            if s and not s.startswith("#") and len(s) > 20:
                return s[:110]
            if s.startswith("# "):
                return s[2:110]
        return ""
    except Exception:
        return ""
skill_rows = []
for base in [os.path.expanduser(r"~\.config\opencode\skills"), os.path.join(ROOT, ".opencode", "skills")]:
    if not os.path.isdir(base): continue
    scope = "global" if "config" in base else "project"
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d)
        if not os.path.isdir(p): continue
        skill_rows.append({"id": d, "scope": scope, "desc": skill_desc(p)})
# sort global first
skill_rows.sort(key=lambda x: (x["scope"] != "global", x["id"]))

# --- tareas: goals + crons + calendario
goals = []
for st in ("active", "archive"):
    gd = os.path.join(ROOT, ".opencode", "goals", st)
    if not os.path.isdir(gd): continue
    for f in sorted(os.listdir(gd)):
        if not f.endswith(".md"): continue
        txt = open(os.path.join(gd, f), encoding="utf-8-sig", errors="ignore").read()
        title = txt.splitlines()[0].lstrip("# ").strip()[:90] if txt else f
        # success_criteria si existe
        m = re.search(r"success_criteria.*?:\s*(.+)", txt, re.I)
        crit = (m.group(1).strip()[:70] if m else "")
        goals.append({"id": f[:-3], "estado": st, "titulo": title, "crit": crit})

crons, runs = [], {}
cj = os.path.join(ROOT, ".opencode", "cron", "jobs.json")
if os.path.exists(cj):
    try: crons = json.load(open(cj, encoding="utf-8"))
    except Exception: crons = []
rd = os.path.join(ROOT, ".opencode", "cron", "runs")
if os.path.isdir(rd):
    for f in os.listdir(rd):
        if f.endswith(".json"):
            try: runs[f[:-5]] = json.load(open(os.path.join(rd, f), encoding="utf-8"))
            except Exception: pass

# --- git 7d por proyecto (build-time, ponytail: 15 líneas, degradación elegante)
import subprocess
git_rows=[]
# proyectos desde consumo (short name -> path). Reconstruir paths desde DB
try:
    con3=sqlite3.connect(os.path.expanduser("~/.local/share/opencode/opencode.db"))
    cur3=con3.cursor()
    cur3.execute("SELECT id, worktree FROM project")
    p2w=dict(cur3.fetchall())
    cur3.execute("SELECT id, project_id FROM session")
    s2p=dict(cur3.fetchall())
    cur3.execute("SELECT session_id, data FROM message WHERE json_extract(data,'$.role')='assistant'")
    paths=set()
    for sid,d in cur3.fetchall():
        try:
            o=json.loads(d)
            wt=p2w.get(s2p.get(sid,""), "")
            cwd=(o.get("path") or {}).get("cwd") or wt
            if cwd: paths.add(cwd)
        except: pass
    con3.close()
    for p in sorted(paths)[:14]:
        commits=lines_add=lines_del="—"
        try:
            commits=subprocess.check_output(["git","-C",p,"log","--since=7 days","--oneline"], text=True, stderr=subprocess.DEVNULL).strip().count("\n")+1 if os.path.isdir(os.path.join(p,".git")) else 0
            if commits==1 and not subprocess.check_output(["git","-C",p,"log","--since=7 days","--oneline"], text=True, stderr=subprocess.DEVNULL).strip(): commits=0
            ns=subprocess.check_output(["git","-C",p,"log","--since=7 days","--numstat","--pretty=format:"], text=True, stderr=subprocess.DEVNULL)
            lines_add=lines_del=0
            for line in ns.splitlines():
                parts=line.split()
                if len(parts)>=2 and parts[0].isdigit(): lines_add+=int(parts[0])
                if len(parts)>=2 and parts[1].isdigit(): lines_del+=int(parts[1])
        except: pass
        short=os.path.basename(p.rstrip("/\\")) or p
        git_rows.append((short, commits, lines_add, lines_del, p))
except Exception as e:
    git_rows=[("err",0,0,0,str(e)[:40])]

# calendario: el render es JS (estilo Pomodoro), no pre-render estático

payload = {
    "daily": {d: {"t": e["t"], "c": round(e["c"], 4), "k": e["k"],
        "proj": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(e["proj"].items(), key=lambda x: -x[1][0])],
        "mod": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(e["mod"].items(), key=lambda x: -x[1][0])]} for d, e in daily.items()},
    "ranges": {k: {"t": v[0], "c": round(v[1], 4), "k": v[2],
        "proj": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(v[3].items(), key=lambda x: -x[1][0])],
        "mod": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(v[4].items(), key=lambda x: -x[1][0])]}
        for k, v in R.items()},
    "hourly": {h: {"t": v[0], "c": round(v[1], 4), "k": v[2]} for h, v in sorted(hourly.items())},
}
cards = [("Hoy", t_today["t"], t_today["c"], t_today["k"]), ("Ultimos 7 dias", *R["d7"][:3]),
         ("Ultimos 30 dias", *R["d30"][:3]), ("Total historico", R["total"][0], R["total"][1], msgs)]
cards_html = "".join(
    "<div class='card'><h3>" + c[0] + "</h3><div class='big'>" + fmt_tok(c[1]) + "</div>"
    "<div class='row'><span>$" + ("%.2f" % c[2]) + "</span><span>" + str(c[3]) + " msgs</span></div></div>"
    for c in cards)

def goal_row(g):
    pill = "grn" if g["estado"] == "active" else "dim"
    return "<tr><td>" + html.escape(g["id"]) + "</td><td>" + html.escape(g["titulo"]) + "</td><td class='dim'>" + html.escape(g["crit"]) + "</td><td><span class='pill " + pill + "'>" + g["estado"] + "</span></td></tr>"
goal_rows = "".join(goal_row(g) for g in goals) or "<tr><td colspan=4>sin goals</td></tr>"
def cron_row(j):
    sched = j.get("schedule") or {}
    spec = sched.get("cron") or (str(sched.get("everyMs",""))+"ms" if sched.get("everyMs") else sched.get("kind",""))
    name = j.get("name") or j.get("id","?")
    st = runs.get(j.get("id",""), {}) or {}
    on = j.get("enabled")
    pill = "grn" if on else "dim"
    return ("<tr><td>" + html.escape(str(name)) + "</td><td><code>" + html.escape(str(spec)) + "</code></td>"
            "<td><span class='pill " + pill + "'>" + ("on" if on else "off") + "</span></td>"
            "<td>" + html.escape(str(st.get("status","-"))) + "</td></tr>")
cron_rows = "".join(cron_row(j) for j in crons) or "<tr><td colspan=4>0 crons — crea uno con <code>/skill_cron</code></td></tr>"

agent_rows = "".join(
    "<tr><td><code>" + html.escape(a["id"]) + "</code></td><td>" + html.escape(a["desc"]) + "</td><td><span class='pill dim'>" + html.escape(a["mode"]) + "</span></td><td class='dim' style='font-size:12px'>" + html.escape(a["tools"]) + "</td></tr>"
    for a in agents) or "<tr><td colspan=4>—</td></tr>"
mcp_rows = "".join(
    "<tr><td><code>" + html.escape(m["id"]) + "</code></td><td>" + html.escape(m["type"]) + "</td><td><span class='pill " + ("grn" if m["enabled"] else "dim") + "'>" + ("on" if m["enabled"] else "off") + "</span></td><td class='dim'><code>" + html.escape(m["cmd"]) + "</code></td></tr>"
    for m in mcps) or "<tr><td colspan=4>—</td></tr>"
# skills: mostrar primeras 40 + buscador JS filtra el resto
max_vis = 40
skill_tr = "".join(
    "<tr data-skill='" + html.escape(s["id"]) + "'><td><code>" + html.escape(s["id"]) + "</code></td><td><span class='pill " + ("grn" if s['scope']=="global" else "dim") + "'>" + s["scope"] + "</span></td><td class='dim'>" + html.escape(s["desc"]) + "</td></tr>"
    for s in skill_rows[:max_vis])
skill_more = len(skill_rows) - max_vis
skill_more_row = ("<tr id='skill-more'><td colspan=3 class='dim'>+" + str(skill_more) + " mas — usa el filtro para verlos (total " + str(len(skill_rows)) + ")</td></tr>") if skill_more>0 else ""
# para el filtro JS necesitamos todos
skill_json = json.dumps([{"id": s["id"], "scope": s["scope"], "desc": s["desc"]} for s in skill_rows], ensure_ascii=False)

# tool & cache html (build-time)
total_cache = cache_in + cache_read + cache_write
hit = (cache_read / total_cache * 100) if total_cache else 0
cache_html = f"<div class='grid' style='grid-template-columns:repeat(3,1fr)'><div class='card'><h3>Cache hit</h3><div class='big'>{hit:.1f}%</div><div class='row'><span>read {fmt_tok(cache_read)}</span><span>input {fmt_tok(cache_in)}</span></div></div><div class='card'><h3>Tokens cache</h3><div class='big'>{fmt_tok(cache_read+cache_write)}</div><div class='row'><span>write {fmt_tok(cache_write)}</span><span>out {fmt_tok(cache_out)}</span></div></div><div class='card'><h3>Herramientas</h3><div class='big'>{len(tool_cnt)}</div><div class='row'><span>distintas</span><span>{sum(tool_cnt.values())} llamadas</span></div></div></div>"
tool_rows = "".join(f"<tr><td><code>{html.escape(k)}</code></td><td class='num'>{v}</td><td>{''.join(['' for _ in [1]])}{'<div class=\"bar\"><i style=\"width:'+str(max(4, v*100//max(max(tool_cnt.values()),1)))+'%\" ></i></div>'}</td></tr>" for k,v in sorted(tool_cnt.items(), key=lambda x:-x[1])[:10]) or "<tr><td colspan=3>sin datos tool</td></tr>"

git_html_rows = "".join(f"<tr><td title='{html.escape(p[4])}'>{html.escape(p[0])}</td><td class='num'>{p[1]}</td><td class='num' style='color:#3fb950'>+{p[2]}</td><td class='num' style='color:#f85149'>-{p[3]}</td></tr>" for p in git_rows) or "<tr><td colspan=4>sin datos git</td></tr>"

# calendario se pinta en JS (estilo Pomodoro); no hay cal estático

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

TPL = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>OpenCode · Centro de control</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--line:#262c36;--txt:#e6edf3;--dim:#8b949e;--acc:#58a6ff;--grn:#3fb950}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.5 -apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:24px 20px 60px}
.top{display:flex;align-items:center;gap:12px}.dot{width:12px;height:12px;border-radius:50%;background:var(--grn);box-shadow:0 0 8px var(--grn)}
h1{font-size:22px;margin:0}.sub{color:var(--dim);margin:4px 0 18px}
.nav{display:flex;gap:8px;margin-bottom:18px;border-bottom:1px solid var(--line);padding-bottom:0}
.nav button{background:transparent;color:var(--dim);border:0;border-bottom:2px solid transparent;padding:10px 14px;cursor:pointer;font-size:13px;margin-bottom:-1px}
.nav button.on{color:var(--txt);border-color:var(--acc)}
.tabs{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.tabs button{background:var(--panel);color:var(--dim);border:1px solid var(--line);border-radius:20px;padding:7px 16px;cursor:pointer;font-size:13px}
.tabs button.on{background:#1f6feb;color:#fff;border-color:#1f6feb}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:8px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h3{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim)}
.card .big{font-size:26px;font-weight:700}.card .row{display:flex;justify-content:space-between;color:var(--dim);margin-top:4px}
h2{font-size:15px;margin:22px 0 10px;color:var(--dim);text-transform:uppercase;letter-spacing:.06em}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:8px 16px;overflow-x:auto}
table{width:100%;border-collapse:collapse;table-layout:fixed}th{text-align:left;font-size:12px;color:var(--dim);padding:10px 8px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{width:auto}
th.num,td.num{text-align:right;font-variant-numeric:tabular-nums;font-feature-settings:"tnum";white-space:nowrap;width:92px;min-width:92px}
th.num:nth-child(3),td.num:nth-child(3){width:78px;min-width:78px}
th.num:nth-child(4),td.num:nth-child(4){width:92px;min-width:92px}
th.num:last-of-type,td.num:last-of-type{width:72px;min-width:72px}
table.cols-5 th.num,table.cols-5 td.num{width:92px}
table.cols-4 th.num,table.cols-4 td.num{width:92px}
td{padding:9px 8px;border-bottom:1px solid var(--line)}tr:last-child td{border-bottom:0}
.num{text-align:right;font-variant-numeric:tabular-nums;font-feature-settings:"tnum";white-space:nowrap}
.bar{height:6px;background:#21262d;border-radius:4px;min-width:120px}.bar i{display:block;height:100%;background:var(--acc);border-radius:4px}
.days{display:flex;align-items:flex-end;gap:6px;min-height:170px;padding:16px;overflow-x:auto}
.db{flex:1;min-width:34px;display:flex;flex-direction:column;align-items:center;gap:6px;height:150px;justify-content:flex-end}
.db i{width:70%;background:linear-gradient(180deg,var(--acc),#1f6feb);border-radius:4px 4px 0 0;min-height:2px}
.db span{font-size:11px;color:var(--dim)}
.foot{color:var(--dim);margin-top:26px;font-size:12px}
.pill{display:inline-block;background:#0f3d2e;color:var(--grn);border-radius:20px;padding:2px 10px;font-size:12px}
.pill.dim{background:#21262d;color:var(--dim)}code{background:#21262d;padding:1px 6px;border-radius:6px;font-size:12px}
.rangelabel{color:var(--dim);font-size:13px;margin:0 0 10px}
.view{display:none}.view.on{display:block}
.filter{width:100%;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px 12px;color:var(--txt);margin-bottom:12px}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin:10px 0}
.cal-h{font-size:11px;color:var(--dim);text-align:center;font-weight:700;padding:6px 0}
.cal-day{aspect-ratio:1;border-radius:12px;border:1px solid var(--line);background:var(--panel);cursor:pointer;font-size:13px;display:flex;align-items:center;justify-content:center;min-height:42px}
.cal-day.has{background:#1f3a5f;border-color:#1f3a5f;color:var(--txt);font-weight:700}
.cal-day.sel{background:var(--txt);color:var(--bg);border-color:var(--txt)}
.cal-day.muted{opacity:.35;pointer-events:none}
.cal-nav{display:flex;align-items:center;justify-content:space-between;margin:0 0 10px}
.cal-nav b{font-size:14px;text-transform:capitalize}
.cal-nav button{width:auto;margin:0;padding:8px 14px;border:1px solid var(--line);background:var(--panel);color:var(--txt);border-radius:10px;cursor:pointer}
.cal-nav button:hover{border-color:var(--txt)}
.cal-detail{margin-top:12px}
.cal-detail .hint{font-size:12px;color:var(--dim)}
.small{color:var(--dim);font-size:12px;margin:6px 0}
.small.ghost{border:1px solid var(--line);background:transparent;color:var(--txt);border-radius:10px;padding:8px 14px;cursor:pointer}
</style></head><body><div class="wrap">
<div class="top"><span class="dot"></span><h1>Centro de control</h1><label id="ar-wrap" style="display:none"><input type="checkbox" id="ar" checked></label></div>
<p class="sub">Fuente: <code>opencode.db</code> · __MSGS__ mensajes · <code>opencode.json</code> · generado __NOW__</p>
<div class="nav" id="nav"><button data-v="consumo" class="on">Consumo</button><button data-v="recursos">Recursos</button><button data-v="tareas">Tareas</button></div>

<div id="view-consumo" class="view on">
<div class="grid">__CARDS__</div>
<div class="tabs" id="tabs"><button data-r="total" class="on">Total</button><button data-r="d30">Ultimos 30 dias</button><button data-r="d7">Ultimos 7 dias</button><button data-r="d1">Hoy</button></div>
<p class="rangelabel" id="rangelabel"></p>
<h2>Actividad diaria · ultimos 7 dias (fija)</h2><div class="panel"><div class="days" id="days"></div></div>
<h2 id="t-proj">Por proyecto</h2><div class="panel"><table><tr><th>Proyecto</th><th class="num">Tokens</th><th class="num">Coste</th><th class="num">Coste/msg</th><th class="num">Msgs</th><th></th></tr><tbody id="projs"></tbody></table></div>
<h2>Por modelo (del rango)</h2><div class="panel"><table><tr><th>Modelo</th><th class="num">Tokens</th><th class="num">Coste</th><th class="num">Coste/msg</th><th class="num">Msgs</th><th></th></tr><tbody id="mods"></tbody></table></div>
<h2>Herramientas & caché</h2>__CACHE_HTML__<div class="panel"><table><tr><th>Herramienta</th><th class="num">Llamadas</th><th></th></tr>__TOOL_ROWS__</table><p class="small">MCPs con 0 llamadas = dead weight. Cache alto (>90%) = bien. Datos de <code>part.type=tool</code> + <code>message.tokens.cache</code>.</p></div>
<h2>Git · últimos 7 días</h2><div class="panel"><table><tr><th>Proyecto</th><th class="num">Commits</th><th class="num">Líneas +</th><th class="num">Líneas -</th></tr>__GIT_ROWS__</table><p class="small">Si un proyecto no es git, muestra 0. Coste por commit = coste 7d / commits.</p></div>
</div>

<div id="view-recursos" class="view">
<p class="small">__NAGENTS__ agentes · __NSKILLS__ skills (global+proyecto) · __NMCP__ MCPs — desde <code>~/.config/opencode/opencode.json</code></p>
<h2>Agentes</h2><div class="panel"><table><tr><th>Agente</th><th>Descripcion</th><th>Mode</th><th>Tools</th></tr>__AGENTS__</table></div>
<h2>MCPs</h2><div class="panel"><table><tr><th>MCP</th><th>Type</th><th>Enabled</th><th>Command</th></tr>__MCPS__</table></div>
<h2>Skills</h2>
<input id="skill-filter" class="filter" placeholder="Filtrar skills… (escribe 'seo', 'cron', etc.)">
<div class="panel"><table><tr><th>Skill</th><th>Scope</th><th>Descripcion</th></tr><tbody id="skill-body">__SKILLS__</tbody></table><p class="small" id="skill-count"></p></div>
</div>

<div id="view-tareas" class="view">
<h2>Goals (__NGOALS__)</h2><div class="panel"><table><tr><th>ID</th><th>Titulo</th><th>Criteria</th><th>Estado</th></tr>__GOALS__</table></div>
<h2>Crons (__NCRONS__)</h2><div class="panel"><table><tr><th>Nombre</th><th>Schedule</th><th>Enabled</th><th>Ultimo run</th></tr>__CRONS__</table></div>
<div class="panel"><div class="cal-nav"><button id="calPrev">‹</button><b id="calLabel">—</b><button id="calNext">›</button></div><div id="calGrid" class="cal-grid"></div><div id="calDetail" class="cal-detail"><span class="hint">Toca un dia para ver su resumen.</span></div><p class="small">Fondo azulado = dia con gasto · invertido = hoy/seleccion · atenuado = futuro.</p></div>
</div>

<p class="foot">Regenerar: <code>python scripts/gen-dashboard.py</code> · Consumo filtra por rango (tabs); Recursos/Tareas son inventario vivo.</p>
</div>
<script>
var D = __DATA__;
var SKILLS_ALL = __SKILL_JSON__;
var NAMES = {total:"todas las fechas con datos",d30:"ultimos 30 dias",d7:"ultimos 7 dias",d1:"hoy"};
function fmt(n){if(n>=1e9)return(n/1e9).toFixed(2)+"B";if(n>=1e6)return(n/1e6).toFixed(1)+"M";if(n>=1e3)return(n/1e3).toFixed(0)+"K";return""+n;}
function avg(c,k){var v=k?c/k:0;return "$"+v.toFixed(4);}
function bar(p){return "<div class='bar'><i style='width:"+Math.max(p,1.5).toFixed(1)+"%'></i></div>";}
// top nav
var navBtns = document.querySelectorAll("#nav button");
for(var ni=0;ni<navBtns.length;ni++){(function(b){b.addEventListener("click",function(){
  for(var j=0;j<navBtns.length;j++){navBtns[j].classList.remove("on");document.getElementById("view-"+navBtns[j].getAttribute("data-v")).classList.remove("on");}
  b.classList.add("on");document.getElementById("view-"+b.getAttribute("data-v")).classList.add("on");
});})(navBtns[ni]);}
// consumo range
function render(r){
  var R = D.ranges[r], label = NAMES[r];
  var rl = document.getElementById("rangelabel"); if(rl) rl.textContent = "Mostrando: "+label+" · "+fmt(R.t)+" tokens · $"+R.c.toFixed(2)+" · "+R.k+" msgs";
  var tbs = document.querySelectorAll("#tabs button");
  for(var i=0;i<tbs.length;i++){tbs[i].classList.toggle("on",tbs[i].getAttribute("data-r")===r);}
  var box = document.getElementById("days");
  if(box && !box.hasChildNodes()){
    var all = Object.keys(D.daily).sort();
    var days = all.slice(-7).map(function(d){return {l:d.slice(5),t:D.daily[d].t,c:D.daily[d].c};});
    var mx = 1, j; for(j=0;j<days.length;j++){if(days[j].t>mx)mx=days[j].t;}
    for(j=0;j<days.length;j++){var x=days[j],d=document.createElement("div");d.className="db";d.title=x.l+": "+fmt(x.t)+" / $"+x.c.toFixed(2);d.innerHTML="<i style='height:"+Math.max(x.t/mx*100,1.5).toFixed(1)+"%'></i><span>"+x.l+"</span>";box.appendChild(d);}
  }
  var mxp = 1, j; for(j=0;j<R.proj.length;j++){if(R.proj[j][1]>mxp)mxp=R.proj[j][1];}
  var ph="",mh="";
  for(j=0;j<R.proj.length;j++){var p=R.proj[j];ph+="<tr><td>"+p[0]+"</td><td class='num'>"+fmt(p[1])+"</td><td class='num'>$"+p[2].toFixed(2)+"</td><td class='num'>"+avg(p[2],p[3])+"</td><td class='num'>"+p[3]+"</td><td>"+bar(p[1]/mxp*100)+"</td></tr>";}
  for(j=0;j<R.mod.length;j++){var m=R.mod[j];mh+="<tr><td>"+m[0]+"</td><td class='num'>"+fmt(m[1])+"</td><td class='num'>$"+m[2].toFixed(2)+"</td><td class='num'>"+avg(m[2],m[3])+"</td><td class='num'>"+m[3]+"</td><td></td></tr>";}
  var pe=document.getElementById("projs"), me=document.getElementById("mods");
  if(pe) pe.innerHTML = ph || "<tr><td colspan=5>sin datos en este rango</td></tr>";
  if(me) me.innerHTML = mh || "<tr><td colspan=5>sin datos</td></tr>";
  var tp=document.getElementById("t-proj"); if(tp) tp.textContent="Por proyecto ("+label+")";
}
var rbtns = document.querySelectorAll("#tabs button");
for(var i2=0;i2<rbtns.length;i2++){(function(b){b.addEventListener("click",function(){render(b.getAttribute("data-r"));});})(rbtns[i2]);}
render("total");
// skill filter
var sf = document.getElementById("skill-filter");
var sb = document.getElementById("skill-body");
var sc = document.getElementById("skill-count");
function skillRender(q){
  q=(q||"").toLowerCase();
  var vis=0, html="";
  for(var i=0;i<SKILLS_ALL.length;i++){var s=SKILLS_ALL[i]; if(q && s.id.toLowerCase().indexOf(q)===-1 && s.desc.toLowerCase().indexOf(q)===-1) continue; vis++; html+="<tr><td><code>"+s.id+"</code></td><td><span class='pill "+(s.scope==="global"?"grn":"dim")+"'>"+s.scope+"</span></td><td class='dim'>"+s.desc.replace(/</g,"&lt;")+"</td></tr>"; if(!q && vis>=40) break; }
  // si hay filtro, mostrar todos los matching sin limite 40
  if(q){ html=""; vis=0; for(var j=0;j<SKILLS_ALL.length;j++){var t=SKILLS_ALL[j]; if(t.id.toLowerCase().indexOf(q)===-1 && t.desc.toLowerCase().indexOf(q)===-1) continue; vis++; html+="<tr><td><code>"+t.id+"</code></td><td><span class='pill "+(t.scope==="global"?"grn":"dim")+"'>"+t.scope+"</span></td><td class='dim'>"+t.desc.replace(/</g,"&lt;")+"</td></tr>"; } }
  sb.innerHTML = html || "<tr><td colspan=3>sin coincidencias</td></tr>";
  sc.textContent = vis+" / "+SKILLS_ALL.length+" skills";
}
if(sf){ sf.addEventListener("input", function(){ skillRender(sf.value); }); skillRender(""); }
// auto-refresh oculto pero marcado: Ctrl+F5 manual
var ar=document.getElementById('ar'); if(ar){ ar.checked=true; var iv=setInterval(()=>location.reload(),30000); document.addEventListener('keydown', function(e){ if(e.ctrlKey && e.key==='F5'){ e.preventDefault(); location.reload(); } if(e.ctrlKey && e.key.toLowerCase()==='r' && e.shiftKey){ e.preventDefault(); location.reload(); } }); }
// ordenable 3 estados: desc -> asc -> default (fix cross-table)
function parseVal(txt){
  txt=(txt||'').trim();
  if(!txt) return -1;
  if(txt[0]==='$') txt=txt.slice(1);
  if(/[BMK]$/.test(txt)){ var n=parseFloat(txt); if(txt.endsWith('B')) return n*1e9; if(txt.endsWith('M')) return n*1e6; if(txt.endsWith('K')) return n*1e3; return n; }
  var v=parseFloat(txt.replace(/,/g,'')); return isNaN(v)? txt.toLowerCase() : v;
}
document.addEventListener('click', function(e){
  var th=e.target.closest('th'); if(!th) return;
  var table=th.closest('table'); if(!table || !table.closest('.panel')) return;
  if(th.textContent.trim()==='') return;
  var ths=[...table.querySelectorAll('th')];
  var col=ths.indexOf(th);
  var tbodies=[...table.querySelectorAll('tbody')];
  var tbody=tbodies.find(tb=>tb.querySelector('td')) || table.querySelector('tbody') || table;
  var rows=[...tbody.querySelectorAll('tr')];
  if(!rows.length) return;
  if(!table._orig) table._orig=rows.map(r=>r.cloneNode(true));
  var next = th._sortState===1?2: th._sortState===2?0:1;
  ths.forEach(h=>{ if(h!==th) h._sortState=0; h.textContent=h.textContent.replace(/ [▲▼]$/,''); });
  th._sortState=next;
  ths.forEach(h=>{ h.textContent=h.textContent.replace(/ [▲▼]$/,''); if(h._sortState===1) h.textContent+=' ▼'; else if(h._sortState===2) h.textContent+=' ▲'; });
  if(next===0){ tbody.innerHTML=''; table._orig.forEach(r=>tbody.appendChild(r.cloneNode(true))); return; }
  rows.sort((a,b)=>{
    var av=parseVal(a.children[col]?.textContent), bv=parseVal(b.children[col]?.textContent);
    if(typeof av==='string' && typeof bv==='string') return next===1? bv.localeCompare(av) : av.localeCompare(bv);
    if(typeof av==='string') return 1; if(typeof bv==='string') return -1;
    return next===1? bv-av : av-bv;
  });
  tbody.innerHTML=''; rows.forEach(r=>tbody.appendChild(r));
});
document.querySelectorAll('.panel table th').forEach(th=>{ if(th.textContent.trim()!==''){ th.style.cursor='pointer'; th.title='Ordenar'; } });
// calendario estilo Pomodoro (historial.js) + detalle por dia
var calY=new Date().getFullYear(), calM=new Date().getMonth(), calSel=null;
function calDetail(iso){
  var det=document.getElementById("calDetail"), rec=D.daily[iso];
  if(!det) return;
  if(!rec || !rec.t){ det.innerHTML='<span class="hint">'+iso+' · sin actividad</span>'; return; }
  var hdr='<b>'+iso+'</b> · '+fmt(rec.t)+' tokens · $'+rec.c.toFixed(2)+' · '+rec.k+' consultas';
  var html=hdr;
  if(rec.proj && rec.proj.length){
    html+='<div class="panel" style="margin-top:10px"><table><tr><th>Proyecto</th><th class="num">Tokens</th><th class="num">Coste</th><th class="num">Coste/msg</th><th class="num">Msgs</th></tr>';
    for(var i=0;i<rec.proj.length;i++){var p=rec.proj[i]; var a=p[3]?p[2]/p[3]:0; var av=a.toFixed(4); html+='<tr><td>'+p[0]+'</td><td class="num">'+fmt(p[1])+'</td><td class="num">$'+p[2].toFixed(2)+'</td><td class="num">$'+av+'</td><td class="num">'+p[3]+'</td></tr>';}
    html+='</table></div>';
  }
  if(rec.mod && rec.mod.length){
    html+='<div class="panel" style="margin-top:10px"><table><tr><th>Modelo</th><th class="num">Tokens</th><th class="num">Coste</th><th class="num">Coste/msg</th><th class="num">Msgs</th></tr>';
    for(var j=0;j<rec.mod.length;j++){var m=rec.mod[j]; var aa=m[3]?m[2]/m[3]:0; var av2=aa.toFixed(4); html+='<tr><td>'+m[0]+'</td><td class="num">'+fmt(m[1])+'</td><td class="num">$'+m[2].toFixed(2)+'</td><td class="num">$'+av2+'</td><td class="num">'+m[3]+'</td></tr>';}
    html+='</table></div>';
  }
  det.innerHTML=html;
}
function renderCal(){
  var grid=document.getElementById("calGrid"), lab=document.getElementById("calLabel");
  if(!grid||!lab) return;
  var first=new Date(calY, calM, 1), start=(first.getDay()+6)%7, dim=new Date(calY, calM+1, 0).getDate();
  lab.textContent=first.toLocaleDateString("es-ES",{month:"long", year:"numeric"});
  grid.innerHTML="";
  var heads=["L","M","X","J","V","S","D"];
  for(var h=0;h<heads.length;h++){ var e=document.createElement("div"); e.className="cal-h"; e.textContent=heads[h]; grid.appendChild(e); }
  for(var s=0;s<start;s++){ var pad=document.createElement("div"); grid.appendChild(pad); }
  var todayIso=new Date().toISOString().slice(0,10);
  for(var d=1; d<=dim; d++){
    var iso=calY+"-"+String(calM+1).padStart(2,"0")+"-"+String(d).padStart(2,"0");
    var rec=D.daily[iso], has=rec&&rec.t>0;
    var b=document.createElement("button"); b.className="cal-day"+(has?" has":"")+(iso===todayIso?" sel":"")+(calSel===iso?" sel":"");
    if(iso>todayIso) b.classList.add("muted");
    b.textContent=d; b.title=iso+(has?" · "+fmt(rec.t)+" / $"+rec.c.toFixed(2):" · sin actividad");
    (function(iso2){ b.onclick=function(){calSel=iso2; renderCal(); calDetail(iso2);}; })(iso);
    grid.appendChild(b);
  }
}
var cp=document.getElementById("calPrev"), cn=document.getElementById("calNext");
if(cp) cp.onclick=function(){calM--; if(calM<0){calM=11;calY--;} renderCal();};
if(cn) cn.onclick=function(){calM++; if(calM>11){calM=0;calY++;} var now=new Date(); if(calY>now.getFullYear()||(calY===now.getFullYear()&&calM>now.getMonth())){calM=now.getMonth();calY=now.getFullYear();} renderCal();};
renderCal();
var todayIsoInit=new Date().toISOString().slice(0,10);
if(D.daily[todayIsoInit]&&D.daily[todayIsoInit].t>0){calSel=todayIsoInit; renderCal(); calDetail(todayIsoInit);}
</script></body></html>"""

doc = TPL.replace("__MSGS__", str(msgs)).replace("__NOW__", now).replace("__CARDS__", cards_html)
doc = doc.replace("__CACHE_HTML__", cache_html).replace("__TOOL_ROWS__", tool_rows).replace("__GIT_ROWS__", git_html_rows)
doc = doc.replace("__GOALS__", goal_rows).replace("__CRONS__", cron_rows)
doc = doc.replace("__NGOALS__", str(len(goals))).replace("__NCRONS__", str(len(crons)))
doc = doc.replace("__AGENTS__", agent_rows).replace("__MCPS__", mcp_rows).replace("__SKILLS__", skill_tr + skill_more_row)
doc = doc.replace("__NAGENTS__", str(len(agents))).replace("__NSKILLS__", str(len(skill_rows))).replace("__NMCP__", str(len(mcps)))
doc = doc.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
doc = doc.replace("__SKILL_JSON__", json.dumps([{"id": s["id"], "scope": s["scope"], "desc": s["desc"]} for s in skill_rows], ensure_ascii=False))
out = os.path.join(ROOT, "dashboard.html")
open(out, "w", encoding="utf-8").write(doc)
print("OK ->", out, "| consumo total=" + fmt_tok(R["total"][0]), "| agentes=" + str(len(agents)), "skills=" + str(len(skill_rows)), "mcps=" + str(len(mcps)), "| goals=" + str(len(goals)), "crons=" + str(len(crons)))
