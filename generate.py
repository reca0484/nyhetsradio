"""Gratis nyhetsöversikt från offentliga RSS-flöden. Ingen AI eller betaltjänst."""
import datetime, email.utils, html, json, re, urllib.request, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

NOW=datetime.datetime.now(ZoneInfo("Europe/Stockholm"))
FEEDS={
 "SVT Nyheter":"https://www.svt.se/nyheter/rss.xml",
 "Sveriges Radio Ekot":"https://api.sr.se/api/rss/program/83",
 "Dagens Nyheter":"https://www.dn.se/rss/",
}
TOPICS=[
 ("Kriminalvården",r"kriminalvård|anstalt|häkte|fängelse|intagen|frihetsberöv|JO-kritik|fångtransport|beläggning"),
 ("Östergötland",r"östergöt|linköping|norrköping|motala|mjölby|finspång|vadstena|söderköping|kinda|åtvidaberg|valdemarsvik|ydre|boxholm|ödeshög"),
 ("Politik och ekonomi",r"regering|riksdag|minister|valet|budget|ränta|inflation|ekonomi|företag|arbetslös|skatt|bostad"),
 ("Kultur och litteratur",r"kultur|litteratur|bok|författare|teater|film|konst|musik|roman"),
]
def clean(s):
 s=re.sub(r"<[^>]*>"," ",html.unescape(s or ""))
 return re.sub(r"\\s+"," ",s).strip()
def fetch(pair):
 name,url=pair
 req=urllib.request.Request(url,headers={"User-Agent":"Nyhetsradio/1.0 (RSS reader)"})
 with urllib.request.urlopen(req,timeout=22) as r: data=r.read(2_000_000)
 root=ET.fromstring(data)
 entries=[]
 for item in root.findall(".//item")[:100]:
  title=clean(item.findtext("title"))
  desc=clean(item.findtext("description"))
  link=(item.findtext("link") or "").strip()
  date=item.findtext("pubDate") or ""
  try: published=email.utils.parsedate_to_datetime(date).astimezone(ZoneInfo("Europe/Stockholm"))
  except Exception: published=NOW
  if title and link and published >= NOW-datetime.timedelta(hours=42):
   entries.append(dict(source=name,title=title,desc=desc,link=link,date=published.isoformat()))
 return entries
items=[];errors=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 futures={pool.submit(fetch,p):p[0] for p in FEEDS.items()}
 for future in as_completed(futures):
  try: items.extend(future.result())
  except Exception as e: errors.append(f"{futures[future]}: {type(e).__name__}")
if not items: raise SystemExit("Inga RSS-nyheter kunde hämtas; tidigare rapport behålls.")
seen=set(); unique=[]
for x in sorted(items,key=lambda a:a["date"],reverse=True):
 k=re.sub(r"[^a-zåäö0-9]","",x["title"].lower())[:90]
 if k in seen: continue
 seen.add(k);unique.append(x)
sections={name:[] for name,_ in TOPICS}
sections["Sverige och världen"]=[]
for x in unique:
 hay=(x["title"]+" "+x["desc"]).lower()
 topic=next((name for name,pat in TOPICS if re.search(pat,hay)), "Sverige och världen")
 sections[topic].append(x)
lines=[f"Nyheter. {NOW.strftime('%d %B %Y')}.","Automatisk nyhetsöversikt från öppna nyhetsflöden. Detta är inte en fullständig genomgång av radio- eller tv-sändningar."]
selected=[]
limits={"Kriminalvården":25,"Östergötland":25,"Sverige och världen":32,"Politik och ekonomi":18,"Kultur och litteratur":12}
for section in ["Sverige och världen","Östergötland","Kriminalvården","Politik och ekonomi","Kultur och litteratur"]:
 chosen=sections[section][:limits[section]]
 if not chosen: continue
 lines.append("\\n"+section+".")
 for x in chosen:
  # Återger rubriker, inte hela upphovsrättsskyddade artiklar.
  lines.append(f'{x["source"]}. {x["title"]}.')
  selected.append(x)
lines.append("\\nP1 Morgon: Se dagens avsnitt och kapitellänkar på https://www.sverigesradio.se/poddar/p1-morgon")
lines.append("TV4 Nyhetsmorgon: Se dagens avsnitt på https://www.tv4play.se/")
lines.append("TV4 Nyhetsdagen: Se dagens klipp på https://www.tv4.se/nyhetsdagen")
lines.append("\\nKällänkar.")
for x in selected:lines.append(f'{x["source"]}: {x["link"]}')
if errors:lines.append("Källor som inte kunde hämtas: "+", ".join(errors))
with open("report.json","w",encoding="utf-8") as f:
 json.dump({"updated":NOW.strftime("%Y-%m-%d %H:%M %Z"),"text":"\\n".join(lines),"items":selected,"warnings":errors,"method":"Gratis RSS-översikt, inte fullständig programsammanfattning"},f,ensure_ascii=False,indent=2)
print(f"Skrev {len(selected)} artikellänkar från {len(FEEDS)-len(errors)} källor.")
