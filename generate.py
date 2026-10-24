"""Nyhetsradio: gratis, redaktionellt prioriterad RSS-sammanställning utan AI-API."""
import datetime,email.utils,html,json,os,re,urllib.request,xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor,as_completed
from zoneinfo import ZoneInfo

NOW=datetime.datetime.now(ZoneInfo("Europe/Stockholm"))
if os.getenv("SCHEDULED")=="1" and NOW.hour!=11:
 print("Utanför klockan 11 svensk tid.");raise SystemExit(0)

# Svenska redaktioner ger svenska texter. Utländska RSS-texter läses inte upp oöversatta.
FEEDS={
 "Ekot":"https://api.sr.se/api/rss/program/83",
 "SVT":"https://www.svt.se/nyheter/rss.xml",
 "SVT Öst":"https://www.svt.se/nyheter/lokalt/ost/rss.xml",
 "DN":"https://www.dn.se/rss/",
 "Svenska Dagbladet":"https://www.svd.se/feed/articles.rss",
 "Sydsvenskan":"https://www.sydsvenskan.se/feeds/feed.xml",
 "Expressen":"https://feeds.expressen.se/nyheter/",
 "Aftonbladet":"https://rss.aftonbladet.se/rss2/small/pages/sections/senastenytt/",
 "BBC":"https://feeds.bbci.co.uk/news/world/rss.xml",
 "New York Times":"https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
 "Financial Times":"https://www.ft.com/rss/home",
 "Der Spiegel":"https://www.spiegel.de/international/index.rss",
 "CNN":"https://rss.cnn.com/rss/edition_world.rss",
 "Washington Post":"https://feeds.washingtonpost.com/rss/world",
 "The Guardian":"https://www.theguardian.com/world/rss",
 "BBC":"https://feeds.bbci.co.uk/news/world/rss.xml",
 "New York Times":"https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
 "Financial Times":"https://www.ft.com/rss/home",
 "Der Spiegel":"https://www.spiegel.de/international/index.rss",
 "CNN":"https://rss.cnn.com/rss/edition_world.rss",
 "Washington Post":"https://feeds.washingtonpost.com/rss/world",
 "The Guardian":"https://www.theguardian.com/world/rss",
 "P1 Morgon":"https://api.sr.se/api/rss/program/1602",
}
LOCAL=re.compile(r"östergöt|linköping|norrköping|motala|mjölby|finspång|vadstena|söderköping|kinda|åtvidaberg|valdemarsvik|ydre|boxholm|ödeshög",re.I)
PRISON=re.compile(r"kriminalvård|anstalt|häkte|fängelse|intagen|fångtransport|frihetsberöv",re.I)
CULTURE=re.compile(r"kultur|litteratur|författare|roman|bokpris|teater|utställning|konstnär|musik|skivsläpp",re.I)
WORLD=re.compile(r"ukraina|ryssland|putin|kina|kinesisk|indien|indisk|usa|amerikansk|trump|washington|europa|eu:s|nato|israel|gaza|iran|taiwan|sudan|mellanöstern|frankrike|tyskland|brittisk|japan|pakistan|fn:s|president|utrikes|internationell|världsledare",re.I)
POLITICS=re.compile(r"regering|riksdag|minister|partiledare|budget|ränta|inflation|skatt|arbetslös|sjukvård|skola|ekonomi|energi|bostad|utredning|valresultat",re.I)
IMPORTANT=re.compile(r"krig|attack|vapenvila|fred|kris|katastrof|omkom|död|domstol|åtal|beslut|säkerhet|strejk|klimat|utredning|förhandling",re.I)
SPORT=re.compile(r"fotboll|ishockey|allsvenskan|tennis|olympiad|idrott|mästerskap|sportchef",re.I)
GOSSIP=re.compile(r"influencer|realitystjärna|kändisbråk|dejtar|skilsmässorykte|paradise hotel",re.I)
MARKET=re.compile(r"börsbubbla|börskrasch|börsfall|finanskris|marknadskrasch|systemrisk|kreditkris|risk för börsras|varnar för börsfall",re.I)
STOP=set("och att det den ett med för från till som har hade efter över under inte detta enligt säger uppger nya nytt stora sverige världen rapporterar".split())

def clean(s):
 s=html.unescape(s or "")
 s=re.sub(r"<[^>]*>"," ",s)
 return re.sub(r"\\s+"," ",s).strip()
def fetch(pair):
 source,url=pair
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; Nyhetsradio/2.0)"})
 with urllib.request.urlopen(req,timeout=25) as r:data=r.read(2500000)
 root=ET.fromstring(data)
 result=[]
 for item in root.findall(".//item")[:120]:
  title=clean(item.findtext("title"));desc=clean(item.findtext("description"))
  link=(item.findtext("link") or "").strip()
  try:dt=email.utils.parsedate_to_datetime(item.findtext("pubDate")).astimezone(ZoneInfo("Europe/Stockholm"))
  except Exception:continue
  if title and link and dt>=NOW-datetime.timedelta(hours=48):
   result.append(dict(source=source,title=title,desc=desc,link=link,date=dt.isoformat()))
 return result

items=[];errors=[]
with ThreadPoolExecutor(max_workers=10) as pool:
 futures={pool.submit(fetch,p):p[0] for p in FEEDS.items()}
 for future in as_completed(futures):
  try:items+=future.result()
  except Exception as e:errors.append(f"{futures[future]}: {type(e).__name__}")
if not items:raise SystemExit("Inga nyhetsflöden tillgängliga. Föregående rapport behålls.")

def words(s):
 return {w for w in re.findall(r"[a-zåäö0-9]{3,}",s.lower()) if w not in STOP}
def same(a,b):
 if a["link"]==b["link"]:return True
 wa,wb=words(a["title"]),words(b["title"])
 common=len(wa&wb)
 return (common>=3 and common/max(1,min(len(wa),len(wb)))>=.63) or (common>=2 and SequenceMatcher(None,a["title"].lower(),b["title"].lower()).ratio()>=.76)
FOREIGN={"BBC","New York Times","Financial Times","Der Spiegel","CNN","Washington Post","The Guardian"}
def valid(x):
 d=x["desc"]
 return len(d)>=65 and SequenceMatcher(None,x["title"].lower(),d.lower()).ratio()<.78 and not d.lower().startswith(x["title"].lower()[:40])
def score(x):
 hay=x["title"]+" "+x["desc"]
 return 3+(9 if IMPORTANT.search(x["title"]) else 4 if IMPORTANT.search(hay) else 0)+(5 if WORLD.search(x["title"]) or POLITICS.search(x["title"]) else 0)+min(len(x["desc"])//140,3)-(25 if SPORT.search(x["title"]) or GOSSIP.search(x["title"]) else 0)-(18 if re.search(r"influencer|influerare|filmroll|selftape|novell|recension|krönika",x["title"],re.I) else 0)
def section(x):
 hay=x["title"]+" "+x["desc"]
 if LOCAL.search(hay) or x["source"]=="SVT Öst":return "Östergötland"
 if PRISON.search(hay):return "Kriminalvården"
 if WORLD.search(hay):return "Internationell utblick"
 if CULTURE.search(hay):return "Kultur och litteratur"
 if POLITICS.search(hay):return "Politik och ekonomi"
 return "Sverige och världen"
def detail(x):
 d=x["desc"].strip()
 if len(d)>620:
  chunk=d[:620];end=max(chunk.rfind("."),chunk.rfind("!"),chunk.rfind("?"))
  d=chunk[:end+1] if end>260 else chunk.rsplit(" ",1)[0]+"."
 return d if d.endswith((".","!","?")) else d+"."
def story(x,group):
 out=[x["title"].rstrip(".")+"."]
 seen=[]
 for y in [x]+group:
  d=detail(y)
  if any(SequenceMatcher(None,d.lower(),old.lower()).ratio()>.63 for old in seen):continue
  if len(words(d)) and any(len(words(d)&words(old))/max(1,min(len(words(d)),len(words(old))))>.83 for old in seen):continue
  out.append(y["source"]+(" rapporterar: " if not seen else " tillägger: ")+d)
  seen.append(d)
  if len(seen)>=2:break
 return " ".join(out)

# Samla händelser en gång globalt, så att samma nyhet inte kommer i flera avsnitt.
candidates=sorted([x for x in items if valid(x) and x["source"] not in FOREIGN],key=lambda x:(score(x),x["date"]),reverse=True)
groups=[]
for x in candidates:
 match=next((g for g in groups if same(x,g[0])),None)
 if match is None:groups.append([x])
 else:match.append(x)
for g in groups:g.sort(key=lambda x:(x["source"]=="Ekot",score(x),len(x["desc"])),reverse=True)
buckets={k:[] for k in ("Sverige och världen","Politik och ekonomi","Östergötland","Kriminalvården","Kultur och litteratur","Internationell utblick")}
for g in groups:
 primary=g[0]
 buckets[section(primary)].append(g)
for key in buckets:buckets[key].sort(key=lambda g:(score(g[0]),g[0]["date"]),reverse=True)

months="januari februari mars april maj juni juli augusti september oktober november december".split()
lines=[f"{NOW.day} {months[NOW.month-1]} {NOW.year}."]
selected=[];used=set()
limits={"Sverige och världen":7,"Politik och ekonomi":7,"Östergötland":6,"Kriminalvården":5,"Kultur och litteratur":3,"Internationell utblick":5}
def add_group(g,heading):
 if id(g) in used:return False
 if heading not in emitted:lines.append("\n"+heading+".");emitted.add(heading)
 lines.append(story(g[0],g[1:]))
 selected.extend(g);used.add(id(g))
 return True
emitted=set()
for heading in ("Sverige och världen","Politik och ekonomi","Östergötland","Kriminalvården","Kultur och litteratur"):
 for g in buckets[heading]:
  if WORLD.search(g[0]["title"]+" "+g[0]["desc"]) and heading not in ("Östergötland","Kriminalvården"):continue
  if sum(id(z) in used for z in buckets[heading])>=limits[heading]:break
  add_group(g,heading)

# Internationell utblick ska alltid vara en egen del och får hämta relevanta
# världshändelser även från andra rubrikgrupper, men aldrig upprepa en händelse.
world_groups=[g for g in groups if WORLD.search(g[0]["title"]+" "+g[0]["desc"]) and id(g) not in used]
world_groups.sort(key=lambda g:(score(g[0]),g[0]["date"]),reverse=True)
for g in world_groups[:7]:add_group(g,"Internationell utblick")
if "Internationell utblick" not in emitted:
 lines.append("\nInternationell utblick. De tillgängliga svenska nyhetsflödena innehöll inga ytterligare självständiga internationella händelser med tillräcklig bakgrund för en tillförlitlig sammanfattning.")

# Börsnotis kräver substans. Rubrikträffar utan förklaring utelämnas.
market=[g[0] for g in groups if MARKET.search(g[0]["title"]+" "+g[0]["desc"]) and len(g[0]["desc"])>=180]
if market:
 x=sorted(market,key=lambda x:(score(x),x["date"]),reverse=True)[0]
 lines.append("\nBörsrisk. "+x["source"]+" rapporterar: "+x["title"].rstrip(".")+". "+detail(x)+" Det är en riskbedömning, inte en säker prognos.")
 if x not in selected:selected.append(x)
with open("report.json","w",encoding="utf-8") as f:
 json.dump({"updated":NOW.strftime("%Y-%m-%d %H:%M %Z"),"text":"\n".join(lines),"items":selected,"warnings":errors,"source_counts":{name:sum(x["source"]==name for x in selected) for name in FEEDS},"feed_counts":{name:sum(x["source"]==name for x in items) for name in FEEDS},"monitored_not_translated":sorted(FOREIGN),"method":"Redaktionellt prioriterad regelbaserad RSS-översikt, inga AI-genererade eller verifierade helartikelreferat."},f,ensure_ascii=False,indent=2)
print("Rapport klar:",len(selected),"källnotiser;",{name:sum(x["source"]==name for x in selected) for name in FEEDS})
