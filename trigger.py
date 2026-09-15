import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8000/api/users/1/sessions', method='POST')
session_id = json.loads(urllib.request.urlopen(req).read().decode())['id']
payload = {'user_id': 1, 'session_id': session_id, 'message': 'Run google_workspace__manage_accounts with {"operation": "authenticate"}'}
req2 = urllib.request.Request('http://127.0.0.1:8000/api/chat/headless', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
resp = json.loads(urllib.request.urlopen(req2, timeout=120).read().decode())
print(resp.get('response'))
