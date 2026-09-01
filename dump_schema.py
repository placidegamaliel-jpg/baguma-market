import sqlite3
conn = sqlite3.connect("commerce.db")
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table'")
for r in c.fetchall():
    if r[0]:
        print(r[0])
        print()
c.execute("SELECT sql FROM sqlite_master WHERE type='view'")
for r in c.fetchall():
    if r[0]:
        print(r[0])
        print()
conn.close()
