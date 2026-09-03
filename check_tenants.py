import psycopg
conn = psycopg.connect('postgresql://neondb_owner:npg_SuxR81XeavLj@ep-noisy-fog-aebak51k-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require')
cur = conn.execute('SELECT id, nom, actif FROM tenants ORDER BY id')
for r in cur.fetchall():
    print(f"ID={r[0]} Nom={r[1]} Actif={r[2]}")
conn.close()
