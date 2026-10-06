"""HG Runtime V1: HTTP adapter around HG Core primitives."""
from __future__ import annotations
import json, os, re, secrets, base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[2]; DATA=ROOT/"core"/"runtime"/"data"; DB=DATA/"state.json"; LIB=DATA/"library"; LIB.mkdir(parents=True,exist_ok=True)
try:
    from paradise_kernel import Kernel
except Exception: Kernel=None
DEFAULTS={"memory":[],"context":[],"plugin":[],"message":[],"library":[]}
def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return secrets.token_hex(12)
def load():
    if DB.exists():
        try:return json.loads(DB.read_text(encoding="utf-8"))
        except Exception:pass
    DB.parent.mkdir(parents=True,exist_ok=True); DB.write_text(json.dumps(DEFAULTS,ensure_ascii=False,indent=2),encoding="utf-8"); return json.loads(json.dumps(DEFAULTS))
def save(s):
    t=DB.with_suffix(".tmp"); t.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding="utf-8"); t.replace(DB)
def gh(path):
    token=os.getenv("GITHUB_TOKEN","").strip() or None; h={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2026-03-10","User-Agent":"HG-Runtime/1.0"}
    if token:h["Authorization"]="Bearer "+token
    try:
        with urlopen(Request("https://api.github.com"+path,headers=h,method="GET"),timeout=12) as r:return {"ok":True,"authenticated":bool(token),"status":r.status,"data":json.loads(r.read().decode())}
    except Exception as e:return {"ok":False,"authenticated":bool(token),"error":str(e)}
def err(code,msg,status=400):return status,{"ok":False,"error":{"code":code,"message":msg}}
class Handler(BaseHTTPRequestHandler):
    server_version="HG-Runtime/1.0"
    def log_message(self,fmt,*args):print("HG",fmt%args)
    def send_json(self,status,payload):
        raw=json.dumps(payload,ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Headers","Content-Type"); self.send_header("Access-Control-Allow-Methods","GET,POST,PATCH,DELETE,OPTIONS"); self.end_headers(); self.wfile.write(raw)
    def body(self):
        raw=self.rfile.read(int(self.headers.get("Content-Length","0")))
        try:return json.loads(raw or b"{}")
        except Exception:return {}
    def do_OPTIONS(self):self.send_json(204,{"ok":True})
    def do_GET(self):
        p=urlparse(self.path); path=p.path; q=parse_qs(p.query)
        if path=="/api/health":return self.send_json(200,{"ok":True,"runtime":"READY","core":"AVAILABLE" if Kernel else "UNAVAILABLE","time":now()})
        if path=="/api/bootstrap":return self.send_json(200,{"ok":True,"state":load(),"runtime":"READY","core":"AVAILABLE" if Kernel else "UNAVAILABLE"})
        if path=="/api/github/status":
            token=bool(os.getenv("GITHUB_TOKEN","")); d={"configured":token,"mode":"authenticated" if token else "public-read"}
            if token:
                r=gh("/user"); d["authenticated_user"]=r.get("data",{}).get("login") if r.get("ok") else None; d["error"]=r.get("error")
            return self.send_json(200,{"ok":True,"github":d})
        if path=="/api/github/repos":
            owner=q.get("owner",[None])[0]; token=os.getenv("GITHUB_TOKEN","").strip() or None
            target="/user/repos?per_page=50&sort=updated" if token and not owner else (f"/users/{owner}/repos?per_page=50&sort=updated" if owner else None)
            if not target:return self.send_json(*err("OWNER_REQUIRED","owner is required when GITHUB_TOKEN is absent"))
            r=gh(target);return self.send_json(200 if r["ok"] else 502,{"ok":r["ok"],"repos":r.get("data",[]),"error":r.get("error")})
        m=re.fullmatch(r"/api/github/repo/([^/]+)/([^/]+)",path)
        if m:
            r=gh(f"/repos/{m.group(1)}/{m.group(2)}");return self.send_json(200 if r["ok"] else 502,{"ok":r["ok"],"repo":r.get("data"),"error":r.get("error")})
        return self.send_json(404,{"ok":False,"error":{"code":"NOT_FOUND","message":"Unknown endpoint"}})
    def do_POST(self):
        path=urlparse(self.path).path;b=self.body();s=load()
        if path=="/api/chat":
            m={"id":b.get("id",uid()),"role":b.get("role","user"),"text":b.get("text",""),"comments":b.get("comments",[]),"created_at":now()}
            if not m["text"]:return self.send_json(*err("EMPTY_MESSAGE","text is required"))
            s["message"].append(m);save(s);return self.send_json(201,{"ok":True,"message":m})
        if path=="/api/memory":
            m={"id":b.get("id",uid()),"title":b.get("title",""),"content":b.get("content",""),"kind":b.get("kind","user"),"source":b.get("source","runtime"),"conf":float(b.get("conf",1)),"created_at":now()}
            if not m["title"] or not m["content"]:return self.send_json(*err("INVALID_MEMORY","title and content are required"))
            s["memory"].append(m);save(s);return self.send_json(201,{"ok":True,"memory":m})
        if path=="/api/context":
            c={"id":b.get("id",uid()),"name":b.get("name",""),"content":b.get("content",""),"type":b.get("type","custom"),"project":bool(b.get("project",False)),"created_at":now()}
            if not c["name"]:return self.send_json(*err("INVALID_CONTEXT","name is required"))
            s["context"].append(c);save(s);return self.send_json(201,{"ok":True,"context":c})
        m=re.fullmatch(r"/api/plugin/([^/]+)/(install|connect)",path)
        if m:
            p=next((x for x in s["plugin"] if x["id"]==m.group(1)),None)
            if not p and m.group(1)=="github":
                p={"id":"github","name":"GitHub","icon":"◉","desc":"Repos, issues, PRs and publish flows.","installed":False,"connected":False};s["plugin"].append(p)
            if not p:return self.send_json(*err("PLUGIN_NOT_FOUND","plugin not found",404))
            p["installed"]=True if m.group(2)=="install" else p.get("installed",False); p["connected"]=p.get("connected",False) if m.group(2)=="install" else not p.get("connected",False)
            save(s);return self.send_json(200,{"ok":True,"plugin":p})
        if path=="/api/library":
            item={"id":b.get("id",uid()),"name":b.get("name",""),"type":b.get("type","application/octet-stream"),"size":int(b.get("size",0)),"created_at":now()}
            if b.get("data"):
                try:
                    raw=base64.b64decode(b["data"]); safe=re.sub(r"[^A-Za-z0-9._-]","_",item["name"] or item["id"]); dest=LIB/(item["id"]+"-"+safe);dest.write_bytes(raw);item["path"]=str(dest.relative_to(ROOT))
                except Exception:return self.send_json(*err("FILE_DECODE_FAILED","invalid base64 file"))
            if not item["name"]:return self.send_json(*err("INVALID_LIBRARY","name is required"))
            s["library"].append(item);save(s);return self.send_json(201,{"ok":True,"item":item})
        return self.send_json(404,{"ok":False,"error":{"code":"NOT_FOUND","message":"Unknown endpoint"}})
    def do_PATCH(self):
        path=urlparse(self.path).path;b=self.body();s=load();m=re.fullmatch(r"/api/context/([^/]+)",path)
        if m:
            c=next((x for x in s["context"] if x["id"]==m.group(1)),None)
            if not c:return self.send_json(*err("CONTEXT_NOT_FOUND","context not found",404))
            if "project" in b:c["project"]=bool(b["project"])
            save(s);return self.send_json(200,{"ok":True,"context":c})
        return self.send_json(404,{"ok":False,"error":{"code":"NOT_FOUND","message":"Unknown endpoint"}})
    def do_DELETE(self):
        path=urlparse(self.path).path;s=load()
        if path=="/api/library":
            for x in s["library"]:
                if x.get("path"):
                    p=ROOT/x["path"]
                    if p.exists():p.unlink()
            s["library"]=[];save(s);return self.send_json(200,{"ok":True,"deleted_all":True})
        for kind in ("memory","context","library","plugin","message"):
            m=re.fullmatch(r"/api/"+kind+r"/([^/]+)",path)
            if m:
                item_id=m.group(1);items=s[kind];item=next((x for x in items if x["id"]==item_id),None)
                if not item:return self.send_json(*err("NOT_FOUND",f"{kind} not found",404))
                s[kind]=[x for x in items if x["id"]!=item_id]
                if kind=="library" and item.get("path"):
                    p=ROOT/item["path"]
                    if p.exists():p.unlink()
                save(s);return self.send_json(200,{"ok":True,"deleted":item_id})
        return self.send_json(404,{"ok":False,"error":{"code":"NOT_FOUND","message":"Unknown endpoint"}})
def run(host="127.0.0.1",port=8787):
    server=ThreadingHTTPServer((host,port),Handler);print(f"HG Runtime READY http://{host}:{port}",flush=True);server.serve_forever()
if __name__=="__main__":run()
