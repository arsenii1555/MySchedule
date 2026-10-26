import json,sys,collections
D=json.load(open("data/parsed.json"))
DN=["","Пн","Вт","Ср","Чт","Пт","Сб"]
k=int(sys.argv[1]); pgs=[int(x) for x in sys.argv[2].split(",")]
C=D["courses"][k-1]
for pg in pgs:
    print(f"===== курс {k} стор {pg}")
    Ls=[L for L in C["L"] if L.get("_pg")==pg]
    Ls.sort(key=lambda L:(L["d"],L["p"],L.get("w",""),L.get("el",""),str(L.get("eg","")),L["g"][0],L.get("sg",0)))
    st=None
    for L in Ls:
        gs=L["g"]; 
        stx=[s for s in C["streams"] if gs[0] in s][0]
        g="ПОТІК" if gs==stx else ",".join(x.replace("ЮРД-","") for x in gs)
        extra=[]
        if L.get("sg"):extra.append(f"пг{L['sg']}")
        if L.get("fl"):extra.append("мова:"+L["fl"])
        if L.get("el"):extra.append("ВИБ")
        if L.get("eg"):extra.append("гр"+",".join(map(str,L["eg"])))
        if L.get("time"):extra.append("час "+"-".join(L["time"]))
        print(f"{DN[L['d']]}{L['p']} {L.get('w','') or '*':1} | {g:10} | {' '.join(extra):14} | {L['s']} – {L['k']} | {L.get('t','')} | {L.get('r','')}")
