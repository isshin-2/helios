import sqlite3
import json
import os

db_path = 'data/helios.db'
if not os.path.exists(db_path):
    # Try looking for it in the root or router directory
    db_path = 'helios.db'
if not os.path.exists(db_path):
    print("DB not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT system_access FROM users WHERE id = 1")
row = cursor.fetchone()
if row and row[0]:
    access = json.loads(row[0])
    # Add paths
    new_path = r'C:\Users\krithik\tempsense'
    if new_path not in access['file_read']['paths']:
        access['file_read']['paths'].append(new_path)
    if new_path not in access['directory_list']['paths']:
        access['directory_list']['paths'].append(new_path)
    # Also give it file write access while we're at it? No, maybe just read and list.
    cursor.execute("UPDATE users SET system_access = ? WHERE id = 1", (json.dumps(access),))
    conn.commit()
    print("Permissions updated successfully.")
else:
    print("User not found or no system_access set.")
conn.close()
