import json
D=json.load(open("data/parsed.json"))
PDF={1:"https://law.lnu.edu.ua/wp-content/uploads/2026/09/1-kurs-1-semestr-2026-2027-2.pdf",2:"https://law.lnu.edu.ua/wp-content/uploads/2026/09/2-kurs-1-semestr-2026-2027-2.pdf",3:"https://law.lnu.edu.ua/wp-content/uploads/2026/09/3-kurs-1-semestr-2026-2027-2.pdf",4:"https://law.lnu.edu.ua/wp-content/uploads/2026/09/4-kurs-1-semestr-2026-2027-2.pdf"}
out={"updated":"остаточний розклад, вересень 2026","sem":{"start":"2026-09-01","end":"2026-12-31"},"ref":{"mon":"2026-10-19","t":"z"},
"times":{"1":["08:30","09:50"],"2":["10:10","11:30"],"3":["11:50","13:10"],"4":["13:30","14:50"],"5":["15:05","16:25"],"6":["16:40","18:00"],"7":["18:10","19:30"]},"courses":[]}
for C in D["courses"]:
    L=[]; seen={}
    for x in C["L"]:
        x=dict(x); x.pop("_pg",None); x.pop("potok",None)
        if x["s"]=="ДВВС" and not x.get("el"): x["s"]="ДВВС"; x["k"]=""
        key=json.dumps({k:v for k,v in x.items() if k!="g"},ensure_ascii=False,sort_keys=True)
        if key in seen: seen[key]["g"]=sorted(set(seen[key]["g"])|set(x["g"]),key=C["groups"].index)
        else: seen[key]=x; L.append(x)
    out["courses"].append({"n":C["n"],"pdf":PDF[C["n"]],"groups":C["groups"],"streams":C["streams"],"L":L})
json.dump(out,open("data/data.json","w"),ensure_ascii=False,separators=(",",":"))
import os;print(os.path.getsize("data/data.json"),"bytes")
