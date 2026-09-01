import psycopg2
import psycopg2.extras
import sqlite3
import os

DB_URL = os.environ.get("DATABASE_URL", "")
LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commerce.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    nom TEXT UNIQUE NOT NULL,
    actif INTEGER DEFAULT 1,
    date_creation TEXT,
    localisation TEXT DEFAULT '',
    type_commerce TEXT DEFAULT 'Chaussures'
);

CREATE TABLE IF NOT EXISTS utilisateurs (
    id SERIAL PRIMARY KEY,
    login TEXT UNIQUE,
    code TEXT,
    tenant_id INTEGER DEFAULT 0,
    role TEXT DEFAULT 'vendeur'
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    nom TEXT,
    emoji TEXT,
    tenant_id INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS produits (
    id SERIAL PRIMARY KEY,
    categorie_id INTEGER,
    nom TEXT,
    prix_usd REAL,
    prix_cdf REAL,
    stock INTEGER DEFAULT 100,
    tenant_id INTEGER DEFAULT 0,
    FOREIGN KEY (categorie_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS ventes (
    id SERIAL PRIMARY KEY,
    produit_id INTEGER,
    quantite INTEGER,
    total_usd REAL,
    total_cdf REAL,
    date TEXT,
    heure TEXT,
    recu_num TEXT DEFAULT '',
    client_nom TEXT DEFAULT '',
    client_tel TEXT DEFAULT '',
    prix_unit_usd REAL DEFAULT 0,
    prix_unit_cdf REAL DEFAULT 0,
    est_client_honneur INTEGER DEFAULT 0,
    client_id INTEGER DEFAULT NULL,
    tenant_id INTEGER DEFAULT 0,
    vendeur_login TEXT DEFAULT '',
    FOREIGN KEY (produit_id) REFERENCES produits(id)
);

CREATE TABLE IF NOT EXISTS recus (
    id SERIAL PRIMARY KEY,
    numero TEXT UNIQUE,
    client_nom TEXT,
    client_tel TEXT,
    total_usd REAL,
    total_cdf REAL,
    est_honneur INTEGER DEFAULT 0,
    date TEXT,
    heure TEXT,
    client_id INTEGER DEFAULT NULL,
    tenant_id INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    nom TEXT,
    telephone TEXT UNIQUE,
    nb_visites INTEGER DEFAULT 0,
    total_usd REAL DEFAULT 0,
    total_cdf REAL DEFAULT 0,
    premier_visite TEXT,
    derniere_visite TEXT,
    tenant_id INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    login TEXT,
    tenant_id INTEGER DEFAULT 0,
    action TEXT,
    details TEXT,
    date_heure TEXT
);

CREATE TABLE IF NOT EXISTS tenant_prices (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    produit_id INTEGER NOT NULL,
    prix_usd REAL,
    prix_cdf REAL,
    UNIQUE(tenant_id, produit_id),
    FOREIGN KEY (produit_id) REFERENCES produits(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER DEFAULT 0,
    user_id INTEGER DEFAULT NULL,
    message TEXT,
    is_read INTEGER DEFAULT 0,
    created_at TEXT,
    responsable TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS notif_settings (
    tenant_id INTEGER PRIMARY KEY,
    alertes_actives INTEGER DEFAULT 1,
    notif_ventes INTEGER DEFAULT 1,
    notif_stock INTEGER DEFAULT 1,
    notif_prix INTEGER DEFAULT 1,
    notif_connexion INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stock (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    mouvement TEXT NOT NULL CHECK(mouvement IN ('entree','sortie')),
    quantite INTEGER NOT NULL,
    marque TEXT,
    code_produit TEXT,
    user_id INTEGER NOT NULL,
    date_mouvement TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    tenant_id INTEGER DEFAULT 0,
    key TEXT,
    value TEXT,
    PRIMARY KEY (tenant_id, key)
);

CREATE OR REPLACE VIEW stock_restant AS
    SELECT s.product_id, s.tenant_id, s.marque, s.code_produit,
           p.nom AS produit_nom,
           SUM(CASE WHEN s.mouvement='entree' THEN s.quantite ELSE -s.quantite END) AS stock_disponible,
           SUM(CASE WHEN s.mouvement='entree' THEN s.quantite ELSE 0 END) AS total_entrees,
           SUM(CASE WHEN s.mouvement='sortie' THEN s.quantite ELSE 0 END) AS total_sorties
    FROM stock s
    JOIN produits p ON s.product_id=p.id
    GROUP BY s.product_id, s.tenant_id, s.marque, s.code_produit, p.nom;
"""

TABLES = [
    "tenants", "utilisateurs", "categories", "produits",
    "ventes", "recus", "clients", "logs", "tenant_prices",
    "notifications", "notif_settings", "stock", "settings"
]

def migrate():
    if not DB_URL:
        print("ERROR: Set DATABASE_URL environment variable first!")
        print("Example: $env:DATABASE_URL='postgres://user:pass@host:5432/baguma'")
        return

    url = DB_URL
    if "?" not in url:
        url += "?sslmode=require"

    print("Connecting to PostgreSQL...")
    pg = psycopg2.connect(url)
    pg.autocommit = True
    cur = pg.cursor()

    print("Creating schema...")
    cur.execute(SCHEMA)
    print("Schema created OK")

    cur.execute("SELECT COUNT(*) FROM tenants")
    if cur.fetchone()[0] == 0:
        print("Seeding initial data...")
        cur.execute("INSERT INTO tenants (nom, actif, localisation, type_commerce) VALUES ('Chaussure Bukavu', 1, 'Bukavu', 'Chaussures')")
        cur.execute("INSERT INTO tenants (nom, actif, localisation, type_commerce) VALUES ('Chaussure Goma', 1, 'Goma', 'Chaussures')")
        cur.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES ('0891624401', '251988', 0, 'admin')")
        cur.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES ('graciella@gmail.com', '251988', 0, 'admin')")
        cur.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES ('bukavu@gmail.com', 'Baguma2020', 1, 'vendeur')")
        cur.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES ('goma@gmail.com', 'Baguma2018', 2, 'vendeur')")
        cats = [('Chaussures Homme','👞'), ('Chaussures Femme','👠'), ('Chaussures Enfant','👟'), ('Accessoires','👜'), ('Sport','⚽')]
        for nom, emoji in cats:
            cur.execute("INSERT INTO categories (nom, emoji, tenant_id) VALUES (%s,%s,0)", (nom, emoji))
        cat_rows = cur.execute("SELECT id, nom FROM categories ORDER BY id")
        cat_ids = {r[1]: r[0] for r in cur.execute("SELECT id, nom FROM categories ORDER BY id").fetchall()}
        produits = [
            ('Nike Air Max','Nike',90), ('Nike Air Force','Nike',85), ('Adidas Ultraboost','Adidas',95),
            ('Adidas Stan Smith','Adidas',75), ('Puma RS-X','Puma',70), ('Reebok Classic','Reebok',65),
            ('New Balance 574','New Balance',80), ('Converse Chuck','Converse',55), ('Vans Old Skool','Vans',50),
            ('Timberland 6-Inch','Timberland',120)
        ]
        for nom, marque, prix in produits:
            cur.execute("INSERT INTO categories (nom, emoji, tenant_id) VALUES (%s,%s,0) RETURNING id", (nom,))
        cat_id_list = [r[0] for r in cur.execute("SELECT id FROM categories ORDER BY id").fetchall()]
        for i, (nom, marque, prix) in enumerate(produits):
            cat_id = cat_id_list[i] if i < len(cat_id_list) else 1
            cur.execute("INSERT INTO produits (nom, categorie_id, prix_usd, prix_cdf, stock, tenant_id) VALUES (%s,%s,%s,%s,100,0)", (nom, cat_id, prix, prix*2800))
            cur.execute("INSERT INTO produits (nom, categorie_id, prix_usd, prix_cdf, stock, tenant_id) VALUES (%s,%s,%s,%s,100,1)", (nom, cat_id, prix, prix*2800))
            cur.execute("INSERT INTO produits (nom, categorie_id, prix_usd, prix_cdf, stock, tenant_id) VALUES (%s,%s,%s,%s,100,2)", (nom, cat_id, prix, prix*2800))
        cur.execute("INSERT INTO settings (tenant_id, key, value) VALUES (1, 'taux_cdf', '2800')")
        cur.execute("INSERT INTO settings (tenant_id, key, value) VALUES (2, 'taux_cdf', '2800')")
        print("Initial data seeded!")

    if not os.path.exists(LOCAL_DB):
        print("No local commerce.db found. Schema only.")
        pg.close()
        return

    print("Reading local SQLite data...")
    lite = sqlite3.connect(LOCAL_DB)
    lite.row_factory = sqlite3.Row

    for table in TABLES:
        try:
            rows = lite.execute(f"SELECT * FROM {table}").fetchall()
        except Exception:
            continue
        if not rows:
            continue
        cols = rows[0].keys()
        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join(cols)
        sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        count = 0
        for row in rows:
            vals = [row[c] for c in cols]
            try:
                cur.execute(sql, vals)
                count += 1
            except Exception as e:
                pass
        print(f"  {table}: {count} rows migrated")

    lite.close()
    pg.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
