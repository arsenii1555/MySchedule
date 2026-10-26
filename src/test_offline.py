import asyncio,subprocess,os,time
from playwright.async_api import async_playwright
srv=subprocess.Popen(["python3","-m","http.server","8765","--bind","127.0.0.1"],cwd="..",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(1)
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(); ctx=await b.new_context(viewport={"width":390,"height":844}); pg=await ctx.new_page()
    errs=[];pg.on("pageerror",lambda e:errs.append(str(e)))
    await pg.goto("http://localhost:8765/?g=1r"); await pg.wait_for_timeout(1500)
    print("sw:",await pg.evaluate("()=>navigator.serviceWorker.controller?'controlled':'no'"))
    await pg.reload(); await pg.wait_for_timeout(1000)
    print("sw after reload:",await pg.evaluate("()=>navigator.serviceWorker.controller?'controlled':'no'"))
    print("setup step:",await pg.evaluate("()=>document.querySelector('#setup .step')&&document.querySelector('#setup .step').textContent"))
    srv.terminate(); await ctx.set_offline(True)
    await pg.goto("http://localhost:8765/"); await pg.wait_for_timeout(800)
    print("offline title:",await pg.title(), "| has setup:", await pg.evaluate("()=>!!document.getElementById('setup')"))
    print(errs); await b.close()
asyncio.run(main())
