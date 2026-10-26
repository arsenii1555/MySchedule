import os,re,json,hashlib
from PIL import Image,ImageDraw,ImageFont
OUT=os.environ.get("OUT","..")
os.makedirs(OUT,exist_ok=True)
D=open("data/data.json").read()
app=open("app.html").read().replace("/*DATA*/null",D)
ver=hashlib.sha1(app.encode()).hexdigest()[:8]
# --- іконки
def icon(sz,path,pad=0.0):
    im=Image.new("RGB",(sz,sz),(29,59,143)); d=ImageDraw.Draw(im)
    f=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",int(sz*0.56*(1-pad)))
    t="П"; bb=d.textbbox((0,0),t,font=f); w,h=bb[2]-bb[0],bb[3]-bb[1]
    x=(sz-w)/2-bb[0]-sz*0.05; y=(sz-h)/2-bb[1]
    d.text((x,y),t,font=f,fill=(255,255,255))
    r=sz*0.075*(1-pad); cx=x+bb[0]+w+sz*0.085; cy=y+bb[1]+h-r
    d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(242,107,52))
    im.save(path)
icon(512,os.path.join(OUT,"icon-512.png")); icon(192,os.path.join(OUT,"icon-192.png")); icon(180,os.path.join(OUT,"apple-touch-icon.png")); icon(512,os.path.join(OUT,"icon-maskable.png"),pad=0.2)
# --- маніфест
json.dump({"name":"Пара — розклад юрфаку ЛНУ","short_name":"Пара","lang":"uk","start_url":"./","scope":"./","display":"standalone",
 "background_color":"#eceff4","theme_color":"#eceff4","description":"Розклад пар юридичного факультету ЛНУ імені Івана Франка",
 "icons":[{"src":"icon-192.png","sizes":"192x192","type":"image/png"},{"src":"icon-512.png","sizes":"512x512","type":"image/png"},{"src":"icon-maskable.png","sizes":"512x512","type":"image/png","purpose":"maskable"}]},
 open(os.path.join(OUT,"manifest.webmanifest"),"w"),ensure_ascii=False,indent=1)
# --- service worker
open(os.path.join(OUT,"sw.js"),"w").write("""const V="para-%s";
const CORE=["./","./index.html","./manifest.webmanifest","./icon-192.png","./icon-512.png","./apple-touch-icon.png"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(CORE)).then(()=>self.skipWaiting()));});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener("fetch",e=>{const r=e.request;if(r.method!=="GET")return;const u=new URL(r.url);
  if(r.mode==="navigate"){e.respondWith(fetch(r).then(res=>{const c=res.clone();caches.open(V).then(x=>x.put("./index.html",c));return res;}).catch(()=>caches.match("./index.html")));return;}
  if(u.origin===location.origin||/fonts\\.(googleapis|gstatic)\\.com$/.test(u.hostname)){
    e.respondWith(caches.match(r).then(hit=>{const net=fetch(r).then(res=>{if(res&&(res.ok||res.type==="opaque")){const c=res.clone();caches.open(V).then(x=>x.put(r,c));}return res;}).catch(()=>hit);return hit||net;}));}
});
""" % ver)
# --- сторінка
sw='if("serviceWorker" in navigator&&(location.protocol==="https:"||location.hostname==="localhost")){addEventListener("load",()=>navigator.serviceWorker.register("sw.js").catch(()=>{}));}'
body=app.replace("/*SW*/",sw)
title_end=body.index("</title>")+len("</title>")
head_extra='''
<meta name="description" content="Розклад пар юридичного факультету ЛНУ імені Івана Франка: твоя група, англійська й вибіркові, офлайн.">
<meta name="theme-color" content="#eceff4" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0e121a" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Пара">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" type="image/png" href="icon-192.png">
<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}[hidden]{display:none!important}</style>'''
html='<!doctype html>\n<html lang="uk">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'+body[:title_end]+head_extra+body[title_end:]
# розділити на head/body: все до першого <div id="app"> — у head
i=html.index('<div id="app">')
html=html[:i]+"</head>\n<body>\n"+html[i:]+"\n</body>\n</html>\n"
open(os.path.join(OUT,"index.html"),"w").write(html)
open(os.path.join(OUT,".nojekyll"),"w").write("")
print("site ok", ver, os.path.getsize(os.path.join(OUT,"index.html")))
