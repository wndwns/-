import urllib.request, json
d = json.loads(urllib.request.urlopen('http://127.0.0.1:8003/api/cooperative-ranking/naqu-bange?top_n=3', timeout=10).read())
print(json.dumps(d.get('ranking', [])[:3], ensure_ascii=False, indent=2))
print('---')
print('algorithm:', d.get('algorithm'))
print('summary:', d.get('summary'))
