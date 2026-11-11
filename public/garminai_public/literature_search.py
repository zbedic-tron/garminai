"""Rank only manually approved sources; candidate studies never enter output."""
import re

def rank_sources(sources: list[dict], query: str, limit: int = 10):
    query = (query or '').strip().lower()
    terms = set(re.findall(r'[\w]+', query, flags=re.UNICODE))
    def score(item):
        title = item.get('title','').lower()
        topics = ' '.join(item.get('topic', [])).lower()
        notes = item.get('note_sr','').lower()
        return sum(4 for t in terms if t in topics) + sum(2 for t in terms if t in title) + sum(1 for t in terms if t in notes)
    scored = [(score(item), item) for item in sources]
    if terms:
        scored = [(score_, item) for score_, item in scored if score_ > 0]
    return [item for _, item in sorted(scored, key=lambda r: (-r[0],r[1].get('year',0)*-1,r[1].get('title','')))][:max(1,min(int(limit),50))]
