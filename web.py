from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory
import os
import hashlib
from datetime import datetime, timedelta

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "baguma-market-2026-secret")
DB_URL = os.environ.get("DATABASE_URL", "")
LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commerce.db")

if DB_URL and not DB_URL.startswith("postgresql"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
IS_PG = DB_URL.startswith("postgresql")

def init_pg_schema():
    if not IS_PG:
        return
    try:
        import psycopg
        conn = psycopg.connect(DB_URL)
        conn.autocommit = True
        for stmt in SCHEMA_SQL.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
        for alter in [
            "ALTER TABLE produits ADD COLUMN IF NOT EXISTS code TEXT DEFAULT ''",
            "ALTER TABLE produits ADD COLUMN IF NOT EXISTS couleur TEXT DEFAULT ''",
            "ALTER TABLE rapports_temp ADD COLUMN IF NOT EXISTS total_usd REAL DEFAULT 0",
            "ALTER TABLE rapports_temp ADD COLUMN IF NOT EXISTS total_cdf REAL DEFAULT 0",
            "ALTER TABLE rapports_temp ADD COLUMN IF NOT EXISTS nb_ventes INTEGER DEFAULT 0",
            "ALTER TABLE rapports_temp ADD COLUMN IF NOT EXISTS nb_clients INTEGER DEFAULT 0",
            "ALTER TABLE recus ADD COLUMN IF NOT EXISTS signature TEXT DEFAULT ''",
            "ALTER TABLE recus ADD COLUMN IF NOT EXISTS vendeur_login TEXT DEFAULT ''",
            "ALTER TABLE recus ADD COLUMN IF NOT EXISTS verrouille INTEGER DEFAULT 0"
        ]:
            try:
                conn.execute(alter)
            except Exception:
                pass
        for tbl in [
            "CREATE TABLE IF NOT EXISTS rapports (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL, vendeur_login TEXT NOT NULL, vendeur_id INTEGER NOT NULL, total_usd REAL DEFAULT 0, total_cdf REAL DEFAULT 0, nb_ventes INTEGER DEFAULT 0, nb_clients INTEGER DEFAULT 0, date_rapport TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS rapports_temp (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL, vendeur_login TEXT NOT NULL, vendeur_id INTEGER NOT NULL, date_rapport TEXT NOT NULL, expire_at TEXT NOT NULL, total_usd REAL DEFAULT 0, total_cdf REAL DEFAULT 0, nb_ventes INTEGER DEFAULT 0, nb_clients INTEGER DEFAULT 0)"
        ]:
            try:
                conn.execute(tbl)
            except Exception:
                pass
        cur = conn.execute("SELECT COUNT(*) FROM tenants")
        if cur.fetchone()[0] == 0:
            conn.execute("INSERT INTO tenants (nom, actif, localisation, type_commerce) VALUES ('Chaussure Bukavu', 1, 'Bukavu', 'Chaussures')")
            conn.execute("INSERT INTO tenants (nom, actif, localisation, type_commerce) VALUES ('Chaussure Goma', 1, 'Goma', 'Chaussures')")
            conn.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES ('0891624401', '251988', 0, 'admin')")
            conn.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES ('graciella@gmail.com', '251988', 0, 'admin')")
            conn.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES ('bukavu@gmail.com', 'Baguma2020', 1, 'vendeur')")
            conn.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES ('goma@gmail.com', 'Baguma2018', 2, 'vendeur')")
            conn.execute("INSERT INTO settings (tenant_id, key, value) VALUES (1, 'taux_cdf', '2800')")
            conn.execute("INSERT INTO settings (tenant_id, key, value) VALUES (2, 'taux_cdf', '2800')")
            for cat in ['Chaussures Homme','Chaussures Femme','Chaussures Enfant','Accessoires','Sport']:
                conn.execute("INSERT INTO categories (nom, emoji, tenant_id) VALUES (%s,%s,0)", (cat,''))
        conn.close()
        print("PostgreSQL schema initialized OK")
    except Exception as e:
        print(f"Schema init error: {e}")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tenants (id SERIAL PRIMARY KEY, nom TEXT UNIQUE NOT NULL, actif INTEGER DEFAULT 1, date_creation TEXT, localisation TEXT DEFAULT '', type_commerce TEXT DEFAULT 'Chaussures');
CREATE TABLE IF NOT EXISTS utilisateurs (id SERIAL PRIMARY KEY, login TEXT UNIQUE, code TEXT, tenant_id INTEGER DEFAULT 0, role TEXT DEFAULT 'vendeur');
CREATE TABLE IF NOT EXISTS categories (id SERIAL PRIMARY KEY, nom TEXT, emoji TEXT, tenant_id INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS produits (id SERIAL PRIMARY KEY, categorie_id INTEGER, nom TEXT, code TEXT DEFAULT '', couleur TEXT DEFAULT '', prix_usd REAL, prix_cdf REAL, stock INTEGER DEFAULT 100, tenant_id INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ventes (id SERIAL PRIMARY KEY, produit_id INTEGER, quantite INTEGER, total_usd REAL, total_cdf REAL, date TEXT, heure TEXT, recu_num TEXT DEFAULT '', client_nom TEXT DEFAULT '', client_tel TEXT DEFAULT '', prix_unit_usd REAL DEFAULT 0, prix_unit_cdf REAL DEFAULT 0, est_client_honneur INTEGER DEFAULT 0, client_id INTEGER DEFAULT NULL, tenant_id INTEGER DEFAULT 0, vendeur_login TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS recus (id SERIAL PRIMARY KEY, numero TEXT UNIQUE, client_nom TEXT, client_tel TEXT, total_usd REAL, total_cdf REAL, est_honneur INTEGER DEFAULT 0, date TEXT, heure TEXT, client_id INTEGER DEFAULT NULL, tenant_id INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS clients (id SERIAL PRIMARY KEY, nom TEXT, telephone TEXT, nb_visites INTEGER DEFAULT 0, total_usd REAL DEFAULT 0, total_cdf REAL DEFAULT 0, premier_visite TEXT, derniere_visite TEXT, tenant_id INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, user_id INTEGER, login TEXT, tenant_id INTEGER DEFAULT 0, action TEXT, details TEXT, date_heure TEXT);
CREATE TABLE IF NOT EXISTS tenant_prices (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL, produit_id INTEGER NOT NULL, prix_usd REAL, prix_cdf REAL, UNIQUE(tenant_id, produit_id));
CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, tenant_id INTEGER DEFAULT 0, user_id INTEGER DEFAULT NULL, message TEXT, is_read INTEGER DEFAULT 0, created_at TEXT, responsable TEXT DEFAULT NULL);
CREATE TABLE IF NOT EXISTS notif_settings (tenant_id INTEGER PRIMARY KEY, alertes_actives INTEGER DEFAULT 1, notif_ventes INTEGER DEFAULT 1, notif_stock INTEGER DEFAULT 1, notif_prix INTEGER DEFAULT 1, notif_connexion INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS stock (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL, product_id INTEGER NOT NULL, mouvement TEXT NOT NULL, quantite INTEGER NOT NULL, marque TEXT, code_produit TEXT, user_id INTEGER NOT NULL, date_mouvement TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings (tenant_id INTEGER DEFAULT 0, key TEXT, value TEXT, PRIMARY KEY (tenant_id, key));
CREATE TABLE IF NOT EXISTS dettes (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL, client_nom TEXT NOT NULL, client_tel TEXT DEFAULT '', montant_usd REAL NOT NULL, montant_cdf REAL NOT NULL, est_paye INTEGER DEFAULT 0, date TEXT NOT NULL, heure TEXT NOT NULL, recu_num TEXT DEFAULT '', notes TEXT DEFAULT '', vendeur_login TEXT DEFAULT '', date_paiement TEXT DEFAULT NULL, admin_id INTEGER DEFAULT NULL);
CREATE TABLE IF NOT EXISTS corbeille (id SERIAL PRIMARY KEY, table_name TEXT NOT NULL, original_id INTEGER NOT NULL, data TEXT NOT NULL, deleted_by TEXT NOT NULL, deleted_at TEXT NOT NULL, tenant_id INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS rapports_temp (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL, vendeur_login TEXT NOT NULL, vendeur_id INTEGER NOT NULL, date_rapport TEXT NOT NULL, expire_at TEXT NOT NULL, total_usd REAL DEFAULT 0, total_cdf REAL DEFAULT 0, nb_ventes INTEGER DEFAULT 0, nb_clients INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS rapports (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL, vendeur_login TEXT NOT NULL, vendeur_id INTEGER NOT NULL, total_usd REAL DEFAULT 0, total_cdf REAL DEFAULT 0, nb_ventes INTEGER DEFAULT 0, nb_clients INTEGER DEFAULT 0, date_rapport TEXT NOT NULL);
"""

init_pg_schema()

@app.route("/init")
def init_route():
    if not IS_PG:
        return "No PostgreSQL configured"
    try:
        import psycopg
        conn = psycopg.connect(DB_URL, connect_timeout=10)
        conn.execute("SELECT 1")
        conn.close()
        return "PostgreSQL OK"
    except Exception as e:
        return f"Error: {str(e)}"

def get_db():
    if IS_PG:
        import psycopg
        import psycopg.rows
        conn = psycopg.connect(DB_URL, sslmode="require", row_factory=psycopg.rows.dict_row)
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect(LOCAL_DB)
        conn.row_factory = sqlite3.Row
        return conn

def db_execute(conn, sql, params=()):
    return conn.execute(sql, params)

def db_fetchone(conn, sql, params=()):
    cur = conn.execute(sql, params)
    return cur.fetchone()

def db_fetchall(conn, sql, params=()):
    cur = conn.execute(sql, params)
    return cur.fetchall()

def db_insert(conn, sql, params=()):
    cur = conn.execute(sql, params)
    try:
        return cur.fetchone()[0]
    except Exception:
        return None

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def is_admin():
    return session.get("tenant_id", 0) == 0 and session.get("role") == "admin"

def get_effective_tid():
    if is_admin():
        return session.get("view_tenant")
    return session.get("tenant_id")

def get_taux(conn, tenant_id):
    row = db_fetchone(conn, "SELECT value FROM settings WHERE tenant_id=%s AND key='taux_cdf'" if IS_PG else
                      "SELECT value FROM settings WHERE tenant_id=? AND key='taux_cdf'", (tenant_id,))
    return float(row["value"]) if row and row["value"] else 2800.0

TENANT_NAMES = {2: "Chaussure Goma", 1: "Chaussure Bukavu", 0: "Admin Global"}

@app.errorhandler(404)
def not_found(e):
    return render_template("login.html"), 404

@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")

@app.context_processor
def inject_tenant():
    slug = session.get("tenant_slug")
    tid = session.get("tenant_id", 0)
    unread = 0
    if "user_id" in session:
        try:
            conn = get_db()
            etid = get_effective_tid()
            if etid is not None:
                row = db_fetchone(conn, "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0 AND tenant_id=%s" if IS_PG else
                                  "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0 AND tenant_id=?", (etid,))
            else:
                row = db_fetchone(conn, "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0")
            unread = row["cnt"] if row else 0
            conn.close()
        except Exception:
            unread = 0
    return {
        "tenant_slug": slug,
        "tenant_name": TENANT_NAMES.get(tid, "Admin Global"),
        "is_global_admin": tid == 0 and session.get("role") == "admin",
        "unread_notifs": unread,
    }

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_val = request.form.get("login", "").strip()
        code = request.form.get("code", "").strip()
        ville = request.form.get("ville", "").strip().lower()
        conn = get_db()
        row = db_fetchone(conn, "SELECT id, login, tenant_id, role FROM utilisateurs WHERE LOWER(login)=LOWER(%s) AND LOWER(code)=LOWER(%s)" if IS_PG else
                          "SELECT id, login, tenant_id, role FROM utilisateurs WHERE LOWER(login)=LOWER(?) AND LOWER(code)=LOWER(?)", (login_val, code))
        if row:
            user_tid = row["tenant_id"]
            user_role = row["role"]
            t_row = db_fetchone(conn, "SELECT id, nom FROM tenants WHERE LOWER(nom)=%s AND actif=1" if IS_PG else
                                "SELECT id, nom FROM tenants WHERE LOWER(nom)=? AND actif=1", (ville,))
            ville_tid = t_row["id"] if t_row else None
            if user_tid == 0 and user_role == "admin":
                if ville_tid is not None:
                    session["tenant_slug"] = ville
            elif ville_tid is not None and user_tid == ville_tid:
                session["tenant_slug"] = ville
            else:
                conn.close()
                if not ville:
                    flash("Veuillez selectionner votre ville", "error")
                else:
                    flash("Compte non autorise pour cette ville", "error")
                return redirect(url_for("login"))
            session["user_id"] = row["id"]
            session["login"] = row["login"]
            session["tenant_id"] = user_tid
            session["role"] = user_role
            if ville_tid is not None:
                session["tenant_slug"] = ville
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                      "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                      (row["id"], row["login"], user_tid, "Connexion", f"Role: {user_role} | Ville: {ville}", now))
            conn.commit()
            conn.close()
            return redirect(url_for("dashboard"))
        conn.close()
        flash("Code incorrect", "error")
    tenants = []
    try:
        conn = get_db()
        tenants = db_fetchall(conn, "SELECT nom FROM tenants WHERE actif=1 ORDER BY nom")
        conn.close()
    except Exception:
        pass
    return render_template("login.html", tenants=tenants)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/switch/<tenant_slug>")
@login_required
def switch_tenant(tenant_slug):
    if not is_admin():
        return redirect(url_for("dashboard"))
    slug = tenant_slug.lower()
    conn = get_db()
    if slug == "admin":
        session.pop("view_tenant", None)
        session["view_tenant_name"] = "Admin Global"
    else:
        t = db_fetchone(conn, "SELECT id, nom FROM tenants WHERE LOWER(nom)=%s" if IS_PG else
                        "SELECT id, nom FROM tenants WHERE LOWER(nom)=?", (slug,))
        if t:
            session["view_tenant"] = t["id"]
            session["view_tenant_name"] = t["nom"]
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    etid = get_effective_tid()

    if etid is not None:
        cond = " WHERE tenant_id=%s" if IS_PG else " WHERE tenant_id=?"
        params = (etid,)
    else:
        cond = ""
        params = ()

    row = db_fetchone(conn, f"SELECT COUNT(*) as cnt FROM produits{cond}", params)
    nb_produits = row["cnt"]
    row = db_fetchone(conn, f"SELECT COUNT(*) as cnt FROM ventes{cond}", params)
    nb_ventes = row["cnt"]
    row = db_fetchone(conn, f"SELECT COALESCE(SUM(total_usd),0) as s FROM ventes{cond}", params)
    ca_total = row["s"]
    row = db_fetchone(conn, f"SELECT COUNT(*) as cnt FROM clients{cond}", params)
    nb_clients = row["cnt"]
    stock_cond = " AND stock<=5" if cond else " WHERE stock<=5"
    row = db_fetchone(conn, f"SELECT COUNT(*) as cnt FROM produits{cond}{stock_cond}", params)
    low_stock = row["cnt"]

    dettes_cond = " AND est_paye=0" if cond else " WHERE est_paye=0"
    row = db_fetchone(conn, f"SELECT COUNT(*) as cnt, COALESCE(SUM(montant_usd),0) as total FROM dettes{cond}{dettes_cond}", params)
    nb_dettes = row["cnt"]
    total_dettes = row["total"]

    if etid is not None:
        vcond = " WHERE v.tenant_id=%s" if IS_PG else " WHERE v.tenant_id=?"
        vparams = (etid,)
    else:
        vcond = ""
        vparams = ()

    recent = db_fetchall(conn, f"""SELECT v.date||' '||v.heure as datetime, p.nom, v.quantite, v.total_usd, v.vendeur_login
        FROM ventes v JOIN produits p ON v.produit_id=p.id{vcond}
        ORDER BY v.date DESC, v.heure DESC LIMIT 10""", vparams)

    all_tenants = db_fetchall(conn, "SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_execute(conn, "DELETE FROM rapports_temp WHERE expire_at<%s" if IS_PG else "DELETE FROM rapports_temp WHERE expire_at<?", (now,))
    conn.commit()

    rapport_envoye = False
    rapport = None
    if session.get("role") == "vendeur" and session.get("tenant_id", 0) != 0:
        r = db_fetchone(conn, "SELECT * FROM rapports_temp WHERE tenant_id=%s AND vendeur_login=%s AND expire_at>%s" if IS_PG else
                        "SELECT * FROM rapports_temp WHERE tenant_id=? AND vendeur_login=? AND expire_at>?", (session["tenant_id"], session["login"], now))
        if r:
            rapport_envoye = True
            rapport = r

    unread_notifs = 0
    try:
        if etid is not None:
            row = db_fetchone(conn, "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0 AND (tenant_id=%s OR tenant_id=0)" if IS_PG else
                              "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0 AND (tenant_id=? OR tenant_id=0)", (etid,))
        else:
            row = db_fetchone(conn, "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0")
        unread_notifs = row["cnt"] if row else 0
    except Exception:
        pass

    conn.close()
    return render_template("dashboard.html", nb_produits=nb_produits, nb_ventes=nb_ventes,
                           ca_total=ca_total, nb_clients=nb_clients, low_stock=low_stock,
                           recent=recent, is_admin=is_admin(), nb_dettes=nb_dettes, total_dettes=total_dettes,
                           all_tenants=all_tenants, rapport_envoye=rapport_envoye, rapport=rapport,
                           unread_notifs=unread_notifs)

@app.route("/produits")
@login_required
def produits():
    conn = get_db()
    etid = get_effective_tid()
    search = request.args.get("search", "")
    cat = request.args.get("categorie", "")

    cond_parts = []
    params = []
    if etid is not None:
        cond_parts.append("p.tenant_id=%s" if IS_PG else "p.tenant_id=?")
        params.append(etid)
    if search:
        cond_parts.append("(p.nom LIKE %s OR p.code LIKE %s)" if IS_PG else "(p.nom LIKE ? OR p.code LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if cat:
        cond_parts.append("c.nom=%s" if IS_PG else "c.nom=?")
        params.append(cat)
    where = " WHERE " + " AND ".join(cond_parts) if cond_parts else ""

    prods = db_fetchall(conn, f"""SELECT p.id, p.nom, p.code, p.couleur, c.nom as cat_nom, p.prix_usd, p.prix_cdf, p.stock, p.tenant_id
        FROM produits p JOIN categories c ON p.categorie_id=c.id{where} ORDER BY p.nom""", params)

    cats = [r["nom"] for r in db_fetchall(conn, "SELECT DISTINCT nom FROM categories ORDER BY nom")]

    tenants_map = {}
    if is_admin():
        for r in db_fetchall(conn, "SELECT id, nom FROM tenants"):
            tenants_map[r["id"]] = r["nom"]

    conn.close()
    return render_template("produits.html", prods=prods, cats=cats, search=search,
                           cat_selected=cat, is_admin=is_admin(), tenants_map=tenants_map)

@app.route("/stock")
@login_required
def stock():
    conn = get_db()
    etid = get_effective_tid()

    if etid is not None:
        tenants = db_fetchall(conn, "SELECT id, nom FROM tenants WHERE id=%s AND actif=1" if IS_PG else
                              "SELECT id, nom FROM tenants WHERE id=? AND actif=1", (etid,))
    else:
        tenants = db_fetchall(conn, "SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")

    tenant_data = []
    for t in tenants:
        tid2 = t["id"]
        row = db_fetchone(conn, "SELECT COALESCE(SUM(quantite),0) as s FROM stock WHERE tenant_id=%s AND mouvement='entree'" if IS_PG else
                          "SELECT COALESCE(SUM(quantite),0) as s FROM stock WHERE tenant_id=? AND mouvement='entree'", (tid2,))
        entrees = row["s"]
        row = db_fetchone(conn, "SELECT COALESCE(SUM(quantite),0) as s FROM stock WHERE tenant_id=%s AND mouvement='sortie'" if IS_PG else
                          "SELECT COALESCE(SUM(quantite),0) as s FROM stock WHERE tenant_id=? AND mouvement='sortie'", (tid2,))
        sorties = row["s"]

        stock_produits = db_fetchall(conn, """SELECT p.nom as produit_nom, s.code_produit, s.marque,
                       SUM(CASE WHEN s.mouvement='entree' THEN s.quantite ELSE 0 END) as total_entrees,
                       SUM(CASE WHEN s.mouvement='sortie' THEN s.quantite ELSE 0 END) as total_sorties,
                       SUM(CASE WHEN s.mouvement='entree' THEN s.quantite ELSE -s.quantite END) as stock_disponible,
                       (SELECT u.login FROM stock s2 JOIN utilisateurs u ON s2.user_id=u.id
                        WHERE s2.product_id=s.product_id AND s2.tenant_id=s.tenant_id AND s2.mouvement='sortie'
                        ORDER BY s2.date_mouvement DESC LIMIT 1) as responsable
                FROM stock s JOIN produits p ON s.product_id=p.id
                WHERE s.tenant_id=%s
                GROUP BY s.product_id, s.tenant_id, s.code_produit, s.marque, p.nom
                ORDER BY p.nom""" if IS_PG else """SELECT p.nom as produit_nom, s.code_produit, s.marque,
                       SUM(CASE WHEN s.mouvement='entree' THEN s.quantite ELSE 0 END) as total_entrees,
                       SUM(CASE WHEN s.mouvement='sortie' THEN s.quantite ELSE 0 END) as total_sorties,
                       SUM(CASE WHEN s.mouvement='entree' THEN s.quantite ELSE -s.quantite END) as stock_disponible,
                       (SELECT u.login FROM stock s2 JOIN utilisateurs u ON s2.user_id=u.id
                        WHERE s2.product_id=s.product_id AND s2.tenant_id=s.tenant_id AND s2.mouvement='sortie'
                        ORDER BY s2.date_mouvement DESC LIMIT 1) as responsable
                FROM stock s JOIN produits p ON s.product_id=p.id
                WHERE s.tenant_id=?
                GROUP BY s.product_id, s.tenant_id, s.code_produit, s.marque, p.nom
                ORDER BY p.nom""", (tid2,))

        historique = db_fetchall(conn, """SELECT s.date_mouvement, s.mouvement, p.nom, s.code_produit, s.quantite, u.login
                FROM stock s JOIN produits p ON s.product_id=p.id JOIN utilisateurs u ON s.user_id=u.id
                WHERE s.tenant_id=%s ORDER BY s.date_mouvement DESC LIMIT 30""" if IS_PG else """SELECT s.date_mouvement, s.mouvement, p.nom, s.code_produit, s.quantite, u.login
                FROM stock s JOIN produits p ON s.product_id=p.id JOIN utilisateurs u ON s.user_id=u.id
                WHERE s.tenant_id=? ORDER BY s.date_mouvement DESC LIMIT 30""", (tid2,))

        tenant_data.append({"id": tid2, "nom": t["nom"], "entrees": entrees, "sorties": sorties,
                            "net": entrees - sorties, "stock_produits": stock_produits, "historique": historique})

    if etid is not None:
        prods = db_fetchall(conn, "SELECT id, nom FROM produits WHERE tenant_id=%s ORDER BY nom" if IS_PG else
                            "SELECT id, nom FROM produits WHERE tenant_id=? ORDER BY nom", (etid,))
    else:
        prods = db_fetchall(conn, "SELECT id, nom FROM produits ORDER BY nom")
    if etid is not None:
        users = db_fetchall(conn, "SELECT id, login FROM utilisateurs WHERE tenant_id IN (0,%s)" if IS_PG else
                            "SELECT id, login FROM utilisateurs WHERE tenant_id IN (0,?)", (etid,))
    else:
        users = db_fetchall(conn, "SELECT id, login FROM utilisateurs")

    conn.close()
    return render_template("stock.html", tenant_data=tenant_data, is_admin=is_admin(), prods=prods, users=users)

@app.route("/stock/entree", methods=["POST"])
@login_required
def stock_entree():
    conn = get_db()
    try:
        data = request.form
        tid = int(data["tenant_id"]) if is_admin() else session["tenant_id"]
        pid = int(data["produit_id"])
        qte = int(data["quantite"])
    except (ValueError, KeyError):
        conn.close()
        flash("Donnees invalides", "error")
        return redirect(url_for("stock"))
    marque = data.get("marque", "")
    code = data.get("code", "")
    try:
        resp_id = int(data.get("responsable_id", session["user_id"]))
    except ValueError:
        resp_id = session["user_id"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db_insert(conn, "INSERT INTO stock (tenant_id, product_id, mouvement, quantite, marque, code_produit, user_id, date_mouvement) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)" if IS_PG else
              "INSERT INTO stock (tenant_id, product_id, mouvement, quantite, marque, code_produit, user_id, date_mouvement) VALUES (?,?,?,?,?,?,?,?)",
              (tid, pid, "entree", qte, marque, code, resp_id, now))
    db_execute(conn, "UPDATE produits SET stock=stock+%s WHERE id=%s" if IS_PG else "UPDATE produits SET stock=stock+? WHERE id=?", (qte, pid))
    db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
              "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
              (session["user_id"], session["login"], tid, "stock_entree", f"+{qte} produit #{pid}", now))
    conn.commit()
    conn.close()
    flash(f"Entree enregistree : +{qte} paires", "success")
    return redirect(url_for("stock"))

@app.route("/stock/sortie", methods=["POST"])
@login_required
def stock_sortie():
    conn = get_db()
    try:
        data = request.form
        tid = int(data["tenant_id"]) if is_admin() else session["tenant_id"]
        pid = int(data["produit_id"])
        qte = int(data["quantite"])
    except (ValueError, KeyError):
        conn.close()
        flash("Donnees invalides", "error")
        return redirect(url_for("stock"))
    code = data.get("code", "")
    try:
        resp_id = int(data.get("responsable_id", session["user_id"]))
    except ValueError:
        resp_id = session["user_id"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    stock_row = db_fetchone(conn, "SELECT stock FROM produits WHERE id=%s" if IS_PG else "SELECT stock FROM produits WHERE id=?", (pid,))
    stock_actuel = stock_row["stock"]
    if qte > stock_actuel:
        conn.close()
        flash(f"Stock insuffisant ! Disponible : {stock_actuel}", "error")
        return redirect(url_for("stock"))

    db_insert(conn, "INSERT INTO stock (tenant_id, product_id, mouvement, quantite, marque, code_produit, user_id, date_mouvement) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)" if IS_PG else
              "INSERT INTO stock (tenant_id, product_id, mouvement, quantite, marque, code_produit, user_id, date_mouvement) VALUES (?,?,?,?,?,?,?,?)",
              (tid, pid, "sortie", qte, "", code, resp_id, now))
    db_execute(conn, "UPDATE produits SET stock=stock-%s WHERE id=%s" if IS_PG else "UPDATE produits SET stock=stock-? WHERE id=?", (qte, pid))
    db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
              "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
              (session["user_id"], session["login"], tid, "stock_sortie", f"-{qte} produit #{pid}", now))
    conn.commit()
    conn.close()
    flash(f"Sortie enregistree : -{qte} paires", "success")
    return redirect(url_for("stock"))

@app.route("/ventes", methods=["GET", "POST"])
@login_required
def ventes():
    conn = get_db()
    etid = get_effective_tid()

    if request.method == "POST":
        data = request.form
        try:
            pid = int(data.get("produit_id", 0))
            qte = int(data.get("quantite", 0))
        except (ValueError, TypeError):
            pid = 0
            qte = 0
        if not pid or not qte:
            conn.close()
            flash("Veuillez selectionner un produit et une quantite", "error")
            return redirect(url_for("ventes"))
        tid_sale = int(data.get("tenant_id") or etid or session["tenant_id"]) if is_admin() else session["tenant_id"]
        client_nom = data.get("client_nom", "")
        client_tel = data.get("client_tel", "")
        is_honneur = 1 if data.get("honneur") else 0
        try:
            prix_custom = float(data.get("prix_custom") or 0)
        except ValueError:
            prix_custom = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        stock_row = db_fetchone(conn, "SELECT stock FROM produits WHERE id=%s" if IS_PG else "SELECT stock FROM produits WHERE id=?", (pid,))
        if not stock_row or stock_row["stock"] < qte:
            conn.close()
            flash("Stock insuffisant !", "error")
            return redirect(url_for("ventes"))

        prix_row = db_fetchone(conn, "SELECT prix_usd, prix_cdf FROM produits WHERE id=%s" if IS_PG else "SELECT prix_usd, prix_cdf FROM produits WHERE id=?", (pid,))
        if is_honneur and prix_custom > 0:
            taux = get_taux(conn, tid_sale)
            prix_usd = prix_custom
            prix_cdf = prix_custom * taux
        else:
            prix_usd = prix_row["prix_usd"]
            prix_cdf = prix_row["prix_cdf"]

        total_usd = prix_usd * qte
        total_cdf = prix_cdf * qte

        now_date = datetime.now().strftime("%Y-%m-%d")
        now_heure = datetime.now().strftime("%H:%M:%S")

        # Numero sequentiel RCP-YYYY-NNN
        year = datetime.now().strftime("%Y")
        seq_row = db_fetchone(conn, "SELECT COUNT(*) as cnt FROM recus WHERE numero LIKE %s" if IS_PG else
                              "SELECT COUNT(*) as cnt FROM recus WHERE numero LIKE ?", (f"RCP-{year}-%",))
        seq_num = (seq_row["cnt"] if seq_row else 0) + 1
        recu_num = f"RCP-{year}-{seq_num:03d}"

        # Signature SHA256
        cle_secrete = app.secret_key
        contenu = f"{recu_num}-{total_usd}-{total_cdf}-{client_nom}-{client_tel}-{now_date}-{now_heure}-{tid_sale}"
        signature = hashlib.sha256((contenu + cle_secrete).encode()).hexdigest()[:12]

        db_insert(conn, "INSERT INTO ventes (date, heure, produit_id, quantite, prix_unit_usd, prix_unit_cdf, total_usd, total_cdf, client_nom, client_tel, recu_num, est_client_honneur, tenant_id, vendeur_login) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO ventes (date, heure, produit_id, quantite, prix_unit_usd, prix_unit_cdf, total_usd, total_cdf, client_nom, client_tel, recu_num, est_client_honneur, tenant_id, vendeur_login) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (now_date, now_heure, pid, qte, prix_usd, prix_cdf, total_usd, total_cdf, client_nom, client_tel, recu_num, is_honneur, tid_sale, session["login"]))
        db_insert(conn, "INSERT INTO recus (numero, client_nom, client_tel, total_usd, total_cdf, est_honneur, date, heure, tenant_id, signature, vendeur_login) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO recus (numero, client_nom, client_tel, total_usd, total_cdf, est_honneur, date, heure, tenant_id, signature, vendeur_login) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (recu_num, client_nom, client_tel, total_usd, total_cdf, is_honneur, now_date, now_heure, tid_sale, signature, session["login"]))
        db_execute(conn, "UPDATE produits SET stock=stock-%s WHERE id=%s" if IS_PG else "UPDATE produits SET stock=stock-? WHERE id=?", (qte, pid))

        if is_honneur:
            db_insert(conn, "INSERT INTO dettes (tenant_id, client_nom, client_tel, montant_usd, montant_cdf, est_paye, date, heure, recu_num, vendeur_login) VALUES (%s,%s,%s,%s,%s,0,%s,%s,%s,%s)" if IS_PG else
                      "INSERT INTO dettes (tenant_id, client_nom, client_tel, montant_usd, montant_cdf, est_paye, date, heure, recu_num, vendeur_login) VALUES (?,?,?,?,?,0,?,?,?,?)",
                      (tid_sale, client_nom, client_tel, total_usd, total_cdf, now_date, now_heure, recu_num, session["login"]))

        if client_tel:
            cl = db_fetchone(conn, "SELECT id FROM clients WHERE telephone=%s" if IS_PG else "SELECT id FROM clients WHERE telephone=?", (client_tel,))
            if cl:
                db_execute(conn, "UPDATE clients SET nb_visites=nb_visites+1, total_usd=total_usd+%s, total_cdf=total_cdf+%s, nom=%s WHERE id=%s" if IS_PG else
                           "UPDATE clients SET nb_visites=nb_visites+1, total_usd=total_usd+?, total_cdf=total_cdf+?, nom=? WHERE id=?",
                           (total_usd, total_cdf, client_nom, cl["id"]))
            else:
                db_insert(conn, "INSERT INTO clients (nom, telephone, tenant_id, nb_visites, total_usd, total_cdf) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                          "INSERT INTO clients (nom, telephone, tenant_id, nb_visites, total_usd, total_cdf) VALUES (?,?,?,?,?,?)",
                          (client_nom, client_tel, tid_sale, 1, total_usd, total_cdf))

        db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (session["user_id"], session["login"], tid_sale, "vente", f"{qte}x {pid} = ${total_usd:.2f}", now))
        conn.commit()
        conn.close()
        flash(f"Vente enregistree : {qte}x produit = ${total_usd:.2f}", "success")
        return redirect(url_for("ventes"))

    if etid is not None:
        prods = db_fetchall(conn, "SELECT id, nom, prix_usd, stock FROM produits WHERE tenant_id=%s AND stock>0 ORDER BY nom" if IS_PG else
                            "SELECT id, nom, prix_usd, stock FROM produits WHERE tenant_id=? AND stock>0 ORDER BY nom", (etid,))
    else:
        prods = db_fetchall(conn, "SELECT id, nom, prix_usd, stock FROM produits WHERE stock>0 ORDER BY nom")

    if etid is not None:
        ventes_list = db_fetchall(conn, """SELECT v.id, v.date||' '||v.heure as datetime, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login, v.recu_num, v.est_client_honneur
            FROM ventes v JOIN produits p ON v.produit_id=p.id WHERE v.tenant_id=%s ORDER BY v.date DESC, v.heure DESC LIMIT 50""" if IS_PG else """SELECT v.id, v.date||' '||v.heure as datetime, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login, v.recu_num, v.est_client_honneur
            FROM ventes v JOIN produits p ON v.produit_id=p.id WHERE v.tenant_id=? ORDER BY v.date DESC, v.heure DESC LIMIT 50""", (etid,))
    else:
        ventes_list = db_fetchall(conn, """SELECT v.id, v.date||' '||v.heure as datetime, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login, v.recu_num, v.est_client_honneur
            FROM ventes v JOIN produits p ON v.produit_id=p.id ORDER BY v.date DESC, v.heure DESC LIMIT 50""")

    taux = get_taux(conn, etid or session["tenant_id"])
    conn.close()
    return render_template("ventes.html", prods=prods, ventes_list=ventes_list, is_admin=is_admin(), taux=taux)

@app.route("/rapports")
@login_required
def rapports():
    conn = get_db()
    etid = get_effective_tid()

    if etid is not None:
        all_rows = db_fetchall(conn, """SELECT v.date, v.heure, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login
            FROM ventes v JOIN produits p ON v.produit_id=p.id WHERE v.tenant_id=%s
            ORDER BY v.date DESC, v.heure DESC LIMIT 500""" if IS_PG else """SELECT v.date, v.heure, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login
            FROM ventes v JOIN produits p ON v.produit_id=p.id WHERE v.tenant_id=?
            ORDER BY v.date DESC, v.heure DESC LIMIT 500""", (etid,))
    else:
        all_rows = db_fetchall(conn, """SELECT v.date, v.heure, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login
            FROM ventes v JOIN produits p ON v.produit_id=p.id
            ORDER BY v.date DESC, v.heure DESC LIMIT 500""")

    days = {}
    for r in all_rows:
        d = r["date"]
        if d not in days:
            days[d] = {"rows": [], "total_usd": 0, "total_qte": 0, "nb_ventes": 0}
        days[d]["rows"].append(r)
        days[d]["total_usd"] += r["total_usd"]
        days[d]["total_qte"] += r["quantite"]
        days[d]["nb_ventes"] += 1

    sorted_days = sorted(days.keys(), reverse=True)
    conn.close()
    return render_template("rapports.html", days=days, sorted_days=sorted_days, is_admin=is_admin())

@app.route("/clients")
@login_required
def clients():
    conn = get_db()
    etid = get_effective_tid()

    if etid is not None:
        clients_list = db_fetchall(conn, "SELECT * FROM clients WHERE tenant_id=%s ORDER BY nb_visites DESC LIMIT 100" if IS_PG else
                                   "SELECT * FROM clients WHERE tenant_id=? ORDER BY nb_visites DESC LIMIT 100", (etid,))
    else:
        clients_list = db_fetchall(conn, "SELECT * FROM clients ORDER BY nb_visites DESC LIMIT 100")

    conn.close()
    return render_template("clients.html", clients_list=clients_list, is_admin=is_admin())

@app.route("/recus")
@login_required
def recus():
    conn = get_db()
    etid = get_effective_tid()

    if etid is not None:
        recus_list = db_fetchall(conn, """SELECT r.id, r.numero, r.date, r.total_usd, r.total_cdf, r.client_nom, r.est_honneur, r.client_tel, r.heure, r.tenant_id, r.signature, r.verrouille, r.vendeur_login
            FROM recus r WHERE r.tenant_id=%s ORDER BY r.date DESC LIMIT 100""" if IS_PG else """SELECT r.id, r.numero, r.date, r.total_usd, r.total_cdf, r.client_nom, r.est_honneur, r.client_tel, r.heure, r.tenant_id, r.signature, r.verrouille, r.vendeur_login
            FROM recus r WHERE r.tenant_id=? ORDER BY r.date DESC LIMIT 100""", (etid,))
    else:
        recus_list = db_fetchall(conn, """SELECT r.id, r.numero, r.date, r.total_usd, r.total_cdf, r.client_nom, r.est_honneur, r.client_tel, r.heure, r.tenant_id, r.signature, r.verrouille, r.vendeur_login
            FROM recus r ORDER BY r.date DESC LIMIT 100""")

    conn.close()
    return render_template("recus.html", recus_list=recus_list, is_admin=is_admin())

@app.route("/recus/edit/<int:rid>", methods=["GET", "POST"])
@login_required
def recu_edit(rid):
    if not is_admin():
        flash("Seul l'admin peut modifier les recus", "error")
        return redirect(url_for("recus"))
    conn = get_db()
    recu = db_fetchone(conn, "SELECT r.*, t.nom as tenant_nom FROM recus r LEFT JOIN tenants t ON r.tenant_id=t.id WHERE r.id=%s" if IS_PG else
                       "SELECT r.*, t.nom as tenant_nom FROM recus r LEFT JOIN tenants t ON r.tenant_id=t.id WHERE r.id=?", (rid,))
    if not recu:
        conn.close()
        return redirect(url_for("recus"))
    if recu["verrouille"]:
        conn.close()
        flash("Ce recu est verrouille apres le rapport de fin de journee", "error")
        return redirect(url_for("recus"))
    if request.method == "POST":
        data = request.form
        client_nom = data.get("client_nom", recu["client_nom"])
        client_tel = data.get("client_tel", recu["client_tel"])
        try:
            total_usd = float(data.get("total_usd", recu["total_usd"]))
        except ValueError:
            total_usd = recu["total_usd"]
        taux = get_taux(conn, recu["tenant_id"])
        total_cdf = total_usd * taux
        est_honneur = 1 if data.get("est_honneur") else 0
        db_execute(conn, "UPDATE recus SET client_nom=%s, client_tel=%s, total_usd=%s, total_cdf=%s, est_honneur=%s WHERE id=%s" if IS_PG else
                   "UPDATE recus SET client_nom=?, client_tel=?, total_usd=?, total_cdf=?, est_honneur=? WHERE id=?",
                   (client_nom, client_tel, total_usd, total_cdf, est_honneur, rid))
        # Recalculer la signature
        cle_secrete = app.secret_key
        contenu = f"{recu['numero']}-{total_usd}-{total_cdf}-{client_nom}-{client_tel}-{recu['date']}-{recu['heure']}-{recu['tenant_id']}"
        signature = hashlib.sha256((contenu + cle_secrete).encode()).hexdigest()[:12]
        db_execute(conn, "UPDATE recus SET signature=%s WHERE id=%s" if IS_PG else "UPDATE recus SET signature=? WHERE id=?", (signature, rid))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (session["user_id"], session["login"], recu["tenant_id"], "recu_modifie", f"Recu #{recu['numero']}", now))
        conn.commit()
        conn.close()
        flash(f"Recu #{recu['numero']} modifie", "success")
        return redirect(url_for("recus"))
    conn.close()
    return render_template("recu_edit.html", recu=recu, is_admin=is_admin())

@app.route("/logs")
@login_required
def logs():
    if not is_admin():
        return redirect(url_for("dashboard"))
    conn = get_db()
    logs_list = db_fetchall(conn, """SELECT l.date_heure, l.login, l.action, l.details, t.nom as tenant_nom
        FROM logs l LEFT JOIN tenants t ON l.tenant_id=t.id
        ORDER BY l.date_heure DESC LIMIT 200""")
    conn.close()
    return render_template("logs.html", logs_list=logs_list, is_admin=is_admin())

@app.route("/tenants")
@login_required
def tenants():
    if not is_admin():
        return redirect(url_for("dashboard"))
    conn = get_db()
    tenants_list = db_fetchall(conn, "SELECT * FROM tenants ORDER BY id")
    conn.close()
    return render_template("tenants.html", tenants_list=tenants_list, is_admin=is_admin())

@app.route("/tenants/new", methods=["POST"])
@login_required
def tenant_new():
    if not is_admin():
        flash("Seul l'admin peut ajouter des tenants", "error")
        return redirect(url_for("dashboard"))
    data = request.form
    nom = data.get("nom", "").strip()
    localisation = data.get("localisation", "").strip()
    type_commerce = data.get("type_commerce", "").strip()
    if not nom:
        flash("Le nom est obligatoire", "error")
        return redirect(url_for("tenants"))
    conn = get_db()
    existing = db_fetchone(conn, "SELECT id FROM tenants WHERE nom=%s" if IS_PG else "SELECT id FROM tenants WHERE nom=?", (nom,))
    if existing:
        conn.close()
        flash("Ce tenant existe deja", "error")
        return redirect(url_for("tenants"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_insert(conn, "INSERT INTO tenants (nom, actif, localisation, type_commerce, date_creation) VALUES (%s,1,%s,%s,%s) RETURNING id" if IS_PG else
              "INSERT INTO tenants (nom, actif, localisation, type_commerce, date_creation) VALUES (?,1,?,?,?)",
              (nom, localisation, type_commerce, now))
    db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
              "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
              (session["user_id"], session["login"], 0, "tenant_ajoute", f"{nom} - {localisation}", now))
    conn.commit()
    conn.close()
    flash(f"Tenant {nom} ajoute", "success")
    return redirect(url_for("tenants"))

@app.route("/tenants/supprimer/<int:tid>", methods=["POST"])
@login_required
def tenant_supprimer(tid):
    if not is_admin():
        flash("Seul l'admin peut supprimer des tenants", "error")
        return redirect(url_for("dashboard"))
    conn = get_db()
    tenant = db_fetchone(conn, "SELECT * FROM tenants WHERE id=%s" if IS_PG else "SELECT * FROM tenants WHERE id=?", (tid,))
    if tenant:
        import json
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_json = json.dumps(dict(tenant), default=str)
        db_insert(conn, "INSERT INTO corbeille (table_name, original_id, data, deleted_by, deleted_at, tenant_id) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id" if IS_PG else
                  "INSERT INTO corbeille (table_name, original_id, data, deleted_by, deleted_at, tenant_id) VALUES (?,?,?,?,?,?)",
                  ("tenants", tid, data_json, session["login"], now, 0))
        db_execute(conn, "UPDATE tenants SET actif=0 WHERE id=%s" if IS_PG else "UPDATE tenants SET actif=0 WHERE id=?", (tid,))
        db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (session["user_id"], session["login"], 0, "tenant_supprime", f"{tenant['nom']} - {tenant['localisation']}", now))
        conn.commit()
        flash(f"Tenant {tenant['nom']} supprime", "success")
    conn.close()
    return redirect(url_for("tenants"))

@app.route("/utilisateurs")
@login_required
def utilisateurs():
    if not is_admin():
        return redirect(url_for("dashboard"))
    conn = get_db()
    users = db_fetchall(conn, """SELECT u.id, u.login, u.role, u.tenant_id, t.nom as tenant_nom
        FROM utilisateurs u LEFT JOIN tenants t ON u.tenant_id=t.id ORDER BY u.id""")
    tenants = db_fetchall(conn, "SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
    conn.close()
    return render_template("utilisateurs.html", users=users, tenants=tenants, is_admin=is_admin())

@app.route("/utilisateurs/new", methods=["POST"])
@login_required
def utilisateur_new():
    if not is_admin():
        flash("Seul l'admin peut ajouter des utilisateurs", "error")
        return redirect(url_for("dashboard"))
    data = request.form
    login = data.get("login", "").strip()
    code = data.get("code", "").strip()
    role = data.get("role", "vendeur")
    tenant_nom = data.get("tenant_nom", "").strip()
    if not login or not code:
        flash("Login et code requis", "error")
        return redirect(url_for("utilisateurs"))
    conn = get_db()
    existing = db_fetchone(conn, "SELECT id FROM utilisateurs WHERE login=%s" if IS_PG else "SELECT id FROM utilisateurs WHERE login=?", (login,))
    if existing:
        conn.close()
        flash("Ce login existe deja", "error")
        return redirect(url_for("utilisateurs"))
    tenant_id = 0
    if tenant_nom:
        t = db_fetchone(conn, "SELECT id FROM tenants WHERE nom=%s" if IS_PG else "SELECT id FROM tenants WHERE nom=?", (tenant_nom,))
        if t:
            tenant_id = t["id"]
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tenant_id = db_insert(conn, "INSERT INTO tenants (nom, actif, localisation, type_commerce, date_creation) VALUES (%s,1,'','',NOW()) RETURNING id" if IS_PG else
                                  "INSERT INTO tenants (nom, actif, localisation, type_commerce, date_creation) VALUES (?,1,'','',?)",
                                  (tenant_nom, now)) or 1
            if IS_PG:
                cur = conn.execute("SELECT id FROM tenants WHERE nom=%s", (tenant_nom,))
                row = cur.fetchone()
                if row:
                    tenant_id = row["id"]
    db_insert(conn, "INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES (%s,%s,%s,%s) RETURNING id" if IS_PG else
              "INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES (?,?,?,?)",
              (login, code, tenant_id, role))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
              "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
              (session["user_id"], session["login"], tenant_id, "utilisateur_ajoute", f"{login} ({role}) - tenant:{tenant_nom}", now))
    conn.commit()
    conn.close()
    flash(f"Utilisateur {login} ajoute", "success")
    return redirect(url_for("utilisateurs"))

@app.route("/utilisateurs/supprimer/<int:uid>", methods=["POST"])
@login_required
def utilisateur_supprimer(uid):
    if not is_admin():
        flash("Seul l'admin peut supprimer des utilisateurs", "error")
        return redirect(url_for("dashboard"))
    conn = get_db()
    user = db_fetchone(conn, "SELECT * FROM utilisateurs WHERE id=%s" if IS_PG else "SELECT * FROM utilisateurs WHERE id=?", (uid,))
    if user and user["login"] not in ("0891624401", "graciella@gmail.com"):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(conn, "DELETE FROM utilisateurs WHERE id=%s" if IS_PG else "DELETE FROM utilisateurs WHERE id=?", (uid,))
        db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (session["user_id"], session["login"], user["tenant_id"], "utilisateur_supprime", f"{user['login']} ({user['role']})", now))
        conn.commit()
        flash(f"Utilisateur {user['login']} supprime", "success")
    else:
        flash("Impossible de supprimer cet utilisateur", "error")
    conn.close()
    return redirect(url_for("utilisateurs"))

def create_notif(conn, tenant_id, message, responsable="Admin"):
    db_insert(conn, "INSERT INTO notifications (tenant_id, message, is_read, created_at, responsable) VALUES (%s,%s,0,%s,%s)" if IS_PG else
              "INSERT INTO notifications (tenant_id, message, is_read, created_at, responsable) VALUES (?, ?, 0, ?, ?)",
              (tenant_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), responsable))
    conn.commit()

@app.route("/produits/edit/<int:pid>", methods=["GET", "POST"])
@login_required
def produit_edit(pid):
    if not is_admin():
        return redirect(url_for("produits"))
    conn = get_db()
    prod = db_fetchone(conn, "SELECT p.*, c.nom as cat_nom FROM produits p JOIN categories c ON p.categorie_id=c.id WHERE p.id=%s" if IS_PG else
                       "SELECT p.*, c.nom as cat_nom FROM produits p JOIN categories c ON p.categorie_id=c.id WHERE p.id=?", (pid,))
    if not prod:
        conn.close()
        return redirect(url_for("produits"))
    if request.method == "POST":
        data = request.form
        code = data.get("code", "").strip()
        couleur = data.get("couleur", "").strip()
        try:
            prix_usd = float(data["prix_usd"])
        except (ValueError, KeyError):
            conn.close()
            flash("Prix invalide", "error")
            return redirect(url_for("produits"))
        taux = get_taux(conn, prod["tenant_id"])
        prix_cdf = prix_usd * taux
        ancien_prix = prod["prix_usd"]
        db_execute(conn, "UPDATE produits SET code=%s, couleur=%s, prix_usd=%s, prix_cdf=%s WHERE id=%s" if IS_PG else
                   "UPDATE produits SET code=?, couleur=?, prix_usd=?, prix_cdf=? WHERE id=?", (code, couleur, prix_usd, prix_cdf, pid))
        if prix_usd != ancien_prix:
            create_notif(conn, prod["tenant_id"],
                f"Prix modifie : {prod['nom']} passe de ${ancien_prix:.2f} a ${prix_usd:.2f}",
                session["login"])
        conn.commit()
        conn.close()
        flash(f"Produit mis a jour : {prod['nom']}", "success")
        return redirect(url_for("produits"))
    conn.close()
    return render_template("produit_edit.html", prod=prod, is_admin=is_admin())

@app.route("/produits/new", methods=["GET", "POST"])
@login_required
def produit_new():
    if not is_admin():
        return redirect(url_for("produits"))
    conn = get_db()
    etid = get_effective_tid()
    cats = db_fetchall(conn, "SELECT id, nom FROM categories ORDER BY nom")
    tenants = db_fetchall(conn, "SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
    if request.method == "POST":
        data = request.form
        nom = data.get("nom", "").strip()
        code = data.get("code", "").strip()
        couleur = data.get("couleur", "").strip()
        try:
            cat_id = int(data["categorie_id"])
            prix_usd = float(data["prix_usd"])
            stock_val = int(data.get("stock", 0))
        except (ValueError, KeyError):
            conn.close()
            flash("Donnees invalides", "error")
            return redirect(url_for("produit_new"))
        if not nom:
            conn.close()
            flash("Le nom est obligatoire", "error")
            return redirect(url_for("produit_new"))
        tid_prod = int(data["tenant_id"]) if is_admin() else (etid or session["tenant_id"])
        taux = get_taux(conn, tid_prod)
        prix_cdf = prix_usd * taux
        db_insert(conn, "INSERT INTO produits (nom, code, couleur, categorie_id, prix_usd, prix_cdf, stock, tenant_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO produits (nom, code, couleur, categorie_id, prix_usd, prix_cdf, stock, tenant_id) VALUES (?,?,?,?,?,?,?,?)",
                  (nom, code, couleur, cat_id, prix_usd, prix_cdf, stock_val, tid_prod))
        conn.commit()
        create_notif(conn, tid_prod, f"Nouveau produit : {nom} - ${prix_usd:.2f}", session["login"])
        conn.close()
        flash(f"Produit ajoute : {nom}", "success")
        return redirect(url_for("produits"))
    conn.close()
    return render_template("produit_new.html", cats=cats, tenants=tenants, is_admin=is_admin(), etid=etid)

@app.route("/dettes", methods=["GET", "POST"])
@login_required
def dettes():
    conn = get_db()
    etid = get_effective_tid()

    if request.method == "POST":
        if not is_admin():
            conn.close()
            flash("Seul l'admin peut ajouter des dettes", "error")
            return redirect(url_for("dettes"))
        data = request.form
        client_nom = data.get("client_nom", "").strip()
        client_tel = data.get("client_tel", "").strip()
        try:
            montant_usd = float(data.get("montant_usd", 0))
        except ValueError:
            montant_usd = 0
        notes = data.get("notes", "")
        tid_dette = int(data["tenant_id"]) if is_admin() else session["tenant_id"]
        taux = get_taux(conn, tid_dette)
        montant_cdf = montant_usd * taux
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        now_date = datetime.now().strftime("%Y-%m-%d")
        now_heure = datetime.now().strftime("%H:%M:%S")

        if not client_nom or montant_usd <= 0:
            conn.close()
            flash("Nom du client et montant requis", "error")
            return redirect(url_for("dettes"))

        db_insert(conn, "INSERT INTO dettes (tenant_id, client_nom, client_tel, montant_usd, montant_cdf, est_paye, date, heure, notes, vendeur_login) VALUES (%s,%s,%s,%s,%s,0,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO dettes (tenant_id, client_nom, client_tel, montant_usd, montant_cdf, est_paye, date, heure, notes, vendeur_login) VALUES (?,?,?,?,?,0,?,?,?,?)",
                  (tid_dette, client_nom, client_tel, montant_usd, montant_cdf, now_date, now_heure, notes, session["login"]))
        create_notif(conn, tid_dette, f"Nouvelle dette : {client_nom} - ${montant_usd:.2f}", session["login"])
        conn.commit()
        conn.close()
        flash(f"Dette enregistree : {client_nom} = ${montant_usd:.2f}", "success")
        return redirect(url_for("dettes"))

    if etid is not None:
        dettes_list = db_fetchall(conn, """SELECT d.*, t.nom as tenant_nom FROM dettes d LEFT JOIN tenants t ON d.tenant_id=t.id
            WHERE d.tenant_id=%s ORDER BY d.date DESC, d.heure DESC LIMIT 100""" if IS_PG else """SELECT d.*, t.nom as tenant_nom FROM dettes d LEFT JOIN tenants t ON d.tenant_id=t.id
            WHERE d.tenant_id=? ORDER BY d.date DESC, d.heure DESC LIMIT 100""", (etid,))
    else:
        dettes_list = db_fetchall(conn, """SELECT d.*, t.nom as tenant_nom FROM dettes d LEFT JOIN tenants t ON d.tenant_id=t.id
            ORDER BY d.date DESC, d.heure DESC LIMIT 100""")

    non_payees = [d for d in dettes_list if not d["est_paye"]]
    payees = [d for d in dettes_list if d["est_paye"]]
    total_non_paye = sum(d["montant_usd"] for d in non_payees)

    tenants_list = []
    if is_admin():
        tenants_list = db_fetchall(conn, "SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")

    conn.close()
    return render_template("dettes.html", dettes_list=dettes_list, non_payees=non_payees, payees=payees,
                           total_non_paye=total_non_paye, is_admin=is_admin(), tenants=tenants_list)

@app.route("/dettes/payer/<int:did>", methods=["POST"])
@login_required
def dette_payer(did):
    if not is_admin():
        flash("Seul l'admin peut marquer une dette comme payee", "error")
        return redirect(url_for("dettes"))
    conn = get_db()
    dette = db_fetchone(conn, "SELECT * FROM dettes WHERE id=%s" if IS_PG else "SELECT * FROM dettes WHERE id=?", (did,))
    if dette:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(conn, "UPDATE dettes SET est_paye=1, date_paiement=%s, admin_id=%s WHERE id=%s" if IS_PG else
                   "UPDATE dettes SET est_paye=1, date_paiement=?, admin_id=? WHERE id=?",
                   (now, session["user_id"], did))
        create_notif(conn, dette["tenant_id"], f"Dette payee : {dette['client_nom']} - ${dette['montant_usd']:.2f}", session["login"])
        db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (session["user_id"], session["login"], dette["tenant_id"], "dette_payee", f"{dette['client_nom']} - ${dette['montant_usd']:.2f}", now))
        conn.commit()
        flash(f"Dette de {dette['client_nom']} marquee comme payee", "success")
    conn.close()
    return redirect(url_for("dettes"))

@app.route("/dettes/supprimer/<int:did>", methods=["POST"])
@login_required
def dette_supprimer(did):
    if not is_admin():
        flash("Seul l'admin peut supprimer des dettes", "error")
        return redirect(url_for("dettes"))
    conn = get_db()
    dette = db_fetchone(conn, "SELECT * FROM dettes WHERE id=%s" if IS_PG else "SELECT * FROM dettes WHERE id=?", (did,))
    if dette:
        import json
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_json = json.dumps(dict(dette), default=str)
        db_insert(conn, "INSERT INTO corbeille (table_name, original_id, data, deleted_by, deleted_at, tenant_id) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id" if IS_PG else
                  "INSERT INTO corbeille (table_name, original_id, data, deleted_by, deleted_at, tenant_id) VALUES (?,?,?,?,?,?)",
                  ("dettes", did, data_json, session["login"], now, dette["tenant_id"]))
        db_execute(conn, "DELETE FROM dettes WHERE id=%s" if IS_PG else "DELETE FROM dettes WHERE id=?", (did,))
        create_notif(conn, dette["tenant_id"], f"Dette supprimee : {dette['client_nom']} - ${dette['montant_usd']:.2f}", session["login"])
        db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (session["user_id"], session["login"], dette["tenant_id"], "dette_supprimee", f"{dette['client_nom']} - ${dette['montant_usd']:.2f}", now))
        conn.commit()
        flash(f"Dette de {dette['client_nom']} supprimee", "success")
    conn.close()
    return redirect(url_for("dettes"))

@app.route("/corbeille")
@login_required
def corbeille():
    if not is_admin():
        flash("Seul l'admin peut acceder a la corbeille", "error")
        return redirect(url_for("dashboard"))
    conn = get_db()
    items = db_fetchall(conn, "SELECT * FROM corbeille ORDER BY deleted_at DESC")
    conn.close()
    return render_template("corbeille.html", items=items, is_admin=is_admin())

@app.route("/corbeille/restore/<int:cid>", methods=["POST"])
@login_required
def corbeille_restore(cid):
    if not is_admin():
        flash("Seul l'admin peut restaurer des elements", "error")
        return redirect(url_for("dashboard"))
    conn = get_db()
    item = db_fetchone(conn, "SELECT * FROM corbeille WHERE id=%s" if IS_PG else "SELECT * FROM corbeille WHERE id=?", (cid,))
    if item:
        import json
        data = json.loads(item["data"])
        table = item["table_name"]
        oid = item["original_id"]
        if table == "dettes":
            db_execute(conn, "INSERT INTO dettes (id, tenant_id, client_nom, client_tel, montant_usd, montant_cdf, est_paye, date, heure, recu_num, notes, vendeur_login, date_paiement, admin_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" if IS_PG else
                       "INSERT INTO dettes (id, tenant_id, client_nom, client_tel, montant_usd, montant_cdf, est_paye, date, heure, recu_num, notes, vendeur_login, date_paiement, admin_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (oid, data.get("tenant_id", 0), data.get("client_nom", ""), data.get("client_tel", ""), data.get("montant_usd", 0), data.get("montant_cdf", 0), data.get("est_paye", 0), data.get("date", ""), data.get("heure", ""), data.get("recu_num", ""), data.get("notes", ""), data.get("vendeur_login", ""), data.get("date_paiement"), data.get("admin_id")))
        elif table == "tenants":
            db_execute(conn, "UPDATE tenants SET actif=1 WHERE id=%s" if IS_PG else "UPDATE tenants SET actif=1 WHERE id=?", (oid,))
        db_execute(conn, "DELETE FROM corbeille WHERE id=%s" if IS_PG else "DELETE FROM corbeille WHERE id=?", (cid,))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (session["user_id"], session["login"], item["tenant_id"], "corbeille_restore", f"{table} #{oid} restaure", now))
        conn.commit()
        flash(f"Element restaure avec succes", "success")
    conn.close()
    return redirect(url_for("corbeille"))

@app.route("/corbeille/supprimer/<int:cid>", methods=["POST"])
@login_required
def corbeille_supprimer_definitif(cid):
    if not is_admin():
        flash("Seul l'admin peut supprimer definitivement", "error")
        return redirect(url_for("dashboard"))
    conn = get_db()
    item = db_fetchone(conn, "SELECT * FROM corbeille WHERE id=%s" if IS_PG else "SELECT * FROM corbeille WHERE id=?", (cid,))
    if item:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_execute(conn, "DELETE FROM corbeille WHERE id=%s" if IS_PG else "DELETE FROM corbeille WHERE id=?", (cid,))
        db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (session["user_id"], session["login"], item["tenant_id"], "corbeille_supprime_definitif", f"{item['table_name']} #{item['original_id']} supprime definitivement", now))
        conn.commit()
        flash("Element supprime definitivement", "success")
    conn.close()
    return redirect(url_for("corbeille"))

@app.route("/notifications")
@login_required
def notifications():
    conn = get_db()
    etid = get_effective_tid()
    if etid is not None:
        notifs = db_fetchall(conn, "SELECT * FROM notifications WHERE tenant_id=%s ORDER BY created_at DESC LIMIT 50" if IS_PG else
                             "SELECT * FROM notifications WHERE tenant_id=? ORDER BY created_at DESC LIMIT 50", (etid,))
    else:
        notifs = db_fetchall(conn, "SELECT * FROM notifications ORDER BY created_at DESC LIMIT 50")
    row = db_fetchone(conn, "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0" + (" AND tenant_id=%s" if IS_PG else " AND tenant_id=?") if etid is not None else
                      "SELECT COUNT(*) as cnt FROM notifications WHERE is_read=0",
                      (etid,) if etid is not None else ())
    unread = row["cnt"] if row else 0
    conn.close()
    return render_template("notifications.html", notifs=notifs, unread=unread, is_admin=is_admin())

@app.route("/notifications/read/<int:nid>", methods=["POST"])
@login_required
def notif_read(nid):
    conn = get_db()
    db_execute(conn, "UPDATE notifications SET is_read=1 WHERE id=%s" if IS_PG else "UPDATE notifications SET is_read=1 WHERE id=?", (nid,))
    conn.commit()
    conn.close()
    return redirect(url_for("notifications"))

@app.route("/notifications/read-all", methods=["POST"])
@login_required
def notif_read_all():
    conn = get_db()
    etid = get_effective_tid()
    if etid is not None:
        db_execute(conn, "UPDATE notifications SET is_read=1 WHERE tenant_id=%s" if IS_PG else "UPDATE notifications SET is_read=1 WHERE tenant_id=?", (etid,))
    else:
        db_execute(conn, "UPDATE notifications SET is_read=1")
    conn.commit()
    conn.close()
    return redirect(url_for("notifications"))

@app.route("/fin-journee", methods=["POST"])
@login_required
def fin_journee():
    try:
        conn = get_db()
        for tbl in [
            "CREATE TABLE IF NOT EXISTS rapports (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL, vendeur_login TEXT NOT NULL, vendeur_id INTEGER NOT NULL, total_usd REAL DEFAULT 0, total_cdf REAL DEFAULT 0, nb_ventes INTEGER DEFAULT 0, nb_clients INTEGER DEFAULT 0, date_rapport TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS rapports_temp (id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL, vendeur_login TEXT NOT NULL, vendeur_id INTEGER NOT NULL, date_rapport TEXT NOT NULL, expire_at TEXT NOT NULL, total_usd REAL DEFAULT 0, total_cdf REAL DEFAULT 0, nb_ventes INTEGER DEFAULT 0, nb_clients INTEGER DEFAULT 0)"
        ]:
            try:
                conn.execute(tbl)
            except Exception:
                pass
        conn.commit()
        tid = session["tenant_id"]
        vendeur_login = session["login"]
        vendeur_id = session["user_id"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = datetime.now().strftime("%Y-%m-%d")
        expire = (datetime.now() + timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S")
        t = db_fetchone(conn, "SELECT nom FROM tenants WHERE id=%s" if IS_PG else "SELECT nom FROM tenants WHERE id=?", (tid,))
        tenant_nom = t["nom"] if t else "Inconnu"

        stats = db_fetchone(conn, "SELECT COALESCE(SUM(total_usd),0) as total_usd, COALESCE(SUM(total_cdf),0) as total_cdf, COUNT(*) as nb_ventes FROM ventes WHERE vendeur_login=%s AND date=%s AND tenant_id=%s" if IS_PG else
                            "SELECT COALESCE(SUM(total_usd),0) as total_usd, COALESCE(SUM(total_cdf),0) as total_cdf, COUNT(*) as nb_ventes FROM ventes WHERE vendeur_login=? AND date=? AND tenant_id=?", (vendeur_login, today, tid))
        total_usd = stats["total_usd"] if stats else 0
        total_cdf = stats["total_cdf"] if stats else 0
        nb_ventes = stats["nb_ventes"] if stats else 0

        clients = db_fetchone(conn, "SELECT COUNT(DISTINCT client_nom) as nb FROM ventes WHERE vendeur_login=%s AND date=%s AND tenant_id=%s AND client_nom!=''" if IS_PG else
                              "SELECT COUNT(DISTINCT client_nom) as nb FROM ventes WHERE vendeur_login=? AND date=? AND tenant_id=? AND client_nom!=''", (vendeur_login, today, tid))
        nb_clients = clients["nb"] if clients else 0

        rapport_r = db_insert(conn, "INSERT INTO rapports (tenant_id, vendeur_login, vendeur_id, total_usd, total_cdf, nb_ventes, nb_clients, date_rapport) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id" if IS_PG else
                  "INSERT INTO rapports (tenant_id, vendeur_login, vendeur_id, total_usd, total_cdf, nb_ventes, nb_clients, date_rapport) VALUES (?,?,?,?,?,?,?,?)",
                  (tid, vendeur_login, vendeur_id, total_usd, total_cdf, nb_ventes, nb_clients, today))
        rapport_id = rapport_r[0] if rapport_r else 0

        db_insert(conn, "INSERT INTO rapports_temp (tenant_id, vendeur_login, vendeur_id, date_rapport, expire_at, total_usd, total_cdf, nb_ventes, nb_clients) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id" if IS_PG else
                  "INSERT INTO rapports_temp (tenant_id, vendeur_login, vendeur_id, date_rapport, expire_at, total_usd, total_cdf, nb_ventes, nb_clients) VALUES (?,?,?,?,?,?,?,?,?)",
                  (tid, vendeur_login, vendeur_id, now, expire, total_usd, total_cdf, nb_ventes, nb_clients))

        db_insert(conn, "INSERT INTO notifications (tenant_id, message, is_read, created_at, responsable) VALUES (0,%s,0,%s,%s)" if IS_PG else
                  "INSERT INTO notifications (tenant_id, message, is_read, created_at, responsable) VALUES (0,?,0,?,?)",
                  (f"Rapport {tenant_nom} - {vendeur_login} | {nb_ventes} ventes | ${total_usd:.2f} | /rapport/{rapport_id}", now, vendeur_login))

        # Verrouiller les recus du vendeur pour aujourd'hui
        db_execute(conn, "UPDATE recus SET verrouille=1 WHERE vendeur_login=%s AND date=%s AND tenant_id=%s" if IS_PG else
                   "UPDATE recus SET verrouille=1 WHERE vendeur_login=? AND date=? AND tenant_id=?", (vendeur_login, today, tid))

        db_execute(conn, "DELETE FROM ventes WHERE vendeur_login=%s AND date=%s AND tenant_id=%s" if IS_PG else "DELETE FROM ventes WHERE vendeur_login=? AND date=? AND tenant_id=?", (vendeur_login, today, tid))
        db_insert(conn, "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (%s,%s,%s,%s,%s,%s)" if IS_PG else
                  "INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (vendeur_id, vendeur_login, tid, "fin_journee", f"${total_usd:.2f} | {nb_ventes} ventes | {nb_clients} clients", now))
        conn.commit()
        conn.close()
        flash("Rapport envoye avec succes", "success")
    except Exception as e:
        flash(f"Erreur: {str(e)}", "error")
    return redirect(url_for("dashboard"))

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    conn = get_db()
    tid = session["tenant_id"]
    etid = get_effective_tid() or tid

    if request.method == "POST":
        data = request.form
        if "taux_cdf" in data:
            try:
                taux = float(data["taux_cdf"])
            except ValueError:
                flash("Valeur invalide", "error")
                conn.close()
                return redirect(url_for("settings"))
            if IS_PG:
                db_execute(conn, "INSERT INTO settings (tenant_id, key, value) VALUES (%s, 'taux_cdf', %s) ON CONFLICT (tenant_id, key) DO UPDATE SET value=EXCLUDED.value", (etid, str(taux)))
            else:
                db_execute(conn, "INSERT OR REPLACE INTO settings (tenant_id, key, value) VALUES (?, 'taux_cdf', ?)", (etid, str(taux)))
            conn.commit()
            flash(f"Taux mis a jour : 1 USD = {taux} CDF", "success")
        conn.close()
        return redirect(url_for("settings"))

    taux = get_taux(conn, etid)
    conn.close()
    return render_template("settings.html", taux=taux, is_admin=is_admin(),
                           login=session["login"], role=session["role"])

@app.route("/rapport/<int:rapport_id>")
@login_required
def rapport_detail(rapport_id):
    conn = get_db()
    r = db_fetchone(conn, "SELECT * FROM rapports WHERE id=%s" if IS_PG else "SELECT * FROM rapports WHERE id=?", (rapport_id,))
    conn.close()
    if not r:
        flash("Rapport introuvable", "error")
        return redirect(url_for("dashboard"))
    if not is_admin() and r["tenant_id"] != session.get("tenant_id", 0):
        flash("Acces refuse", "error")
        return redirect(url_for("dashboard"))
    return render_template("rapport.html", rapport=r, is_admin=is_admin(),
                           login=session["login"], role=session["role"])

@app.route("/admin/cleanup")
def admin_cleanup():
    if not is_admin():
        return "Admin only"
    conn = get_db()
    deleted = {}
    for tbl in ["ventes", "clients"]:
        try:
            cur = conn.execute(f"SELECT COUNT(*) FROM {tbl}")
            count = cur.fetchone()[0]
            conn.execute(f"DELETE FROM {tbl}")
            deleted[tbl] = count
        except Exception:
            deleted[tbl] = "table not found"
    conn.commit()
    conn.close()
    html = "<h1>Donnees effacees</h1><ul>"
    for k, v in deleted.items():
        html += f"<li>{k}: {v} lignes supprimees</li>"
    html += "</ul><p>Ventes et clients remis a zero.</p><a href='/dashboard'>Retour</a>"
    return html

@app.route("/recu/verifier/<numero>")
def verifier_recu(numero):
    conn = get_db()
    r = db_fetchone(conn, "SELECT * FROM recus WHERE numero=%s" if IS_PG else "SELECT * FROM recus WHERE numero=?", (numero,))
    conn.close()
    if not r:
        return render_template("verifier_recu.html", valide=False, recu=None, numero=numero)
    
    cle_secrete = app.secret_key
    contenu = f"{r['numero']}-{r['total_usd']}-{r['total_cdf']}-{r['client_nom'] or ''}-{r['client_tel'] or ''}-{r['date']}-{r['heure']}-{r['tenant_id']}"
    signature_calculee = hashlib.sha256((contenu + cle_secrete).encode()).hexdigest()[:12]
    valide = signature_calculee == (r['signature'] or '')
    
    return render_template("verifier_recu.html", valide=valide, recu=r, numero=numero)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
