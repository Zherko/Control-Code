"""social_sync.py — push/pull para pestaña Social (Supadata db27/peers). Compartimentado: borra este fichero + bloque SOCIAL en gen-dashboard.py para quitar."""
import os, json, sqlite3, datetime, subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = os.path.expanduser(r"~\.local\share\opencode\opencode.db")
CONF = os.path.expanduser(r"~\.config\opencode\opencode.json")
SUPA_URL = "https://pro-serv.tail9f39ff.ts.net"
DB_ID = "db27"  # panel-control-social (admin)
TABLE = "peers"
SOCIAL_KEY = ""  # no hardcodear: usar SUPADATA_API_KEY de env/mcp

def get_key():
    try:
        cfg=json.load(open(CONF,encoding="utf-8-sig"))
        k = ((cfg.get("mcp",{}).get("supadata",{}).get("environment",{}).get("SUPADATA_API_KEY")) or os.environ.get("SUPADATA_API_KEY") or "").strip()
        if k: return k
    except: pass
    k2 = (os.environ.get("SUPADATA_API_KEY") or "").strip()
    if k2: return k2
    return SOCIAL_KEY

def compute_self():
    # replica mínima de gen-dashboard para tok hoy/30d, churn, proyectos
    try:
        con=sqlite3.connect(DB)
        cur=con.cursor()
        cur.execute("SELECT id, worktree FROM project"); p2w=dict(cur.fetchall())
        cur.execute("SELECT id, project_id FROM session"); s2p=dict(cur.fetchall())
        cur.execute("SELECT session_id, time_created, data FROM message")
        daily={}
        tot_churn_map={}
        for sid,tc,d in cur.fetchall():
            try: j=json.loads(d)
            except: continue
            if j.get("role")!="assistant": continue
            tok=j.get("tokens") or {}
            t=int(tok.get("total") or 0); c=float(j.get("cost") or 0)
            ts=(j.get("time") or {}).get("created") or tc
            try: day=datetime.datetime.fromtimestamp(ts/1000).strftime("%Y-%m-%d")
            except: continue
            e=daily.setdefault(day,{"t":0,"c":0.0,"k":0,"proj":{}})
            e["t"]+=t; e["c"]+=c; e["k"]+=1
            wt=p2w.get(s2p.get(sid,""),"?"); short=os.path.basename((j.get("path") or {}).get("cwd") or wt or "?").strip("/\\") or "?"
            b=e["proj"].setdefault(short,[0,0.0,0]); b[0]+=t; b[1]+=c; b[2]+=1
        con.close()
        today=datetime.date.today()
        d1=today.strftime("%Y-%m-%d")
        d30=[(today-datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
        tok_today=daily.get(d1,{}).get("t",0)
        cost_today=daily.get(d1,{}).get("c",0.0)
        tok_30d=sum(daily.get(d,{}).get("t",0) for d in d30)
        cost_30d=sum(daily.get(d,{}).get("c",0.0) for d in d30)
        # churn 30d por git
        import collections
        # recoge paths
        paths=set()
        try:
            con2=sqlite3.connect(DB)
            cur2=con2.cursor()
            cur2.execute("SELECT id, worktree FROM project"); p2w2=dict(cur2.fetchall())
            cur2.execute("SELECT id, project_id FROM session"); s2p2=dict(cur2.fetchall())
            cur2.execute("SELECT session_id, data FROM message WHERE json_extract(data,'$.role')='assistant'")
            for sid,d in cur2.fetchall():
                try:
                    o=json.loads(d); wt=p2w2.get(s2p2.get(sid,""),""); cwd=(o.get("path") or {}).get("cwd") or wt
                    if cwd: paths.add(cwd)
                except: pass
            con2.close()
        except: pass
        churn_30d=0
        for p in sorted(paths)[:14]:
            if not os.path.isdir(os.path.join(p,".git")): continue
            try:
                ns=subprocess.check_output(["git","-C",p,"log","--since=30 days","--numstat","--pretty=format:"], text=True, stderr=subprocess.DEVNULL, errors="ignore")
                for line in ns.splitlines():
                    sp=line.split()
                    if len(sp)>=2 and sp[0].isdigit(): churn_30d+=int(sp[0])
                    if len(sp)>=2 and sp[1].isdigit(): churn_30d+=int(sp[1])
            except: pass
        projects=len([1 for d in d30 for proj in daily.get(d,{}).get("proj",{})]) 
        # proyectos únicos 30d
        uniq=set()
        for d in d30:
            for proj in daily.get(d,{}).get("proj",{}):
                uniq.add(proj)
        projects=len(uniq)
        return {"tok_today":tok_today,"tok_30d":tok_30d,"cost_today":round(cost_today,4),"cost_30d":round(cost_30d,4),"churn_30d":churn_30d,"projects":projects}
    except Exception as e:
        return {"tok_today":0,"tok_30d":0,"cost_today":0,"cost_30d":0,"churn_30d":0,"projects":0,"err":str(e)[:80]}

def api(path, method="GET", body=None):
    import urllib.request, urllib.error
    key=get_key()
    if not key:
        raise SystemExit("Falta SUPADATA_API_KEY en opencode.json o env")
    hd={"x-api-key":key, "Content-Type":"application/json", "X-Client-Name":"social-sync"}
    data=json.dumps(body).encode() if body else None
    req=urllib.request.Request(SUPA_URL+path, data=data, headers=hd, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def list_peers(limit=50):
    return api(f"/v1/databases/{DB_ID}/rows?table={TABLE}&limit={limit}&order=desc")

def load_profile():
    # prioriza .opencode/social_identity.json (persistencia anon/google)
    try:
        p=ROOT/".opencode"/"social_identity.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8-sig"))
    except: pass
    return None
def save_profile(prof):
    try:
        p=ROOT/".opencode"/"social_identity.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(prof, ensure_ascii=False, indent=2), encoding="utf-8")
    except: pass
def upsert_peer(name, self_stats, status="online", profile=None):
    row={"name":name, "tok_today":self_stats["tok_today"], "tok_30d":self_stats["tok_30d"],
         "cost_today":self_stats["cost_today"], "cost_30d":self_stats["cost_30d"],
         "churn_30d":self_stats["churn_30d"], "projects":self_stats["projects"],
         "updated_at":datetime.datetime.now().isoformat(timespec="seconds"), "status":status}
    prof=profile or load_profile()
    if prof and prof.get("google_sub"):
        row["display_name"]=prof.get("name") or name
        row["avatar_url"]=prof.get("picture") or ""
        row["google_sub"]=prof.get("google_sub") or prof.get("sub") or ""
        if prof.get("email"): row["email"]=prof.get("email")
        return api(f"/v1/databases/{DB_ID}/rows", method="POST", body={"table":TABLE,"row":row,"onConflict":["google_sub"],"resolution":"last"})
    if prof and prof.get("picture"):
        row["display_name"]=prof.get("name") or name
        row["avatar_url"]=prof.get("picture")
    return api(f"/v1/databases/{DB_ID}/rows", method="POST", body={"table":TABLE,"row":row,"onConflict":["name"],"resolution":"last"})

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--connect", action="store_true")
    ap.add_argument("--disconnect", action="store_true")
    ap.add_argument("--name", type=str, default="")
    ap.add_argument("--avatar", type=str, default="")
    ap.add_argument("--google-sub", type=str, default="")
    ap.add_argument("--email", type=str, default="")
    ap.add_argument("--list", action="store_true")
    args=ap.parse_args()
    if args.list:
        print(json.dumps(list_peers(), ensure_ascii=False, indent=2))
        return
    prof=load_profile()
    name=args.name.strip()
    if not name:
        if prof and prof.get("name"):
            name=prof.get("name")
        else:
            # reuse stable anon (fix duplicidad)
            anon_file=ROOT/".opencode"/"social_identity.json"
            if anon_file.exists():
                try:
                    j=json.loads(anon_file.read_text(encoding="utf-8-sig"))
                    if j.get("anon_name"): name=j.get("anon_name")
                except: pass
            if not name:
                import random, string
                name="anon-"+ "".join(random.choices(string.hexdigits[:16], k=4)).lower()
                save_profile({"anon_name": name})
                print(f"Nombre no dado, usando {name} — estable, se reutilizará")
            else:
                print(f"Reusando anon {name}")
    # si se pasan datos Google por CLI, úsalos
    cli_prof=None
    if args.avatar or args.google_sub:
        cli_prof={"name": name, "picture": args.avatar, "google_sub": args.google_sub, "email": args.email}
    else:
        cli_prof=prof
    self_stats=compute_self()
    if args.disconnect:
        res=upsert_peer(name, self_stats, status="offline", profile=cli_prof)
        print(f"Desconectado {name}: {self_stats}")
        print(json.dumps(res, ensure_ascii=False))
        return
    if args.connect or True:
        res=upsert_peer(name, self_stats, status="online", profile=cli_prof)
        # guarda anon estable si es anon
        if name.startswith("anon-") and not (cli_prof and cli_prof.get("google_sub")):
            try:
                cur=json.loads((ROOT/".opencode"/"social_identity.json").read_text(encoding="utf-8-sig")) if (ROOT/".opencode"/"social_identity.json").exists() else {}
            except: cur={}
            cur["anon_name"]=name
            save_profile(cur)
        print(f"Conectado {name}: tok_today={self_stats['tok_today']} tok_30d={self_stats['tok_30d']} churn={self_stats['churn_30d']} proyectos={self_stats['projects']} $/k={(self_stats['cost_30d']/(self_stats['churn_30d']/1000) if self_stats['churn_30d'] else 0):.2f}")
        print(json.dumps(res, ensure_ascii=False))

if __name__=="__main__":
    main()
