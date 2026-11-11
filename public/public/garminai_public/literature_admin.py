"""Candidate discovery via Crossref; explicit human approval required. CLI only."""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen,Request

PATH=Path(__file__).resolve().parents[1]/'data'/'literature'

def discover(query):
    api='https://api.crossref.org/works?'+urlencode({'query.bibliographic':query,'rows':5,'select':'DOI,title,published,URL,type'})
    req=Request(api,headers={'User-Agent':'GarminAI-Public/0.1 (literature discovery; human review required)'})
    with urlopen(req,timeout=15) as resp: items=json.load(resp)['message']['items']
    p=PATH/'candidates.json'; saved=json.loads(p.read_text(encoding='utf-8'))
    old={c.get('doi') for c in saved['candidates']}
    for x in items:
        doi=x.get('DOI','');title=(x.get('title') or [''])[0]
        if not doi or not title or doi in old:continue
        saved['candidates'].append({'doi':doi,'title':title,'url':'https://doi.org/'+doi,
                                    'source':'crossref_metadata','status':'needs_manual_review','found':datetime.now(timezone.utc).date().isoformat()})
        old.add(doi)
    p.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return saved['candidates'][-5:]

def main():
    parser=argparse.ArgumentParser(description='Discover bibliography candidates; does not publish them.')
    parser.add_argument('--query',required=True)
    args=parser.parse_args()
    print(json.dumps(discover(args.query),ensure_ascii=False,indent=2))
    print('REVIEW REQUIRED: verify study text, methodology, applicability, source and conclusions; edit approved.json manually via reviewed PR.')

if __name__=='__main__':main()
