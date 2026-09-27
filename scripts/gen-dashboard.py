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
cur.execute("SELECT id, parent_id FROM session")
sess_parent = {r[0]: r[1] for r in cur.fetchall()}
# mapa session -> agent (primer mensaje assistant, ordenado por tiempo)
sess_agent = {}
enjambre_sessions = set()
try:
    cur.execute("SELECT session_id, data, time_created FROM message WHERE json_extract(data,'$.role')='assistant' ORDER BY time_created ASC")
    for sid2, d2, _tc2 in cur.fetchall():
        try:
            j2 = json.loads(d2)
            ag2 = (j2.get("agent") or "").strip()
            if ag2 and sid2 not in sess_agent:
                sess_agent[sid2] = ag2
            if ag2 and ag2.lower() == "enjambre":
                enjambre_sessions.add(sid2)
        except: pass
    # también sesiones que contienen Enjambre aunque no sea el primer mensaje (sesiones mixtas build+Enjambre)
    cur.execute("SELECT DISTINCT session_id FROM message WHERE lower(json_extract(data,'$.agent'))='enjambre'")
    for (sid_e,) in cur.fetchall():
        enjambre_sessions.add(sid_e)
except: pass
def root_agent_of(sid, fallback_ag):
    # familia genérica: si la cadena de padres contiene una sesión Enjambre, la familia es Enjambre
    # esto une cualquier subagente (general/explore) nacido bajo Enjambre, sin hardcodear más casos
    # para otros orquestadores futuros, el mismo patrón vale: basta con que la sesión padre esté marcada
    cur_sid = sid
    chain = [cur_sid]
    seen = set()
    for _ in range(20):
        par = sess_parent.get(cur_sid)
        if not par or par in seen: break
        seen.add(cur_sid)
        chain.append(par)
        cur_sid = par
    for c in chain:
        if c in enjambre_sessions:
            return "Enjambre"
    # si no hay Enjambre en la cadena, familia = agente del mensaje (normalizado)
    ag = (fallback_ag or "?").strip()
    n = ag.lower()
    if n == "enjambre": return "Enjambre"
    return n

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
    ag = (j.get("agent", "?") or "?").strip()
    fam = root_agent_of(sid, ag)
    e = daily.setdefault(day, {"t": 0, "c": 0.0, "k": 0, "proj": {}, "mod": {}, "agt": {}})
    e["t"] += t; e["c"] += c; e["k"] += 1
    p = e["proj"].setdefault(short, [0, 0.0, 0]); p[0] += t; p[1] += c; p[2] += 1
    mb = e["mod"].setdefault(m, [0, 0.0, 0]); mb[0] += t; mb[1] += c; mb[2] += 1
    ab = e["agt"].setdefault(fam, [0, 0.0, 0]); ab[0] += t; ab[1] += c; ab[2] += 1
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
    pt, md, ag = {}, {}, {}
    t = c = k = 0
    for d in days:
        e = daily.get(d)
        if not e: continue
        t += e["t"]; c += e["c"]; k += e["k"]
        for n, v in e["proj"].items():
            b = pt.setdefault(n, [0, 0.0, 0]); b[0] += v[0]; b[1] += v[1]; b[2] += v[2]
        for n, v in e["mod"].items():
            b = md.setdefault(n, [0, 0.0, 0]); b[0] += v[0]; b[1] += v[1]; b[2] += v[2]
        for n, v in e.get("agt",{}).items():
            b = ag.setdefault(n, [0, 0.0, 0]); b[0] += v[0]; b[1] += v[1]; b[2] += v[2]
    return t, c, k, pt, md, ag

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

# --- Inicio: eficiencia $/k neto (local, sin API, ponytail: heurística coste por autor = C_día / nº autores activos ese día)
inicio_cards_html = ""
inicio_chart_json = "[]"
inicio_author_rows = ""
inicio_team_eff = 0
try:
    # reutilizar paths ya descubiertos, si no los hay re-derívamos rápido
    try:
        all_paths = sorted(paths)[:14]
    except NameError:
        all_paths = []
        try:
            con_tmp = sqlite3.connect(os.path.expanduser("~/.local/share/opencode/opencode.db"))
            cur_tmp = con_tmp.cursor()
            cur_tmp.execute("SELECT id, worktree FROM project")
            p2w_tmp = dict(cur_tmp.fetchall())
            cur_tmp.execute("SELECT id, project_id FROM session")
            s2p_tmp = dict(cur_tmp.fetchall())
            cur_tmp.execute("SELECT session_id, data FROM message WHERE json_extract(data,'$.role')='assistant'")
            s = set()
            for sid, d in cur_tmp.fetchall():
                try:
                    o = json.loads(d); wt = p2w_tmp.get(s2p_tmp.get(sid, ""), ""); cwd = (o.get("path") or {}).get("cwd") or wt
                    if cwd: s.add(cwd)
                except: pass
            con_tmp.close()
            all_paths = sorted(s)[:14]
        except: all_paths = []
    import collections
    author_daily = collections.defaultdict(lambda: collections.defaultdict(int))  # key(lower) -> day -> net (solo rework)
    author_churn_daily = collections.defaultdict(lambda: collections.defaultdict(int))  # key(lower) -> day -> churn a+d
    author_commits = collections.Counter()
    author_add = collections.Counter()
    author_del = collections.Counter()
    author_display = {}  # lower -> display original
    day_authors = collections.defaultdict(set)  # day -> set(lower)
    day_net = collections.Counter()
    day_churn = collections.Counter()
    # parse git log por proyecto últimos 90d
    for p in all_paths:
        if not os.path.isdir(os.path.join(p, ".git")): continue
        try:
            out = subprocess.check_output(["git","-C",p,"log","--all","--since=90 days","--pretty=format:%aN%x1f%ct","--numstat"], text=True, stderr=subprocess.DEVNULL, errors="ignore")
        except: continue
        cur_author = cur_day = cur_key = None
        for line in out.splitlines():
            if "\x1f" in line:
                parts = line.split("\x1f")
                disp = parts[0].strip() or "unknown"; cur_key = disp.lower()
                cur_author = disp
                author_display.setdefault(cur_key, disp)
                try: cur_day = datetime.datetime.fromtimestamp(int(parts[1])).strftime("%Y-%m-%d")
                except: cur_day = None
                if cur_day: author_commits[cur_key] += 1; day_authors[cur_day].add(cur_key)
                continue
            if cur_key is None or cur_day is None: continue
            parts = line.split()
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                a, d = int(parts[0]), int(parts[1]); net = a - d; churn = a + d
                author_daily[cur_key][cur_day] += net
                author_churn_daily[cur_key][cur_day] += churn
                author_add[cur_key] += a; author_del[cur_key] += d
                day_net[cur_day] += net
                day_churn[cur_day] += churn
        # también commits sin numstat (binarios) ya contados arriba, pero sin net
    # rangos
    d90 = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(90)]
    d30 = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
    total_cost_30 = sum(daily.get(d, {}).get("c", 0) for d in d30)
    total_net_30 = sum(day_net.get(d, 0) for d in d30)
    total_churn_30 = sum(day_churn.get(d, 0) for d in d30)
    inicio_team_eff = (total_cost_30 / (total_churn_30/1000)) if total_churn_30 > 0 else 0
    rework_team = (sum(author_del.values()) / max(sum(author_add.values()),1) * 100) if author_add else 0
    # cards
    def fmt_eff(v): return f"${v:.2f}/k" if v else "—"
    inicio_cards_html = (
        f"<div class='grid' style='grid-template-columns:repeat(4,1fr)'>"
        f"<div class='card'><h3>Eficiencia equipo</h3><div class='big'>{fmt_eff(inicio_team_eff)}</div><div class='row'><span>coste/churn 30d</span><span>{'menor es mejor'}</span></div></div>"
        f"<div class='card'><h3>Coste 30d</h3><div class='big'>${total_cost_30:.2f}</div><div class='row'><span>{fmt_tok(int(sum(daily.get(d,{}).get('t',0) for d in d30)))} tokens</span><span>{sum(daily.get(d,{}).get('k',0) for d in d30)} msgs</span></div></div>"
        f"<div class='card'><h3>Impacto churn 30d</h3><div class='big'>{fmt_tok(total_churn_30) if total_churn_30 else '0'}</div><div class='row'><span>líneas tocadas add+del</span><span>{len(author_churn_daily)} autores</span></div></div>"
        f"<div class='card'><h3>Rework 30d</h3><div class='big'>{rework_team:.1f}%</div><div class='row'><span>del/add</span><span>{sum(author_del.values())}/{sum(author_add.values())}</span></div></div>"
        f"</div>"
    )
    # serie histórica 90d para gráfica fija (ancho 100%, sin scroll) — 30d diario, 90d semanal
    # unificado: solo zherko (=equipo si trabajas solo), sin bots
    top_authors = ["zherko"] if "zherko" in author_commits else []
    hist = []
    solo = (len([k for k in author_commits if k=="zherko"]) > 0)  # tu eres el equipo
    for d in reversed(d90):
        c = daily.get(d, {}).get("c", 0); churn = day_churn.get(d, 0)
        team_e = (c / (churn/1000)) if churn > 0 else None
        if solo:
            row = {"d": d[5:], "zherko": round(team_e,2) if team_e is not None else None}
        else:
            row = {"d": d[5:], "team": round(team_e,2) if team_e is not None else None}
            n_auth = len(day_authors.get(d, [])) or 1
            for a in top_authors:
                l = author_churn_daily.get(a, {}).get(d, 0)
                if l:
                    ca = c / n_auth
                    row[a] = round(ca / (l/1000),2) if l != 0 else None
                else:
                    row[a] = None
        hist.append(row)
    inicio_chart_json = json.dumps(hist, ensure_ascii=False)
    # tabla por autor 30d
    rows = []
    for a in author_commits.most_common(12):
        key = a[0]; commits = a[1]
        churn = sum(author_churn_daily.get(key, {}).get(d,0) for d in d30)
        net = sum(author_daily.get(key, {}).get(d,0) for d in d30)
        add_g = author_add.get(key,0); del_g = author_del.get(key,0)
        rework_a = min(del_g / max(add_g,1)*100, 100) if add_g else 0
        if net < 0: rework_a = 100
        days_active = sum(1 for d in d30 if author_churn_daily.get(key, {}).get(d,0) != 0)
        cost_a = sum((daily.get(d,{}).get("c",0) / max(len(day_authors.get(d,[])),1)) for d in d30 if author_churn_daily.get(key,{}).get(d,0)!=0)
        eff_a = (cost_a / (churn/1000)) if churn > 0 else 0
        disp = author_display.get(key, key)
        churn_fmt = fmt_tok(churn) if churn else "0"
        rows.append((disp, churn, eff_a, rework_a, commits, days_active, churn_fmt))
    rows.sort(key=lambda x: x[2] if x[2] else 999)
    inicio_author_rows = "".join(
        f"<tr><td>{html.escape(r[0])}</td><td class='num'>{r[6]}</td><td class='num'>{fmt_eff(r[2])}</td><td class='num'>{r[3]:.1f}%</td><td class='num'>{r[4]}</td><td class='num'>{r[5]}/30</td></tr>"
        for r in rows
    ) or "<tr><td colspan=6>sin datos git 30d</td></tr>"
except Exception as e:
    inicio_cards_html = f"<p class='small'>sin datos inicio: {html.escape(str(e)[:80])}</p>"
    inicio_chart_json = "[]"
    inicio_author_rows = "<tr><td colspan=6>—</td></tr>"

# churn por proyecto y rango para $/k en Consumo (a+d, local, sin API)
proj_churn = {}
try:
    for p in all_paths:
        if not os.path.isdir(os.path.join(p, ".git")): continue
        short = os.path.basename(p.rstrip("/\\")) or p
        proj_churn[short] = {}
        for rk, since in [("d1","1 day"),("d7","7 days"),("d30","30 days"),("total",None)]:
            try:
                args = ["git","-C",p,"log","--numstat","--pretty=format:"]
                if since: args.insert(4, "--since="+since)
                ns = subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, errors="ignore")
                a = d = 0
                for line in ns.splitlines():
                    sp=line.split()
                    if len(sp)>=2 and sp[0].isdigit(): a+=int(sp[0])
                    if len(sp)>=2 and sp[1].isdigit(): d+=int(sp[1])
                proj_churn[short][rk] = a + d
            except: proj_churn[short][rk]=0
except: proj_churn={}
proj_churn_json = json.dumps(proj_churn, ensure_ascii=False)
# churn por modelo estimado por reparto diario (coste_modelo_día / coste_total_día * churn_día)
model_churn = {}
try:
    try: _dc = day_churn
    except NameError: _dc = {}
    if not _dc:
        _dc = {d: sum(proj_churn.get(s,{}).get("total",0) for s in proj_churn) for d in daily}  # fallback
    for rk in ["d1","d7","d30","total"]:
        days = {"d1":d1,"d7":d7,"d30":d30,"total":all_days}[rk]
        acc = {}
        for d in days:
            tot_c = daily.get(d,{}).get("c",0); tot_n = _dc.get(d,0)
            if not tot_c or not tot_n: continue
            for m, vals in daily.get(d,{}).get("mod",{}).items():
                c = vals[1]
                if not c: continue
                acc[m] = acc.get(m,0) + tot_n * (c / tot_c)
        for m, churn in acc.items():
            model_churn.setdefault(m, {})[rk] = int(round(churn))
except: model_churn={}
model_churn_json = json.dumps(model_churn, ensure_ascii=False)
# agent churn por agente estimado idem modelo
agent_churn = {}
try:
    try: _dc2 = day_churn
    except NameError: _dc2 = {}
    if not _dc2:
        _dc2 = {d: sum(proj_churn.get(s,{}).get("total",0) for s in proj_churn) for d in daily}
    for rk in ["d1","d7","d30","total"]:
        days = {"d1":d1,"d7":d7,"d30":d30,"total":all_days}[rk]
        acc = {}
        for d in days:
            tot_c = daily.get(d,{}).get("c",0); tot_n = _dc2.get(d,0)
            if not tot_c or not tot_n: continue
            for ag, vals in daily.get(d,{}).get("agt",{}).items():
                c = vals[1]
                if not c: continue
                acc[ag] = acc.get(ag,0) + tot_n * (c / tot_c)
        for ag, churn in acc.items():
            agent_churn.setdefault(ag, {})[rk] = int(round(churn))
except: agent_churn={}
agent_churn_json = json.dumps(agent_churn, ensure_ascii=False)

# coaching Inicio: sigue / vigila / corta (determinista, sin LLM)
inicio_coaching_html = ""
try:
    # --- sigue ---
    sigue_msg = "Sigue aprovechando el caché"
    sigue_detail = ""
    try:
        h = hit if 'hit' in locals() else 0
        if h and h > 90:
            sigue_msg = f"Cache {h:.1f}%"
            sigue_detail = "sigues reutilizando contexto — mantén sesiones largas con --pure"
        else:
            # mejor proyecto 30d por $/k
            best=None; bestv=1e9
            d30_churn = proj_churn
            d30_cost = R["d30"][3] if len(R["d30"])>3 else {}
            for name, vals in d30_cost.items():
                churn = d30_churn.get(name,{}).get("d30",0) if isinstance(vals, list) else 0
                cost = vals[1] if isinstance(vals, list) and len(vals)>1 else 0
                if churn and churn>500 and cost:
                    eff = cost/(churn/1000)
                    if eff < bestv:
                        bestv=eff; best=name
            if best:
                sigue_msg = f"{best} ${bestv:.2f}/k"
                sigue_detail = "tu proyecto más eficiente 30d — patrón a repetir"
    except: pass
    # --- vigila ---
    vigila_msg = "Rework estable"
    vigila_detail = ""
    try:
        rw = rework_team if 'rework_team' in locals() else 0
        if rw > 25:
            vigila_msg = f"Rework {rw:.1f}%"
            vigila_detail = "borras 1 de cada 4 líneas — revisa espec antes de picar"
        else:
            # peor autor
            worst=None; worstv=0
            for k in author_add:
                a=author_add.get(k,0); d=author_del.get(k,0)
                if a>200:
                    r=d/max(a,1)*100
                    if r>worstv:
                        worstv=r; worst=author_display.get(k,k)
            if worst and worstv>30:
                vigila_msg = f"{worst} {worstv:.0f}% rework"
                vigila_detail = "re-escribe mucho — afina prompt/router"
            else:
                vigila_msg = f"Coste 7d ${R['d7'][1]:.2f}"
                vigila_detail = "pico semanal controlado"
    except: pass
    # --- corta ---
    corta_msg = "Sin desperdicio detectado"
    corta_detail = ""
    try:
        # proyecto con coste sin churn
        d30_cost2 = R["d30"][3] if len(R["d30"])>3 else {}
        waste=None
        for name, vals in d30_cost2.items():
            cost = vals[1] if isinstance(vals, list) and len(vals)>1 else 0
            churn = proj_churn.get(name,{}).get("d30",0) if 'proj_churn' in locals() else 0
            if cost>0.5 and churn==0:
                waste=name; break
        if waste:
            corta_msg = f"{waste} sin churn"
            corta_detail = f"${d30_cost2[waste][1]:.2f} sin líneas — corta o mueve"
        else:
            # familia más cara por M
            worstAg=None; worstM=0
            d30_agt = R["d30"][5] if len(R["d30"])>5 else {}
            for name, vals in d30_agt.items():
                tokens = vals[0] if isinstance(vals, list) and len(vals)>0 else 0
                cost = vals[1] if isinstance(vals, list) and len(vals)>1 else 0
                msgs = vals[2] if isinstance(vals, list) and len(vals)>2 else 0
                if tokens and cost and msgs >5:
                    perM = cost/(tokens/1e6) if tokens else 0
                    if perM>worstM:
                        worstM=perM; worstAg=name
            if worstAg and worstM>30:
                corta_msg = f"{worstAg} ${worstM:.0f}/M"
                corta_detail = "familia más cara por M — limita para tareas simples"
            else:
                # mcp sin uso
                if 'mcps' in locals() and mcps and not tool_cnt:
                    corta_msg = "MCP sin uso"
                    corta_detail = "dead weight — revisa Plataforma"
    except: pass
    inicio_coaching_html = (
        f"<div class='grid' style='grid-template-columns:repeat(3,1fr);margin:12px 0'>"
        f"<div class='card' style='border-left:4px solid var(--grn)'><h3>✓ Sigue así</h3><div style='font-weight:700;margin:6px 0'>{html.escape(sigue_msg)}</div><div class='small'>{html.escape(sigue_detail)}</div></div>"
        f"<div class='card' style='border-left:4px solid #d29922'><h3>⚠ Vigila</h3><div style='font-weight:700;margin:6px 0'>{html.escape(vigila_msg)}</div><div class='small'>{html.escape(vigila_detail)}</div></div>"
        f"<div class='card' style='border-left:4px solid #f85149'><h3>✕ Corta</h3><div style='font-weight:700;margin:6px 0'>{html.escape(corta_msg)}</div><div class='small'>{html.escape(corta_detail)}</div></div>"
        f"</div>"
        f"<div style='text-align:center;margin:8px 0'><button id='btn-analizar' onclick=\"analizarMargen()\" style='border:1px solid var(--line);background:transparent;padding:8px 14px;border-radius:20px;cursor:pointer;color:var(--acc)'>Analizar margen con LLM →</button></div>"
        f"<div id='analisis-detalle' class='panel' style='display:none;margin-top:8px'></div>"
        f"<script>function analizarMargen(){{var d=document.getElementById('analisis-detalle'); if(!d) return; var projs=(D.ranges['d30']&&D.ranges['d30'].proj)||[]; var list=[]; for(var i=0;i<projs.length;i++){{var p=projs[i]; var churn=(PROJ_CHURN[p[0]]&&PROJ_CHURN[p[0]]['d30'])||0; if(!churn || churn<200) continue; var eff=p[2]/(churn/1000); list.push([p[0],eff,p[2],churn,p[1]]);}} if(!list.length){{d.innerHTML='<span class=\"small\">Sin churn suficiente 30d</span>'; d.style.display='block'; return;}} list.sort(function(a,b){{return b[1]-a[1];}}); var effs=list.map(function(x){{return x[1];}}).sort(function(a,b){{return a-b;}}); var med=effs[Math.floor(effs.length/2)]||0; var html='<div style=\"font-weight:700;margin-bottom:6px\">¿Dónde ganas más si optimizas? (peor $/k 30d)</div><div class=\"small\" style=\"margin-bottom:10px\">Más <b>$/k</b> = más caro por cada 1.000 líneas tocadas. Ordenada del más caro al más barato. <b>Ahorro</b> = lo que ahorrarías si bajara a la mediana ($'+med.toFixed(2)+'/k).</div><table style=\"width:100%;font-size:13px;table-layout:fixed;border-collapse:collapse\"><col style=\"width:auto\"><col style=\"width:90px\"><col style=\"width:110px\"><col style=\"width:135px\"><tr><th style=\"text-align:left;padding:8px 10px 8px 0\">Proyecto</th><th class=\"num\" style=\"padding:8px;white-space:nowrap\">$/k actual</th><th class=\"num\" style=\"padding:8px;white-space:nowrap\">Ahorro a mediana</th><th style=\"text-align:left;padding:8px;white-space:normal\">Consejo</th></tr>'; for(var i=0;i<Math.min(3,list.length);i++){{var r=list[i]; var ahorro=Math.max(0,(r[1]-med)*(r[3]/1000)); var tip=r[1]>1?'Revisa rework / batch':r[1]>0.6?'Usa flash / write-batch':'Mantén patrón'; html+='<tr><td style=\"padding:10px 10px 10px 0;word-break:break-word\"><b>'+r[0]+'</b><br><span class=\"small\">'+r[3]+' líneas · $'+r[2].toFixed(2)+' · '+r[4]+' tok</span></td><td class=\"num\" style=\"padding:10px 8px;color:#f85149;white-space:nowrap\">$'+r[1].toFixed(2)+'/k</td><td class=\"num\" style=\"padding:10px 8px;color:#3fb950;white-space:nowrap\">-$'+ahorro.toFixed(2)+'</td><td class=\"small\" style=\"padding:10px 8px;white-space:normal;word-break:break-word\">'+tip+'</td></tr>';}} html+='</table><div class=\"small\" style=\"margin-top:10px\">Determinista. Para el porqué: <code>opencode --agent Enjambre \"analiza '+list[0][0]+' y propone 1 ajuste para bajar $/k\"</code></div>'; d.innerHTML=html; d.style.display='block';}}</script>"
    )
except Exception as e:
    inicio_coaching_html = f"<p class='small'>coaching no disponible: {html.escape(str(e)[:60])}</p>"

# calendario: el render es JS (estilo Pomodoro), no pre-render estático

payload = {
    "daily": {d: {"t": e["t"], "c": round(e["c"], 4), "k": e["k"],
        "proj": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(e["proj"].items(), key=lambda x: -x[1][0])],
        "mod": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(e["mod"].items(), key=lambda x: -x[1][0])],
        "agt": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(e.get("agt",{}).items(), key=lambda x: -x[1][0])]} for d, e in daily.items()},
    "ranges": {k: {"t": v[0], "c": round(v[1], 4), "k": v[2],
        "proj": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(v[3].items(), key=lambda x: -x[1][0])],
        "mod": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(v[4].items(), key=lambda x: -x[1][0])],
        "agt": [[n, p[0], round(p[1], 4), p[2]] for n, p in sorted(v[5].items(), key=lambda x: -x[1][0])]}
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
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:8px 16px;overflow-x:auto;margin-bottom:14px}
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
.evo-wrap{position:relative;width:100%;height:220px;overflow:hidden}
.evo-wrap svg{width:100%;height:100%;display:block}
.evo-legend{display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 0;font-size:12px;color:var(--dim)}
.evo-legend span{display:inline-flex;align-items:center;gap:6px}
.evo-legend i{width:12px;height:3px;border-radius:2px;display:inline-block}
.evo-tip{position:absolute;top:0;left:0;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:12px;color:var(--txt);pointer-events:none;display:none;white-space:nowrap;box-shadow:0 6px 20px rgba(0,0,0,.5);transform:translate(-50%,-110%)}
.evo-tip b{color:var(--txt)}
.info-btn{width:18px;height:18px;border-radius:50%;border:1px solid var(--line);background:var(--panel);color:var(--dim);font-size:11px;line-height:16px;text-align:center;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;margin-left:8px;vertical-align:middle}
.info-btn:hover{border-color:var(--acc);color:var(--acc)}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:center;justify-content:center;z-index:99;padding:20px}
.modal.on{display:flex}
.modal-box{background:var(--panel);border:1px solid var(--line);border-radius:12px;max-width:560px;width:100%;padding:20px;box-shadow:0 12px 40px rgba(0,0,0,.5)}
.modal-box h3{margin:0 0 8px;font-size:14px;color:var(--txt)}
.modal-box p{margin:8px 0;color:var(--dim);font-size:13px;line-height:1.6}
.modal-box ul{margin:8px 0 0 18px;color:var(--dim);font-size:13px;line-height:1.6}
.modal-close{margin-top:14px;border:1px solid var(--line);background:var(--bg);color:var(--txt);border-radius:8px;padding:8px 14px;cursor:pointer}
.modal-close:hover{border-color:var(--txt)}
</style></head><body><div class="wrap">
<div class="top"><span class="dot"></span><h1>Centro de control</h1><label id="ar-wrap" style="display:none"><input type="checkbox" id="ar" checked></label></div>
<p class="sub">Fuente: <code>opencode.db</code> · __MSGS__ mensajes · <code>opencode.json</code> · generado __NOW__</p>
<div class="nav" id="nav"><button data-v="inicio" class="on">Inicio</button><button data-v="consumo">Consumo</button><button data-v="plataforma">Plataforma</button><button data-v="recursos">Recursos</button><button data-v="tareas">Tareas</button></div>

<div id="view-inicio" class="view on">
<div class="grid">__CARDS__</div>
__INICIO_CARDS__
__INICIO_COACHING__
<div style="display:flex;gap:8px;margin:12px 0;flex-wrap:wrap">
<button class="ghost small" data-evo="30" style="border:1px solid var(--line);background:var(--panel);color:var(--txt);border-radius:20px;padding:7px 14px;cursor:pointer">30 días</button>
<button class="ghost small" data-evo="90" style="border:1px solid var(--line);background:transparent;color:var(--dim);border-radius:20px;padding:7px 14px;cursor:pointer">90 días (semanal)</button>
</div>
<h2>Evolución eficiencia · $/k churn (menor es mejor) <button class="info-btn" data-info="evo">i</button></h2><div class="panel"><div id="evoChart" class="evo-wrap"></div><div id="evoLegend" class="evo-legend"></div><p class="small">Fijo ancho 100% sin scroll. Churn = add+del tocadas. Ventana 30d por autor (coste del día repartido equitativamente entre autores activos). 90d agrega por semana.</p></div>
<h2>Por autor · 30 días <button class="info-btn" data-info="autores">i</button></h2><div class="panel"><table><tr><th>Autor</th><th class="num">Churn</th><th class="num">$/k churn</th><th class="num">Rework</th><th class="num">Commits</th><th class="num">Días</th></tr><tbody>__INICIO_AUTHORS__</tbody></table><p class="small">Ordenado por eficiencia ($/k menor primero). Churn = add+del tocadas (no se degrada). Rework = del/add. Sin API Git, solo <code>git log --numstat</code>.</p></div>
<h2>Resumen rápido</h2><div class="panel"><p class="small">Consumo: <span id="sumConsumo">—</span> · Recursos: __NAGENTS__ agentes · __NSKILLS__ skills · Tareas: __NGOALS__ goals · __NCRONS__ crons · <a href="#" onclick="document.querySelector('[data-v=consumo]').click();return false;" style="color:var(--acc)">ir a Consumo</a></p></div>
</div>

<div id="view-consumo" class="view">
<div class="grid">__CARDS__</div>
<div class="tabs" id="tabs"><button data-r="total" class="on">Total</button><button data-r="d30">Ultimos 30 dias</button><button data-r="d7">Ultimos 7 dias</button><button data-r="d1">Hoy</button></div>
<p class="rangelabel" id="rangelabel"></p>
<h2>Actividad diaria · ultimos 7 dias (fija) <button class="info-btn" data-info="actividad">i</button></h2><div class="panel"><div class="days" id="days"></div></div>
<h2 id="t-proj">Por proyecto <button class="info-btn" data-info="proyecto">i</button></h2><div class="panel"><table><tr><th>Proyecto</th><th class="num">Tokens</th><th class="num">Coste</th><th class="num">Coste/msg</th><th class="num">Msgs</th><th class="num">$/k churn</th><th></th></tr><tbody id="projs"></tbody></table></div>
<h2>Por modelo (del rango) <button class="info-btn" data-info="modelo">i</button></h2><div class="panel"><table><tr><th>Modelo</th><th class="num">Tokens</th><th class="num">Coste</th><th class="num">Coste/msg</th><th class="num">Msgs</th><th class="num">$/k churn</th><th></th></tr><tbody id="mods"></tbody></table></div>
<h2>Por agente — familia (del rango) <button class="info-btn" data-info="agente">i</button></h2><div class="panel"><table><tr><th>Familia</th><th class="num">Tokens</th><th class="num">Coste</th><th class="num">Coste/msg</th><th class="num">Msgs</th><th class="num">$/k churn</th><th></th></tr><tbody id="agts"></tbody></table></div>
</div>

<div id="view-plataforma" class="view">
<h2>Herramientas & caché <button class="info-btn" data-info="tools">i</button></h2>__CACHE_HTML__<div class="panel"><table><tr><th>Herramienta</th><th class="num">Llamadas</th><th></th></tr>__TOOL_ROWS__</table><p class="small">MCPs con 0 llamadas = dead weight. Cache alto (>90%) = bien. Datos de <code>part.type=tool</code> + <code>message.tokens.cache</code>.</p></div>
<h2>Git · últimos 7 días <button class="info-btn" data-info="git">i</button></h2><div class="panel"><table><tr><th>Proyecto</th><th class="num">Commits</th><th class="num">Líneas +</th><th class="num">Líneas -</th></tr>__GIT_ROWS__</table><p class="small">Si un proyecto no es git, muestra 0. Coste por commit = coste 7d / commits.</p></div>
</div>

<div id="view-recursos" class="view">
<p class="small">__NAGENTS__ agentes · __NSKILLS__ skills (global+proyecto) · __NMCP__ MCPs — desde <code>~/.config/opencode/opencode.json</code></p>
<h2>Agentes <button class="info-btn" data-info="agentes">i</button></h2><div class="panel"><table><tr><th>Agente</th><th>Descripcion</th><th>Mode</th><th>Tools</th></tr>__AGENTS__</table></div>
<h2>MCPs <button class="info-btn" data-info="mcps">i</button></h2><div class="panel"><table><tr><th>MCP</th><th>Type</th><th>Enabled</th><th>Command</th></tr>__MCPS__</table></div>
<h2>Skills <button class="info-btn" data-info="skills">i</button></h2>
<input id="skill-filter" class="filter" placeholder="Filtrar skills… (escribe 'seo', 'cron', etc.)">
<div class="panel"><table><tr><th>Skill</th><th>Scope</th><th>Descripcion</th></tr><tbody id="skill-body">__SKILLS__</tbody></table><p class="small" id="skill-count"></p></div>
</div>

<div id="view-tareas" class="view">
<h2>Goals (__NGOALS__) <button class="info-btn" data-info="goals">i</button></h2><div class="panel"><table><tr><th>ID</th><th>Titulo</th><th>Criteria</th><th>Estado</th></tr>__GOALS__</table></div>
<h2>Crons (__NCRONS__) <button class="info-btn" data-info="crons">i</button></h2><div class="panel"><table><tr><th>Nombre</th><th>Schedule</th><th>Enabled</th><th>Ultimo run</th></tr>__CRONS__</table></div>
<div class="panel"><div class="cal-nav"><button id="calPrev">‹</button><b id="calLabel">—</b><button id="calNext">›</button></div><div id="calGrid" class="cal-grid"></div><div id="calDetail" class="cal-detail"><span class="hint">Toca un dia para ver su resumen.</span></div><p class="small">Fondo azulado = dia con gasto · invertido = hoy/seleccion · atenuado = futuro <button class="info-btn" data-info="calendario" style="vertical-align:middle">i</button></p></div>
</div>

<p class="foot">Regenerar: <code>python scripts/gen-dashboard.py</code> · Consumo filtra por rango (tabs); Recursos/Tareas son inventario vivo.</p>
</div>
<div id="infoModal" class="modal" onclick="if(event.target===this) closeInfo()"><div class="modal-box"><h3 id="infoTitle"></h3><div id="infoBody"></div><button class="modal-close" onclick="closeInfo()">Cerrar</button></div></div>
<script>
var D = __DATA__;
var EVO = __EVO_DATA__;
var PROJ_CHURN = __PROJ_CHURN__;
var MODEL_CHURN = __MODEL_CHURN__;
var AGENT_CHURN = __AGENT_CHURN__;
var SKILLS_ALL = __SKILL_JSON__;
var NAMES = {total:"todas las fechas con datos",d30:"ultimos 30 dias",d7:"ultimos 7 dias",d1:"hoy"};
function fmt(n){if(n>=1e9)return(n/1e9).toFixed(2)+"B";if(n>=1e6)return(n/1e6).toFixed(1)+"M";if(n>=1e3)return(n/1e3).toFixed(0)+"K";return""+n;}
function avg(c,k){var v=k?c/k:0;return "$"+v.toFixed(4);}
function bar(p){return "<div class='bar'><i style='width:"+Math.max(p,1.5).toFixed(1)+"%'></i></div>";}
// top nav + persist
var navBtns = document.querySelectorAll("#nav button");
for(var ni=0;ni<navBtns.length;ni++){(function(b){b.addEventListener("click",function(){
  for(var j=0;j<navBtns.length;j++){navBtns[j].classList.remove("on");document.getElementById("view-"+navBtns[j].getAttribute("data-v")).classList.remove("on");}
  b.classList.add("on");document.getElementById("view-"+b.getAttribute("data-v")).classList.add("on");
  try{localStorage.setItem('pc_view', b.getAttribute('data-v'));}catch(e){}
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
  var ph="",mh="",ah="";
  for(j=0;j<R.proj.length;j++){var p=R.proj[j]; var churn=(PROJ_CHURN[p[0]]&&PROJ_CHURN[p[0]][r]!=null)?PROJ_CHURN[p[0]][r]:null; var eff=(churn&&churn>0)?"$"+(p[2]/(churn/1000)).toFixed(2)+"/k":"—"; ph+="<tr><td>"+p[0]+"</td><td class='num'>"+fmt(p[1])+"</td><td class='num'>$"+p[2].toFixed(2)+"</td><td class='num'>"+avg(p[2],p[3])+"</td><td class='num'>"+p[3]+"</td><td class='num'>"+eff+"</td><td>"+bar(p[1]/mxp*100)+"</td></tr>";}
  for(j=0;j<R.mod.length;j++){var m=R.mod[j]; var mchurn=(MODEL_CHURN[m[0]]&&MODEL_CHURN[m[0]][r]!=null)?MODEL_CHURN[m[0]][r]:null; var meff=(mchurn&&mchurn>0)?"$"+(m[2]/(mchurn/1000)).toFixed(2)+"/k":"—"; mh+="<tr><td>"+m[0]+"</td><td class='num'>"+fmt(m[1])+"</td><td class='num'>$"+m[2].toFixed(2)+"</td><td class='num'>"+avg(m[2],m[3])+"</td><td class='num'>"+m[3]+"</td><td class='num'>"+meff+"</td><td></td></tr>";}
  for(j=0;j<R.agt.length;j++){var a=R.agt[j]; var achurn=(AGENT_CHURN[a[0]]&&AGENT_CHURN[a[0]][r]!=null)?AGENT_CHURN[a[0]][r]:null; var aeff=(achurn&&achurn>0)?"$"+(a[2]/(achurn/1000)).toFixed(2)+"/k":"—"; ah+="<tr><td><code>"+a[0]+"</code></td><td class='num'>"+fmt(a[1])+"</td><td class='num'>$"+a[2].toFixed(2)+"</td><td class='num'>"+avg(a[2],a[3])+"</td><td class='num'>"+a[3]+"</td><td class='num'>"+aeff+"</td><td></td></tr>";}
  var pe=document.getElementById("projs"), me=document.getElementById("mods"), ae=document.getElementById("agts");
  if(pe){ pe.innerHTML = ph || "<tr><td colspan=6>sin datos en este rango</td></tr>"; var _tp=pe.closest('table'); if(_tp) _tp._orig=null; }
  if(me){ me.innerHTML = mh || "<tr><td colspan=5>sin datos</td></tr>"; var _tm=me.closest('table'); if(_tm) _tm._orig=null; }
  if(ae){ ae.innerHTML = ah || "<tr><td colspan=6>sin datos</td></tr>"; var _ta=ae.closest('table'); if(_ta) _ta._orig=null; }
  var tp=document.getElementById("t-proj"); if(tp) tp.textContent="Por proyecto ("+label+")";
  try{localStorage.setItem('pc_range', r);}catch(e){}
  setTimeout(restoreSorts, 0);
}
var rbtns = document.querySelectorAll("#tabs button");
for(var i2=0;i2<rbtns.length;i2++){(function(b){b.addEventListener("click",function(){render(b.getAttribute("data-r"));});})(rbtns[i2]);}
var _initRange=null; try{_initRange=localStorage.getItem('pc_range');}catch(e){}
render(_initRange && D.ranges[_initRange] ? _initRange : "total");
try{ var _initView=localStorage.getItem('pc_view'); if(_initView && document.getElementById('view-'+_initView)){ navBtns.forEach(function(b){b.classList.remove('on');}); document.querySelectorAll('.view').forEach(function(v){v.classList.remove('on');}); document.querySelector('#nav [data-v="'+_initView+'"]').classList.add('on'); document.getElementById('view-'+_initView).classList.add('on'); } }catch(e){}
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
var ar=document.getElementById('ar'); if(ar){ ar.checked=true; var iv=setInterval(()=>{ if(document.getElementById('infoModal')?.classList.contains('on')) return; location.reload(); },30000); document.addEventListener('keydown', function(e){ if(e.ctrlKey && e.key==='F5'){ e.preventDefault(); location.reload(); } if(e.ctrlKey && e.key.toLowerCase()==='r' && e.shiftKey){ e.preventDefault(); location.reload(); } }); }
// ordenable 3 estados: desc -> asc -> default (fix cross-table + persist clave estable)
function parseVal(txt){
  txt=(txt||'').trim();
  if(!txt) return -1;
  if(txt[0]==='$') txt=txt.slice(1);
  if(/[BMK]$/.test(txt)){ var n=parseFloat(txt); if(txt.endsWith('B')) return n*1e9; if(txt.endsWith('M')) return n*1e6; if(txt.endsWith('K')) return n*1e3; return n; }
  var v=parseFloat(txt.replace(/,/g,'')); return isNaN(v)? txt.toLowerCase() : v;
}
function tableKey(t){ try{ var tb=t.querySelector('tbody'); var id=(tb&&tb.id)||t.id||''; if(id) return 'id:'+id; var hdr=[...t.querySelectorAll('th')].map(function(h){return h.textContent.trim().replace(/ [▲▼]$/,'');}).join('|'); var view=t.closest('.view'); var vid=view?view.id:''; return vid+'|'+hdr; }catch(e){return '';} }
function saveSorts(){ try{ var tables=[...document.querySelectorAll('.panel table')]; var o={}; tables.forEach(function(t){ var th=[...t.querySelectorAll('th')].find(function(h){return h._sortState}); if(th){ var k=tableKey(t); if(k) o[k]={c:[...t.querySelectorAll('th')].indexOf(th), s:th._sortState}; } }); localStorage.setItem('pc_sorts_v2', JSON.stringify(o)); try{localStorage.removeItem('pc_sorts');}catch(e){} }catch(e){} }
function restoreSorts(){ try{ var o=JSON.parse(localStorage.getItem('pc_sorts_v2')||localStorage.getItem('pc_sorts')||'{}'); var tables=[...document.querySelectorAll('.panel table')]; var map={}; tables.forEach(function(t){ map[tableKey(t)]=t; }); for(var k in o){ var t=map[k]; if(!t){ // compat indice numerico viejo
        var idx=parseInt(k,10); if(!isNaN(idx)) t=tables[idx];
      } if(!t) continue; var th=t.querySelectorAll('th')[o[k].c]; if(!th) continue; for(var n=0;n<o[k].s;n++){ th.click(); } } }catch(e){} }
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
  if(next===0){ tbody.innerHTML=''; table._orig.forEach(r=>tbody.appendChild(r.cloneNode(true))); saveSorts(); return; }
  rows.sort((a,b)=>{
    var av=parseVal(a.children[col]?.textContent), bv=parseVal(b.children[col]?.textContent);
    if(typeof av==='string' && typeof bv==='string') return next===1? bv.localeCompare(av) : av.localeCompare(bv);
    if(typeof av==='string') return 1; if(typeof bv==='string') return -1;
    return next===1? bv-av : av-bv;
  });
  tbody.innerHTML=''; rows.forEach(r=>tbody.appendChild(r)); saveSorts();
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
  if(rec.agt && rec.agt.length){
    html+='<div class="panel" style="margin-top:10px"><table><tr><th>Agente</th><th class="num">Tokens</th><th class="num">Coste</th><th class="num">Coste/msg</th><th class="num">Msgs</th></tr>';
    for(var k=0;k<rec.agt.length;k++){var ag=rec.agt[k]; var aa2=ag[3]?ag[2]/ag[3]:0; var av3=aa2.toFixed(4); html+='<tr><td><code>'+ag[0]+'</code></td><td class="num">'+fmt(ag[1])+'</td><td class="num">$'+ag[2].toFixed(2)+'</td><td class="num">$'+av3+'</td><td class="num">'+ag[3]+'</td></tr>';}
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
// resumen Inicio
var sc=document.getElementById('sumConsumo'); if(sc&&D.ranges){ var r=D.ranges.d30; sc.textContent=fmt(r.t)+' tokens · $'+r.c.toFixed(2)+' · '+r.k+' msgs (30d)'; }
// evolución: fija ancho 100%, sin scroll
var COLORS=['#58a6ff','#3fb950','#f778ba','#d29922','#8b949e'];
function renderEvo(mode){
  var c=document.getElementById('evoChart'), leg=document.getElementById('evoLegend');
  if(!c) return;
  var data=EVO||[];
  if(mode==='90'){
    var k0 = (data[0] && Object.keys(data[0]).find(function(k){return k!=='d';})) || 'team';
    var wk=[];
    for(var i=0;i<data.length;i++){
      var idx=Math.floor(i/7); if(!wk[idx]){ wk[idx]={d:'S'+(idx+1)}; wk[idx][k0]=0; wk[idx].n=0; }
      if(data[i][k0]!=null){ wk[idx][k0]+=data[i][k0]; wk[idx].n++; }
      wk[idx].d=data[i].d;
    }
    data=wk.map(function(w){ var o={d:w.d}; o[k0]= w.n? +(w[k0]/w.n).toFixed(2): null; return o; });
  } else {
    // 30d: usa solo últimos 30 de los 90 disponibles
    if(data.length>30) data=data.slice(-30);
  }
  var keys=[]; if(data[0]) for(var k in data[0]) if(k!=='d') keys.push(k);
  var vals=[]; for(var i=0;i<data.length;i++){ for(var ki=0;ki<keys.length;ki++){ var v=data[i][keys[ki]]; if(v!=null) vals.push(v); } }
  // autores top (si solo zherko, keys será ["zherko"])
  var authors=[]; if(EVO&&EVO[0]){ for(var k in EVO[0]) if(k!=='d') authors.push(k); }
  // en modo solo, authors es ["zherko"], lo tratamos como principal
  if(authors.length===1 && authors[0]==='zherko'){ /* solo tú = usa ese key */ }
  if(!vals.length){ c.innerHTML='<p class="small" style="padding:40px;text-align:center">sin datos git 30d — haz commits para ver evolución</p>'; if(leg) leg.innerHTML=''; return; }
  var mn=Math.min.apply(null,vals), mx=Math.max.apply(null,vals);
  if(mn===mx){ mn-=1; mx+=1; }
  var pad= (mx-mn)*0.15; mn-=pad; mx+=pad;
  var W=c.clientWidth||600, H=220, pl=36, pr=28, pt=12, pb=22;
  var step=(W-pl-pr)/Math.max(data.length-1,1);
  function x(i){ return pl + i*step; }
  function y(v){ return pt + (mx-v)/(mx-mn)*(H-pt-pb); }
  var svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%;height:100%">'
  +'<line x1="'+pl+'" y1="'+(H-pb)+'" x2="'+(W-pr)+'" y2="'+(H-pb)+'" stroke="#262c36" stroke-width="1"/>'
  +'<line x1="'+pl+'" y1="'+pt+'" x2="'+pl+'" y2="'+(H-pb)+'" stroke="#262c36" stroke-width="1"/>';
  // grid + labels y
  for(var g=0;g<3;g++){ var gv=mn+(mx-mn)*g/2, gy=y(gv); svg+='<line x1="'+pl+'" y1="'+gy+'" x2="'+(W-pr)+'" y2="'+gy+'" stroke="#21262d" stroke-dasharray="4 4"/><text x="'+(pl-4)+'" y="'+(gy+3)+'" text-anchor="end" fill="#8b949e" font-size="10">$'+gv.toFixed(1)+'</text>'; }
  // x labels cada ~5
  for(var i=0;i<data.length;i+=Math.ceil(data.length/6)){ svg+='<text x="'+x(i)+'" y="'+(H-4)+'" text-anchor="middle" fill="#8b949e" font-size="10">'+data[i].d+'</text>'; }
  function pathFor(key, color){
    var d=''; var first=true;
    for(var i=0;i<data.length;i++){ var v=data[i][key]; if(v==null) continue; var xi=x(i), yi=y(v); d+=(first?'M':'L')+xi+','+yi+' '; first=false; }
    if(!d) return '';
    return '<path d="'+d.trim()+'" fill="none" stroke="'+color+'" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
  }
  // dibuja: si solo zherko, una sola línea (evita duplicado Equipo/zherko)
  if(keys.length===1){
    svg+=pathFor(keys[0], COLORS[0]);
    for(var i=0;i<data.length;i++){ var v=data[i][keys[0]]; if(v==null) continue; svg+='<circle cx="'+x(i)+'" cy="'+y(v)+'" r="3" fill="'+COLORS[0]+'" stroke="#0d1117" stroke-width="1"><title>'+data[i].d+': $'+v+'/k</title></circle>'; }
  } else {
    svg+=pathFor('team', COLORS[0]);
    for(var ai=0;ai<authors.length;ai++){ if(authors[ai]==='team') continue; svg+=pathFor(authors[ai], COLORS[(ai+1)%COLORS.length]); }
    for(var i=0;i<data.length;i++){ var v=data[i].team; if(v==null) continue; svg+='<circle cx="'+x(i)+'" cy="'+y(v)+'" r="3" fill="'+COLORS[0]+'" stroke="#0d1117" stroke-width="1"><title>'+data[i].d+': $'+v+'/k</title></circle>'; }
  }
  svg+='</svg>';
  c.innerHTML=svg;
  // tooltip al pasar ratón: valor exacto
  (function(){
    var tip=document.getElementById('evoTip'); if(!tip){ tip=document.createElement('div'); tip.id='evoTip'; tip.className='evo-tip'; c.appendChild(tip); }
    var svgEl=c.querySelector('svg'); if(!svgEl) return;
    svgEl.addEventListener('mousemove', function(e){
      var r=svgEl.getBoundingClientRect(); var mX=e.clientX-r.left;
      var curW=c.clientWidth||600, curPl=36, curPr=28, curStep=(curW-curPl-curPr)/Math.max(data.length-1,1);
      var idx=Math.round((mX-curPl)/curStep); if(idx<0) idx=0; if(idx>=data.length) idx=data.length-1;
      var best=idx; if(data[idx][keys[0]]==null){ var bd=1e9; for(var d=0;d<data.length;d++){ var v=data[d][keys[0]]; if(v==null) continue; var dist=Math.abs(d-idx); if(dist<bd){ bd=dist; best=d; } } }
      var rec=data[best], val=rec?rec[keys[0]]:null;
      if(val==null){ tip.style.display='none'; return; }
      tip.innerHTML='<b>'+rec.d+'</b> · $'+val.toFixed(2)+'/k';
      tip.style.display='block';
      var tipW=tip.offsetWidth||80;
      var rawL=curPl+best*curStep;
      var clampedL=Math.max(tipW/2+4, Math.min(rawL, curW - tipW/2 - 4));
      tip.style.left=clampedL+'px';
      var ty= pt+(mx-val)/(mx-mn)*(H-pt-pb);
      tip.style.top=ty+'px';
    });
    svgEl.addEventListener('mouseleave', function(){ tip.style.display='none'; });
  })();
  if(leg){
    var html='';
    if(keys.length===1 && keys[0]==='zherko'){ html='<span><i style="background:'+COLORS[0]+'"></i>zherko (equipo)</span>'; }
    else if(keys.length===1){ html='<span><i style="background:'+COLORS[0]+'"></i>'+keys[0]+'</span>'; }
    else { html='<span><i style="background:'+COLORS[0]+'"></i>Equipo</span>';
    for(var ai=0;ai<authors.length;ai++){ if(authors[ai]==='team') continue; html+='<span><i style="background:'+COLORS[(ai+1)%COLORS.length]+'"></i>'+authors[ai]+'</span>'; } }
    leg.innerHTML=html;
  }
}
var _evoInit=null; try{_evoInit=localStorage.getItem('pc_evo');}catch(e){}
renderEvo(_evoInit==='90'?'90':'30');
try{ document.querySelectorAll('[data-evo]').forEach(function(b){ var on=b.getAttribute('data-evo')===(_evoInit==='90'?'90':'30'); b.style.background=on?'var(--panel)':'transparent'; b.style.color=on?'var(--txt)':'var(--dim)'; }); }catch(e){}
document.querySelectorAll('[data-evo]').forEach(function(b){ b.addEventListener('click',function(){
  document.querySelectorAll('[data-evo]').forEach(function(x){ x.style.background='transparent'; x.style.color='var(--dim)'; });
  b.style.background='var(--panel)'; b.style.color='var(--txt)';
  try{localStorage.setItem('pc_evo', b.getAttribute('data-evo'));}catch(e){}
  renderEvo(b.getAttribute('data-evo'));
});});
window.addEventListener('resize', function(){ var active=document.querySelector('[data-evo][style*="var(--panel)"]'); renderEvo(active?active.getAttribute('data-evo'):'30'); });
setTimeout(restoreSorts, 300);
// info popups mismo estilo web
var INFO={
  evo:{t:'Evolución eficiencia',h:'<p><b>Qué ves:</b> $ por cada 1.000 líneas <b>tocadas</b> (churn = add+del de <code>git log --numstat</code> / coste de <code>opencode.db</code>).</p><p><b>Por qué churn:</b> neto (add−del) se hunde cuando reescribes — al inicio todo queda, luego solo sustituyes y neto→0 aunque trabajes. Churn cuenta lo que tocas (quitas+pones) y no se degrada con la edad del proyecto.</p><p><b>Cómo leerlo:</b> línea baja y estable = gastas poco por lo que tocas. Pico = día caro con poco churn.</p><ul><li><b>Equipo</b> = media diaria</li><li>Top autores = reparto equitativo del coste del día</li><li>90d agrega por semana (sin scroll)</li></ul><p>Ventana 30d: todos comparables.</p>'},
  autores:{t:'Por autor · 30 días',h:'<p><b>Churn</b> = add+del tocadas (esfuerzo real, no lo que sobrevive). <b>$/k churn</b> = tu parte del coste / churn. <b>Rework</b> = del/add (estable &lt;20% ideal).</p><p><b>Interpreta:</b> $/k bajo + churn alto + rework bajo = eficiente. Neto se degrada, churn no — compara churn.</p><p>100% local con <code>git log --since=30 days</code>, sin API.</p>'},
  actividad:{t:'Actividad diaria',h:'<p>Barras de los últimos 7 días con tokens y coste. Fija, no cambia con los tabs de abajo. Es tu pulso diario.</p><p>Barra alta = día intenso. Útil para detectar picos de consumo.</p>'},
  proyecto:{t:'Por proyecto',h:'<p>Reparto por proyecto en el rango seleccionado (tabs Total/30d/7d/Hoy).</p><p><b>Coste/msg</b> = precio medio por consulta. <b>$/k churn</b> = coste / 1.000 líneas tocadas (add+del) git de ese proyecto/rango (menor es mejor). Barra = peso. Clic cabecera para ordenar.</p><p>Churn no se degrada como neto: mide esfuerzo, no lo que sobrevive.</p>'},
  modelo:{t:'Por modelo',h:'<p>Mismo que Por proyecto pero por modelo (<code>mimo-v2.5</code>, <code>muse-spark</code>…).</p><p><b>$/k churn (est.)</b> = coste / churn estimado (reparto diario: churn_día * coste_modelo_día / coste_total_día). Menor es mejor. Es estimado porque git no guarda modelo.</p><p>Compara coste/msg + $/k est. para ver modelo más eficiente. Churn estable entre fases.</p>'},
  agente:{t:'Por agente (familia)',h:'<p>Familia = agente root + todos sus subagentes (<code>session.parent_id</code> hasta el root). No es el agente suelto: <b>general</b> hijo de <b>Enjambre</b> cuenta en <b>Enjambre (familia)</b>.</p><p>Unifica cualquier orquestador (Enjambre, build con hijos, etc.) sin hardcodear nombres — 274 sesiones con padre en tu DB.</p><p><b>$/k churn (est.)</b> = coste familia / churn estimado (reparto diario: churn_día * coste_familia_día / coste_total_día). Compara familias, no agentes sueltos.</p><p>Fuente 100% local: <code>message.agent</code> + <code>session.parent_id</code>.</p>'},
  tools:{t:'Herramientas & caché',h:'<p><b>Cache hit</b> = % de tokens leídos de caché (alto &gt;90% es bueno). <b>Herramientas</b> = llamadas totales.</p><p>Tabla = herramientas más usadas (<code>bash, read, edit</code>). Si ves MCP con 0 llamadas, es dead weight.</p>'},
  git:{t:'Git · 7 días',h:'<p>Commits y líneas +/− por proyecto en 7 días desde <code>git log --since=7 days --numstat</code>.</p><p>0 = no es repo git. Útil para cruzar coste vs actividad real en código.</p>'},
  agentes:{t:'Agentes',h:'<p>26 agentes definidos en <code>~/.config/opencode/opencode.json</code>. Mode = primary/subagent, Tools = qué puede usar.</p><p>Inventario vivo: lo que realmente tienes disponible.</p>'},
  mcps:{t:'MCPs',h:'<p>Servidores MCP conectados (ej. <code>gsc</code>, <code>supadata</code>). Si está off, sus tools no cuentan en Herramientas.</p>'},
  skills:{t:'Skills',h:'<p>247 skills globales + proyecto. Filtra escribiendo. Scope global = disponible siempre, project = solo aquí.</p>'},
  goals:{t:'Goals',h:'<p>Objetivos activos/archivados en <code>.opencode/goals</code>. Criterio = cómo se da por cumplido.</p>'},
  crons:{t:'Crons',h:'<p>Tareas programadas en <code>.opencode/cron/jobs.json</code>. Si ves 0, crea uno con <code>/skill_cron</code>.</p>'},
  calendario:{t:'Calendario',h:'<p>Vista mensual estilo Pomodoro. Fondo azulado = día con gasto, invertido = hoy/selección, atenuado = futuro.</p><p>Pincha un día para ver su detalle de proyecto/modelo y coste/msg de ese día.</p>'}
};
function openInfo(k){ var d=INFO[k]; if(!d) return; document.getElementById('infoTitle').textContent=d.t; document.getElementById('infoBody').innerHTML=d.h; document.getElementById('infoModal').classList.add('on'); }
function closeInfo(){ document.getElementById('infoModal').classList.remove('on'); }
document.addEventListener('click',function(e){ var b=e.target.closest('.info-btn'); if(b){ openInfo(b.getAttribute('data-info')); }});
document.addEventListener('keydown',function(e){ if(e.key==='Escape') closeInfo(); });
</script></body></html>"""

doc = TPL.replace("__MSGS__", str(msgs)).replace("__NOW__", now).replace("__CARDS__", cards_html)
doc = doc.replace("__INICIO_CARDS__", inicio_cards_html).replace("__INICIO_AUTHORS__", inicio_author_rows).replace("__INICIO_COACHING__", inicio_coaching_html)
doc = doc.replace("__CACHE_HTML__", cache_html).replace("__TOOL_ROWS__", tool_rows).replace("__GIT_ROWS__", git_html_rows)
doc = doc.replace("__GOALS__", goal_rows).replace("__CRONS__", cron_rows)
doc = doc.replace("__NGOALS__", str(len(goals))).replace("__NCRONS__", str(len(crons)))
doc = doc.replace("__AGENTS__", agent_rows).replace("__MCPS__", mcp_rows).replace("__SKILLS__", skill_tr + skill_more_row)
doc = doc.replace("__NAGENTS__", str(len(agents))).replace("__NSKILLS__", str(len(skill_rows))).replace("__NMCP__", str(len(mcps)))
doc = doc.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
doc = doc.replace("__EVO_DATA__", inicio_chart_json)
doc = doc.replace("__PROJ_CHURN__", proj_churn_json)
doc = doc.replace("__MODEL_CHURN__", model_churn_json)
doc = doc.replace("__AGENT_CHURN__", agent_churn_json)
doc = doc.replace("__SKILL_JSON__", json.dumps([{"id": s["id"], "scope": s["scope"], "desc": s["desc"]} for s in skill_rows], ensure_ascii=False))
out = os.path.join(ROOT, "dashboard.html")
open(out, "w", encoding="utf-8").write(doc)
print("OK ->", out, "| consumo total=" + fmt_tok(R["total"][0]), "| agentes=" + str(len(agents)), "skills=" + str(len(skill_rows)), "mcps=" + str(len(mcps)), "| goals=" + str(len(goals)), "crons=" + str(len(crons)))
