import sys
sys.stdout.reconfigure(encoding='utf-8')
import psycopg
from datetime import datetime

conn = psycopg.connect('postgresql://neondb_owner:npg_SuxR81XeavLj@ep-noisy-fog-aebak51k-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require', sslmode='require')
conn.autocommit = True

today = datetime.now().strftime('%Y-%m-%d')
print('Today:', today)

r = conn.execute('SELECT id, tenant_id, mouvement, quantite, date_mouvement FROM stock ORDER BY id DESC LIMIT 10')
for row in r.fetchall():
    print(row)

print()
q = """SELECT COALESCE(SUM(CASE WHEN mouvement='entree' THEN quantite ELSE 0 END),0), 
       COALESCE(SUM(CASE WHEN mouvement='sortie' THEN quantite ELSE 0 END),0) FROM stock"""
r = conn.execute(q)
print('All time entrees/sorties:', r.fetchone())

q2 = """SELECT COALESCE(SUM(CASE WHEN mouvement='entree' THEN quantite ELSE 0 END),0), 
        COALESCE(SUM(CASE WHEN mouvement='sortie' THEN quantite ELSE 0 END),0) FROM stock 
        WHERE SUBSTRING(date_mouvement,1,10)=%s"""
r2 = conn.execute(q2, (today,))
print('Today entrees/sorties:', r2.fetchone())

print()
r3 = conn.execute('SELECT p.id, p.nom, p.tenant_id, p.stock FROM produits p')
for row in r3.fetchall():
    print(f'Product: {row}')

conn.close()
