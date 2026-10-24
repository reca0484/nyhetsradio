"""Gratis nyhetsöversikt från offentliga RSS-flöden. Ingen AI eller betaltjänst."""
from difflib import SequenceMatcher
import datetime, email.utils, html, json, os, re, urllib.request, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

NOW=datetime.datetime.now(ZoneInfo("Europe/Stockholm"))
if os.environ.get("SCHEDULED")=="1" and NOW.hour!=11:
 print("Inte klockan 11 svensk tid, hoppar över.");raise SystemExit(0)
FEEDS={
 "SVT Nyheter":"https://www.svt.se/nyheter/rss.xml",
 "Sveriges Radio Ekot":"https://api.sr.se/api/rss/program/83",
 "Dagens Nyheter":"https://www.dn.se/rss/",
 "SVT Öst":"https://www.svt.se/nyheter/lokalt/ost/rss.xml",
}
TOPICS=[
 ("Kriminalvården",r"kriminalvård|anstalt|häkte|fängelse|intagen|frihetsberöv|JO-kritik|fångtransport|beläggning"),
 ("Östergötland",r"östergöt|linköping|norrköping|motala|mjölby|finspång|vadstena|söderköping|kinda|åtvidaberg|valdemarsvik|ydre|boxholm|ödeshög"),
 ("Politik och ekonomi",r"regering|riksdag|minister|valet|budget|ränta|inflation|ekonomi|företag|arbetslös|skatt|bostad"),
 ("Kultur och litteratur",r"kultur|litteratur|bok|författare|teater|film|konst|musik|roman"),
]
def clean(s):
 s=re.sub(r"<[^>]*>"," ",html.unescape(s or ""))
 return re.sub(r"\s+"," ",s).strip()
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
# Väsentlighetsbedömning utifrån nyckelord, aktualitet och ämne.
# Denna regelbaserade metod är inte en AI-bedömning.
SPORT=re.compile(r"\b(fotboll|hockey|ishockey|allsvenskan|elitserien|derby|derbyt|matchen|målet|straffmål|guldstrid|skellefteå|brynäs|djurgården|bajen|sirius|aik|häcken|björklöven|tennis|idrott|olympiad|vm-final|os-final)\b",re.I)
SKVALLER=re.compile(r"\b(influencer|realitystjärna|kändisbråk|dejtar|skilsmässorykte|tiktokprofil|instagramprofil|paradise hotel)\b",re.I)
VIKTIGT=re.compile(r"\b(krig|fred|vapenvila|attack|död|omkom|katastrof|brand|evaku|regering|riksdag|budget|beslut|domstol|åtal|sjukvård|skola|energi|elpris|arbetslöshet|ränta|inflation|ekonomi|kris|valresultat|strejk|säkerhet|klimat|kriminalvård|anstalt|häkte|fängelse|utredning)\b",re.I)
def category(x):
 hay=(x["title"]+" "+x["desc"]).lower()
 if SPORT.search(hay): return "Sport"
 if SKVALLER.search(hay): return "Nöje"
 return next((name for name,pat in TOPICS if re.search(pat,hay)), "Sverige och världen")
def score(x):
 hay=x["title"]+" "+x["desc"]
 section=category(x)
 value=2 + (6 if VIKTIGT.search(hay) else 0)
 value+= {"Kriminalvården":5,"Östergötland":4,"Politik och ekonomi":3,"Kultur och litteratur":2,"Sverige och världen":2,"Sport":-8,"Nöje":-12}.get(section,0)
 value+=min(len(x["desc"])//110,3)
 if len(x["desc"])<75:value-=8
 if SPORT.search(hay) or SKVALLER.search(hay):value-=20
 if x["source"]=="Sveriges Radio Ekot":value+=1
 return value
def sentence(x):
 # Beskrivningen är den kontext som faktiskt publicerats av källan.
 # Ingen påhittad bakgrund eller slutsats läggs till.
 desc=x["desc"].strip()
 title=x["title"].strip().rstrip(".")
 if not desc or desc.lower()==title.lower():
  return f'{x["source"]} rapporterar: {title}. Någon närmare förklaring finns inte i det öppna nyhetsflödet.'
 desc=re.sub(r"\s+"," ",desc)
 if len(desc)>360:
  desc=desc[:360].rsplit(" ",1)[0].rstrip(" ,;:")+"."
 if not desc.endswith((".","!","?")):desc+="."
 return f'{x["source"]}. {title}. {desc}'
sections={name:[] for name,_ in TOPICS}
sections.update({"Sverige och världen":[],"Sport":[],"Nöje":[]})
for x in unique:
 x["section"]=category(x)
 x["score"]=score(x)
 sections[x["section"]].append(x)
for section in sections:sections[section].sort(key=lambda x:(x["score"],x["date"]),reverse=True)
def related(a,b):
 if a["source"]==b["source"]:return False
 ta=set(re.findall(r"[a-zåäö]{4,}",a["title"].lower()))
 tb=set(re.findall(r"[a-zåäö]{4,}",b["title"].lower()))
 common=ta&tb
 return len(common)>=3 and len(common)/max(1,min(len(ta),len(tb)))>=0.7 and SequenceMatcher(None,a["title"].lower(),b["title"].lower()).ratio()>0.45
def combined(x,others):
 result=sentence(x)
 for y in others[:3]:
  if SequenceMatcher(None,x["desc"].lower(),y["desc"].lower()).ratio()>0.75:continue
  detail=y["desc"][:450].strip()
  if detail:result+=" "+y["source"]+" tillägger: "+detail
 return result
months=["januari","februari","mars","april","maj","juni","juli","augusti","september","oktober","november","december"]
lines=[f"{NOW.day} {months[NOW.month-1]} {NOW.year}."]
selected=[]
used=set()
limits={"Sverige och världen":7,"Östergötland":6,"Kriminalvården":5,"Politik och ekonomi":6,"Kultur och litteratur":3}
for section in ["Sverige och världen","Politik och ekonomi","Östergötland","Kriminalvården","Kultur och litteratur"]:
 chosen=[x for x in sections[section] if x["score"]>=5 and len(x["desc"])>=75 and x["desc"].lower()!=x["title"].lower()][:limits[section]]
 if not chosen: continue
 lines.append("\n"+section+".")
 for x in chosen:
  if x["link"] in used:continue
  related_items=[y for y in unique if y["link"] not in used and y["link"]!=x["link"] and related(x,y) and category(y) not in ("Sport","Nöje")][:3]
  lines.append(combined(x,related_items))
  selected.extend([x]+related_items)
  used.update(y["link"] for y in [x]+related_items)
with open("report.json","w",encoding="utf-8") as f:
 json.dump({"updated":NOW.strftime("%Y-%m-%d %H:%M %Z"),"text":"\n".join(lines),"items":selected,"warnings":errors,"method":"Gratis prioriterad RSS-översikt med källornas egna kortbeskrivningar; inte AI-analys eller fullständig programsammanfattning"},f,ensure_ascii=False,indent=2)
print(f"Skrev {len(selected)} prioriterade nyhetsinslag från {len(FEEDS)-len(errors)} källor.")
