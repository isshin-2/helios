import json
from db import get_db

conn = get_db()
cursor = conn.cursor()
cursor.execute("SELECT id, system_access FROM users WHERE id = 1")
row = cursor.fetchone()
if row:
    access = json.loads(row['system_access']) if row['system_access'] else {}
    print(json.dumps(access, indent=2))
else:
    print("User not found")
conn.close()
