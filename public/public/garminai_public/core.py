"""Demo-only core; no Garmin credentials or real user data."""
import json
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / 'data'

def _read(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))

def status():
    rows = _read('demo_activities.json')['activities']
    return {'mode':'DEMO_ONLY', 'garmin_oauth':'NOT_CONNECTED', 'users':0,
            'demo_activities':len(rows), 'message_sr':'Prikazani podaci su izmišljeni; ne predstavljaju stvaran Garmin nalog.'}

def activities(start_date=None, end_date=None, sport=None, limit=50):
    limit=max(1,min(int(limit),100))
    for val in (start_date,end_date):
        if val: date.fromisoformat(val)
    if start_date and end_date and start_date>end_date: raise ValueError('start_date posle end_date')
    rows=_read('demo_activities.json')['activities']
    filtered=[x for x in rows if (not start_date or x['date']>=start_date)
              and (not end_date or x['date']<=end_date) and (not sport or x['sport']==sport)]
    return {'mode':'DEMO_ONLY','count':len(filtered),'activities':filtered[:limit]}

def detail(activity_id):
    rows=_read('demo_activities.json')['activities']
    a=next((x for x in rows if x['id']==activity_id),None)
    if not a: return {'error':'unknown_demo_activity','id':activity_id,'mode':'DEMO_ONLY'}
    return {'mode':'DEMO_ONLY','activity':a}

def weekly_summary(start_date=None,end_date=None):
    rows=activities(start_date,end_date,sport='running',limit=100)['activities']
    weeks={}
    for a in rows:
        d=date.fromisoformat(a['date']); key=f'{d.isocalendar().year}-W{d.isocalendar().week:02}'
        w=weeks.setdefault(key,{'runs':0,'km':0.0,'minutes':0.0})
        w['runs']+=1; w['km']+=a['distance_km'];w['minutes']+=a['duration_min']
    for w in weeks.values():w['km']=round(w['km'],2);w['minutes']=round(w['minutes'],1)
    return {'mode':'DEMO_ONLY','weeks':dict(sorted(weeks.items())),'warning_sr':'Oporavak i intenzitet se ne mogu pouzdano odrediti samo iz prosečnog pulsa.'}

def literature(topic=None,limit=20):
    items=_read('literature/approved.json')['sources']
    if topic:items=[x for x in items if topic.lower() in [y.lower() for y in x['topic']]]
    return {'catalog':'reviewed','count':len(items),'sources':items[:max(1,min(int(limit),50))]}

def guidance(distance='10k', language='sr'):
    key=distance.lower().replace(' ','')
    lookup={'5k':('5 km','Ekonomija trčanja, aerobni rad i ciljane brže deonice.'),
            '10k':('10 km','Aerobna baza, prag, kontrolisana intenzivna sesija.'),
            '21k':('21,1 km','Postepene dužine, tempo oko ciljne trke i oporavak.'),
            '21.1k':('21,1 km','Postepene dužine, tempo oko ciljne trke i oporavak.'),
            'halfmarathon':('21,1 km','Postepene dužine, tempo oko ciljne trke i oporavak.'),
            '42k':('42,2 km','Dužine, stabilan obim, vežbanje unosa tečnosti i energije.'),
            '42.2k':('42,2 km','Dužine, stabilan obim, vežbanje unosa tečnosti i energije.'),
            'marathon':('42,2 km','Dužine, stabilan obim, vežbanje unosa tečnosti i energije.')}
    if key not in lookup:raise ValueError('Distance: 5k, 10k, 21k ili marathon')
    name,summary=lookup[key]
    return {'mode':'DEMO_ONLY','distance':name,'language':language,'principles_sr':summary,
            'evidence':literature(limit=5)['sources'],
            'warning_sr':'Ovo nisu personalizovane zone pulsa niti propisan plan. Preporuke zahtevaju istoriju, cilj, raspoložive dane i subjektivni osećaj napora.'}
