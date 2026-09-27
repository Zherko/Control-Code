"""social_sync.py — push/pull para pestaña Social (Supadata db27/peers). Compartimentado: borra este fichero + bloque SOCIAL en gen-dashboard.py para quitar."""
import os, json, sqlite3, datetime, subprocess, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = os.path.expanduser(r"~\.local\share\opencode\opencode.db")
CONF = os.path.expanduser(r"~\.config\opencode\opencode.json")
SUPA_URL = "https://pro-serv.tail9f39ff.ts.net"
DB_ID = "db28"  # panel-social-v2 (owner social, key publica sd_qKMP...)
TABLE = "peers"
SOCIAL_KEY = "sd_qKMPbKz3p36CZpBoVO-sOOheH0WdyzCq"

def get_key():
    # usa key publica social si no hay admin key
    try:
        cfg=json.load(open(CONF,encoding="utf-8-sig"))
        k = ((cfg.get("mcp",{}).get("supadata",{}).get("environment",{}).get("SUPADATA_API_KEY")) or os.environ.get("SUPADATA_API_KEY") or "").strip()
        if k: return k
    except: pass
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

def upsert_peer(name, self_stats, status="online"):
    row={"name":name, "tok_today":self_stats["tok_today"], "tok_30d":self_stats["tok_30d"],
         "cost_today":self_stats["cost_today"], "cost_30d":self_stats["cost_30d"],
         "churn_30d":self_stats["churn_30d"], "projects":self_stats["projects"],
         "updated_at":datetime.datetime.now().isoformat(timespec="seconds"), "status":status}
    return api(f"/v1/databases/{DB_ID}/rows", method="POST", body={"table":TABLE,"row":row,"onConflict":["name"],"resolution":"last"})

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--connect", action="store_true")
    ap.add_argument("--disconnect", action="store_true")
    ap.add_argument("--name", type=str, default="")
    ap.add_argument("--list", action="store_true")
    args=ap.parse_args()
    if args.list:
        print(json.dumps(list_peers(), ensure_ascii=False, indent=2))
        return
    name=args.name.strip()
    if not name:
        # intenta leer de localStorage exportado? fallback anon
        import random, string
        name="anon-"+ "".join(random.choices(string.hexdigits[:16], k=4)).lower()
        print(f"Nombre no dado, usando {name} — pásalo con --name para fijarlo")
    self_stats=compute_self()
    if args.disconnect:
        res=upsert_peer(name, self_stats, status="offline")
        print(f"Desconectado {name}: {self_stats}")
        print(json.dumps(res, ensure_ascii=False))
        return
    if args.connect or True:
        # si name existe con otro churn? onConflict last lo actualiza
        res=upsert_peer(name, self_stats, status="online")
        print(f"Conectado {name}: tok_today={self_stats['tok_today']} tok_30d={self_stats['tok_30d']} churn={self_stats['churn_30d']} proyectos={self_stats['projects']} $/k={(self_stats['cost_30d']/(self_stats['churn_30d']/1000) if self_stats['churn_30d'] else 0):.2f}")
        print(json.dumps(res, ensure_ascii=False))

if __name__=="__main__":
    main()
