"""watch.py — regenera dashboard.html solo cuando opencode.db cambia. Compartimentado: borra este fichero para volver a polling ciego."""
import os, time, subprocess, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = os.path.expanduser(r"~\.local\share\opencode\opencode.db")
CONF = os.path.expanduser(r"~\.config\opencode\opencode.json")
PENDING = ROOT / ".opencode" / "pending_tasks.json"
GEN = ROOT / "scripts" / "gen-dashboard.py"

WATCH = [DB, CONF, str(PENDING)]
# también mira git HEAD de cada proyecto (si existe) — se añade dinámico
def extra_watches():
    extra=[]
    try:
        import sqlite3, json
        con=sqlite3.connect(DB); cur=con.cursor()
        cur.execute("SELECT id, worktree FROM project"); p2w=dict(cur.fetchall())
        cur.execute("SELECT id, project_id FROM session"); s2p=dict(cur.fetchall())
        cur.execute("SELECT session_id, data FROM message WHERE json_extract(data,'$.role')='assistant' LIMIT 200")
        paths=set()
        for sid,d in cur.fetchall():
            try:
                import json as js; o=js.loads(d); wt=p2w.get(s2p.get(sid,""),""); cwd=(o.get("path") or {}).get("cwd") or wt
                if cwd: paths.add(cwd)
            except: pass
        con.close()
        for p in paths:
            h=os.path.join(p,".git","HEAD")
            if os.path.exists(h): extra.append(h)
    except: pass
    return extra

def regen():
    try:
        r=subprocess.run([sys.executable, str(GEN)], cwd=str(ROOT), capture_output=True, text=True, timeout=20)
        print(r.stdout.strip() or r.stderr.strip())
    except Exception as e:
        print(f"regen err: {e}")

def try_watchdog():
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        import pathlib as pl
        class H(FileSystemEventHandler):
            def __init__(self): self.last=0
            def on_any_event(self, e):
                if e.is_directory: return
                now=time.time()
                if now-self.last < 2: return
                self.last=now
                # debounce 2s
                time.sleep(0.6)
                print(f"cambio {e.src_path[:80]} -> regen")
                regen()
                self.last=time.time()
        obs=Observer(); h=H()
        for p in WATCH+extra_watches():
            d=str(pl.Path(p).parent) if os.path.isfile(p) else p
            if os.path.isdir(d):
                obs.schedule(h, d, recursive=False)
                print(f"watchdog {d} -> {os.path.basename(p)}")
        obs.start()
        print("watch activo (watchdog) — Ctrl+C para salir")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            obs.stop(); obs.join()
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"watchdog err {e}")
        return False

def poll_loop():
    print("watch activo (poll mtime) — sin watchdog, cada 2s — Ctrl+C para salir")
    mtimes={}
    def snap():
        for p in WATCH+extra_watches():
            try: mtimes[p]=os.path.getmtime(p)
            except: mtimes[p]=0
    snap()
    last_regen=0
    while True:
        time.sleep(2)
        changed=False
        for p in list(mtimes.keys()):
            try: mt=os.path.getmtime(p)
            except: mt=0
            if mt!=mtimes[p]:
                mtimes[p]=mt; changed=True
        # también detecta ficheros nuevos
        for p in extra_watches():
            if p not in mtimes:
                try: mtimes[p]=os.path.getmtime(p); changed=True
                except: pass
        if changed:
            now=time.time()
            if now-last_regen < 5:
                continue
            print("cambio detectado -> regen (debounce 5s)")
            time.sleep(0.5)
            regen()
            last_regen=time.time()
            snap()

if __name__=="__main__":
    print("Panel Control watch — solo regenera si hay cambio real")
    regen()
    if not try_watchdog():
        print("watchdog no instalado (pip install watchdog) -> usando poll")
        poll_loop()
