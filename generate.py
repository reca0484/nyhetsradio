import json, os, datetime, urllib.request, urllib.error
from zoneinfo import ZoneInfo
now=datetime.datetime.now(ZoneInfo('Europe/Stockholm'))
if os.environ.get('SCHEDULED')=='1' and now.hour!=11:
 print('Not 11 in Stockholm; skipping');raise SystemExit(0)
key=os.environ.get('OPENAI_API_KEY')
if not key: raise SystemExit('Missing OPENAI_API_KEY secret')
prompt='''Skriv en aktuell svensk nyhetsuppläsning för dagens datum enligt svensk tid. Gör bred webbsökning och använd färska källor. Täck Sverige, världen, Östergötland inklusive Linköping och Norrköping, Kriminalvården i hela Sverige, politik, ekonomi, samhälle, kultur och litteratur. Prioritera Östergötland och Kriminalvården. Ange källan före varje inslag. Inled exakt med Nyheter. och dagens datum. Skriv sakligt och naturligt för uppläsning. Ange källornas länkar sist. Hitta inte på fakta. Sikta på 15–25 minuter, högst 30. Om källorna inte räcker, skriv kortare.'''
payload={'model':'gpt-4.1','tools':[{'type':'web_search_preview'}],'input':prompt,'max_output_tokens':9000}
req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
try:
 with urllib.request.urlopen(req,timeout=240) as res:data=json.load(res)
except urllib.error.HTTPError as e:
 detail=e.read().decode('utf-8','replace')[:3000]
 if e.code==429:
  raise SystemExit('OpenAI API svarade 429. Kontrollera API-saldo och fakturering på platform.openai.com, samt eventuella rate limits. Detaljer: '+detail)
 raise SystemExit(f'OpenAI API-fel HTTP {e.code}: {detail}')
parts=[c.get('text','') for i in data.get('output',[]) if i.get('type')=='message' for c in i.get('content',[]) if c.get('type')=='output_text']
text='\n\n'.join(parts).strip()
if len(text)<700:raise RuntimeError('Report too short; keeping previous report')
with open('report.json','w',encoding='utf-8') as f:json.dump({'updated':now.strftime('%Y-%m-%d %H:%M %Z'),'text':text},f,ensure_ascii=False,indent=2)
