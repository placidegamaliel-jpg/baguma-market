from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "baguma-market-2026-secret")
DB = os.environ.get("DATABASE_URL", os.path.join(os.path.dirname(os.path.abspath(__file__)), "commerce.db"))

@app.errorhandler(404)
def not_found(e):
    return render_template("login.html"), 404

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

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
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE tenant_id=? AND key='taux_cdf'", (tenant_id,))
    row = c.fetchone()
    return float(row[0]) if row else 2800.0

TENANT_SLUGS = {
    "goma": 2,
    "bukavu": 1,
    "admin": 0,
}
TENANT_NAMES = {
    2: "Chaussure Goma",
    1: "Chaussure Bukavu",
    0: "Admin Global",
}

@app.context_processor
def inject_tenant():
    slug = session.get("tenant_slug")
    tid = session.get("tenant_id", 0)
    unread = 0
    if "user_id" in session:
        try:
            conn = get_db()
            c = conn.cursor()
            etid = get_effective_tid()
            if etid is not None:
                c.execute("SELECT COUNT(*) FROM notifications WHERE is_read=0 AND tenant_id=?", (etid,))
            else:
                c.execute("SELECT COUNT(*) FROM notifications WHERE is_read=0")
            unread = c.fetchone()[0]
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
        c = conn.cursor()
        c.execute("SELECT id, login, tenant_id, role FROM utilisateurs WHERE login=? AND code=?", (login_val, code))
        row = c.fetchone()
        if row:
            user_tid = row["tenant_id"]
            user_role = row["role"]
            ville_tid = TENANT_SLUGS.get(ville, None)
            if user_tid == 0 and user_role == "admin":
                if ville_tid is not None:
                    session["tenant_slug"] = ville
            elif ville_tid is not None and user_tid == ville_tid:
                session["tenant_slug"] = ville
            else:
                conn.close()
                flash("Ce compte n'est pas autorise pour cette ville", "error")
                return redirect(url_for("login"))
            session["user_id"] = row["id"]
            session["login"] = row["login"]
            session["tenant_id"] = user_tid
            session["role"] = user_role
            if ville_tid is not None:
                session["tenant_slug"] = ville
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                      (row["id"], row["login"], user_tid, "Connexion", f"Role: {user_role} | Ville: {ville}", now))
            conn.commit()
            conn.close()
            return redirect(url_for("dashboard"))
        conn.close()
        flash("Login ou code incorrect", "error")
    return render_template("login.html")

@app.route("/<tenant_slug>")
def login_tenant(tenant_slug):
    slug = tenant_slug.lower()
    if slug in TENANT_SLUGS:
        session["url_tenant"] = TENANT_SLUGS[slug]
        session["tenant_slug"] = slug
        return redirect(url_for("login"))
    return redirect(url_for("login"))

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
    if slug == "admin":
        session.pop("view_tenant", None)
        session["view_tenant_name"] = "Admin Global"
    elif slug in TENANT_SLUGS:
        session["view_tenant"] = TENANT_SLUGS[slug]
        session["view_tenant_name"] = TENANT_NAMES[TENANT_SLUGS[slug]]
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    c = conn.cursor()
    etid = get_effective_tid()

    if etid is not None:
        cond = " WHERE tenant_id=?"
        params = (etid,)
    else:
        cond = ""
        params = ()

    c.execute(f"SELECT COUNT(*) FROM produits{cond}", params)
    nb_produits = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM ventes{cond}", params)
    nb_ventes = c.fetchone()[0]
    c.execute(f"SELECT COALESCE(SUM(total_usd),0) FROM ventes{cond}", params)
    ca_total = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM clients{cond}", params)
    nb_clients = c.fetchone()[0]
    stock_cond = " AND stock<=5" if cond else " WHERE stock<=5"
    c.execute(f"SELECT COUNT(*) FROM produits{cond}{stock_cond}", params)
    low_stock = c.fetchone()[0]

    if etid is not None:
        vcond = " WHERE v.tenant_id=?"
        vparams = (etid,)
    else:
        vcond = ""
        vparams = ()

    c.execute(f"""SELECT v.date||' '||v.heure, p.nom, v.quantite, v.total_usd, v.vendeur_login
        FROM ventes v JOIN produits p ON v.produit_id=p.id{vcond}
        ORDER BY v.date DESC, v.heure DESC LIMIT 10""", vparams)
    recent = c.fetchall()

    conn.close()
    return render_template("dashboard.html", nb_produits=nb_produits, nb_ventes=nb_ventes,
                           ca_total=ca_total, nb_clients=nb_clients, low_stock=low_stock,
                           recent=recent, is_admin=is_admin())

@app.route("/produits")
@login_required
def produits():
    conn = get_db()
    c = conn.cursor()
    etid = get_effective_tid()
    search = request.args.get("search", "")
    cat = request.args.get("categorie", "")

    cond_parts = []
    params = []
    if etid is not None:
        cond_parts.append("p.tenant_id=?")
        params.append(etid)
    if search:
        cond_parts.append("p.nom LIKE ?")
        params.append(f"%{search}%")
    if cat:
        cond_parts.append("c.nom=?")
        params.append(cat)
    where = " WHERE " + " AND ".join(cond_parts) if cond_parts else ""

    c.execute(f"""SELECT p.id, p.nom, c.nom, p.prix_usd, p.prix_cdf, p.stock, p.tenant_id
        FROM produits p JOIN categories c ON p.categorie_id=c.id{where} ORDER BY p.nom""", params)
    prods = c.fetchall()

    c.execute("SELECT DISTINCT nom FROM categories ORDER BY nom")
    cats = [r[0] for r in c.fetchall()]

    tenants_map = {}
    if is_admin():
        c.execute("SELECT id, nom FROM tenants")
        for r in c.fetchall():
            tenants_map[r["id"]] = r["nom"]

    conn.close()
    return render_template("produits.html", prods=prods, cats=cats, search=search,
                           cat_selected=cat, is_admin=is_admin(), tenants_map=tenants_map)

@app.route("/stock")
@login_required
def stock():
    conn = get_db()
    c = conn.cursor()
    etid = get_effective_tid()

    if etid is not None:
        c.execute("SELECT id, nom FROM tenants WHERE id=? AND actif=1", (etid,))
    else:
        c.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
    tenants = c.fetchall()

    tenant_data = []
    for t in tenants:
        tid2 = t["id"]
        c.execute("SELECT COALESCE(SUM(quantite),0) FROM stock WHERE tenant_id=? AND mouvement='entree'", (tid2,))
        entrees = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(quantite),0) FROM stock WHERE tenant_id=? AND mouvement='sortie'", (tid2,))
        sorties = c.fetchone()[0]

        c.execute("""SELECT sr.produit_nom, sr.code_produit, sr.marque, sr.total_entrees, sr.total_sorties, sr.stock_disponible,
                       (SELECT u.login FROM stock s2 JOIN utilisateurs u ON s2.user_id=u.id
                        WHERE s2.product_id=sr.product_id AND s2.tenant_id=sr.tenant_id AND s2.mouvement='sortie'
                        ORDER BY s2.date_mouvement DESC LIMIT 1)
                FROM stock_restant sr
                WHERE sr.tenant_id=?
                ORDER BY sr.produit_nom""", (tid2,))
        stock_produits = c.fetchall()

        c.execute("""SELECT s.date_mouvement, s.mouvement, p.nom, s.code_produit, s.quantite, u.login
                FROM stock s JOIN produits p ON s.product_id=p.id JOIN utilisateurs u ON s.user_id=u.id
                WHERE s.tenant_id=? ORDER BY s.date_mouvement DESC LIMIT 30""", (tid2,))
        historique = c.fetchall()

        tenant_data.append({"id": tid2, "nom": t["nom"], "entrees": entrees, "sorties": sorties,
                            "net": entrees - sorties, "stock_produits": stock_produits, "historique": historique})

    if etid is not None:
        c.execute("SELECT id, nom FROM produits WHERE tenant_id=? ORDER BY nom", (etid,))
    else:
        c.execute("SELECT id, nom FROM produits ORDER BY nom")
    prods = c.fetchall()
    if etid is not None:
        c.execute("SELECT id, login FROM utilisateurs WHERE tenant_id IN (0,?)", (etid,))
    else:
        c.execute("SELECT id, login FROM utilisateurs")
    users = c.fetchall()

    conn.close()
    return render_template("stock.html", tenant_data=tenant_data, is_admin=is_admin(), prods=prods, users=users)

@app.route("/stock/entree", methods=["POST"])
@login_required
def stock_entree():
    conn = get_db()
    c = conn.cursor()
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

    c.execute("INSERT INTO stock (tenant_id, product_id, mouvement, quantite, marque, code_produit, user_id, date_mouvement) VALUES (?,?,?,?,?,?,?,?)",
              (tid, pid, "entree", qte, marque, code, resp_id, now))
    c.execute("UPDATE produits SET stock=stock+? WHERE id=?", (qte, pid))
    c.execute("INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
              (session["user_id"], session["login"], tid, "stock_entree", f"+{qte} produit #{pid}", now))
    conn.commit()
    conn.close()
    flash(f"Entree enregistree : +{qte} paires", "success")
    return redirect(url_for("stock"))

@app.route("/stock/sortie", methods=["POST"])
@login_required
def stock_sortie():
    conn = get_db()
    c = conn.cursor()
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

    c.execute("SELECT stock FROM produits WHERE id=?", (pid,))
    stock_actuel = c.fetchone()[0]
    if qte > stock_actuel:
        conn.close()
        flash(f"Stock insuffisant ! Disponible : {stock_actuel}", "error")
        return redirect(url_for("stock"))

    c.execute("INSERT INTO stock (tenant_id, product_id, mouvement, quantite, marque, code_produit, user_id, date_mouvement) VALUES (?,?,?,?,?,?,?,?)",
              (tid, pid, "sortie", qte, "", code, resp_id, now))
    c.execute("UPDATE produits SET stock=stock-? WHERE id=?", (qte, pid))
    c.execute("INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
              (session["user_id"], session["login"], tid, "stock_sortie", f"-{qte} produit #{pid}", now))
    conn.commit()
    conn.close()
    flash(f"Sortie enregistree : -{qte} paires", "success")
    return redirect(url_for("stock"))

@app.route("/ventes", methods=["GET", "POST"])
@login_required
def ventes():
    conn = get_db()
    c = conn.cursor()
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

        c.execute("SELECT stock FROM produits WHERE id=?", (pid,))
        stock_row = c.fetchone()
        if not stock_row or stock_row[0] < qte:
            conn.close()
            flash("Stock insuffisant !", "error")
            return redirect(url_for("ventes"))

        c.execute("SELECT prix_usd, prix_cdf FROM produits WHERE id=?", (pid,))
        prix_row = c.fetchone()
        if is_honneur and prix_custom > 0:
            taux = get_taux(conn, tid_sale)
            prix_usd = prix_custom
            prix_cdf = prix_custom * taux
        else:
            prix_usd = prix_row["prix_usd"]
            prix_cdf = prix_row["prix_cdf"]

        total_usd = prix_usd * qte
        total_cdf = prix_cdf * qte

        recu_num = f"N{datetime.now().strftime('%Y%m%d%H%M%S')}"
        now_date = datetime.now().strftime("%Y-%m-%d")
        now_heure = datetime.now().strftime("%H:%M:%S")

        c.execute("INSERT INTO ventes (date, heure, produit_id, quantite, prix_unit_usd, prix_unit_cdf, total_usd, total_cdf, client_nom, client_tel, recu_num, est_client_honneur, tenant_id, vendeur_login) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (now_date, now_heure, pid, qte, prix_usd, prix_cdf, total_usd, total_cdf, client_nom, client_tel, recu_num, is_honneur, tid_sale, session["login"]))
        c.execute("INSERT INTO recus (numero, client_nom, client_tel, total_usd, total_cdf, est_honneur, date, heure, tenant_id) VALUES (?,?,?,?,?,?,?,?,?)",
                  (recu_num, client_nom, client_tel, total_usd, total_cdf, is_honneur, now_date, now_heure, tid_sale))
        c.execute("UPDATE produits SET stock=stock-? WHERE id=?", (qte, pid))

        if client_tel:
            c.execute("SELECT id FROM clients WHERE telephone=?", (client_tel,))
            cl = c.fetchone()
            if cl:
                c.execute("UPDATE clients SET nb_visites=nb_visites+1, total_usd=total_usd+?, total_cdf=total_cdf+?, nom=? WHERE id=?",
                          (total_usd, total_cdf, client_nom, cl["id"]))
            else:
                c.execute("INSERT INTO clients (nom, telephone, tenant_id, nb_visites, total_usd, total_cdf) VALUES (?,?,?,?,?,?)",
                          (client_nom, client_tel, tid_sale, 1, total_usd, total_cdf))

        c.execute("INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure) VALUES (?,?,?,?,?,?)",
                  (session["user_id"], session["login"], tid_sale, "vente", f"{qte}x {pid} = ${total_usd:.2f}", now))
        conn.commit()
        conn.close()
        flash(f"Vente enregistree : {qte}x produit = ${total_usd:.2f}", "success")
        return redirect(url_for("ventes"))

    if etid is not None:
        c.execute("SELECT id, nom, prix_usd, stock FROM produits WHERE tenant_id=? AND stock>0 ORDER BY nom", (etid,))
    else:
        c.execute("SELECT id, nom, prix_usd, stock FROM produits WHERE stock>0 ORDER BY nom")
    prods = c.fetchall()

    if etid is not None:
        c.execute("""SELECT v.id, v.date||' '||v.heure, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login, v.recu_num, v.est_client_honneur
            FROM ventes v JOIN produits p ON v.produit_id=p.id WHERE v.tenant_id=? ORDER BY v.date DESC, v.heure DESC LIMIT 50""", (etid,))
    else:
        c.execute("""SELECT v.id, v.date||' '||v.heure, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login, v.recu_num, v.est_client_honneur
            FROM ventes v JOIN produits p ON v.produit_id=p.id ORDER BY v.date DESC, v.heure DESC LIMIT 50""")
    ventes_list = c.fetchall()

    taux = get_taux(conn, etid or session["tenant_id"])
    conn.close()
    return render_template("ventes.html", prods=prods, ventes_list=ventes_list, is_admin=is_admin(), taux=taux)

@app.route("/rapports")
@login_required
def rapports():
    conn = get_db()
    c = conn.cursor()
    etid = get_effective_tid()

    if etid is not None:
        c.execute("""SELECT v.date, v.heure, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login
            FROM ventes v JOIN produits p ON v.produit_id=p.id WHERE v.tenant_id=?
            ORDER BY v.date DESC, v.heure DESC LIMIT 500""", (etid,))
    else:
        c.execute("""SELECT v.date, v.heure, p.nom, v.quantite, v.total_usd, v.client_nom, v.vendeur_login
            FROM ventes v JOIN produits p ON v.produit_id=p.id
            ORDER BY v.date DESC, v.heure DESC LIMIT 500""")
    all_rows = c.fetchall()

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
    c = conn.cursor()
    etid = get_effective_tid()

    if etid is not None:
        c.execute("SELECT * FROM clients WHERE tenant_id=? ORDER BY nb_visites DESC LIMIT 100", (etid,))
    else:
        c.execute("SELECT * FROM clients ORDER BY nb_visites DESC LIMIT 100")
    clients_list = c.fetchall()

    conn.close()
    return render_template("clients.html", clients_list=clients_list, is_admin=is_admin())

@app.route("/recus")
@login_required
def recus():
    conn = get_db()
    c = conn.cursor()
    etid = get_effective_tid()

    if etid is not None:
        c.execute("""SELECT r.id, r.numero, r.date, r.total_usd, r.total_cdf, r.client_nom, r.est_honneur
            FROM recus r WHERE r.tenant_id=? ORDER BY r.date DESC LIMIT 100""", (etid,))
    else:
        c.execute("""SELECT r.id, r.numero, r.date, r.total_usd, r.total_cdf, r.client_nom, r.est_honneur
            FROM recus r ORDER BY r.date DESC LIMIT 100""")
    recus_list = c.fetchall()

    conn.close()
    return render_template("recus.html", recus_list=recus_list, is_admin=is_admin())

@app.route("/logs")
@login_required
def logs():
    if not is_admin():
        return redirect(url_for("dashboard"))
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT l.date_heure, l.login, l.action, l.details, t.nom
        FROM logs l LEFT JOIN tenants t ON l.tenant_id=t.id
        ORDER BY l.date_heure DESC LIMIT 200""")
    logs_list = c.fetchall()
    conn.close()
    return render_template("logs.html", logs_list=logs_list)

@app.route("/tenants")
@login_required
def tenants():
    if not is_admin():
        return redirect(url_for("dashboard"))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tenants ORDER BY id")
    tenants_list = c.fetchall()
    conn.close()
    return render_template("tenants.html", tenants_list=tenants_list)

@app.route("/utilisateurs")
@login_required
def utilisateurs():
    if not is_admin():
        return redirect(url_for("dashboard"))
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT u.id, u.login, u.role, u.tenant_id, t.nom
        FROM utilisateurs u LEFT JOIN tenants t ON u.tenant_id=t.id ORDER BY u.id""")
    users = c.fetchall()
    c.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
    tenants = c.fetchall()
    conn.close()
    return render_template("utilisateurs.html", users=users, tenants=tenants)

def create_notif(conn, tenant_id, message, responsable="Admin"):
    c = conn.cursor()
    c.execute("INSERT INTO notifications (tenant_id, message, is_read, created_at, responsable) VALUES (?,?,0,?,?)",
              (tenant_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), responsable))
    conn.commit()

@app.route("/produits/edit/<int:pid>", methods=["GET", "POST"])
@login_required
def produit_edit(pid):
    if not is_admin():
        return redirect(url_for("produits"))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT p.*, c.nom as cat_nom FROM produits p JOIN categories c ON p.categorie_id=c.id WHERE p.id=?", (pid,))
    prod = c.fetchone()
    if not prod:
        conn.close()
        return redirect(url_for("produits"))
    if request.method == "POST":
        data = request.form
        try:
            prix_usd = float(data["prix_usd"])
        except (ValueError, KeyError):
            conn.close()
            flash("Prix invalide", "error")
            return redirect(url_for("produits"))
        taux = get_taux(conn, prod["tenant_id"])
        prix_cdf = prix_usd * taux
        ancien_prix = prod["prix_usd"]
        c.execute("UPDATE produits SET prix_usd=?, prix_cdf=? WHERE id=?", (prix_usd, prix_cdf, pid))
        if prix_usd != ancien_prix:
            create_notif(conn, prod["tenant_id"],
                f"Prix modifie : {prod['nom']} passe de ${ancien_prix:.2f} a ${prix_usd:.2f}",
                session["login"])
        conn.commit()
        conn.close()
        flash(f"Prix mis a jour : {prod['nom']} = ${prix_usd:.2f}", "success")
        return redirect(url_for("produits"))
    conn.close()
    return render_template("produit_edit.html", prod=prod, is_admin=is_admin())

@app.route("/produits/new", methods=["GET", "POST"])
@login_required
def produit_new():
    if not is_admin():
        return redirect(url_for("produits"))
    conn = get_db()
    c = conn.cursor()
    etid = get_effective_tid()
    c.execute("SELECT id, nom FROM categories ORDER BY nom")
    cats = c.fetchall()
    c.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
    tenants = c.fetchall()
    if request.method == "POST":
        data = request.form
        nom = data.get("nom", "").strip()
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
        c.execute("INSERT INTO produits (nom, categorie_id, prix_usd, prix_cdf, stock, tenant_id) VALUES (?,?,?,?,?,?)",
                  (nom, cat_id, prix_usd, prix_cdf, stock_val, tid_prod))
        conn.commit()
        create_notif(conn, tid_prod, f"Nouveau produit : {nom} - ${prix_usd:.2f}", session["login"])
        conn.close()
        flash(f"Produit ajoute : {nom}", "success")
        return redirect(url_for("produits"))
    conn.close()
    return render_template("produit_new.html", cats=cats, tenants=tenants, is_admin=is_admin(), etid=etid)

@app.route("/notifications")
@login_required
def notifications():
    conn = get_db()
    c = conn.cursor()
    etid = get_effective_tid()
    if etid is not None:
        c.execute("SELECT * FROM notifications WHERE tenant_id=? ORDER BY created_at DESC LIMIT 50", (etid,))
    else:
        c.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 50")
    notifs = c.fetchall()
    c.execute("SELECT COUNT(*) FROM notifications WHERE is_read=0" + (" AND tenant_id=?" if etid is not None else ""),
              (etid,) if etid is not None else ())
    unread = c.fetchone()[0]
    conn.close()
    return render_template("notifications.html", notifs=notifs, unread=unread, is_admin=is_admin())

@app.route("/notifications/read/<int:nid>", methods=["POST"])
@login_required
def notif_read(nid):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read=1 WHERE id=?", (nid,))
    conn.commit()
    conn.close()
    return redirect(url_for("notifications"))

@app.route("/notifications/read-all", methods=["POST"])
@login_required
def notif_read_all():
    conn = get_db()
    c = conn.cursor()
    etid = get_effective_tid()
    if etid is not None:
        c.execute("UPDATE notifications SET is_read=1 WHERE tenant_id=?", (etid,))
    else:
        c.execute("UPDATE notifications SET is_read=1")
    conn.commit()
    conn.close()
    return redirect(url_for("notifications"))

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    conn = get_db()
    c = conn.cursor()
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
            c.execute("INSERT OR REPLACE INTO settings (tenant_id, key, value) VALUES (?, 'taux_cdf', ?)",
                      (etid, str(taux)))
            conn.commit()
            flash(f"Taux mis a jour : 1 USD = {taux} CDF", "success")
        conn.close()
        return redirect(url_for("settings"))

    taux = get_taux(conn, etid)
    conn.close()
    return render_template("settings.html", taux=taux, is_admin=is_admin(),
                           login=session["login"], role=session["role"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
