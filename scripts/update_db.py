import json
from db import get_db

conn = get_db()
cursor = conn.cursor()
cursor.execute("SELECT id, system_access FROM users WHERE id = 1")
row = cursor.fetchone()
if row:
    access = json.loads(row['system_access']) if row['system_access'] else {}
    access["terminal"]["enabled"] = True
    access["terminal"]["commands"].append("whatsapp")
    
    cursor.execute("UPDATE users SET system_access = ? WHERE id = ?", (json.dumps(access), 1))
    conn.commit()
    print("Permissions updated.")
else:
    print("User not found")
conn.close()
