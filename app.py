import customtkinter as ctk
from tkinter import messagebox, Canvas, Tk
import sqlite3
from datetime import date, datetime, timedelta
import os
import io

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

LOGIN_BG = "#0b0b1a"
LOGIN_FRAME = "#111128"
LOGIN_NEON_PINK = "#e84393"
LOGIN_NEON_BLUE = "#6c5ce7"
LOGIN_NEON_PURPLE = "#a29bfe"
LOGIN_INPUT_BG = "#13132d"
LOGIN_BTN_RED = "#e63946"

MAIN_BG = "#0b0b1a"
SIDEBAR_BG = "#101028"
CARD_BG = "#161636"
GOLD = "#d4a843"
GOLD_LIGHT = "#f0d078"
GOLD_DARK = "#b8860b"
ACCENT_BLUE = "#0984e3"
ACCENT_GREEN = "#00b894"
ACCENT_RED = "#e63946"
ACCENT_ORANGE = "#fdcb6e"
TEXT_WHITE = "#f5f5f5"
TEXT_GRAY = "#a0a0b0"
TEXT_DIM = "#636e72"
DARK_CARD = "#1a1a3e"
HONOR_COLOR = "#e84393"
NOTIF_BG = "#2d3436"

FONT_FAMILY = "Segoe UI"

ADMIN_TENANT_ID = 0

ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_VENDEUR = "vendeur"
ROLE_CAISSIER = "caissier"
ALL_ROLES = [ROLE_ADMIN, ROLE_MANAGER, ROLE_VENDEUR, ROLE_CAISSIER]

PERMISSIONS = {
    ROLE_ADMIN: {"gerer_utilisateurs", "gerer_produits", "faire_vente",
                 "voir_rapports", "voir_clients", "modifier_taux", "supprimer_vente",
                 "voir_logs", "gerer_tenants"},
    ROLE_MANAGER: {"gerer_produits", "faire_vente", "voir_rapports", "voir_clients",
                   "modifier_taux", "supprimer_vente"},
    ROLE_VENDEUR: {"faire_vente", "voir_clients", "voir_rapports"},
    ROLE_CAISSIER: {"faire_vente"},
}


def has_permission(role, perm):
    return perm in PERMISSIONS.get(role, set())


def log_action(cursor, conn, user_id, login, tenant_id, action, details=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""INSERT INTO logs (user_id, login, tenant_id, action, details, date_heure)
                      VALUES (?, ?, ?, ?, ?, ?)""",
                   (user_id, login, tenant_id, action, details, now))
    conn.commit()


def add_notification(cursor, conn, tenant_id, message, user_id=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""INSERT INTO notifications (tenant_id, user_id, message, created_at)
                      VALUES (?, ?, ?, ?)""",
                   (tenant_id, user_id, message, now))
    conn.commit()


def init_db():
    conn = sqlite3.connect("commerce.db", timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS tenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT UNIQUE NOT NULL,
        localisation TEXT DEFAULT '',
        type_commerce TEXT DEFAULT 'Chaussures',
        actif INTEGER DEFAULT 1,
        date_creation TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS utilisateurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE, code TEXT,
        tenant_id INTEGER DEFAULT 0,
        role TEXT DEFAULT 'vendeur')""")

    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, emoji TEXT,
        tenant_id INTEGER DEFAULT 0)""")

    c.execute("""CREATE TABLE IF NOT EXISTS produits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categorie_id INTEGER, nom TEXT,
        prix_usd REAL, prix_cdf REAL, stock INTEGER DEFAULT 100,
        tenant_id INTEGER DEFAULT 0,
        FOREIGN KEY (categorie_id) REFERENCES categories(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, telephone TEXT,
        nb_visites INTEGER DEFAULT 0, total_usd REAL DEFAULT 0,
        total_cdf REAL DEFAULT 0, premier_visite TEXT, derniere_visite TEXT,
        tenant_id INTEGER DEFAULT 0)""")

    c.execute("""CREATE TABLE IF NOT EXISTS ventes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recu_num TEXT, client_id INTEGER,
        produit_id INTEGER, quantite INTEGER,
        prix_unit_usd REAL, prix_unit_cdf REAL,
        total_usd REAL, total_cdf REAL,
        est_client_honneur INTEGER DEFAULT 0,
        date TEXT, heure TEXT,
        tenant_id INTEGER DEFAULT 0,
        FOREIGN KEY (produit_id) REFERENCES produits(id),
        FOREIGN KEY (client_id) REFERENCES clients(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS recus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE, client_id INTEGER,
        total_usd REAL, total_cdf REAL,
        est_honneur INTEGER DEFAULT 0,
        date TEXT, heure TEXT,
        tenant_id INTEGER DEFAULT 0,
        FOREIGN KEY (client_id) REFERENCES clients(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT,
        tenant_id INTEGER DEFAULT 0)""")

    c.execute("""CREATE TABLE IF NOT EXISTS tenant_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        produit_id INTEGER NOT NULL,
        prix_usd REAL, prix_cdf REAL,
        UNIQUE(tenant_id, produit_id),
        FOREIGN KEY (produit_id) REFERENCES produits(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER DEFAULT 0,
        user_id INTEGER DEFAULT NULL,
        message TEXT, is_read INTEGER DEFAULT 0,
        created_at TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS notif_settings (
        tenant_id INTEGER PRIMARY KEY,
        alertes_actives INTEGER DEFAULT 1,
        notif_ventes INTEGER DEFAULT 1,
        notif_stock INTEGER DEFAULT 1,
        notif_prix INTEGER DEFAULT 1,
        notif_connexion INTEGER DEFAULT 0)""")

    c.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, login TEXT,
        tenant_id INTEGER DEFAULT 0,
        action TEXT, details TEXT,
        date_heure TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        mouvement TEXT NOT NULL CHECK(mouvement IN ('entree','sortie')),
        quantite INTEGER NOT NULL,
        marque TEXT,
        code_produit TEXT,
        user_id INTEGER NOT NULL,
        date_mouvement TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE VIEW IF NOT EXISTS stock_restant AS
        SELECT s.product_id, s.tenant_id, s.marque, s.code_produit,
               p.nom AS produit_nom,
               SUM(CASE WHEN s.mouvement='entree' THEN s.quantite ELSE -s.quantite END) AS stock_disponible,
               SUM(CASE WHEN s.mouvement='entree' THEN s.quantite ELSE 0 END) AS total_entrees,
               SUM(CASE WHEN s.mouvement='sortie' THEN s.quantite ELSE 0 END) AS total_sorties
        FROM stock s
        JOIN produits p ON s.product_id=p.id
        GROUP BY s.product_id, s.tenant_id, s.marque, s.code_produit""")

    for tbl, cols_info in [
        ("tenants", [("localisation", "TEXT DEFAULT ''"), ("type_commerce", "TEXT DEFAULT 'Chaussures'")]),
        ("utilisateurs", [("tenant_id", "INTEGER DEFAULT 0"), ("role", "TEXT DEFAULT 'vendeur'")]),
        ("categories", [("tenant_id", "INTEGER DEFAULT 0")]),
        ("produits", [("stock", "INTEGER DEFAULT 100"), ("categorie_id", "INTEGER DEFAULT 0"),
                       ("tenant_id", "INTEGER DEFAULT 0")]),
        ("clients", [("tenant_id", "INTEGER DEFAULT 0")]),
        ("ventes", [("recu_num", "TEXT DEFAULT ''"), ("client_id", "INTEGER DEFAULT NULL"),
                     ("prix_unit_usd", "REAL DEFAULT 0"), ("prix_unit_cdf", "REAL DEFAULT 0"),
                     ("est_client_honneur", "INTEGER DEFAULT 0"), ("tenant_id", "INTEGER DEFAULT 0"),
                     ("vendeur_login", "TEXT DEFAULT ''")]),
        ("recus", [("client_id", "INTEGER DEFAULT NULL"), ("est_honneur", "INTEGER DEFAULT 0"),
                    ("tenant_id", "INTEGER DEFAULT 0")]),
        ("settings", [("tenant_id", "INTEGER DEFAULT 0")]),
    ]:
        c.execute(f"PRAGMA table_info({tbl})")
        existing = {col[1] for col in c.fetchall()}
        for col_name, col_def in cols_info:
            if col_name not in existing:
                c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_def}")

    c.execute("SELECT COUNT(*) FROM utilisateurs")
    if c.fetchone()[0] == 0:
        c.execute("""INSERT INTO utilisateurs (login, code, tenant_id, role)
                     VALUES (?, ?, ?, ?)""",
                  ("0838029045", "Baguma06", ADMIN_TENANT_ID, ROLE_ADMIN))
        c.execute("""INSERT INTO utilisateurs (login, code, tenant_id, role)
                     VALUES (?, ?, ?, ?)""",
                  ("baguma.com", "Baguma06", ADMIN_TENANT_ID, ROLE_ADMIN))

    c.execute("SELECT COUNT(*) FROM categories WHERE tenant_id=0")
    if c.fetchone()[0] == 0:
        seed_produits(c, ADMIN_TENANT_ID)

    c.execute("SELECT value FROM settings WHERE key='taux_cdf' AND tenant_id=0")
    if not c.fetchone():
        c.execute("INSERT INTO settings (key, value, tenant_id) VALUES ('taux_cdf', '2800', 0)")

    c.execute("SELECT role FROM utilisateurs WHERE login='0838029045'")
    row = c.fetchone()
    if row and row[0] != ROLE_ADMIN:
        c.execute("UPDATE utilisateurs SET role=? WHERE login IN ('0838029045','baguma.com')", (ROLE_ADMIN,))

    conn.commit()
    return conn


def seed_produits(c, tenant_id):
    catalogue = {
        "Bottes et bottines": {
            "emoji": "\U0001f97e",
            "items": [
                ("Chelsea", 17), ("Chukka", 17), ("Desert boots", 17),
                ("Botte de cowboy / Santiag", 17), ("Botte militaire / combat", 17),
                ("Botte de pluie / Wellington", 17), ("Botte de randonnee", 17),
                ("Botte de travail", 17), ("Botte de moto", 17),
                ("Botte d'equitation", 17), ("Botte de ski", 17),
                ("Botte de neige", 17), ("Cuissarde", 17),
                ("Botte haute", 17), ("Botte a plateforme", 17), ("Demi Botte", 17),
            ]
        },
        "Sandales": {
            "emoji": "\U0001fa74",
            "items": [
                ("Tong / flip-flop", 9), ("Claquette / slide", 9),
                ("Sandale plate", 9), ("Sandale a talon", 9),
                ("Sandale compensee", 9), ("Sandale gladiateur", 9),
                ("Sandale a brides", 9), ("Sandale T-strap", 9),
                ("Sandale Fisherman", 9), ("Sandale romaine", 9),
                ("Sandale de randonnee", 9), ("Sandale de plage", 9),
                ("Sandale a plateforme", 9), ("Sandale a semelle compensee", 9),
                ("Sandale minimaliste", 9), ("Sandale barefoot", 9),
                ("Sandalle haut talo", 9), ("Sandalle base talo", 7.5),
            ]
        },
        "Nike / Jordan": {
            "emoji": "\U0001f45f",
            "items": [
                ("Jordan 1", 16), ("Jordan 3", 16), ("Jordan 4", 16),
                ("Jordan 5", 16), ("Jordan 6", 16), ("Jordan 11", 16), ("Jordan 12", 16),
                ("Air Force 1", 11), ("Air Max 1", 15), ("Air Max 90", 15),
                ("Air Max 95", 15), ("Air Max 97", 15), ("Mocoto", 25),
                ("TN", 17), ("DN", 17),
            ]
        },
        "Adidas": {
            "emoji": "\u26bf",
            "items": [
                ("Superstar", 15), ("Stan Smith", 15), ("Samba", 17),
                ("Gazelle", 17), ("Campus", 10),
            ]
        },
        "Autres": {
            "emoji": "\U0001f97e",
            "items": [
                ("Mocassin pro", 17), ("Mocassin moyenne", 16), ("Mocassin base", 14),
                ("J.M Weston", 25), ("Asixe", 16), ("Vans", 10), ("New Balance", 17),
            ]
        },
    }
    for cat_name, cat_data in catalogue.items():
        c.execute("INSERT INTO categories (nom, emoji, tenant_id) VALUES (?, ?, ?)",
                  (cat_name, cat_data["emoji"], tenant_id))
        cat_id = c.lastrowid
        for nom, prix in cat_data["items"]:
            c.execute("""INSERT INTO produits (categorie_id, nom, prix_usd, prix_cdf, stock, tenant_id)
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (cat_id, nom, prix, prix * 2800, 100, tenant_id))


def get_taux(cursor, tenant_id=0):
    cursor.execute("SELECT value FROM settings WHERE key='taux_cdf' AND tenant_id=?", (tenant_id,))
    row = cursor.fetchone()
    if row:
        return float(row[0])
    cursor.execute("SELECT value FROM settings WHERE key='taux_cdf' AND tenant_id=0")
    row = cursor.fetchone()
    return float(row[0]) if row else 2800.0


def set_taux(cursor, conn, val, tenant_id=0):
    cursor.execute("UPDATE OR REPLACE INTO settings (key, value, tenant_id) VALUES ('taux_cdf', ?, ?)",
                   (str(val), tenant_id))
    conn.commit()


def get_next_recu_num(cursor, tenant_id=0):
    cursor.execute("SELECT COUNT(*) FROM recus WHERE tenant_id=?", (tenant_id,))
    count = cursor.fetchone()[0] + 1
    return f"N\u00b0{count:03d}"


def get_produit_prix(cursor, produit_id, tenant_id, taux):
    cursor.execute("SELECT prix_usd, prix_cdf FROM produits WHERE id=?", (produit_id,))
    row = cursor.fetchone()
    if not row:
        return 0, 0
    default_usd = row[0]
    cursor.execute("SELECT prix_usd, prix_cdf FROM tenant_prices WHERE tenant_id=? AND produit_id=?",
                   (tenant_id, produit_id))
    tp = cursor.fetchone()
    if tp:
        return tp[0], tp[1]
    return default_usd, default_usd * taux


def set_tenant_price(cursor, conn, tenant_id, produit_id, prix_usd, taux):
    prix_cdf = prix_usd * taux
    cursor.execute("""INSERT OR REPLACE INTO tenant_prices (tenant_id, produit_id, prix_usd, prix_cdf)
                      VALUES (?, ?, ?, ?)""", (tenant_id, produit_id, prix_usd, prix_cdf))
    conn.commit()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.conn = init_db()
        self.cursor = self.conn.cursor()
        self.geometry("1250x720")
        self.minsize(1100, 640)
        self.title("Baguma Market")
        self.resizable(True, True)
        self.cart_items = []
        self.is_honneur = False
        self.current_tenant_id = ADMIN_TENANT_ID
        self.current_user_id = 0
        self.current_user_login = ""
        self.current_role = ROLE_ADMIN
        self.is_admin = False
        self.notif_count = 0
        self.taux_cdf = get_taux(self.cursor, self.current_tenant_id)
        self.inactivity_timer = None
        self.inactivity_limit = 300000
        self.show_login()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def reset_inactivity(self):
        if self.inactivity_timer:
            self.after_cancel(self.inactivity_timer)
        self.inactivity_timer = self.after(self.inactivity_limit, self.auto_logout)

    def auto_logout(self):
        messagebox.showwarning("Inactivite", "Deconnexion automatique apres 5 minutes d'inactivite.")
        self.show_login()

    def bind_activity(self):
        for event in ["<Key>", "<Button-1>", "<Motion>", "<MouseWheel>"]:
            self.bind_all(event, lambda e: self.reset_inactivity())

    def can(self, perm):
        if self.is_admin:
            return True
        return has_permission(self.current_role, perm)

    def _q(self, where_extra="", params_extra=None):
        tid = self.current_tenant_id
        if self.is_admin and not where_extra:
            return "", ()
        if self.is_admin and where_extra:
            return where_extra, params_extra or ()
        if where_extra:
            return f" AND {where_extra}", (tid,) + (params_extra or ())
        return " AND tenant_id=?", (tid,)

    def show_login(self):
        if self.inactivity_timer:
            self.after_cancel(self.inactivity_timer)
            self.inactivity_timer = None
        self.clear()
        self.configure(fg_color="#18191a")

        card = ctk.CTkFrame(self, fg_color="#242526", corner_radius=8,
                             width=396, height=420)
        card.place(relx=0.5, rely=0.45, anchor="center")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=32, pady=(28, 20))

        ctk.CTkLabel(inner, text="\U0001f45f", font=("", 30)).pack(pady=(0, 2))

        ctk.CTkLabel(inner, text="BAGUMA  MARKET", font=(FONT_FAMILY, 30, "bold"),
                     text_color="#2d88ff").pack(pady=(0, 2))

        ctk.CTkFrame(inner, fg_color="#2d88ff", height=2, width=200).pack(pady=(0, 4))

        ctk.CTkLabel(inner, text="Connectez-vous a Baguma Market",
                     font=(FONT_FAMILY, 14), text_color="#8a8d91").pack(pady=(0, 18))

        self.entry_login = ctk.CTkEntry(inner, placeholder_text="Numero ou Email",
                                         height=52, corner_radius=6,
                                         fg_color="#3a3b3c", border_color="#3e4042",
                                         text_color="#e4e6eb", placeholder_text_color="#8a8d91",
                                         font=(FONT_FAMILY, 15))
        self.entry_login.pack(fill="x", pady=(0, 12))

        pwd_frame = ctk.CTkFrame(inner, fg_color="transparent")
        pwd_frame.pack(fill="x", pady=(0, 16))
        pwd_frame.pack_propagate(False)
        pwd_frame.configure(height=52)

        self.entry_code = ctk.CTkEntry(pwd_frame, placeholder_text="Mot de passe",
                                        height=52, corner_radius=6, show="*",
                                        fg_color="#3a3b3c", border_color="#3e4042",
                                        text_color="#e4e6eb", placeholder_text_color="#8a8d91",
                                        font=(FONT_FAMILY, 15))
        self.entry_code.pack(side="left", fill="x", expand=True, ipady=10)

        self.pwd_visible = False
        self.btn_eye = ctk.CTkButton(pwd_frame, text="\U0001f441", width=40, height=40,
                                      fg_color="transparent", hover_color="#4e4f50",
                                      text_color="#8a8d91", font=(FONT_FAMILY, 16),
                                      command=self.toggle_password)
        self.btn_eye.pack(side="right", padx=(2, 0))

        ctk.CTkButton(inner, text="Se connecter", height=48,
                      corner_radius=6, font=(FONT_FAMILY, 18, "bold"),
                      fg_color="#2d88ff", hover_color="#2672e0",
                      text_color="#ffffff",
                      command=self.login).pack(fill="x")

        ctk.CTkButton(inner, text="Mot de passe oublie ?", height=28,
                      fg_color="transparent", hover_color="#3a3b3c",
                      text_color="#2d88ff", font=(FONT_FAMILY, 14),
                      command=self.forgot_password).pack(pady=(12, 0))

        ctk.CTkFrame(inner, fg_color="#3e4042", height=1).pack(fill="x", pady=(16, 0))

        ctk.CTkButton(inner, text="Creer un nouveau compte", height=48,
                      corner_radius=6, font=(FONT_FAMILY, 17, "bold"),
                      fg_color="#42b72a", hover_color="#36a420",
                      text_color="#ffffff",
                      command=self.show_create_account).pack(fill="x", pady=(16, 0))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.place(relx=0.5, rely=0.82, anchor="center")
        ctk.CTkButton(bottom, text="Changer le mot de passe", height=25,
                      fg_color="transparent", hover_color="#3a3b3c",
                      text_color="#8a8d91", font=(FONT_FAMILY, 12),
                      command=self.change_password).pack()

        self.entry_code.bind("<Return>", lambda e: self.login())

    def toggle_password(self):
        self.pwd_visible = not self.pwd_visible
        if self.pwd_visible:
            self.entry_code.configure(show="")
            self.btn_eye.configure(text="\U0001f441\u200d\U0001f5e8")
        else:
            self.entry_code.configure(show="*")
            self.btn_eye.configure(text="\U0001f441")
        self.entry_code.bind("<Return>", lambda e: self.login())

    def login(self):
        lg = self.entry_login.get().strip()
        cd = self.entry_code.get().strip()
        if not lg or not cd:
            messagebox.showwarning("Attention", "Remplissez tous les champs.")
            return
        self.cursor.execute("SELECT id, login, tenant_id, role FROM utilisateurs WHERE login=? AND code=?",
                            (lg, cd))
        row = self.cursor.fetchone()
        if row:
            self.current_user_id = row[0]
            self.current_user_login = row[1]
            self.current_tenant_id = row[2]
            self.current_role = row[3] or ROLE_VENDEUR
            self.is_admin = (self.current_tenant_id == ADMIN_TENANT_ID and self.current_role == ROLE_ADMIN)
            self.taux_cdf = get_taux(self.cursor, self.current_tenant_id)
            log_action(self.cursor, self.conn, self.current_user_id, self.current_user_login,
                       self.current_tenant_id, "Connexion", f"Role: {self.current_role}")
            self.bind_activity()
            self.reset_inactivity()
            self.show_main()
        else:
            messagebox.showerror("Erreur", "Identifiants incorrects.")

    def forgot_password(self):
        win = ctk.CTkToplevel(self)
        win.title("Mot de passe oublie")
        win.geometry("400x250")
        win.configure(fg_color="#f0f2f5")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="Mot de passe oublie", font=(FONT_FAMILY, 18, "bold"),
                     text_color="#1c1e21").pack(pady=(20, 5))
        ctk.CTkLabel(win, text="Entrez votre numero ou email pour\nrecevoir le code de reinitialisation.",
                     font=(FONT_FAMILY, 11), text_color="#65676b").pack(pady=(0, 10))
        entry = ctk.CTkEntry(win, width=280, height=40, placeholder_text="Numero ou Email",
                              fg_color="#ffffff", border_color="#dddfe2", text_color="#1c1e21",
                              font=(FONT_FAMILY, 13))
        entry.pack(pady=5)

        def send_reset():
            val = entry.get().strip()
            if val:
                self.cursor.execute("SELECT code FROM utilisateurs WHERE login=?", (val,))
                row = self.cursor.fetchone()
                if row:
                    messagebox.showinfo("Code envoye", f"Votre code : {row[0]}\n\nContactez l'admin si besoin.")
                else:
                    messagebox.showwarning("Attention", "Aucun compte trouve avec cet identifiant.")
                win.destroy()

        ctk.CTkButton(win, text="Envoyer le code", width=200, height=38,
                      fg_color="#1877f2", hover_color="#166fe5", text_color="#ffffff",
                      font=(FONT_FAMILY, 13, "bold"), command=send_reset).pack(pady=10)

    def change_password(self):
        win = ctk.CTkToplevel(self)
        win.title("Changer le mot de passe")
        win.geometry("400x320")
        win.configure(fg_color="#f0f2f5")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="Changer le mot de passe", font=(FONT_FAMILY, 18, "bold"),
                     text_color="#1c1e21").pack(pady=(20, 5))

        entry_login = ctk.CTkEntry(win, width=280, height=40, placeholder_text="Numero ou Email",
                                    fg_color="#ffffff", border_color="#dddfe2", text_color="#1c1e21",
                                    font=(FONT_FAMILY, 13))
        entry_login.pack(pady=5)

        entry_old = ctk.CTkEntry(win, width=280, height=40, placeholder_text="Ancien mot de passe",
                                  fg_color="#ffffff", border_color="#dddfe2", text_color="#1c1e21",
                                  font=(FONT_FAMILY, 13), show="*")
        entry_old.pack(pady=5)

        entry_new = ctk.CTkEntry(win, width=280, height=40, placeholder_text="Nouveau mot de passe",
                                  fg_color="#ffffff", border_color="#dddfe2", text_color="#1c1e21",
                                  font=(FONT_FAMILY, 13), show="*")
        entry_new.pack(pady=5)

        def do_change():
            lg = entry_login.get().strip()
            old = entry_old.get().strip()
            new = entry_new.get().strip()
            if not lg or not old or not new:
                messagebox.showwarning("Attention", "Remplissez tous les champs.")
                return
            self.cursor.execute("SELECT id FROM utilisateurs WHERE login=? AND code=?", (lg, old))
            if self.cursor.fetchone():
                self.cursor.execute("UPDATE utilisateurs SET code=? WHERE login=?", (new, lg))
                self.conn.commit()
                messagebox.showinfo("Succes", "Mot de passe change avec succes.")
                win.destroy()
            else:
                messagebox.showerror("Erreur", "Identifiants incorrects.")

        ctk.CTkButton(win, text="Changer", width=200, height=38,
                      fg_color="#1877f2", hover_color="#166fe5", text_color="#ffffff",
                      font=(FONT_FAMILY, 13, "bold"), command=do_change).pack(pady=10)

    def show_create_account(self):
        win = ctk.CTkToplevel(self)
        win.title("Creer un compte")
        win.geometry("400x400")
        win.configure(fg_color="#f0f2f5")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="Creer un nouveau compte", font=(FONT_FAMILY, 18, "bold"),
                     text_color="#1c1e21").pack(pady=(20, 5))

        ctk.CTkLabel(win, text="Commerce :", font=(FONT_FAMILY, 12),
                     text_color="#65676b").pack()

        self.cursor.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY nom")
        tenants = self.cursor.fetchall()
        tenant_names = [t[1] for t in tenants]
        tenant_map = {t[1]: t[0] for t in tenants}

        entry_login = ctk.CTkEntry(win, width=280, height=40, placeholder_text="Numero ou Email",
                                    fg_color="#ffffff", border_color="#dddfe2", text_color="#1c1e21",
                                    font=(FONT_FAMILY, 13))
        entry_login.pack(pady=5)

        entry_code = ctk.CTkEntry(win, width=280, height=40, placeholder_text="Mot de passe",
                                  fg_color="#ffffff", border_color="#dddfe2", text_color="#1c1e21",
                                  font=(FONT_FAMILY, 13), show="*")
        entry_code.pack(pady=5)

        combo_tenant = ctk.CTkOptionMenu(win, values=tenant_names or ["Aucun commerce"],
                                          width=280, height=36,
                                          fg_color="#ffffff", button_color="#dddfe2",
                                          text_color="#1c1e21")
        combo_tenant.pack(pady=5)
        if tenant_names:
            combo_tenant.set(tenant_names[0])

        ctk.CTkLabel(win, text="Role :", font=(FONT_FAMILY, 12),
                     text_color="#65676b").pack()
        combo_role = ctk.CTkOptionMenu(win, values=[ROLE_VENDEUR, ROLE_CAISSIER, ROLE_MANAGER],
                                        width=280, height=36,
                                        fg_color="#ffffff", button_color="#dddfe2",
                                        text_color="#1c1e21")
        combo_role.pack(pady=5)
        combo_role.set(ROLE_VENDEUR)

        def do_create():
            lg = entry_login.get().strip()
            cd = entry_code.get().strip()
            tenant_nom = combo_tenant.get()
            role = combo_role.get()
            if not lg or not cd:
                messagebox.showwarning("Attention", "Remplissez tous les champs.")
                return
            if tenant_nom not in tenant_map:
                messagebox.showwarning("Attention", "Choisissez un commerce valide.")
                return
            tenant_id = tenant_map[tenant_nom]
            try:
                self.cursor.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES (?, ?, ?, ?)",
                                    (lg, cd, tenant_id, role))
                self.conn.commit()
                log_action(self.cursor, self.conn, 0, "system", tenant_id,
                           "Creation compte", f"{lg} - Role: {role}")
                messagebox.showinfo("Succes",
                    f"Compte cree pour '{tenant_nom}' avec le role '{role}'.")
                win.destroy()
            except Exception:
                messagebox.showerror("Erreur", "Ce login existe deja.")

        ctk.CTkButton(win, text="Creer le compte", width=200, height=38,
                      fg_color="#42b72a", hover_color="#36a420", text_color="#ffffff",
                      font=(FONT_FAMILY, 13, "bold"), command=do_create).pack(pady=10)

    # ========================= MAIN =========================
    def show_main(self):
        self.clear()
        self.configure(fg_color=MAIN_BG)

        top_bar = ctk.CTkFrame(self, fg_color=SIDEBAR_BG, height=52)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        tenant_label = ""
        if self.is_admin:
            tenant_label = " [ADMIN GLOBAL]"
        else:
            self.cursor.execute("SELECT nom FROM tenants WHERE id=?", (self.current_tenant_id,))
            r = self.cursor.fetchone()
            tenant_label = f" [{r[0]}]" if r else ""

        role_colors = {ROLE_ADMIN: ACCENT_RED, ROLE_MANAGER: GOLD, ROLE_VENDEUR: ACCENT_GREEN, ROLE_CAISSIER: ACCENT_BLUE}
        role_lbl = self.current_role.upper()
        role_col = role_colors.get(self.current_role, TEXT_GRAY)

        ctk.CTkLabel(top_bar, text=f"\U0001f45f  BAGUMA MARKET{tenant_label}",
                     font=(FONT_FAMILY, 17, "bold"), text_color=GOLD_LIGHT).pack(side="left", padx=10)
        ctk.CTkLabel(top_bar, text=f"[{role_lbl}]",
                     font=(FONT_FAMILY, 11, "bold"), text_color=role_col).pack(side="left", padx=5)
        ctk.CTkLabel(top_bar, text=f"({self.current_user_login})",
                     font=(FONT_FAMILY, 10), text_color=TEXT_GRAY).pack(side="left", padx=3)
        self.taux_lbl = ctk.CTkLabel(top_bar,
            text=f"Taux: 1 USD = {self.taux_cdf:,.0f} CDF",
            font=(FONT_FAMILY, 12), text_color=ACCENT_BLUE)
        self.taux_lbl.pack(side="left", padx=10)
        if self.can("modifier_taux"):
            ctk.CTkButton(top_bar, text="Modifier taux", width=105, height=28,
                          fg_color=ACCENT_BLUE, hover_color="#0090b0",
                          text_color="#000", font=(FONT_FAMILY, 10, "bold"),
                          command=self.modifier_taux).pack(side="left", padx=5)

        cond_notif = "" if self.is_admin else " AND tenant_id=?"
        params_notif = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"SELECT COUNT(*) FROM notifications WHERE is_read=0{cond_notif}", params_notif)
        self.notif_count = self.cursor.fetchone()[0]
        notif_text = f"\U0001f514 {self.notif_count}" if self.notif_count > 0 else "\U0001f514"
        notif_color = ACCENT_RED if self.notif_count > 0 else DARK_CARD
        ctk.CTkButton(top_bar, text=notif_text, width=50, height=30,
                      fg_color=notif_color, hover_color="#b30030",
                      corner_radius=6, command=self.page_notifications).pack(side="right", padx=4)

        ctk.CTkButton(top_bar, text="\u274c Deconnexion", width=110, height=30,
                      fg_color=LOGIN_BTN_RED, hover_color="#b30030",
                      corner_radius=6, command=self.show_login).pack(side="right", padx=4)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(body, fg_color=SIDEBAR_BG, width=200)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="\U0001f4cb MENU", font=(FONT_FAMILY, 13, "bold"),
                     text_color=GOLD).pack(pady=(18, 8), anchor="w", padx=12)

        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"SELECT COUNT(*) FROM produits WHERE stock <= 5 AND stock > 0{cond}", params)
        low_stock = self.cursor.fetchone()[0]
        if low_stock > 0:
            notif = ctk.CTkFrame(sidebar, fg_color=ACCENT_RED, corner_radius=6, height=32)
            notif.pack(fill="x", padx=10, pady=(0, 6))
            ctk.CTkLabel(notif, text=f"\u26a0 {low_stock} produit(s) stock faible",
                         font=(FONT_FAMILY, 10, "bold"), text_color="#fff").pack(pady=6)

        btns = []
        btns.append(("\U0001f4ca  Dashboard", self.page_dashboard))
        if self.can("gerer_produits"):
            btns.append(("\U0001f45f  Produits", self.page_produits))
        if self.can("gerer_produits"):
            btns.append(("\U0001f4e6  Stock", self.page_stock))
        if self.can("faire_vente"):
            btns.append(("\U0001f4b8  Ventes", self.page_ventes))
        if self.can("voir_rapports"):
            btns.append(("\U0001f4c8  Rapports", self.page_rapports))
        btns.append(("\U0001f4c4  Recus", self.page_recus))
        if self.can("voir_clients"):
            btns.append(("\U0001f464  Clients", self.page_clients))
        if self.is_admin:
            btns.append(("\U0001f3e2  Tenants", self.page_tenants))
            btns.append(("\U0001f46e  Utilisateurs", self.page_utilisateurs))
        btns.append(("\u2699\ufe0f  Parametres", self.page_settings))

        for text, cmd in btns:
            ctk.CTkButton(sidebar, text=text, anchor="w", height=38, corner_radius=7,
                          fg_color="transparent", hover_color=DARK_CARD,
                          font=(FONT_FAMILY, 12), text_color="#ccccee",
                          command=cmd).pack(pady=2, padx=10, fill="x")

        self.content = ctk.CTkFrame(body, fg_color=MAIN_BG)
        self.content.pack(side="left", fill="both", expand=True)

        self.page_dashboard()
        self.check_low_stock()

    def check_low_stock(self):
        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"SELECT nom, stock FROM produits WHERE stock <= 5 AND stock > 0{cond}", params)
        low = self.cursor.fetchall()
        if low:
            msg = "\n".join([f"  {nom}: {stock} paires" for nom, stock in low[:5]])
            self.after(500, lambda: messagebox.showwarning("Stock faible",
                f"Produits bientot en rupture :\n{msg}"))

    def modifier_taux(self):
        win = ctk.CTkToplevel(self)
        win.title("Modifier le taux")
        win.geometry("350x200")
        win.configure(fg_color=LOGIN_BG)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="\U0001f4b1 Taux de change",
                     font=(FONT_FAMILY, 16, "bold"), text_color=GOLD_LIGHT).pack(pady=(15, 5))
        ctk.CTkLabel(win, text="1 USD = ? CDF",
                     font=(FONT_FAMILY, 12), text_color=TEXT_GRAY).pack()
        entry = ctk.CTkEntry(win, width=150, height=38, font=(FONT_FAMILY, 16),
                              fg_color=DARK_CARD, border_color=GOLD_DARK, justify="center")
        entry.insert(0, str(int(self.taux_cdf)))
        entry.pack(pady=10)
        entry.select_range(0, "end")
        entry.focus()

        def save():
            try:
                val = float(entry.get())
                if val <= 0:
                    raise ValueError
                self.taux_cdf = val
                set_taux(self.cursor, self.conn, val, self.current_tenant_id)
                self.taux_lbl.configure(text=f"Taux: 1 USD = {val:,.0f} CDF")
                win.destroy()
            except Exception:
                messagebox.showwarning("Erreur", "Entrez un nombre valide.")

        ctk.CTkButton(win, text="Enregistrer", width=120, height=36,
                      fg_color=GOLD_DARK, text_color="#000",
                      font=(FONT_FAMILY, 13, "bold"), command=save).pack(pady=5)
        entry.bind("<Return>", lambda e: save())

    # ========================= DASHBOARD =========================
    def page_dashboard(self):
        for w in self.content.winfo_children():
            w.destroy()

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(12, 8))
        ctk.CTkLabel(header, text="\U0001f4ca  Tableau de bord",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(side="left")
        ctk.CTkButton(header, text="\U0001f4b8 Nouvelle vente", width=160, height=32,
                      fg_color=ACCENT_GREEN, hover_color="#00a884", text_color="#000",
                      font=(FONT_FAMILY, 12, "bold"),
                      command=self.page_ventes).pack(side="right", padx=8)
        ctk.CTkLabel(header, text=date.today().strftime("%d/%m/%Y"),
                     font=(FONT_FAMILY, 12), text_color=TEXT_GRAY).pack(side="right")

        today = date.today().isoformat()
        cond = "" if self.is_admin else " AND tenant_id=?"
        params_d = () if self.is_admin else (self.current_tenant_id,)

        self.cursor.execute(f"SELECT COALESCE(SUM(total_usd),0), COALESCE(SUM(total_cdf),0) FROM ventes WHERE date=?{cond}",
                            (today,) + params_d)
        tot = self.cursor.fetchone()
        self.cursor.execute(f"SELECT COUNT(DISTINCT client_id) FROM ventes WHERE date=?{cond}",
                            (today,) + params_d)
        nb_clients = self.cursor.fetchone()[0]
        self.cursor.execute(f"SELECT COUNT(*) FROM ventes WHERE date=?{cond}",
                            (today,) + params_d)
        nb_ventes = self.cursor.fetchone()[0]
        self.cursor.execute(f"SELECT COALESCE(SUM(stock),0) FROM produits WHERE 1=1{cond}", params_d)
        stock_total = self.cursor.fetchone()[0]
        self.cursor.execute(f"SELECT COUNT(*) FROM ventes WHERE est_client_honneur=1 AND date=?{cond}",
                            (today,) + params_d)
        nb_honneur = self.cursor.fetchone()[0]

        cards_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        cards_frame.pack(fill="x", padx=18, pady=3)

        stats = [
            ("\U0001f4b0 Ventes USD", f"${tot[0]:,.2f}", GOLD_LIGHT),
            ("\U0001f4b0 Ventes CDF", f"{tot[1]:,.0f} CDF", "#f4a261"),
            ("\U0001f4c5 Clients", str(nb_clients), ACCENT_GREEN),
            ("\U0001f4e6 Ventes", str(nb_ventes), ACCENT_BLUE),
            ("\U0001f4e6 Stock", str(stock_total), GOLD),
            ("\u2b50 Honneur", str(nb_honneur), HONOR_COLOR),
        ]
        for i, (label, val, color) in enumerate(stats):
            card = ctk.CTkFrame(cards_frame, fg_color=CARD_BG, corner_radius=9, height=85)
            card.grid(row=0, column=i, padx=3, pady=4, sticky="nsew")
            cards_frame.columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=label, font=(FONT_FAMILY, 9), text_color=TEXT_GRAY).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=val, font=(FONT_FAMILY, 15, "bold"), text_color=color).pack(pady=(2, 8))

        bottom = ctk.CTkFrame(self.content, fg_color="transparent")
        bottom.pack(fill="both", expand=True, padx=18, pady=(5, 10))

        left = ctk.CTkFrame(bottom, fg_color=CARD_BG, corner_radius=9)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))
        ctk.CTkLabel(left, text="\U0001f4b8 Dernieres ventes",
                     font=(FONT_FAMILY, 13, "bold"), text_color=ACCENT_GREEN).pack(anchor="w", padx=14, pady=(10, 5))
        self.cursor.execute(f"""SELECT p.nom, v.quantite, v.total_usd, v.date, v.heure
            FROM ventes v JOIN produits p ON v.produit_id=p.id
            WHERE 1=1{cond}
            ORDER BY v.id DESC LIMIT 10""", params_d)
        for nom, qte, usd, d, h in self.cursor.fetchall():
            row = ctk.CTkFrame(left, fg_color="transparent", height=24)
            row.pack(fill="x", padx=14, pady=1)
            ctk.CTkLabel(row, text=f"{nom}  x{qte}", font=(FONT_FAMILY, 11),
                         text_color="#ccccee", anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"${usd:,.2f}  {h}", font=(FONT_FAMILY, 11, "bold"),
                         text_color=GOLD_LIGHT).pack(side="right")

        right = ctk.CTkFrame(bottom, fg_color=CARD_BG, corner_radius=9)
        right.pack(side="left", fill="both", expand=True, padx=(4, 0))
        ctk.CTkLabel(right, text="\U0001f4c4 Derniers recus",
                     font=(FONT_FAMILY, 13, "bold"), text_color=GOLD).pack(anchor="w", padx=14, pady=(10, 5))
        self.cursor.execute(f"""SELECT r.numero, cl.nom, r.total_usd, r.est_honneur, r.heure
            FROM recus r LEFT JOIN clients cl ON r.client_id=cl.id
            WHERE 1=1{cond}
            ORDER BY r.id DESC LIMIT 10""", params_d)
        for num, nom, usd, hon, h in self.cursor.fetchall():
            row = ctk.CTkFrame(right, fg_color="transparent", height=24)
            row.pack(fill="x", padx=14, pady=1)
            honor = " \u2b50" if hon else ""
            ctk.CTkLabel(row, text=f"{num} - {nom or 'Anonyme'}{honor}", font=(FONT_FAMILY, 11),
                         text_color="#ccccee", anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"${usd:,.2f}  {h}", font=(FONT_FAMILY, 11, "bold"),
                         text_color=GOLD_LIGHT).pack(side="right")

        if self.is_admin:
            self._build_admin_dashboard(today)

    def _build_admin_dashboard(self, today):
        bottom2 = ctk.CTkFrame(self.content, fg_color="transparent")
        bottom2.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        left2 = ctk.CTkFrame(bottom2, fg_color=CARD_BG, corner_radius=9)
        left2.pack(side="left", fill="both", expand=True, padx=(0, 4))

        header_r = ctk.CTkFrame(left2, fg_color="transparent")
        header_r.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(header_r, text="\U0001f4ca  Ventes par Tenant (7 jours)",
                     font=(FONT_FAMILY, 13, "bold"), text_color=GOLD).pack(side="left")

        debut_7 = (date.today() - timedelta(days=6)).isoformat()
        self.cursor.execute("""SELECT t.nom, COALESCE(SUM(v.total_usd),0)
            FROM tenants t LEFT JOIN ventes v ON t.id=v.tenant_id AND v.date BETWEEN ? AND ?
            WHERE t.actif=1 GROUP BY t.id ORDER BY SUM(v.total_usd) DESC""",
            (debut_7, today))
        tenant_sales = self.cursor.fetchall()
        max_sale = max((s[1] for s in tenant_sales), default=1) or 1

        bar_frame = ctk.CTkFrame(left2, fg_color="transparent")
        bar_frame.pack(fill="both", expand=True, padx=14, pady=(4, 10))

        bar_colors = [ACCENT_GREEN, ACCENT_BLUE, GOLD, HONOR_COLOR, ACCENT_ORANGE]
        for i, (tnom, total) in enumerate(tenant_sales):
            pct = (total / max_sale * 100) if max_sale > 0 else 0
            bar_color = bar_colors[i % len(bar_colors)]

            brow = ctk.CTkFrame(bar_frame, fg_color="transparent", height=32)
            brow.pack(fill="x", pady=2)
            ctk.CTkLabel(brow, text=tnom, font=(FONT_FAMILY, 11, "bold"),
                         text_color=TEXT_WHITE, width=150, anchor="w").pack(side="left")

            bar_bg = ctk.CTkFrame(brow, fg_color=DARK_CARD, height=20, corner_radius=4)
            bar_bg.pack(side="left", fill="x", expand=True, padx=6)
            bar_bg.pack_propagate(False)
            bar = ctk.CTkFrame(bar_bg, fg_color=bar_color, height=20, corner_radius=4)
            bar.place(relx=0, rely=0, relwidth=max(pct / 100, 0.02), relheight=1.0)

            ctk.CTkLabel(brow, text=f"${total:,.0f}", font=(FONT_FAMILY, 11, "bold"),
                         text_color=GOLD_LIGHT, width=90, anchor="e").pack(side="right")

        right2 = ctk.CTkFrame(bottom2, fg_color=CARD_BG, corner_radius=9)
        right2.pack(side="left", fill="both", expand=True, padx=(4, 0))

        ctk.CTkLabel(right2, text="\U0001f3c6  Classement Chiffre d'Affaires",
                     font=(FONT_FAMILY, 13, "bold"), text_color=GOLD).pack(anchor="w", padx=14, pady=(10, 5))

        rank_frame = ctk.CTkFrame(right2, fg_color="transparent")
        rank_frame.pack(fill="both", expand=True, padx=14, pady=(0, 4))

        self.cursor.execute("""SELECT t.id, t.nom,
            COALESCE(SUM(v.total_usd),0) as ca_usd,
            COALESCE(SUM(v.total_cdf),0) as ca_cdf,
            COUNT(v.id) as nb_ventes,
            (SELECT COUNT(*) FROM produits WHERE tenant_id=t.id) as nb_produits,
            (SELECT COALESCE(SUM(stock),0) FROM produits WHERE tenant_id=t.id) as stock
            FROM tenants t LEFT JOIN ventes v ON t.id=v.tenant_id
            WHERE t.actif=1 GROUP BY t.id ORDER BY ca_usd DESC""")
        ranking = self.cursor.fetchall()

        medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
        for idx, (tid, tnom, ca_usd, ca_cdf, nb_v, nb_p, stk) in enumerate(ranking):
            medal = medals[idx] if idx < 3 else f"#{idx+1}"
            rcard = ctk.CTkFrame(rank_frame, fg_color=DARK_CARD, corner_radius=7, height=58)
            rcard.pack(fill="x", pady=2)
            rcard.pack_propagate(False)

            left_part = ctk.CTkFrame(rcard, fg_color="transparent")
            left_part.pack(side="left", fill="y", padx=8)
            ctk.CTkLabel(left_part, text=f"{medal}  {tnom}", font=(FONT_FAMILY, 12, "bold"),
                         text_color=TEXT_WHITE).pack(anchor="w", pady=(6, 0))
            ctk.CTkLabel(left_part, text=f"{nb_v} ventes  |  {nb_p} produits  |  Stock: {stk}",
                         font=(FONT_FAMILY, 9), text_color=TEXT_GRAY).pack(anchor="w")

            right_part = ctk.CTkFrame(rcard, fg_color="transparent")
            right_part.pack(side="right", fill="y", padx=12)
            ctk.CTkLabel(right_part, text=f"${ca_usd:,.0f}", font=(FONT_FAMILY, 14, "bold"),
                         text_color=GOLD_LIGHT).pack(anchor="e", pady=(6, 0))
            ctk.CTkLabel(right_part, text=f"{ca_cdf:,.0f} CDF", font=(FONT_FAMILY, 9),
                         text_color="#f4a261").pack(anchor="e")

        alert_header = ctk.CTkFrame(right2, fg_color="transparent")
        alert_header.pack(fill="x", padx=14, pady=(6, 2))
        ctk.CTkLabel(alert_header, text="\u26a0  Alertes Stock Faible",
                     font=(FONT_FAMILY, 11, "bold"), text_color=ACCENT_RED).pack(side="left")

        self.cursor.execute("""SELECT t.nom, p.nom, p.stock
            FROM produits p JOIN categories c ON p.categorie_id=c.id
            JOIN tenants t ON p.tenant_id=t.id
            WHERE p.stock <= 5 AND p.stock > 0 ORDER BY p.stock ASC LIMIT 8""")
        low_stock = self.cursor.fetchall()
        if low_stock:
            for tnom, pnom, stk in low_stock:
                arow = ctk.CTkFrame(right2, fg_color="transparent", height=20)
                arow.pack(fill="x", padx=14, pady=1)
                ctk.CTkLabel(arow, text=f"  [{tnom}] {pnom}: {stk} paires",
                             font=(FONT_FAMILY, 9), text_color=ACCENT_RED, anchor="w").pack(side="left")
        else:
            ctk.CTkLabel(right2, text="  Aucune alerte stock",
                         font=(FONT_FAMILY, 9), text_color=ACCENT_GREEN).pack(anchor="w", padx=14)

    # ========================= PRODUITS =========================
    def page_produits(self):
        for w in self.content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.content, text="\U0001f45f  Catalogue des Produits",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(pady=(12, 8), anchor="w", padx=18)

        top_bar = ctk.CTkFrame(self.content, fg_color="transparent")
        top_bar.pack(fill="x", padx=18, pady=4)

        self.search_var = ctk.StringVar()
        ctk.CTkEntry(top_bar, textvariable=self.search_var, placeholder_text="Rechercher...",
                     width=260, height=34, corner_radius=7,
                     fg_color=DARK_CARD, border_color=GOLD_DARK).pack(side="left")
        ctk.CTkButton(top_bar, text="Chercher", width=90, height=34,
                      fg_color=GOLD_DARK, hover_color=GOLD, text_color="#000",
                      command=self.rechercher_produits).pack(side="left", padx=4)

        cond = "" if self.is_admin else " AND c.tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"SELECT nom FROM categories c WHERE 1=1{cond} ORDER BY nom", params)
        cats = [r[0] for r in self.cursor.fetchall()]
        self.filtre_cat = ctk.StringVar(value="Toutes")
        ctk.CTkOptionMenu(top_bar, variable=self.filtre_cat,
                          values=["Toutes"] + cats, width=170, height=34,
                          fg_color=DARK_CARD,
                          command=lambda e: self.afficher_produits()).pack(side="left", padx=4)

        tree_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        tree_frame.pack(fill="both", expand=True, padx=18, pady=(5, 10))

        from tkinter import ttk
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Gold.Treeview", background=DARK_CARD, foreground="white",
                             fieldbackground=DARK_CARD, rowheight=30, font=(FONT_FAMILY, 11))
        self.style.configure("Gold.Treeview.Heading", background=GOLD_DARK, foreground="#000",
                             font=(FONT_FAMILY, 11, "bold"))
        self.style.map("Gold.Treeview", background=[("selected", GOLD_DARK)])

        cols = ("ID", "Nom", "Categorie", "Prix USD", "Prix CDF", "Stock")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                 style="Gold.Treeview", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("ID", width=38, anchor="center")
        self.tree.column("Nom", width=230)
        self.tree.column("Categorie", width=130)
        self.tree.column("Prix USD", width=85, anchor="center")
        self.tree.column("Prix CDF", width=105, anchor="center")
        self.tree.column("Stock", width=55, anchor="center")
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.afficher_produits()

    def afficher_produits(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        cat = self.filtre_cat.get()
        cond = "" if self.is_admin else " AND p.tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)

        if cat == "Toutes":
            self.cursor.execute(f"""SELECT p.id, p.nom, c.nom, p.prix_usd, p.prix_cdf, p.stock
                FROM produits p JOIN categories c ON p.categorie_id=c.id
                WHERE 1=1{cond} ORDER BY c.nom, p.nom""", params)
        else:
            self.cursor.execute(f"""SELECT p.id, p.nom, c.nom, p.prix_usd, p.prix_cdf, p.stock
                FROM produits p JOIN categories c ON p.categorie_id=c.id
                WHERE c.nom=?{cond} ORDER BY p.nom""", (cat,) + params)
        for p in self.cursor.fetchall():
            self.tree.insert("", "end", values=(p[0], p[1], p[2], f"${p[3]:.2f}", f"{p[4]:,.0f}", p[5]))

    def rechercher_produits(self):
        term = self.search_var.get().strip()
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not term:
            self.afficher_produits()
            return
        cond = "" if self.is_admin else " AND p.tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"""SELECT p.id, p.nom, c.nom, p.prix_usd, p.prix_cdf, p.stock
            FROM produits p JOIN categories c ON p.categorie_id=c.id
            WHERE p.nom LIKE ?{cond} ORDER BY p.nom""",
            (f"%{term}%",) + params)
        for p in self.cursor.fetchall():
            self.tree.insert("", "end", values=(p[0], p[1], p[2], f"${p[3]:.2f}", f"{p[4]:,.0f}", p[5]))

    # ========================= STOCK =========================
    def page_stock(self):
        for w in self.content.winfo_children():
            w.destroy()

        top_bar = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=0, height=60)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)
        inner = ctk.CTkFrame(top_bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=8)
        ctk.CTkLabel(inner, text="\U0001f4e6  Gestion du Stock",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(side="left")
        ctk.CTkButton(inner, text="\u2795 Entree", width=120, height=34,
                      fg_color=ACCENT_GREEN, hover_color="#00a884", text_color="#000",
                      font=(FONT_FAMILY, 12, "bold"),
                      command=self._stock_entree).pack(side="right", padx=4)
        ctk.CTkButton(inner, text="\u2796 Sortie", width=120, height=34,
                      fg_color=ACCENT_RED, hover_color="#e74c3c", text_color="#000",
                      font=(FONT_FAMILY, 12, "bold"),
                      command=self._stock_sortie).pack(side="right", padx=4)

        scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=(6, 0))

        self.cursor.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
        tenants = self.cursor.fetchall()
        from tkinter import ttk

        for tenant_id, tenant_name in tenants:
            card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=12)
            card.pack(fill="x", pady=(0, 10), padx=4)

            hdr = ctk.CTkFrame(card, fg_color=GOLD_DARK, corner_radius=12, height=44)
            hdr.pack(fill="x")
            hdr.pack_propagate(False)
            emoji = "\U0001f1ea\U0001f1f6" if "Bukavu" in tenant_name else "\U0001f30d"
            ctk.CTkLabel(hdr, text=f"  {emoji}  {tenant_name}",
                         font=(FONT_FAMILY, 15, "bold"), text_color="#000").pack(side="left", padx=10)

            self.cursor.execute(
                "SELECT COALESCE(SUM(quantite),0) FROM stock WHERE tenant_id=? AND mouvement='entree'",
                (tenant_id,))
            total_entrees = self.cursor.fetchone()[0]
            self.cursor.execute(
                "SELECT COALESCE(SUM(quantite),0) FROM stock WHERE tenant_id=? AND mouvement='sortie'",
                (tenant_id,))
            total_sorties = self.cursor.fetchone()[0]
            net = total_entrees - total_sorties

            stats = ctk.CTkFrame(card, fg_color="transparent")
            stats.pack(fill="x", padx=12, pady=(8, 4))
            for lbl, val, col in [
                ("\u2b07 Entrees", str(total_entrees), ACCENT_GREEN),
                ("\u2b06 Sorties", str(total_sorties), ACCENT_RED),
                ("\U0001f4b0 Stock Net", str(net), GOLD_LIGHT),
            ]:
                sc = ctk.CTkFrame(stats, fg_color=MAIN_BG, corner_radius=8, height=50)
                sc.pack(side="left", fill="x", expand=True, padx=3)
                sc.pack_propagate(False)
                ctk.CTkLabel(sc, text=lbl, font=(FONT_FAMILY, 9), text_color=TEXT_GRAY).pack(pady=(5, 0))
                ctk.CTkLabel(sc, text=val, font=(FONT_FAMILY, 16, "bold"), text_color=col).pack()

            sep = ctk.CTkFrame(card, fg_color=GOLD_DARK, height=1)
            sep.pack(fill="x", padx=12, pady=(6, 2))

            ctk.CTkLabel(card, text="\U0001f4ca  Stock par produit",
                         font=(FONT_FAMILY, 12, "bold"), text_color=ACCENT_GREEN).pack(anchor="w", padx=14, pady=(6, 2))

            st_frame = ctk.CTkFrame(card, fg_color=MAIN_BG, corner_radius=8)
            st_frame.pack(fill="x", padx=12, pady=(0, 6))

            style = ttk.Style()
            style.theme_use("clam")
            style.configure("SR.Treeview", background=MAIN_BG, foreground=TEXT_WHITE,
                            fieldbackground=MAIN_BG, rowheight=30, font=(FONT_FAMILY, 10))
            style.configure("SR.Treeview.Heading", background=ACCENT_GREEN, foreground="#000",
                            font=(FONT_FAMILY, 10, "bold"))
            style.map("SR.Treeview", background=[("selected", ACCENT_BLUE)])

            s_cols = ("produit", "code", "marque", "entrees", "sorties", "restant", "resp")
            s_tree = ttk.Treeview(st_frame, columns=s_cols, show="headings", style="SR.Treeview", height=5)
            for c, txt, w in [("produit", "Produit", 160), ("code", "Code", 90),
                              ("marque", "Marque", 100), ("entrees", "Entrees", 80),
                              ("sorties", "Sorties", 80), ("restant", "Restant", 85),
                              ("resp", "Dernier resp.", 140)]:
                s_tree.heading(c, text=txt)
                s_tree.column(c, width=w, anchor="center")
            s_tree.pack(fill="x", padx=4, pady=4)

            self.cursor.execute("""
                SELECT sr.produit_nom, sr.code_produit, sr.marque, sr.total_entrees, sr.total_sorties, sr.stock_disponible,
                       (SELECT u.login FROM stock s2 JOIN utilisateurs u ON s2.user_id=u.id
                        WHERE s2.product_id=sr.product_id AND s2.tenant_id=sr.tenant_id AND s2.mouvement='sortie'
                        ORDER BY s2.date_mouvement DESC LIMIT 1)
                FROM stock_restant sr
                WHERE sr.tenant_id=?
                ORDER BY sr.produit_nom
            """, (tenant_id,))
            for r in self.cursor.fetchall():
                rest = r[5]
                tag = "low" if rest <= 0 else "ok"
                s_tree.insert("", "end",
                    values=(r[0] or "-", r[1] or "-", r[2] or "-", f"{r[3]}", f"{r[4]}", f"{rest}", r[6] or "-"),
                    tags=(tag,))
            s_tree.tag_configure("ok", foreground=ACCENT_GREEN)
            s_tree.tag_configure("low", foreground=ACCENT_RED)

            sep2 = ctk.CTkFrame(card, fg_color=GOLD_DARK, height=1)
            sep2.pack(fill="x", padx=12, pady=(4, 2))

            ctk.CTkLabel(card, text="\U0001f4dd  Historique des mouvements",
                         font=(FONT_FAMILY, 12, "bold"), text_color=TEXT_GRAY).pack(anchor="w", padx=14, pady=(6, 2))

            h_frame = ctk.CTkFrame(card, fg_color=MAIN_BG, corner_radius=8)
            h_frame.pack(fill="x", padx=12, pady=(0, 10))

            style.configure("SH.Treeview", background=MAIN_BG, foreground=TEXT_WHITE,
                            fieldbackground=MAIN_BG, rowheight=28, font=(FONT_FAMILY, 9))
            style.configure("SH.Treeview.Heading", background=GOLD_DARK, foreground="#000",
                            font=(FONT_FAMILY, 9, "bold"))
            style.map("SH.Treeview", background=[("selected", ACCENT_BLUE)])

            h_cols = ("date", "type", "produit", "code", "qte", "resp")
            h_tree = ttk.Treeview(h_frame, columns=h_cols, show="headings", style="SH.Treeview", height=5)
            for c, txt, w in [("date", "Date/Heure", 140), ("type", "Type", 80),
                              ("produit", "Produit", 160), ("code", "Code", 90),
                              ("qte", "Quantite", 80), ("resp", "Responsable", 140)]:
                h_tree.heading(c, text=txt)
                h_tree.column(c, width=w, anchor="center")
            h_tree.pack(fill="x", padx=4, pady=4)

            self.cursor.execute("""
                SELECT s.date_mouvement, s.mouvement, p.nom, s.code_produit, s.quantite, u.login
                FROM stock s
                JOIN produits p ON s.product_id=p.id
                JOIN utilisateurs u ON s.user_id=u.id
                WHERE s.tenant_id=?
                ORDER BY s.date_mouvement DESC LIMIT 30
            """, (tenant_id,))
            for r in self.cursor.fetchall():
                dt = r[0][:16] if r[0] else ""
                tag = "entree" if r[1] == "entree" else "sortie"
                qte = f"+{r[4]}" if r[1] == "entree" else f"-{r[4]}"
                h_tree.insert("", "end", values=(dt, r[1].upper(), r[2], r[3], qte, r[5]),
                              tags=(tag,))
            h_tree.tag_configure("entree", foreground=ACCENT_GREEN)
            h_tree.tag_configure("sortie", foreground=ACCENT_RED)

    def _stock_entree(self):
        d = ctk.CTkToplevel(self)
        d.title("Entree de stock")
        d.geometry("420x480")
        d.configure(fg_color=MAIN_BG)
        d.transient(self)
        d.grab_set()

        ctk.CTkLabel(d, text="\U0001f4e6  Entree de Stock", font=(FONT_FAMILY, 16, "bold"),
                     text_color=ACCENT_GREEN).pack(pady=(12, 8))

        row_p = ctk.CTkFrame(d, fg_color="transparent")
        row_p.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_p, text="Produit :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        cond = "" if self.is_admin else " WHERE tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"SELECT id, nom FROM produits{cond} ORDER BY nom", params)
        prods = self.cursor.fetchall()
        prod_map = {p[1]: p[0] for p in prods}
        prod_var = ctk.StringVar(value=prods[0][1] if prods else "")
        ctk.CTkOptionMenu(row_p, variable=prod_var, values=[p[1] for p in prods],
                          width=250, fg_color=DARK_CARD).pack(side="left", padx=6)

        row_m = ctk.CTkFrame(d, fg_color="transparent")
        row_m.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_m, text="Marque :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        marque_entry = ctk.CTkEntry(row_m, width=250, fg_color=DARK_CARD, border_color=GOLD_DARK)
        marque_entry.pack(side="left", padx=6)

        row_c = ctk.CTkFrame(d, fg_color="transparent")
        row_c.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_c, text="Code :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        code_entry = ctk.CTkEntry(row_c, width=250, fg_color=DARK_CARD, border_color=GOLD_DARK)
        code_entry.pack(side="left", padx=6)

        row_q = ctk.CTkFrame(d, fg_color="transparent")
        row_q.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_q, text="Quantite :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        qte_entry = ctk.CTkEntry(row_q, width=250, fg_color=DARK_CARD, border_color=GOLD_DARK, placeholder_text="Nombre de paires")
        qte_entry.pack(side="left", padx=6)

        row_r = ctk.CTkFrame(d, fg_color="transparent")
        row_r.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_r, text="Responsable :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        tid_u = self.current_tenant_id
        if self.is_admin:
            self.cursor.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
            _tnts_e = self.cursor.fetchall()
            _tnt_map_e = {t[1]: t[0] for t in _tnts_e}
            tid_u = _tnt_map_e.get(_tnts_e[0][1], self.current_tenant_id) if _tnts_e else self.current_tenant_id
        self.cursor.execute("SELECT id, login FROM utilisateurs WHERE tenant_id IN (0, ?) ORDER BY login", (tid_u,))
        _all_users_e = self.cursor.fetchall()
        _user_names_e = [u[1] for u in _all_users_e]
        resp_entry = ctk.CTkEntry(row_r, width=200, fg_color=DARK_CARD, border_color=GOLD_DARK,
                                   text_color="#ffffff", placeholder_text="Nom du responsable",
                                   font=(FONT_FAMILY, 12, "bold"))
        resp_entry.pack(side="left", padx=(6, 2))
        resp_entry.insert(0, self.current_user_login)
        resp_entry.focus()

        def pick_resp_e(val):
            resp_entry.delete(0, "end")
            resp_entry.insert(0, val)
            resp_entry.focus()
        ctk.CTkOptionMenu(row_r, values=["--- Choisir ---"] + _user_names_e, command=lambda v: pick_resp_e(v) if v != "--- Choisir ---" else None,
                          width=90, fg_color=GOLD_DARK, text_color="#000").pack(side="left", padx=2)

        if self.is_admin:
            row_t = ctk.CTkFrame(d, fg_color="transparent")
            row_t.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(row_t, text="Commerce :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
            self.cursor.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
            tnts = self.cursor.fetchall()
            tnt_map = {t[1]: t[0] for t in tnts}
            tnt_var = ctk.StringVar(value=tnts[0][1] if tnts else "")
            ctk.CTkOptionMenu(row_t, variable=tnt_var, values=[t[1] for t in tnts],
                              width=250, fg_color=DARK_CARD).pack(side="left", padx=6)

        def valider():
            try:
                qte = int(qte_entry.get())
                if qte <= 0:
                    messagebox.showerror("Erreur", "La quantite doit etre > 0")
                    return
            except ValueError:
                messagebox.showerror("Erreur", "Quantite invalide")
                return
            prod_id = prod_map.get(prod_var.get())
            if not prod_id:
                messagebox.showerror("Erreur", "Produit invalide")
                return
            marque = marque_entry.get().strip()
            code = code_entry.get().strip()
            tenant_id = tnt_map.get(tnt_var.get()) if self.is_admin else self.current_tenant_id
            resp_login = resp_entry.get().strip()
            resp_id = self.current_user_id
            for u in _all_users_e:
                if u[1] == resp_login:
                    resp_id = u[0]
                    break

            self.cursor.execute("INSERT INTO stock (tenant_id, product_id, mouvement, quantite, marque, code_produit, user_id) VALUES (?,?,?,?,?,?,?)",
                                (tenant_id, prod_id, "entree", qte, marque, code, resp_id))
            self.cursor.execute("UPDATE produits SET stock=stock+? WHERE id=?", (qte, prod_id))
            self.conn.commit()
            log_action(self.cursor, self.conn, self.current_user_id, self.current_user_login, tenant_id, "stock_entree",
                       f"+{qte} {prod_var.get()} ({marque}) (resp: {resp_login})")
            messagebox.showinfo("Succes", f"Entree enregistree : +{qte} paires (Resp: {resp_login})")
            d.destroy()
            self.page_stock()

        ctk.CTkButton(d, text="Valider l'entree", width=200, height=36,
                      fg_color=ACCENT_GREEN, hover_color="#00a884", text_color="#000",
                      font=(FONT_FAMILY, 12, "bold"),
                      command=valider).pack(pady=16)

    def _stock_sortie(self):
        d = ctk.CTkToplevel(self)
        d.title("Sortie de stock")
        d.geometry("420x510")
        d.configure(fg_color=MAIN_BG)
        d.transient(self)
        d.grab_set()

        ctk.CTkLabel(d, text="\U0001f4e6  Sortie de Stock", font=(FONT_FAMILY, 16, "bold"),
                     text_color=ACCENT_RED).pack(pady=(12, 8))

        if self.is_admin:
            row_t = ctk.CTkFrame(d, fg_color="transparent")
            row_t.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(row_t, text="Commerce :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
            self.cursor.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
            tnts = self.cursor.fetchall()
            tnt_map = {t[1]: t[0] for t in tnts}
            tnt_var = ctk.StringVar(value=tnts[0][1] if tnts else "")
            ctk.CTkOptionMenu(row_t, variable=tnt_var, values=[t[1] for t in tnts],
                              width=250, fg_color=DARK_CARD).pack(side="left", padx=6)
        else:
            tnts = []
            tnt_map = {}
            tnt_var = ctk.StringVar(value="")

        row_p = ctk.CTkFrame(d, fg_color="transparent")
        row_p.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_p, text="Produit :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")

        prod_var = ctk.StringVar(value="")
        stock_label = ctk.CTkLabel(d, text="", font=(FONT_FAMILY, 10), text_color=TEXT_GRAY)
        stock_label.pack(padx=20, anchor="w")
        pm = {}
        sm = {}

        def load_prods(*args):
            pm.clear()
            sm.clear()
            tid = tnt_map.get(tnt_var.get()) if self.is_admin else self.current_tenant_id
            self.cursor.execute("SELECT id, nom, stock FROM produits WHERE tenant_id=? ORDER BY nom", (tid,))
            prods = self.cursor.fetchall()
            for p in prods:
                pm[p[1]] = p[0]
                sm[p[1]] = p[2]
            noms = [p[1] for p in prods]
            prod_var.set(noms[0] if noms else "")
            for w in row_p.winfo_children():
                if isinstance(w, ctk.CTkOptionMenu):
                    w.destroy()
            om = ctk.CTkOptionMenu(row_p, variable=prod_var, values=noms if noms else [""],
                                   width=250, fg_color=DARK_CARD)
            om.pack(side="left", padx=6)
            def update_lbl(*a):
                stock_label.configure(text=f"Stock disponible : {sm.get(prod_var.get(), 0)} paires")
            prod_var.trace_add("write", update_lbl)
            update_lbl()

        load_prods()

        if self.is_admin:
            tnt_var.trace_add("write", lambda *a: load_prods())

        row_q = ctk.CTkFrame(d, fg_color="transparent")
        row_q.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_q, text="Quantite :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        qte_entry = ctk.CTkEntry(row_q, width=250, fg_color=DARK_CARD, border_color=GOLD_DARK, placeholder_text="Nombre de paires")
        qte_entry.pack(side="left", padx=6)

        row_c = ctk.CTkFrame(d, fg_color="transparent")
        row_c.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_c, text="Code :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        code_entry = ctk.CTkEntry(row_c, width=250, fg_color=DARK_CARD, border_color=GOLD_DARK, placeholder_text="Code produit / SKU")
        code_entry.pack(side="left", padx=6)

        row_r = ctk.CTkFrame(d, fg_color="transparent")
        row_r.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row_r, text="Responsable :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        tid_u = self.current_tenant_id
        if self.is_admin and tnts:
            tid_u = tnt_map.get(tnts[0][1], self.current_tenant_id)
        self.cursor.execute("SELECT id, login FROM utilisateurs WHERE tenant_id IN (0, ?) ORDER BY login", (tid_u,))
        all_users = self.cursor.fetchall()
        user_names = [u[1] for u in all_users]

        resp_entry = ctk.CTkEntry(row_r, width=200, fg_color=DARK_CARD, border_color=GOLD_DARK,
                                   text_color="#ffffff", placeholder_text="Nom du responsable",
                                   font=(FONT_FAMILY, 12, "bold"))
        resp_entry.pack(side="left", padx=(6, 2))
        resp_entry.insert(0, self.current_user_login)
        resp_entry.focus()

        def pick_resp(val):
            resp_entry.delete(0, "end")
            resp_entry.insert(0, val)
            resp_entry.focus()
        ctk.CTkOptionMenu(row_r, values=["--- Choisir ---"] + user_names, command=lambda v: pick_resp(v) if v != "--- Choisir ---" else None,
                          width=90, fg_color=GOLD_DARK, text_color="#000").pack(side="left", padx=2)

        def valider():
            try:
                qte = int(qte_entry.get())
                if qte <= 0:
                    messagebox.showerror("Erreur", "La quantite doit etre > 0")
                    return
            except ValueError:
                messagebox.showerror("Erreur", "Quantite invalide")
                return
            nom_prod = prod_var.get()
            prod_id = pm.get(nom_prod)
            if not prod_id:
                messagebox.showerror("Erreur", "Produit invalide")
                return
            dispo = sm.get(nom_prod, 0)
            if qte > dispo:
                messagebox.showerror("Stock insuffisant", f"Stock disponible : {dispo} paires")
                return
            tenant_id = tnt_map.get(tnt_var.get()) if self.is_admin else self.current_tenant_id
            resp_login = resp_entry.get().strip()
            resp_id = self.current_user_id
            for u in all_users:
                if u[1] == resp_login:
                    resp_id = u[0]
                    break
            code = code_entry.get().strip()

            self.cursor.execute("INSERT INTO stock (tenant_id, product_id, mouvement, quantite, marque, code_produit, user_id) VALUES (?,?,?,?,?,?,?)",
                                (tenant_id, prod_id, "sortie", qte, "", code, resp_id))
            self.cursor.execute("UPDATE produits SET stock=stock-? WHERE id=?", (qte, prod_id))
            self.conn.commit()
            log_action(self.cursor, self.conn, self.current_user_id, self.current_user_login, tenant_id, "stock_sortie",
                       f"-{qte} {nom_prod} (resp: {resp_login})")
            messagebox.showinfo("Succes", f"Sortie enregistree : -{qte} paires (Resp: {resp_login})")
            d.destroy()
            self.page_stock()

        ctk.CTkButton(d, text="Valider la sortie", width=200, height=36,
                      fg_color=ACCENT_RED, hover_color="#e74c3c", text_color="#000",
                      font=(FONT_FAMILY, 12, "bold"),
                      command=valider).pack(pady=16)

    # ========================= VENTES =========================
    def page_ventes(self):
        for w in self.content.winfo_children():
            w.destroy()
        self.cart_items = []
        self.is_honneur = False

        ctk.CTkLabel(self.content, text="\U0001f4b8  Nouvelle Vente",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(pady=(10, 5), anchor="w", padx=15)

        info_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        info_frame.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(info_frame, text="Nom :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).grid(row=0, column=0, padx=6, pady=6)
        self.entry_client_nom = ctk.CTkEntry(info_frame, width=180, height=32, placeholder_text="Nom client",
                                              fg_color=DARK_CARD, border_color=GOLD_DARK)
        self.entry_client_nom.grid(row=0, column=1, padx=6, pady=6)

        ctk.CTkLabel(info_frame, text="Tel :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).grid(row=0, column=2, padx=6, pady=6)
        self.entry_client_tel = ctk.CTkEntry(info_frame, width=140, height=32, placeholder_text="08...",
                                              fg_color=DARK_CARD, border_color=GOLD_DARK)
        self.entry_client_tel.grid(row=0, column=3, padx=6, pady=6)

        self.btn_honneur = ctk.CTkButton(info_frame, text="\u2b50 Client d'honneur",
                                          width=150, height=32, fg_color=DARK_CARD,
                                          border_color=HONOR_COLOR, border_width=2,
                                          text_color=HONOR_COLOR, hover_color="#2a1040",
                                          command=self.toggle_honneur)
        self.btn_honneur.grid(row=0, column=4, padx=8, pady=6)

        add_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        add_frame.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(add_frame, text="Produit :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).grid(row=0, column=0, padx=6, pady=6)

        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"SELECT id, nom, prix_usd, stock FROM produits WHERE stock > 0{cond} ORDER BY nom", params)
        prods = self.cursor.fetchall()
        self.prod_map = {}
        for p in prods:
            pid, pnom, def_usd, stk = p
            t_usd, t_cdf = get_produit_prix(self.cursor, pid, self.current_tenant_id, self.taux_cdf)
            self.prod_map[pnom] = (pid, t_usd, stk)
        self.combo_prod = ctk.CTkOptionMenu(add_frame, values=list(self.prod_map.keys()) or ["Aucun"],
                                             width=240, height=32, fg_color=DARK_CARD,
                                             button_color=GOLD_DARK,
                                             command=self.calculer_prix_unitaire)
        self.combo_prod.grid(row=0, column=1, padx=6, pady=6)

        ctk.CTkLabel(add_frame, text="Qte :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).grid(row=0, column=2, padx=6, pady=6)
        self.entry_qte = ctk.CTkEntry(add_frame, width=55, height=32, placeholder_text="1",
                                       fg_color=DARK_CARD, border_color=GOLD_DARK)
        self.entry_qte.grid(row=0, column=3, padx=6, pady=6)
        self.entry_qte.insert(0, "1")

        ctk.CTkLabel(add_frame, text="Prix unit. :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).grid(row=0, column=4, padx=6, pady=6)
        self.entry_prix_custom = ctk.CTkEntry(add_frame, width=75, height=32, placeholder_text="USD",
                                               fg_color=DARK_CARD, border_color=HONOR_COLOR)
        self.entry_prix_custom.grid(row=0, column=5, padx=6, pady=6)
        self.entry_prix_custom.configure(state="disabled")

        self.lbl_calcul = ctk.CTkLabel(add_frame, text="= $0 / 0 CDF",
                                        font=(FONT_FAMILY, 12, "bold"), text_color=GOLD_LIGHT)
        self.lbl_calcul.grid(row=0, column=6, padx=8, pady=6)

        ctk.CTkButton(add_frame, text="+ Ajouter", width=90, height=32,
                      fg_color=ACCENT_GREEN, hover_color="#27ae60", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.ajouter_au_panier).grid(row=0, column=7, padx=6, pady=6)

        cart_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        cart_frame.pack(fill="both", expand=True, padx=15, pady=3)

        hdr = ctk.CTkFrame(cart_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(hdr, text="\U0001f6d2 Panier", font=(FONT_FAMILY, 13, "bold"), text_color=GOLD).pack(side="left")
        self.lbl_nb_articles = ctk.CTkLabel(hdr, text="0 articles", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY)
        self.lbl_nb_articles.pack(side="left", padx=8)
        self.lbl_total_general = ctk.CTkLabel(hdr, text="TOTAL: $0 / 0 CDF",
                                               font=(FONT_FAMILY, 13, "bold"), text_color=GOLD_LIGHT)
        self.lbl_total_general.pack(side="right")

        from tkinter import ttk
        self.style_cart = ttk.Style()
        self.style_cart.configure("Cart.Treeview", background=DARK_CARD, foreground="white",
                                  fieldbackground=DARK_CARD, rowheight=26, font=(FONT_FAMILY, 10))
        self.style_cart.configure("Cart.Treeview.Heading", background=GOLD_DARK, foreground="#000",
                                  font=(FONT_FAMILY, 10, "bold"))

        cols = ("#", "Produit", "Qte", "Prix U.", "Total USD", "Total CDF")
        self.tree_cart = ttk.Treeview(cart_frame, columns=cols, show="headings",
                                      style="Cart.Treeview", selectmode="browse")
        for c in cols:
            self.tree_cart.heading(c, text=c)
        self.tree_cart.column("#", width=28, anchor="center")
        self.tree_cart.column("Produit", width=200)
        self.tree_cart.column("Qte", width=42, anchor="center")
        self.tree_cart.column("Prix U.", width=75, anchor="center")
        self.tree_cart.column("Total USD", width=80, anchor="center")
        self.tree_cart.column("Total CDF", width=90, anchor="center")
        self.tree_cart.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        bf = ctk.CTkFrame(cart_frame, fg_color="transparent")
        bf.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(bf, text="\U0001f5d1 Supprimer", width=110, height=30,
                      fg_color="#e63946", hover_color="#c1121f",
                      command=self.supprimer_du_panier).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="\U0001f504 Vider", width=90, height=30,
                      fg_color=DARK_CARD, command=self.vider_panier).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="\U0001f4b8  VALIDER LA VENTE", width=190, height=34,
                      fg_color=ACCENT_GREEN, hover_color="#27ae60", text_color="#000",
                      font=(FONT_FAMILY, 13, "bold"),
                      command=self.valider_vente).pack(side="right", padx=4)

        self.combo_prod.configure(command=self.calculer_prix_unitaire)
        self.entry_qte.bind("<KeyRelease>", lambda e: self.calculer_prix_unitaire())

    def toggle_honneur(self):
        self.is_honneur = not self.is_honneur
        if self.is_honneur:
            self.btn_honneur.configure(fg_color=HONOR_COLOR, text_color="#fff", text="\u2b50 HONNEUR ACTIF")
            self.entry_prix_custom.configure(state="normal")
            self.entry_prix_custom.delete(0, "end")
        else:
            self.btn_honneur.configure(fg_color=DARK_CARD, text_color=HONOR_COLOR, text="\u2b50 Client d'honneur")
            self.entry_prix_custom.configure(state="disabled")
        self.calculer_prix_unitaire()

    def calculer_prix_unitaire(self, event=None):
        try:
            nom = self.combo_prod.get()
            if nom not in self.prod_map:
                return
            pid, def_usd, stock = self.prod_map[nom]
            qte = int(self.entry_qte.get() or 1)
            unit_usd = float(self.entry_prix_custom.get()) if (self.is_honneur and self.entry_prix_custom.get().strip()) else def_usd
            unit_cdf = unit_usd * self.taux_cdf
            self.lbl_calcul.configure(text=f"= ${unit_usd * qte:,.2f} / {unit_cdf * qte:,.0f} CDF  (stk:{stock})")
        except Exception:
            pass

    def ajouter_au_panier(self):
        try:
            nom = self.combo_prod.get()
            if nom not in self.prod_map:
                return
            pid, def_usd, stock = self.prod_map[nom]
            qte = int(self.entry_qte.get())
            if qte <= 0:
                raise ValueError
            unit_usd = float(self.entry_prix_custom.get()) if (self.is_honneur and self.entry_prix_custom.get().strip()) else def_usd
            qte_deja = sum(item["qte"] for item in self.cart_items if item["pid"] == pid)
            if qte_deja + qte > stock:
                messagebox.showwarning("Stock", f"Stock restant: {stock - qte_deja}")
                return
            unit_cdf = unit_usd * self.taux_cdf
            self.cart_items.append({
                "pid": pid, "nom": nom, "qte": qte,
                "unit_usd": unit_usd, "unit_cdf": unit_cdf,
                "total_usd": unit_usd * qte, "total_cdf": unit_cdf * qte,
                "honneur": self.is_honneur
            })
            self.refresh_cart()
            self.entry_qte.delete(0, "end")
            self.entry_qte.insert(0, "1")
            self.entry_prix_custom.delete(0, "end")
            self.calculer_prix_unitaire()
        except ValueError:
            messagebox.showwarning("Attention", "Quantite invalide.")

    def refresh_cart(self):
        for row in self.tree_cart.get_children():
            self.tree_cart.delete(row)
        t_usd = t_cdf = 0
        for i, item in enumerate(self.cart_items):
            hon = " \u2b50" if item["honneur"] else ""
            self.tree_cart.insert("", "end", values=(
                i + 1, item["nom"] + hon, item["qte"],
                f"${item['unit_usd']:.2f}", f"${item['total_usd']:,.2f}", f"{item['total_cdf']:,.0f}"))
            t_usd += item["total_usd"]
            t_cdf += item["total_cdf"]
        self.lbl_nb_articles.configure(text=f"{len(self.cart_items)} articles")
        self.lbl_total_general.configure(text=f"TOTAL: ${t_usd:,.2f} / {t_cdf:,.0f} CDF")

    def supprimer_du_panier(self):
        sel = self.tree_cart.selection()
        if not sel:
            return
        idx = self.tree_cart.index(sel[0])
        if 0 <= idx < len(self.cart_items):
            self.cart_items.pop(idx)
        self.refresh_cart()

    def vider_panier(self):
        self.cart_items = []
        self.refresh_cart()

    def valider_vente(self):
        if not self.cart_items:
            messagebox.showwarning("Attention", "Panier vide.")
            return

        client_nom = self.entry_client_nom.get().strip() or "Anonyme"
        client_tel = self.entry_client_tel.get().strip() or "-"
        today = date.today().isoformat()
        heure = datetime.now().strftime("%H:%M")
        tid = self.current_tenant_id
        recu_num = get_next_recu_num(self.cursor, tid)

        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (tid,)

        self.cursor.execute(f"SELECT id FROM clients WHERE telephone=?{cond}", (client_tel,) + params)
        row = self.cursor.fetchone()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        total_usd_cart = sum(it["total_usd"] for it in self.cart_items)
        total_cdf_cart = sum(it["total_cdf"] for it in self.cart_items)

        if row:
            client_id = row[0]
            self.cursor.execute(f"""UPDATE clients SET nb_visites=nb_visites+1,
                total_usd=total_usd+(?), total_cdf=total_cdf+(?),
                derniere_visite=? WHERE id=?{cond}""",
                (total_usd_cart, total_cdf_cart, now_str, client_id) + params)
        else:
            self.cursor.execute(f"""INSERT INTO clients
                (nom, telephone, nb_visites, total_usd, total_cdf, premier_visite, derniere_visite, tenant_id)
                VALUES (?, ?, 1, ?, ?, ?, ?, ?)""",
                (client_nom, client_tel, total_usd_cart, total_cdf_cart, now_str, now_str, tid))
            client_id = self.cursor.lastrowid

        total_usd = sum(it["total_usd"] for it in self.cart_items)
        total_cdf = sum(it["total_cdf"] for it in self.cart_items)
        any_honneur = any(it["honneur"] for it in self.cart_items)

        for item in self.cart_items:
            self.cursor.execute("""INSERT INTO ventes
                (recu_num, client_id, produit_id, quantite,
                 prix_unit_usd, prix_unit_cdf, total_usd, total_cdf,
                 est_client_honneur, date, heure, tenant_id, vendeur_login)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (recu_num, client_id, item["pid"], item["qte"],
                 item["unit_usd"], item["unit_cdf"], item["total_usd"], item["total_cdf"],
                 1 if item["honneur"] else 0, today, heure, tid, self.current_user_login))
            self.cursor.execute("UPDATE produits SET stock=stock-? WHERE id=?", (item["qte"], item["pid"]))

        self.cursor.execute("""INSERT INTO recus
            (numero, client_id, total_usd, total_cdf, est_honneur, date, heure, tenant_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (recu_num, client_id, total_usd, total_cdf, 1 if any_honneur else 0, today, heure, tid))
        self.conn.commit()

        log_action(self.cursor, self.conn, self.current_user_id, self.current_user_login,
                   tid, "Vente", f"Recu {recu_num} - ${total_usd:,.2f} - {len(self.cart_items)} articles")

        add_notification(self.cursor, self.conn, tid,
            f"Nouvelle vente: {recu_num} - ${total_usd:,.2f} USD - {len(self.cart_items)} articles - Par {self.current_user_login}")

        self.afficher_recu(recu_num, client_nom, client_tel, today, heure,
                           total_usd, total_cdf, any_honneur)

        self.cart_items = []
        self.entry_client_nom.delete(0, "end")
        self.entry_client_tel.delete(0, "end")
        self.is_honneur = False
        self.btn_honneur.configure(fg_color=DARK_CARD, text_color=HONOR_COLOR, text="\u2b50 Client d'honneur")
        self.entry_prix_custom.configure(state="disabled")
        self.refresh_cart()
        self.refresh_prod_list()

    def refresh_prod_list(self):
        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"SELECT id, nom, prix_usd, stock FROM produits WHERE stock > 0{cond} ORDER BY nom", params)
        prods = self.cursor.fetchall()
        self.prod_map = {}
        for p in prods:
            pid, pnom, def_usd, stk = p
            t_usd, t_cdf = get_produit_prix(self.cursor, pid, self.current_tenant_id, self.taux_cdf)
            self.prod_map[pnom] = (pid, t_usd, stk)
        self.combo_prod.configure(values=list(self.prod_map.keys()) or ["Aucun"])

    # ========================= RECUS =========================
    def afficher_recu(self, num, nom, tel, date_str, heure, usd, cdf, honneur):
        recu_data = {
            "num": num, "nom": nom, "tel": tel, "date": date_str,
            "heure": heure, "usd": usd, "cdf": cdf, "honneur": honneur,
            "items": list(self.cart_items), "taux": self.taux_cdf
        }

        win = ctk.CTkToplevel(self)
        win.title(f"Recu {num}")
        win.geometry("420x600")
        win.configure(fg_color="#0d0221")
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="\U0001f45f BAGUMA MARKET", font=(FONT_FAMILY, 17, "bold"),
                     text_color=GOLD_LIGHT).pack(pady=(12, 3))
        ctk.CTkLabel(win, text=f"RECET {num}", font=(FONT_FAMILY, 20, "bold"),
                     text_color=ACCENT_GREEN).pack(pady=(0, 8))

        ctk.CTkFrame(win, fg_color=GOLD_DARK, height=2).pack(fill="x", padx=18, pady=4)

        info = ctk.CTkFrame(win, fg_color="transparent")
        info.pack(fill="x", padx=18)
        ctk.CTkLabel(info, text=f"Date: {date_str}  Heure: {heure}", font=(FONT_FAMILY, 10), text_color=TEXT_GRAY).pack(anchor="w")
        ctk.CTkLabel(info, text=f"Client: {nom}", font=(FONT_FAMILY, 11, "bold"), text_color=TEXT_WHITE).pack(anchor="w")
        ctk.CTkLabel(info, text=f"Tel: {tel}", font=(FONT_FAMILY, 10), text_color=TEXT_GRAY).pack(anchor="w")

        if honneur:
            ctk.CTkLabel(win, text="\u2b50 CLIENT D'HONNEUR \u2b50",
                         font=(FONT_FAMILY, 13, "bold"), text_color=HONOR_COLOR).pack(pady=6)

        ctk.CTkFrame(win, fg_color=GOLD_DARK, height=2).pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(win, text="Articles :", font=(FONT_FAMILY, 11, "bold"),
                     text_color=GOLD).pack(anchor="w", padx=18, pady=(3, 1))

        for item in recu_data["items"]:
            hon = " \u2b50" if item["honneur"] else ""
            txt = f"  {item['nom']}{hon}  x{item['qte']}  ${item['unit_usd']:.2f}/u  =  ${item['total_usd']:,.2f}  /  {item['total_cdf']:,.0f} CDF"
            ctk.CTkLabel(win, text=txt, font=(FONT_FAMILY, 9), text_color="#ccccee", anchor="w").pack(fill="x", padx=18)

        ctk.CTkFrame(win, fg_color=GOLD_DARK, height=2).pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(win, text=f"TOTAL: ${usd:,.2f} USD  /  {cdf:,.0f} CDF",
                     font=(FONT_FAMILY, 15, "bold"), text_color=GOLD_LIGHT).pack(pady=(3, 4))
        ctk.CTkLabel(win, text="Merci pour votre achat !", font=(FONT_FAMILY, 10), text_color=TEXT_GRAY).pack()
        ctk.CTkLabel(win, text=f"Taux: 1 USD = {self.taux_cdf:,.0f} CDF",
                     font=(FONT_FAMILY, 9), text_color="#555577").pack(pady=(0, 6))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=4)
        ctk.CTkButton(btn_row, text="\U0001f5a8 Imprimer", width=110, height=32,
                      fg_color=ACCENT_BLUE, hover_color="#0090b0", text_color="#000",
                      command=lambda: self.imprimer_recu(recu_data)).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="\U0001f4be Exporter", width=110, height=32,
                      fg_color=GOLD_DARK, text_color="#000",
                      command=lambda: self.sauvegarder_recu(recu_data)).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Fermer", width=90, height=32,
                      fg_color=DARK_CARD, text_color="#ccccee",
                      command=win.destroy).pack(side="left", padx=4)

    def generer_texte_recu(self, data):
        lines = [
            "=" * 44,
            "          BAGUMA MARKET",
            "      Gestion de Commerce",
            "=" * 44,
            f"  Recu {data['num']}",
            f"  Date: {data['date']}  Heure: {data['heure']}",
            "-" * 44,
            f"  Client: {data['nom']}",
            f"  Tel: {data['tel']}",
        ]
        if data["honneur"]:
            lines += ["", "  *** CLIENT D'HONNEUR ***"]
        lines += ["-" * 44, "  ARTICLES:", "-" * 44]
        for item in data["items"]:
            hon = " *" if item["honneur"] else ""
            lines += [
                f"  {item['nom']}{hon}",
                f"    Qte: {item['qte']}  x  ${item['unit_usd']:.2f}/u",
                f"    Total: ${item['total_usd']:,.2f} / {item['total_cdf']:,.0f} CDF", ""
            ]
        lines += [
            "=" * 44,
            f"  TOTAL: ${data['usd']:,.2f} USD / {data['cdf']:,.0f} CDF",
            f"  Taux: 1 USD = {data['taux']:,.0f} CDF",
            "=" * 44,
            "        Merci pour votre achat !",
            "=" * 44,
        ]
        return "\n".join(lines)

    def sauvegarder_recu(self, data):
        try:
            dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recus")
            os.makedirs(dossier, exist_ok=True)
            fname = os.path.join(dossier, f"Recu_{data['num'].replace(chr(176), '')}.txt")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(self.generer_texte_recu(data))
            messagebox.showinfo("Sauvegarde", f"Recu sauvegarde:\n{fname}")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def imprimer_recu(self, data):
        try:
            dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recus")
            os.makedirs(dossier, exist_ok=True)
            fname = os.path.join(dossier, f"Recu_{data['num'].replace(chr(176), '')}.txt")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(self.generer_texte_recu(data))
            os.startfile(fname, "print")
        except Exception as e:
            messagebox.showwarning("Impression", f"Impression non dispo.\nFichier sauvegarde.\n{e}")

    # ========================= HISTORIQUE RECUS =========================
    def page_recus(self):
        for w in self.content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.content, text="\U0001f4c4  Historique des Recus",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(pady=(12, 8), anchor="w", padx=18)

        tree_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        tree_frame.pack(fill="both", expand=True, padx=18, pady=(5, 10))

        from tkinter import ttk
        s = ttk.Style(); s.configure("R.Treeview", background=DARK_CARD, foreground="white",
                                      fieldbackground=DARK_CARD, rowheight=28, font=(FONT_FAMILY, 10))
        s.configure("R.Treeview.Heading", background=GOLD_DARK, foreground="#000", font=(FONT_FAMILY, 10, "bold"))

        cols = ("Num", "Client", "Tel", "Total USD", "Total CDF", "Honneur", "Date", "Heure")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="R.Treeview")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Num", width=70, anchor="center")
        tree.column("Client", width=130)
        tree.column("Tel", width=100)
        tree.column("Total USD", width=85, anchor="center")
        tree.column("Total CDF", width=95, anchor="center")
        tree.column("Honneur", width=60, anchor="center")
        tree.column("Date", width=85, anchor="center")
        tree.column("Heure", width=55, anchor="center")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        cond = "" if self.is_admin else " AND r.tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"""SELECT r.numero, cl.nom, cl.telephone, r.total_usd, r.total_cdf,
            r.est_honneur, r.date, r.heure FROM recus r
            LEFT JOIN clients cl ON r.client_id=cl.id
            WHERE 1=1{cond} ORDER BY r.id DESC LIMIT 100""", params)
        for r in self.cursor.fetchall():
            hon = "\u2b50" if r[5] else ""
            tree.insert("", "end", values=(r[0], r[1] or "Anonyme", r[2] or "-",
                         f"${r[3]:,.2f}", f"{r[4]:,.0f}", hon, r[6], r[7]))

    # ========================= CLIENTS =========================
    def page_clients(self):
        for w in self.content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.content, text="\U0001f464  Gestion des Clients",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(pady=(12, 8), anchor="w", padx=18)

        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=4)
        self.search_client = ctk.StringVar()
        ctk.CTkEntry(top, textvariable=self.search_client, placeholder_text="Rechercher client...",
                     width=280, height=34, fg_color=DARK_CARD, border_color=GOLD_DARK).pack(side="left")
        ctk.CTkButton(top, text="Chercher", width=90, height=34, fg_color=GOLD_DARK,
                      text_color="#000", command=self.afficher_clients).pack(side="left", padx=5)

        tree_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        tree_frame.pack(fill="both", expand=True, padx=18, pady=(5, 10))

        from tkinter import ttk
        s = ttk.Style(); s.configure("C.Treeview", background=DARK_CARD, foreground="white",
                                      fieldbackground=DARK_CARD, rowheight=28, font=(FONT_FAMILY, 10))
        s.configure("C.Treeview.Heading", background=GOLD_DARK, foreground="#000", font=(FONT_FAMILY, 10, "bold"))

        cols = ("ID", "Nom", "Telephone", "Visites", "Total USD", "Total CDF", "1ere visite", "Derniere visite")
        self.tree_clients = ttk.Treeview(tree_frame, columns=cols, show="headings", style="C.Treeview")
        for c in cols:
            self.tree_clients.heading(c, text=c)
        self.tree_clients.column("ID", width=35, anchor="center")
        self.tree_clients.column("Nom", width=150)
        self.tree_clients.column("Telephone", width=100)
        self.tree_clients.column("Visites", width=55, anchor="center")
        self.tree_clients.column("Total USD", width=85, anchor="center")
        self.tree_clients.column("Total CDF", width=95, anchor="center")
        self.tree_clients.column("1ere visite", width=110, anchor="center")
        self.tree_clients.column("Derniere visite", width=110, anchor="center")
        self.tree_clients.pack(fill="both", expand=True, padx=8, pady=8)
        self.afficher_clients()

    def afficher_clients(self):
        for row in self.tree_clients.get_children():
            self.tree_clients.delete(row)
        term = self.search_client.get().strip() if hasattr(self, "search_client") else ""
        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)

        if term:
            self.cursor.execute(f"""SELECT id, nom, telephone, nb_visites, total_usd, total_cdf,
                premier_visite, derniere_visite FROM clients
                WHERE (nom LIKE ? OR telephone LIKE ?){cond} ORDER BY nom""",
                (f"%{term}%", f"%{term}%") + params)
        else:
            self.cursor.execute(f"""SELECT id, nom, telephone, nb_visites, total_usd, total_cdf,
                premier_visite, derniere_visite FROM clients
                WHERE 1=1{cond} ORDER BY nom""", params)
        for r in self.cursor.fetchall():
            self.tree_clients.insert("", "end", values=(
                r[0], r[1], r[2], r[3], f"${r[4]:,.2f}", f"{r[5]:,.0f}", r[6] or "-", r[7] or "-"))

    # ========================= HONNEUR =========================
    def page_honneur(self):
        for w in self.content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.content, text="\u2b50  Clients d'Honneur",
                     font=(FONT_FAMILY, 20, "bold"), text_color=HONOR_COLOR).pack(pady=(12, 8), anchor="w", padx=18)

        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=4)

        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)

        self.cursor.execute(f"SELECT COUNT(*) FROM ventes WHERE est_client_honneur=1{cond}", params)
        nb = self.cursor.fetchone()[0]
        self.cursor.execute(f"SELECT COALESCE(SUM(total_usd),0), COALESCE(SUM(total_cdf),0) FROM ventes WHERE est_client_honneur=1{cond}", params)
        tot = self.cursor.fetchone()

        cards = ctk.CTkFrame(top, fg_color="transparent")
        cards.pack(fill="x")
        for i, (lbl, val, col) in enumerate([
            ("Total ventes honneur", str(nb), HONOR_COLOR),
            ("Total USD honneur", f"${tot[0]:,.2f}", GOLD_LIGHT),
            ("Total CDF honneur", f"{tot[1]:,.0f} CDF", "#f4a261"),
        ]):
            card = ctk.CTkFrame(cards, fg_color=CARD_BG, corner_radius=9, height=70)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            cards.columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=lbl, font=(FONT_FAMILY, 10), text_color=TEXT_GRAY).pack(pady=(8, 0))
            ctk.CTkLabel(card, text=val, font=(FONT_FAMILY, 16, "bold"), text_color=col).pack(pady=(2, 6))

        tree_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        tree_frame.pack(fill="both", expand=True, padx=18, pady=(5, 10))

        from tkinter import ttk
        s = ttk.Style(); s.configure("H.Treeview", background=DARK_CARD, foreground="white",
                                      fieldbackground=DARK_CARD, rowheight=28, font=(FONT_FAMILY, 10))
        s.configure("H.Treeview.Heading", background=HONOR_COLOR, foreground="white", font=(FONT_FAMILY, 10, "bold"))

        cols = ("Recu", "Client", "Tel", "Total USD", "Total CDF", "Date", "Heure")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="H.Treeview")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Recu", width=70, anchor="center")
        tree.column("Client", width=150)
        tree.column("Tel", width=100)
        tree.column("Total USD", width=90, anchor="center")
        tree.column("Total CDF", width=100, anchor="center")
        tree.column("Date", width=85, anchor="center")
        tree.column("Heure", width=55, anchor="center")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.cursor.execute(f"""SELECT r.numero, cl.nom, cl.telephone, r.total_usd, r.total_cdf, r.date, r.heure
            FROM recus r LEFT JOIN clients cl ON r.client_id=cl.id
            WHERE r.est_honneur=1{cond} ORDER BY r.id DESC LIMIT 100""", params)
        for r in self.cursor.fetchall():
            tree.insert("", "end", values=(
                r[0], r[1] or "Anonyme", r[2] or "-",
                f"${r[3]:,.2f}", f"{r[4]:,.0f}", r[5], r[6]))

    # ========================= RAPPORTS =========================
    def page_rapports(self):
        for w in self.content.winfo_children():
            w.destroy()

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(12, 6))
        ctk.CTkLabel(header, text="\U0001f4c8  Rapports",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(side="left")
        ctk.CTkButton(header, text="\U0001f5a8 Imprimer", width=110, height=30,
                      fg_color=ACCENT_BLUE, hover_color="#0090b0", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.imprimer_rapport).pack(side="right", padx=3)
        ctk.CTkButton(header, text="\U0001f4e4 Exporter CSV", width=130, height=30,
                      fg_color=ACCENT_GREEN, hover_color="#00a884", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.exporter_rapport_csv).pack(side="right", padx=3)

        date_bar = ctk.CTkFrame(self.content, fg_color="transparent")
        date_bar.pack(fill="x", padx=18, pady=4)

        if self.is_admin:
            ctk.CTkLabel(date_bar, text="Tenant :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
            self.cursor.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
            t_opts = ["Tous"] + [f"{t[0]} - {t[1]}" for t in self.cursor.fetchall()]
            self.filtre_rap_tenant = ctk.StringVar(value="Tous")
            ctk.CTkOptionMenu(date_bar, variable=self.filtre_rap_tenant, values=t_opts,
                              width=160, height=32, fg_color=DARK_CARD,
                              command=lambda e: self.generer_rapport()).pack(side="left", padx=6)

        ctk.CTkLabel(date_bar, text="Date :", font=(FONT_FAMILY, 12), text_color=TEXT_GRAY).pack(side="left")
        self.entry_date_rap = ctk.CTkEntry(date_bar, width=130, height=32,
                                            fg_color=DARK_CARD, border_color=GOLD_DARK)
        self.entry_date_rap.insert(0, date.today().isoformat())
        self.entry_date_rap.pack(side="left", padx=6)

        ctk.CTkButton(date_bar, text="Generer", width=80, height=32, fg_color=GOLD_DARK,
                      text_color="#000", command=self.generer_rapport).pack(side="left", padx=3)
        ctk.CTkButton(date_bar, text="Auj.", width=45, height=32, fg_color=DARK_CARD,
                      command=lambda: self._set_rap_date(date.today().isoformat())).pack(side="left", padx=2)
        ctk.CTkButton(date_bar, text="Hier", width=45, height=32, fg_color=DARK_CARD,
                      command=lambda: self._set_rap_date((date.today() - timedelta(days=1)).isoformat())).pack(side="left", padx=2)
        ctk.CTkButton(date_bar, text="7 jours", width=55, height=32, fg_color=DARK_CARD,
                      command=self.rapport_7jours).pack(side="left", padx=2)

        range_bar = ctk.CTkFrame(self.content, fg_color="transparent")
        range_bar.pack(fill="x", padx=18, pady=2)
        ctk.CTkLabel(range_bar, text="Periode :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        self.entry_date_from = ctk.CTkEntry(range_bar, width=110, height=28, placeholder_text="AAAA-MM-JJ",
                                             fg_color=DARK_CARD, border_color=GOLD_DARK, font=(FONT_FAMILY, 10))
        self.entry_date_from.pack(side="left", padx=5)
        ctk.CTkLabel(range_bar, text="a", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        self.entry_date_to = ctk.CTkEntry(range_bar, width=110, height=28, placeholder_text="AAAA-MM-JJ",
                                           fg_color=DARK_CARD, border_color=GOLD_DARK, font=(FONT_FAMILY, 10))
        self.entry_date_to.pack(side="left", padx=5)
        ctk.CTkButton(range_bar, text="Voir periode", width=90, height=28, fg_color=ACCENT_BLUE,
                      text_color="#000", command=self.rapport_periode).pack(side="left", padx=5)

        stats_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        stats_frame.pack(fill="x", padx=18, pady=4)

        self.r_stats = {}
        stat_labels = [
            ("usd", "\U0001f4b0 Total USD", "$0.00", GOLD_LIGHT),
            ("cdf", "\U0001f4b0 Total CDF", "0 CDF", "#fdcb6e"),
            ("clients", "\U0001f4c5 Clients", "0", ACCENT_GREEN),
            ("recus", "\U0001f4c4 Recus", "0", ACCENT_BLUE),
            ("stock", "\U0001f4e6 Stock", "0", GOLD),
            ("honneur", "\u2b50 Honneur", "0", HONOR_COLOR),
        ]
        for i, (key, lbl, val, col) in enumerate(stat_labels):
            card = ctk.CTkFrame(stats_frame, fg_color=CARD_BG, corner_radius=8, height=65)
            card.grid(row=0, column=i, padx=3, sticky="nsew")
            stats_frame.columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=lbl, font=(FONT_FAMILY, 9), text_color=TEXT_GRAY).pack(pady=(6, 0))
            lbl_widget = ctk.CTkLabel(card, text=val, font=(FONT_FAMILY, 14, "bold"), text_color=col)
            lbl_widget.pack(pady=(1, 5))
            self.r_stats[key] = lbl_widget

        middle = ctk.CTkFrame(self.content, fg_color="transparent")
        middle.pack(fill="both", expand=True, padx=18, pady=(4, 6))

        tree_frame = ctk.CTkFrame(middle, fg_color=CARD_BG, corner_radius=9)
        tree_frame.pack(side="left", fill="both", expand=True)

        from tkinter import ttk
        s = ttk.Style(); s.configure("Rp.Treeview", background=DARK_CARD, foreground="white",
                                      fieldbackground=DARK_CARD, rowheight=26, font=(FONT_FAMILY, 10))
        s.configure("Rp.Treeview.Heading", background=GOLD_DARK, foreground="#000", font=(FONT_FAMILY, 10, "bold"))

        cols = ("Produit", "Qte", "Prix U. USD", "Total USD", "Total CDF")
        self.tree_r = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Rp.Treeview")
        for c in cols:
            self.tree_r.heading(c, text=c)
        self.tree_r.column("Produit", width=200)
        self.tree_r.column("Qte", width=55, anchor="center")
        self.tree_r.column("Prix U. USD", width=85, anchor="center")
        self.tree_r.column("Total USD", width=95, anchor="center")
        self.tree_r.column("Total CDF", width=100, anchor="center")
        self.tree_r.pack(fill="both", expand=True, padx=6, pady=6)

        comp_frame = ctk.CTkFrame(middle, fg_color=CARD_BG, corner_radius=9, width=260)
        comp_frame.pack(side="left", fill="y", padx=(6, 0))
        comp_frame.pack_propagate(False)

        ctk.CTkLabel(comp_frame, text="\U0001f4ca Comparaison",
                     font=(FONT_FAMILY, 12, "bold"), text_color=GOLD).pack(anchor="w", padx=10, pady=(10, 4))

        self.comp_label_hier = ctk.CTkLabel(comp_frame, text="", font=(FONT_FAMILY, 10),
                                            text_color=TEXT_GRAY, anchor="w", justify="left")
        self.comp_label_hier.pack(fill="x", padx=10, pady=2)

        ctk.CTkFrame(comp_frame, fg_color=GOLD_DARK, height=1).pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(comp_frame, text="\u26a0 Stock faible",
                     font=(FONT_FAMILY, 11, "bold"), text_color=ACCENT_RED).pack(anchor="w", padx=10, pady=(4, 4))

        self.stock_low_frame = ctk.CTkFrame(comp_frame, fg_color="transparent")
        self.stock_low_frame.pack(fill="both", expand=True, padx=10)

        self.generer_rapport()

    def _set_rap_date(self, d):
        self.entry_date_rap.delete(0, "end")
        self.entry_date_rap.insert(0, d)
        self.generer_rapport()

    def generer_rapport(self):
        d = self.entry_date_rap.get().strip()
        if not d:
            return

        for row in self.tree_r.get_children():
            self.tree_r.delete(row)

        tenant_cond = ""
        tenant_params = ()
        if self.is_admin and hasattr(self, 'filtre_rap_tenant'):
            ft = self.filtre_rap_tenant.get()
            if ft != "Tous":
                tid = int(ft.split(" - ")[0])
                tenant_cond = " AND v.tenant_id=?"
                tenant_params = (tid,)
            else:
                tenant_cond = ""
                tenant_params = ()
        elif not self.is_admin:
            tenant_cond = " AND v.tenant_id=?"
            tenant_params = (self.current_tenant_id,)

        ventes_cond = tenant_cond.replace("v.", "")
        client_cond = tenant_cond.replace("v.", "cl.").replace("AND cl.tenant_id", "AND cl.tenant_id")

        self.cursor.execute(f"SELECT SUM(total_usd), SUM(total_cdf), COUNT(*) FROM ventes WHERE date=?{ventes_cond}",
                            (d,) + tenant_params)
        r = self.cursor.fetchone()
        tot_usd = r[0] or 0
        tot_cdf = r[1] or 0
        nb_ventes = r[2] or 0

        self.cursor.execute(f"SELECT COUNT(DISTINCT client_id) FROM ventes WHERE date=?{ventes_cond}",
                            (d,) + tenant_params)
        nb_clients = self.cursor.fetchone()[0]

        self.cursor.execute(f"SELECT COUNT(*) FROM recus WHERE date=?{ventes_cond}",
                            (d,) + tenant_params)
        nb_recus = self.cursor.fetchone()[0]

        self.cursor.execute(f"SELECT COUNT(*) FROM ventes WHERE est_client_honneur=1 AND date=?{ventes_cond}",
                            (d,) + tenant_params)
        nb_honneur = self.cursor.fetchone()[0]

        self.cursor.execute(f"SELECT COALESCE(SUM(stock),0) FROM produits WHERE 1=1{ventes_cond}", tenant_params)
        stock = self.cursor.fetchone()[0]

        self.r_stats["usd"].configure(text=f"${tot_usd:,.2f}")
        self.r_stats["cdf"].configure(text=f"{tot_cdf:,.0f} CDF")
        self.r_stats["clients"].configure(text=str(nb_clients))
        self.r_stats["recus"].configure(text=str(nb_recus))
        self.r_stats["stock"].configure(text=str(stock))
        self.r_stats["honneur"].configure(text=str(nb_honneur))

        self.cursor.execute(f"""SELECT p.nom, SUM(v.quantite), p.prix_usd,
            SUM(v.total_usd), SUM(v.total_cdf)
            FROM ventes v JOIN produits p ON v.produit_id=p.id
            WHERE v.date=?{tenant_cond} GROUP BY v.produit_id ORDER BY SUM(v.total_usd) DESC""",
            (d,) + tenant_params)
        for row in self.cursor.fetchall():
            self.tree_r.insert("", "end", values=(
                row[0], row[1], f"${row[2]:.2f}", f"${row[3]:,.2f}", f"{row[4]:,.0f}"))

        hier = (date.today() - timedelta(days=1)).isoformat()
        self.cursor.execute(f"SELECT COALESCE(SUM(total_usd),0) FROM ventes WHERE date=?{ventes_cond}",
                            (hier,) + tenant_params)
        hier_usd = self.cursor.fetchone()[0]
        diff = tot_usd - hier_usd
        signe = "+" if diff >= 0 else ""
        color = ACCENT_GREEN if diff >= 0 else ACCENT_RED
        self.comp_label_hier.configure(
            text=f"Hier: ${hier_usd:,.2f}\nAuj: ${tot_usd:,.2f}\nDifference: {signe}${diff:,.2f}",
            text_color=color)

        for w in self.stock_low_frame.winfo_children():
            w.destroy()
        stock_cond = "" if self.is_admin else " AND tenant_id=?"
        stock_params = () if self.is_admin else (self.current_tenant_id,)
        if self.is_admin and hasattr(self, 'filtre_rap_tenant'):
            ft = self.filtre_rap_tenant.get()
            if ft != "Tous":
                tid = int(ft.split(" - ")[0])
                stock_cond = " AND tenant_id=?"
                stock_params = (tid,)
        self.cursor.execute(f"SELECT nom, stock FROM produits WHERE stock <= 5 AND stock > 0{stock_cond} ORDER BY stock ASC", stock_params)
        low = self.cursor.fetchall()
        if low:
            for nom, stk in low[:8]:
                ctk.CTkLabel(self.stock_low_frame, text=f"  {nom}: {stk}",
                             font=(FONT_FAMILY, 9), text_color=ACCENT_RED, anchor="w").pack(fill="x")
        else:
            ctk.CTkLabel(self.stock_low_frame, text="  Aucun alerte",
                         font=(FONT_FAMILY, 9), text_color=ACCENT_GREEN).pack(fill="x")

    def rapport_7jours(self):
        debut = (date.today() - timedelta(days=6)).isoformat()
        fin = date.today().isoformat()
        self._set_rap_date(debut)
        self.generer_rapport_periode(debut, fin)

    def rapport_periode(self):
        d_from = self.entry_date_from.get().strip()
        d_to = self.entry_date_to.get().strip()
        if not d_from or not d_to:
            messagebox.showwarning("Attention", "Entrez les deux dates.")
            return
        self.generer_rapport_periode(d_from, d_to)

    def generer_rapport_periode(self, d_from, d_to):
        for row in self.tree_r.get_children():
            self.tree_r.delete(row)

        tenant_cond = ""
        tenant_params = ()
        if self.is_admin and hasattr(self, 'filtre_rap_tenant'):
            ft = self.filtre_rap_tenant.get()
            if ft != "Tous":
                tid = int(ft.split(" - ")[0])
                tenant_cond = " AND v.tenant_id=?"
                tenant_params = (tid,)
        elif not self.is_admin:
            tenant_cond = " AND v.tenant_id=?"
            tenant_params = (self.current_tenant_id,)

        self.cursor.execute(f"""SELECT SUM(total_usd), SUM(total_cdf), COUNT(*) FROM ventes
            WHERE date BETWEEN ? AND ?{tenant_cond}""", (d_from, d_to) + tenant_params)
        r = self.cursor.fetchone()
        tot_usd = r[0] or 0
        tot_cdf = r[1] or 0
        nb_ventes = r[2] or 0

        self.cursor.execute(f"SELECT COUNT(DISTINCT client_id) FROM ventes WHERE date BETWEEN ? AND ?{tenant_cond}",
                            (d_from, d_to) + tenant_params)
        nb_clients = self.cursor.fetchone()[0]

        self.cursor.execute(f"SELECT COUNT(*) FROM recus WHERE date BETWEEN ? AND ?{tenant_cond}",
                            (d_from, d_to) + tenant_params)
        nb_recus = self.cursor.fetchone()[0]

        self.cursor.execute(f"SELECT COUNT(*) FROM ventes WHERE est_client_honneur=1 AND date BETWEEN ? AND ?{tenant_cond}",
                            (d_from, d_to) + tenant_params)
        nb_honneur = self.cursor.fetchone()[0]

        stock_cond = tenant_cond.replace("v.", "")
        self.cursor.execute(f"SELECT COALESCE(SUM(stock),0) FROM produits WHERE 1=1{stock_cond}", tenant_params)
        stock = self.cursor.fetchone()[0]

        self.r_stats["usd"].configure(text=f"${tot_usd:,.2f}")
        self.r_stats["cdf"].configure(text=f"{tot_cdf:,.0f} CDF")
        self.r_stats["clients"].configure(text=str(nb_clients))
        self.r_stats["recus"].configure(text=str(nb_recus))
        self.r_stats["stock"].configure(text=str(stock))
        self.r_stats["honneur"].configure(text=str(nb_honneur))

        self.cursor.execute(f"""SELECT p.nom, SUM(v.quantite), p.prix_usd,
            SUM(v.total_usd), SUM(v.total_cdf)
            FROM ventes v JOIN produits p ON v.produit_id=p.id
            WHERE v.date BETWEEN ? AND ?{tenant_cond} GROUP BY v.produit_id ORDER BY SUM(v.total_usd) DESC""",
            (d_from, d_to) + tenant_params)
        for row in self.cursor.fetchall():
            self.tree_r.insert("", "end", values=(
                row[0], row[1], f"${row[2]:.2f}", f"${row[3]:,.2f}", f"{row[4]:,.0f}"))

        self.comp_label_hier.configure(
            text=f"Periode: {d_from}\nau {d_to}\nTotal: ${tot_usd:,.2f}",
            text_color=GOLD_LIGHT)

    def imprimer_rapport(self):
        try:
            d = self.entry_date_rap.get().strip()
            lines = [
                "=" * 50,
                "           BAGUMA MARKET",
                "        RAPPORT JOURNALIER",
                "=" * 50,
                f"  Date: {d}",
                f"  Taux: 1 USD = {self.taux_cdf:,.0f} CDF",
                "-" * 50,
                "  RESUME:",
                f"  Total ventes USD: ${self.r_stats['usd'].cget('text')}",
                f"  Total ventes CDF: {self.r_stats['cdf'].cget('text')}",
                f"  Clients servis: {self.r_stats['clients'].cget('text')}",
                f"  Recus generes: {self.r_stats['recus'].cget('text')}",
                f"  Stock restant: {self.r_stats['stock'].cget('text')}",
                f"  Clients d'honneur: {self.r_stats['honneur'].cget('text')}",
                "-" * 50,
                "  DETAIL PAR PRODUIT:",
                "-" * 50,
            ]
            for item in self.tree_r.get_children():
                vals = self.tree_r.item(item)["values"]
                lines.append(f"  {vals[0]}  x{vals[1]}  {vals[2]}/u  =  {vals[3]}  {vals[4]}")
            lines += [
                "=" * 50,
                "        Genere par Baguma Market",
                "=" * 50,
            ]
            dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rapports")
            os.makedirs(dossier, exist_ok=True)
            fname = os.path.join(dossier, f"Rapport_{d}.txt")
            with open(fname, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            os.startfile(fname, "print")
        except Exception as e:
            messagebox.showwarning("Impression", f"Fichier sauvegarde.\n{e}")

    def exporter_rapport_csv(self):
        try:
            d = self.entry_date_rap.get().strip()
            tenant_label = ""
            if self.is_admin and hasattr(self, 'filtre_rap_tenant'):
                tenant_label = f"_{self.filtre_rap_tenant.get().replace(' ', '_').replace('-', '')}"
            elif not self.is_admin:
                self.cursor.execute("SELECT nom FROM tenants WHERE id=?", (self.current_tenant_id,))
                r = self.cursor.fetchone()
                tenant_label = f"_{r[0]}" if r else ""

            lines = ["Produit;Qte;Prix U. USD;Total USD;Total CDF"]
            for item in self.tree_r.get_children():
                vals = self.tree_r.item(item)["values"]
                lines.append(f"{vals[0]};{vals[1]};{vals[2]};{vals[3]};{vals[4]}")

            lines.append("")
            lines.append(f"Resume;{d}")
            lines.append(f"Total USD;{self.r_stats['usd'].cget('text')}")
            lines.append(f"Total CDF;{self.r_stats['cdf'].cget('text')}")
            lines.append(f"Clients;{self.r_stats['clients'].cget('text')}")
            lines.append(f"Recus;{self.r_stats['recus'].cget('text')}")
            lines.append(f"Stock;{self.r_stats['stock'].cget('text')}")
            lines.append(f"Honneur;{self.r_stats['honneur'].cget('text')}")

            dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rapports")
            os.makedirs(dossier, exist_ok=True)
            fname = os.path.join(dossier, f"Rapport_{d}{tenant_label}.csv")
            with open(fname, "w", encoding="utf-8-sig") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("Export", f"Rapport exporte:\n{fname}")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    # ========================= TENANTS (Admin) =========================
    def page_tenants(self):
        for w in self.content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.content, text="\U0001f3e2  Gestion des Tenants (Commerces)",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(pady=(12, 8), anchor="w", padx=18)

        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=4)

        ctk.CTkButton(top, text="+ Nouveau commerce", width=170, height=34,
                      fg_color=ACCENT_GREEN, hover_color="#27ae60", text_color="#000",
                      font=(FONT_FAMILY, 12, "bold"),
                      command=self.ajouter_tenant).pack(side="left")

        tree_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        tree_frame.pack(fill="both", expand=True, padx=18, pady=(5, 10))

        from tkinter import ttk
        s = ttk.Style(); s.configure("T.Treeview", background=DARK_CARD, foreground="white",
                                      fieldbackground=DARK_CARD, rowheight=30, font=(FONT_FAMILY, 11))
        s.configure("T.Treeview.Heading", background=GOLD_DARK, foreground="#000", font=(FONT_FAMILY, 11, "bold"))

        cols = ("ID", "Nom", "Localisation", "Type", "Actif", "Nb Produits", "Nb Ventes", "Date creation")
        self.tree_tenants = ttk.Treeview(tree_frame, columns=cols, show="headings", style="T.Treeview")
        for c in cols:
            self.tree_tenants.heading(c, text=c)
        self.tree_tenants.column("ID", width=35, anchor="center")
        self.tree_tenants.column("Nom", width=160)
        self.tree_tenants.column("Localisation", width=100)
        self.tree_tenants.column("Type", width=90)
        self.tree_tenants.column("Actif", width=45, anchor="center")
        self.tree_tenants.column("Nb Produits", width=75, anchor="center")
        self.tree_tenants.column("Nb Ventes", width=75, anchor="center")
        self.tree_tenants.column("Date creation", width=100, anchor="center")
        self.tree_tenants.pack(fill="both", expand=True, padx=8, pady=8)

        btn_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkButton(btn_frame, text="Desactiver / Activer", width=160, height=30,
                      fg_color=ACCENT_ORANGE, text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.toggle_tenant).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Voir le shop", width=120, height=30,
                      fg_color=ACCENT_BLUE, text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.voir_shop_tenant).pack(side="left", padx=4)

        self.afficher_tenants()

    def afficher_tenants(self):
        for row in self.tree_tenants.get_children():
            self.tree_tenants.delete(row)
        self.cursor.execute("""SELECT t.id, t.nom, COALESCE(t.localisation, ''), COALESCE(t.type_commerce, ''),
            t.actif,
            (SELECT COUNT(*) FROM produits WHERE tenant_id=t.id),
            (SELECT COUNT(*) FROM ventes WHERE tenant_id=t.id),
            t.date_creation
            FROM tenants t ORDER BY t.id""")
        for r in self.cursor.fetchall():
            actif = "Oui" if r[4] else "Non"
            self.tree_tenants.insert("", "end", values=(
                r[0], r[1], r[2] or "-", r[3] or "-", actif, r[5], r[6], r[7] or "-"))

    def ajouter_tenant(self):
        win = ctk.CTkToplevel(self)
        win.title("Nouveau commerce")
        win.geometry("400x420")
        win.configure(fg_color=LOGIN_BG)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="\U0001f3e2 Nouveau commerce",
                     font=(FONT_FAMILY, 18, "bold"), text_color=GOLD_LIGHT).pack(pady=(15, 10))

        entry_nom = ctk.CTkEntry(win, width=280, height=38, placeholder_text="Nom du commerce",
                                  fg_color=DARK_CARD, border_color=GOLD_DARK,
                                  font=(FONT_FAMILY, 13))
        entry_nom.pack(pady=5)

        entry_loc = ctk.CTkEntry(win, width=280, height=38, placeholder_text="Localisation (ex: Bukavu, Goma)",
                                  fg_color=DARK_CARD, border_color=GOLD_DARK,
                                  font=(FONT_FAMILY, 13))
        entry_loc.pack(pady=5)

        ctk.CTkLabel(win, text="Type de commerce :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack()
        combo_type = ctk.CTkOptionMenu(win, values=["Chaussures", "Vetements", "Electronique",
                                                     "Alimentation", "Autre"],
                                        width=280, height=34, fg_color=DARK_CARD, button_color=GOLD_DARK)
        combo_type.pack(pady=5)

        def save():
            nom = entry_nom.get().strip()
            loc = entry_loc.get().strip()
            type_c = combo_type.get()
            if not nom:
                messagebox.showwarning("Attention", "Entrez un nom.")
                return
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                self.cursor.execute("INSERT INTO tenants (nom, localisation, type_commerce, date_creation) VALUES (?, ?, ?, ?)",
                                    (nom, loc, type_c, now))
                new_tid = self.cursor.lastrowid
                seed_produits(self.cursor, new_tid)
                self.cursor.execute("INSERT INTO settings (key, value, tenant_id) VALUES ('taux_cdf', '2800', ?)",
                                    (new_tid,))
                self.conn.commit()
                add_notification(self.cursor, self.conn, new_tid,
                    f"Commerce '{nom}' cree a {loc} (Type: {type_c}) - {61} produits ajoutes")
                messagebox.showinfo("Succes",
                    f"Commerce '{nom}' cree a {loc}.\nType: {type_c}\nProduits: {61}")
                self.afficher_tenants()
                win.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", str(e))

        ctk.CTkButton(win, text="Creer le commerce", width=180, height=38,
                      fg_color=GOLD_DARK, text_color="#000",
                      font=(FONT_FAMILY, 13, "bold"), command=save).pack(pady=15)

    def toggle_tenant(self):
        sel = self.tree_tenants.selection()
        if not sel:
            messagebox.showwarning("Attention", "Selectionnez un tenant.")
            return
        tid = self.tree_tenants.item(sel[0])["values"][0]
        self.cursor.execute("SELECT actif FROM tenants WHERE id=?", (tid,))
        actif = self.cursor.fetchone()[0]
        new_val = 0 if actif else 1
        self.cursor.execute("UPDATE tenants SET actif=? WHERE id=?", (new_val, tid))
        self.conn.commit()
        self.afficher_tenants()

    def voir_shop_tenant(self):
        sel = self.tree_tenants.selection()
        if not sel:
            messagebox.showwarning("Attention", "Selectionnez un tenant.")
            return
        tid = self.tree_tenants.item(sel[0])["values"][0]
        self.cursor.execute("SELECT nom FROM tenants WHERE id=?", (tid,))
        nom = self.cursor.fetchone()[0]

        win = ctk.CTkToplevel(self)
        win.title(f"Shop: {nom}")
        win.geometry("700x450")
        win.configure(fg_color=MAIN_BG)
        win.transient(self)

        ctk.CTkLabel(win, text=f"\U0001f45f Produits de '{nom}'",
                     font=(FONT_FAMILY, 16, "bold"), text_color=GOLD_LIGHT).pack(pady=(12, 8))

        from tkinter import ttk
        s = ttk.Style(); s.configure("St.Treeview", background=DARK_CARD, foreground="white",
                                      fieldbackground=DARK_CARD, rowheight=26, font=(FONT_FAMILY, 10))
        s.configure("St.Treeview.Heading", background=GOLD_DARK, foreground="#000", font=(FONT_FAMILY, 10, "bold"))

        cols = ("Nom", "Prix USD", "Stock")
        tree = ttk.Treeview(win, columns=cols, show="headings", style="St.Treeview")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("Nom", width=300)
        tree.column("Prix USD", width=100, anchor="center")
        tree.column("Stock", width=80, anchor="center")
        tree.pack(fill="both", expand=True, padx=18, pady=(0, 8))

        self.cursor.execute("""SELECT nom, prix_usd, stock FROM produits
            WHERE tenant_id=? ORDER BY nom""", (tid,))
        for r in self.cursor.fetchall():
            tree.insert("", "end", values=(r[0], f"${r[1]:.2f}", r[2]))

        ctk.CTkButton(win, text="Fermer", width=100, height=30,
                      fg_color=DARK_CARD, command=win.destroy).pack(pady=(0, 10))

    # ========================= UTILISATEURS (Admin) =========================
    def page_utilisateurs(self):
        for w in self.content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.content, text="\U0001f46e  Gestion des Utilisateurs",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(pady=(12, 8), anchor="w", padx=18)

        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=4)

        ctk.CTkButton(top, text="+ Nouvel utilisateur", width=170, height=34,
                      fg_color=ACCENT_GREEN, hover_color="#27ae60", text_color="#000",
                      font=(FONT_FAMILY, 12, "bold"),
                      command=self.ajouter_utilisateur).pack(side="left")

        tree_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        tree_frame.pack(fill="both", expand=True, padx=18, pady=(5, 10))

        from tkinter import ttk
        s = ttk.Style(); s.configure("U.Treeview", background=DARK_CARD, foreground="white",
                                      fieldbackground=DARK_CARD, rowheight=30, font=(FONT_FAMILY, 11))
        s.configure("U.Treeview.Heading", background=GOLD_DARK, foreground="#000", font=(FONT_FAMILY, 11, "bold"))

        cols = ("ID", "Login", "Tenant", "Role")
        self.tree_users = ttk.Treeview(tree_frame, columns=cols, show="headings", style="U.Treeview")
        for c in cols:
            self.tree_users.heading(c, text=c)
        self.tree_users.column("ID", width=40, anchor="center")
        self.tree_users.column("Login", width=180)
        self.tree_users.column("Tenant", width=200)
        self.tree_users.column("Role", width=100, anchor="center")
        self.tree_users.pack(fill="both", expand=True, padx=8, pady=8)

        btn_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        btn_frame.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkButton(btn_frame, text="Supprimer", width=110, height=30,
                      fg_color=ACCENT_RED, text_color="#fff",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.supprimer_utilisateur).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Reinitialiser mot de passe", width=180, height=30,
                      fg_color=ACCENT_ORANGE, text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.reset_mdp_utilisateur).pack(side="left", padx=4)

        self.afficher_utilisateurs()

    def afficher_utilisateurs(self):
        for row in self.tree_users.get_children():
            self.tree_users.delete(row)
        self.cursor.execute("""SELECT u.id, u.login, COALESCE(t.nom, 'Admin Global'), u.tenant_id, u.role
            FROM utilisateurs u LEFT JOIN tenants t ON u.tenant_id=t.id
            ORDER BY u.tenant_id, u.login""")
        for r in self.cursor.fetchall():
            role = r[4] or "vendeur"
            self.tree_users.insert("", "end", values=(r[0], r[1], r[2], role.upper()), iid=str(r[0]))

    def ajouter_utilisateur(self):
        win = ctk.CTkToplevel(self)
        win.title("Nouvel utilisateur")
        win.geometry("400x420")
        win.configure(fg_color=LOGIN_BG)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="\U0001f464 Nouvel utilisateur",
                     font=(FONT_FAMILY, 18, "bold"), text_color=GOLD_LIGHT).pack(pady=(15, 10))

        entry_login = ctk.CTkEntry(win, width=280, height=36, placeholder_text="Login (numero/email)",
                                    fg_color=DARK_CARD, border_color=GOLD_DARK, font=(FONT_FAMILY, 13))
        entry_login.pack(pady=5)

        entry_code = ctk.CTkEntry(win, width=280, height=36, placeholder_text="Mot de passe",
                                   fg_color=DARK_CARD, border_color=GOLD_DARK, font=(FONT_FAMILY, 13), show="*")
        entry_code.pack(pady=5)

        self.cursor.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY nom")
        tenants = self.cursor.fetchall()
        tenant_names = [t[1] for t in tenants]
        tenant_map = {t[1]: t[0] for t in tenants}

        ctk.CTkLabel(win, text="Commerce :", font=(FONT_FAMILY, 12), text_color=TEXT_GRAY).pack()
        combo = ctk.CTkOptionMenu(win, values=tenant_names or ["Admin Global"],
                                   width=280, height=34, fg_color=DARK_CARD, button_color=GOLD_DARK)
        combo.pack(pady=5)
        if tenant_names:
            combo.set(tenant_names[0])

        ctk.CTkLabel(win, text="Role :", font=(FONT_FAMILY, 12), text_color=TEXT_GRAY).pack()
        combo_role = ctk.CTkOptionMenu(win, values=ALL_ROLES,
                                        width=280, height=34, fg_color=DARK_CARD, button_color=GOLD_DARK)
        combo_role.pack(pady=5)
        combo_role.set(ROLE_VENDEUR)

        def save():
            lg = entry_login.get().strip()
            cd = entry_code.get().strip()
            tenant_nom = combo.get()
            role = combo_role.get()
            if not lg or not cd:
                messagebox.showwarning("Attention", "Remplissez tous les champs.")
                return
            if tenant_nom in tenant_map:
                tid = tenant_map[tenant_nom]
            else:
                tid = ADMIN_TENANT_ID
            try:
                self.cursor.execute("INSERT INTO utilisateurs (login, code, tenant_id, role) VALUES (?, ?, ?, ?)",
                                    (lg, cd, tid, role))
                self.conn.commit()
                log_action(self.cursor, self.conn, self.current_user_id, self.current_user_login,
                           tid, "Creation utilisateur", f"{lg} - Role: {role}")
                messagebox.showinfo("Succes", f"Utilisateur '{lg}' cree avec le role '{role}'.")
                self.afficher_utilisateurs()
                win.destroy()
            except Exception:
                messagebox.showerror("Erreur", "Ce login existe deja.")

        ctk.CTkButton(win, text="Creer", width=150, height=36,
                      fg_color=GOLD_DARK, text_color="#000",
                      font=(FONT_FAMILY, 13, "bold"), command=save).pack(pady=15)

    def supprimer_utilisateur(self):
        sel = self.tree_users.selection()
        if not sel:
            messagebox.showwarning("Attention", "Selectionnez un utilisateur.")
            return
        uid = int(sel[0])
        self.cursor.execute("SELECT login FROM utilisateurs WHERE id=?", (uid,))
        login = self.cursor.fetchone()[0]
        if login in ("0838029045", "baguma.com"):
            messagebox.showwarning("Attention", "Impossible de supprimer le compte admin principal.")
            return
        if messagebox.askyesno("Confirmer", f"Supprimer l'utilisateur '{login}' ?"):
            self.cursor.execute("DELETE FROM utilisateurs WHERE id=?", (uid,))
            self.conn.commit()
            self.afficher_utilisateurs()

    def reset_mdp_utilisateur(self):
        sel = self.tree_users.selection()
        if not sel:
            messagebox.showwarning("Attention", "Selectionnez un utilisateur.")
            return
        uid = int(sel[0])
        win = ctk.CTkToplevel(self)
        win.title("Reinitialiser mot de passe")
        win.geometry("350x200")
        win.configure(fg_color=LOGIN_BG)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="Nouveau mot de passe",
                     font=(FONT_FAMILY, 16, "bold"), text_color=GOLD_LIGHT).pack(pady=(15, 5))
        entry_new = ctk.CTkEntry(win, width=250, height=36, show="*",
                                  fg_color=DARK_CARD, border_color=GOLD_DARK, font=(FONT_FAMILY, 14))
        entry_new.pack(pady=10)

        def save():
            new = entry_new.get().strip()
            if not new:
                messagebox.showwarning("Attention", "Entrez un mot de passe.")
                return
            self.cursor.execute("UPDATE utilisateurs SET code=? WHERE id=?", (new, uid))
            self.conn.commit()
            messagebox.showinfo("Succes", "Mot de passe reinitialise.")
            win.destroy()

        ctk.CTkButton(win, text="Enregistrer", width=120, height=34,
                      fg_color=GOLD_DARK, text_color="#000",
                      font=(FONT_FAMILY, 12, "bold"), command=save).pack(pady=10)

    # ========================= NOTIFICATIONS =========================
    def page_notifications(self):
        for w in self.content.winfo_children():
            w.destroy()

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(12, 8))
        ctk.CTkLabel(header, text="\U0001f514  Notifications",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(side="left")
        ctk.CTkButton(header, text="Tout marquer lu", width=140, height=30,
                      fg_color=ACCENT_GREEN, hover_color="#00a884", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.marquer_toutes_lues).pack(side="right", padx=4)
        ctk.CTkButton(header, text="Supprimer lues", width=130, height=30,
                      fg_color=ACCENT_RED, hover_color="#c1121f", text_color="#fff",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.supprimer_notifs_lues).pack(side="right", padx=4)

        scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"""SELECT id, tenant_id, message, is_read, created_at
            FROM notifications WHERE 1=1{cond} ORDER BY id DESC LIMIT 100""", params)
        notifs = self.cursor.fetchall()

        if not notifs:
            ctk.CTkLabel(scroll, text="Aucune notification",
                         font=(FONT_FAMILY, 14), text_color=TEXT_GRAY).pack(pady=40)
            return

        for nid, tid, msg, is_read, created_at in notifs:
            bg = DARK_CARD if is_read else CARD_BG
            border = GOLD_DARK if is_read else ACCENT_GREEN
            ncard = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=7, border_width=1,
                                  border_color=border)
            ncard.pack(fill="x", pady=3)

            top_row = ctk.CTkFrame(ncard, fg_color="transparent")
            top_row.pack(fill="x", padx=12, pady=(8, 2))

            if not is_read:
                ctk.CTkLabel(top_row, text="\U0001f7e2", font=(FONT_FAMILY, 10)).pack(side="left")

            if self.is_admin and tid != 0:
                self.cursor.execute("SELECT nom FROM tenants WHERE id=?", (tid,))
                tr = self.cursor.fetchone()
                tenant_name = tr[0] if tr else f"Tenant {tid}"
                ctk.CTkLabel(top_row, text=f"[{tenant_name}]", font=(FONT_FAMILY, 9, "bold"),
                             text_color=ACCENT_BLUE).pack(side="left", padx=4)

            ctk.CTkLabel(top_row, text=created_at, font=(FONT_FAMILY, 9),
                         text_color=TEXT_DIM).pack(side="right")

            ctk.CTkLabel(ncard, text=msg, font=(FONT_FAMILY, 11),
                         text_color=TEXT_WHITE, anchor="w", justify="left").pack(
                            fill="x", padx=12, pady=(0, 8))

    def marquer_toutes_lues(self):
        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"UPDATE notifications SET is_read=1 WHERE is_read=0{cond}", params)
        self.conn.commit()
        self.page_notifications()

    def supprimer_notifs_lues(self):
        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"DELETE FROM notifications WHERE is_read=1{cond}", params)
        self.conn.commit()
        self.page_notifications()

    # ========================= PRIX PAR TENANT =========================
    def page_tenant_prices(self):
        for w in self.content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.content, text="\U0001f4b3  Prix par Tenant",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(pady=(12, 8), anchor="w", padx=18)

        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=4)

        self.cursor.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
        tenants = self.cursor.fetchall()
        tenant_names = [t[1] for t in tenants]
        tenant_map = {t[1]: t[0] for t in tenants}

        ctk.CTkLabel(top, text="Commerce :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        self.filtre_price_tenant = ctk.StringVar(value=tenant_names[0] if tenant_names else "")
        ctk.CTkOptionMenu(top, variable=self.filtre_price_tenant, values=tenant_names,
                          width=200, height=32, fg_color=DARK_CARD,
                          command=lambda e: self.afficher_tenant_prices()).pack(side="left", padx=6)

        ctk.CTkButton(top, text="Ajouter/Modifier prix", width=170, height=32,
                      fg_color=ACCENT_GREEN, hover_color="#00a884", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.modifier_prix_tenant).pack(side="left", padx=6)

        ctk.CTkButton(top, text="Reinitialiser au prix defaut", width=200, height=32,
                      fg_color=ACCENT_ORANGE, hover_color="#e17055", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.reset_prix_tenant).pack(side="left", padx=6)

        tree_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        tree_frame.pack(fill="both", expand=True, padx=18, pady=(5, 10))

        from tkinter import ttk
        s = ttk.Style(); s.configure("TP.Treeview", background=DARK_CARD, foreground="white",
                                      fieldbackground=DARK_CARD, rowheight=28, font=(FONT_FAMILY, 10))
        s.configure("TP.Treeview.Heading", background=GOLD_DARK, foreground="#000",
                    font=(FONT_FAMILY, 10, "bold"))

        cols = ("ID", "Produit", "Categorie", "Prix Defaut USD", "Prix Defaut CDF",
                "Prix Tenant USD", "Prix Tenant CDF", "Statut")
        self.tree_tp = ttk.Treeview(tree_frame, columns=cols, show="headings", style="TP.Treeview")
        for c in cols:
            self.tree_tp.heading(c, text=c)
        self.tree_tp.column("ID", width=35, anchor="center")
        self.tree_tp.column("Produit", width=180)
        self.tree_tp.column("Categorie", width=110)
        self.tree_tp.column("Prix Defaut USD", width=100, anchor="center")
        self.tree_tp.column("Prix Defaut CDF", width=110, anchor="center")
        self.tree_tp.column("Prix Tenant USD", width=100, anchor="center")
        self.tree_tp.column("Prix Tenant CDF", width=110, anchor="center")
        self.tree_tp.column("Statut", width=80, anchor="center")
        self.tree_tp.pack(fill="both", expand=True, padx=8, pady=8)

        self.tenant_price_map = tenant_map
        self.afficher_tenant_prices()

    def afficher_tenant_prices(self):
        for row in self.tree_tp.get_children():
            self.tree_tp.delete(row)

        tenant_nom = self.filtre_price_tenant.get()
        if not tenant_nom or tenant_nom not in self.tenant_price_map:
            return
        tid = self.tenant_price_map[tenant_nom]

        self.cursor.execute("""SELECT p.id, p.nom, c.nom, p.prix_usd, p.prix_cdf
            FROM produits p JOIN categories c ON p.categorie_id=c.id
            WHERE p.tenant_id=? ORDER BY c.nom, p.nom""", (tid,))
        produits = self.cursor.fetchall()

        for pid, pnom, cnom, def_usd, def_cdf in produits:
            self.cursor.execute("SELECT prix_usd, prix_cdf FROM tenant_prices WHERE tenant_id=? AND produit_id=?",
                                (tid, pid))
            tp = self.cursor.fetchone()
            if tp:
                t_usd, t_cdf = tp
                statut = "Personnalise"
            else:
                t_usd, t_cdf = def_usd, def_cdf
                statut = "Defaut"
            self.tree_tp.insert("", "end", values=(
                pid, pnom, cnom, f"${def_usd:.2f}", f"{def_cdf:,.0f}",
                f"${t_usd:.2f}", f"{t_cdf:,.0f}", statut))

    def modifier_prix_tenant(self):
        sel = self.tree_tp.selection()
        if not sel:
            messagebox.showwarning("Attention", "Selectionnez un produit.")
            return
        vals = self.tree_tp.item(sel[0])["values"]
        pid = vals[0]
        pnom = vals[1]
        tenant_nom = self.filtre_price_tenant.get()
        tid = self.tenant_price_map.get(tenant_nom)

        win = ctk.CTkToplevel(self)
        win.title(f"Modifier prix - {pnom}")
        win.geometry("400x250")
        win.configure(fg_color=LOGIN_BG)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text=f"\U0001f4b3 Prix pour '{pnom}'",
                     font=(FONT_FAMILY, 16, "bold"), text_color=GOLD_LIGHT).pack(pady=(15, 5))
        ctk.CTkLabel(win, text=f"Commerce: {tenant_nom}",
                     font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack()

        entry_usd = ctk.CTkEntry(win, width=150, height=38, font=(FONT_FAMILY, 16),
                                  fg_color=DARK_CARD, border_color=GOLD_DARK, justify="center")
        entry_usd.insert(0, str(float(vals[3].replace("$", ""))))
        entry_usd.pack(pady=10)
        entry_usd.select_range(0, "end")
        entry_usd.focus()

        ctk.CTkLabel(win, text="Prix USD", font=(FONT_FAMILY, 10), text_color=TEXT_GRAY).pack()

        def save():
            try:
                new_usd = float(entry_usd.get())
                if new_usd <= 0:
                    raise ValueError
                set_tenant_price(self.cursor, self.conn, tid, pid, new_usd, self.taux_cdf)
                add_notification(self.cursor, self.conn, tid,
                    f"Prix modifie: {pnom} = ${new_usd:.2f} USD")
                log_action(self.cursor, self.conn, self.current_user_id, self.current_user_login,
                           tid, "Modification prix", f"{pnom} = ${new_usd:.2f}")
                self.afficher_tenant_prices()
                win.destroy()
            except Exception:
                messagebox.showwarning("Erreur", "Entrez un prix valide.")

        ctk.CTkButton(win, text="Enregistrer", width=120, height=36,
                      fg_color=GOLD_DARK, text_color="#000",
                      font=(FONT_FAMILY, 13, "bold"), command=save).pack(pady=5)
        entry_usd.bind("<Return>", lambda e: save())

    def reset_prix_tenant(self):
        sel = self.tree_tp.selection()
        if not sel:
            messagebox.showwarning("Attention", "Selectionnez un produit.")
            return
        vals = self.tree_tp.item(sel[0])["values"]
        pid = vals[0]
        tenant_nom = self.filtre_price_tenant.get()
        tid = self.tenant_price_map.get(tenant_nom)
        if messagebox.askyesno("Confirmer", f"Reinitialiser le prix du produit {vals[1]} au prix defaut ?"):
            self.cursor.execute("DELETE FROM tenant_prices WHERE tenant_id=? AND produit_id=?", (tid, pid))
            self.conn.commit()
            add_notification(self.cursor, self.conn, tid,
                f"Prix reinitialise: {vals[1]} (retour au prix defaut)")
            self.afficher_tenant_prices()

    # ========================= PARAMETRES =========================
    def page_settings(self):
        for w in self.content.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.content, text="\u2699\ufe0f  Parametres",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(pady=(12, 8), anchor="w", padx=18)

        scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        self.settings_frame = scroll
        self._build_section_generaux(scroll)
        ctk.CTkFrame(scroll, fg_color=GOLD_DARK, height=1).pack(fill="x", pady=8)
        self._build_section_securite(scroll)
        ctk.CTkFrame(scroll, fg_color=GOLD_DARK, height=1).pack(fill="x", pady=8)
        self._build_section_notifications(scroll)
        ctk.CTkFrame(scroll, fg_color=GOLD_DARK, height=1).pack(fill="x", pady=8)
        if self.can("gerer_produits"):
            self._build_section_prix_tenant(scroll)
            ctk.CTkFrame(scroll, fg_color=GOLD_DARK, height=1).pack(fill="x", pady=8)
        self._build_section_honneur(scroll)
        ctk.CTkFrame(scroll, fg_color=GOLD_DARK, height=1).pack(fill="x", pady=8)
        self._build_section_logs(scroll)
        ctk.CTkFrame(scroll, fg_color=GOLD_DARK, height=1).pack(fill="x", pady=8)
        self._build_section_avances(scroll)

    def _build_section_generaux(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=9)
        section.pack(fill="x", pady=4)
        ctk.CTkLabel(section, text="\U0001f4b1  Parametres Generaux",
                     font=(FONT_FAMILY, 14, "bold"), text_color=GOLD_LIGHT).pack(anchor="w", padx=14, pady=(10, 6))

        row_taux = ctk.CTkFrame(section, fg_color="transparent")
        row_taux.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row_taux, text="Taux de change (1 USD = ? CDF) :", font=(FONT_FAMILY, 11),
                     text_color=TEXT_GRAY).pack(side="left")
        self.entry_taux = ctk.CTkEntry(row_taux, width=120, height=32, font=(FONT_FAMILY, 13),
                                        fg_color=DARK_CARD, border_color=GOLD_DARK, justify="center")
        self.entry_taux.insert(0, str(int(self.taux_cdf)))
        self.entry_taux.pack(side="left", padx=8)
        ctk.CTkButton(row_taux, text="Appliquer", width=90, height=32,
                      fg_color=ACCENT_GREEN, hover_color="#00a884", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self._save_taux).pack(side="left", padx=4)

        row_theme = ctk.CTkFrame(section, fg_color="transparent")
        row_theme.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row_theme, text="Theme :", font=(FONT_FAMILY, 11),
                     text_color=TEXT_GRAY).pack(side="left")
        self.theme_var = ctk.StringVar(value="Dark")
        ctk.CTkOptionMenu(row_theme, variable=self.theme_var,
                          values=["Dark", "Clair"], width=120, height=32,
                          fg_color=DARK_CARD, command=self._change_theme).pack(side="left", padx=8)

        row_info = ctk.CTkFrame(section, fg_color="transparent")
        row_info.pack(fill="x", padx=14, pady=(4, 10))
        ctk.CTkLabel(row_info, text="Utilisateur :", font=(FONT_FAMILY, 11),
                     text_color=TEXT_GRAY).pack(side="left")
        ctk.CTkLabel(row_info, text=f"{self.current_user_login} [{self.current_role.upper()}]",
                     font=(FONT_FAMILY, 11, "bold"), text_color=ACCENT_BLUE).pack(side="left", padx=8)

    def _save_taux(self):
        try:
            val = float(self.entry_taux.get())
            if val <= 0:
                raise ValueError
            self.taux_cdf = val
            set_taux(self.cursor, self.conn, val, self.current_tenant_id)
            self.taux_lbl.configure(text=f"Taux: 1 USD = {val:,.0f} CDF")
            messagebox.showinfo("Succes", f"Taux mis a jour : 1 USD = {val:,.0f} CDF")
        except Exception:
            messagebox.showwarning("Erreur", "Entrez un nombre valide.")

    def _change_theme(self, choice):
        mode = "dark" if choice == "Dark" else "light"
        ctk.set_appearance_mode(mode)

    def _build_section_securite(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=9)
        section.pack(fill="x", pady=4)
        ctk.CTkLabel(section, text="\U0001f512  Parametres de Securite",
                     font=(FONT_FAMILY, 14, "bold"), text_color=GOLD_LIGHT).pack(anchor="w", padx=14, pady=(10, 6))

        row_mdp = ctk.CTkFrame(section, fg_color="transparent")
        row_mdp.pack(fill="x", padx=14, pady=4)
        ctk.CTkButton(row_mdp, text="Changer mon mot de passe", width=200, height=32,
                      fg_color=ACCENT_BLUE, hover_color="#0090b0", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.change_password).pack(side="left")

        row_logout = ctk.CTkFrame(section, fg_color="transparent")
        row_logout.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row_logout, text="Deconnexion auto. (inactivite) :", font=(FONT_FAMILY, 11),
                     text_color=TEXT_GRAY).pack(side="left")
        self.auto_logout_var = ctk.StringVar(value="5 min")
        ctk.CTkOptionMenu(row_logout, variable=self.auto_logout_var,
                          values=["Desactive", "5 min", "15 min", "30 min"],
                          width=120, height=32, fg_color=DARK_CARD,
                          command=self._change_logout_time).pack(side="left", padx=8)

        if self.is_admin:
            row_roles = ctk.CTkFrame(section, fg_color="transparent")
            row_roles.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(row_roles, text="Permissions par role :", font=(FONT_FAMILY, 11),
                         text_color=TEXT_GRAY).pack(side="left")
            ctk.CTkButton(row_roles, text="Voir les roles", width=130, height=32,
                          fg_color=DARK_CARD, hover_color=CARD_BG,
                          command=self._show_roles_info).pack(side="left", padx=8)

    def _change_logout_time(self, choice):
        times = {"Desactive": 0, "5 min": 300000, "15 min": 900000, "30 min": 1800000}
        self.inactivity_limit = times.get(choice, 300000)
        if self.inactivity_limit == 0 and self.inactivity_timer:
            self.after_cancel(self.inactivity_timer)
            self.inactivity_timer = None
        else:
            self.reset_inactivity()

    def _show_roles_info(self):
        win = ctk.CTkToplevel(self)
        win.title("Permissions par role")
        win.geometry("500x400")
        win.configure(fg_color=LOGIN_BG)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(win, text="\U0001f46e Permissions par Role",
                     font=(FONT_FAMILY, 16, "bold"), text_color=GOLD_LIGHT).pack(pady=(12, 8))

        for role, perms in PERMISSIONS.items():
            rframe = ctk.CTkFrame(win, fg_color=DARK_CARD, corner_radius=7)
            rframe.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(rframe, text=f"  {role.upper()}", font=(FONT_FAMILY, 12, "bold"),
                         text_color=ACCENT_BLUE).pack(anchor="w", padx=10, pady=(6, 0))
            perms_text = "  |  ".join(sorted(perms))
            ctk.CTkLabel(rframe, text=f"  {perms_text}", font=(FONT_FAMILY, 9),
                         text_color=TEXT_GRAY, anchor="w", wraplength=450).pack(anchor="w", padx=10, pady=(0, 6))

        ctk.CTkButton(win, text="Fermer", width=100, height=30,
                      fg_color=DARK_CARD, command=win.destroy).pack(pady=10)

    def _build_section_notifications(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=9)
        section.pack(fill="x", pady=4)
        ctk.CTkLabel(section, text="\U0001f514  Parametres de Notifications",
                     font=(FONT_FAMILY, 14, "bold"), text_color=GOLD_LIGHT).pack(anchor="w", padx=14, pady=(10, 6))

        self.cursor.execute("SELECT * FROM notif_settings WHERE tenant_id=?", (self.current_tenant_id,))
        ns = self.cursor.fetchone()
        if not ns:
            self.cursor.execute("INSERT INTO notif_settings (tenant_id) VALUES (?)", (self.current_tenant_id,))
            self.conn.commit()
            ns = (self.current_tenant_id, 1, 1, 1, 1, 0)

        toggles = [
            ("Alertes actives", "alertes_actives", ns[1]),
            ("Notif. ventes", "notif_ventes", ns[2]),
            ("Notif. stock faible", "notif_stock", ns[3]),
            ("Notif. modifications prix", "notif_prix", ns[4]),
            ("Notif. connexions", "notif_connexion", ns[5]),
        ]
        self.notif_toggles = {}
        for label, key, val in toggles:
            row = ctk.CTkFrame(section, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=label, font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
            var = ctk.BooleanVar(value=bool(val))
            switch = ctk.CTkSwitch(row, text="", variable=var, onvalue=True, offvalue=False,
                                    fg_color=ACCENT_RED, progress_color=ACCENT_GREEN)
            switch.pack(side="right")
            self.notif_toggles[key] = var

        btn_row = ctk.CTkFrame(section, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(8, 4))
        ctk.CTkButton(btn_row, text="Enregistrer", width=130, height=30,
                      fg_color=GOLD_DARK, text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self._save_notif_settings).pack(side="left")
        ctk.CTkButton(btn_row, text="Voir l'historique", width=130, height=30,
                      fg_color=DARK_CARD,
                      command=self.page_notifications).pack(side="left", padx=6)

    def _save_notif_settings(self):
        vals = {k: 1 if v.get() else 0 for k, v in self.notif_toggles.items()}
        self.cursor.execute("""INSERT OR REPLACE INTO notif_settings
            (tenant_id, alertes_actives, notif_ventes, notif_stock, notif_prix, notif_connexion)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (self.current_tenant_id, vals["alertes_actives"], vals["notif_ventes"],
             vals["notif_stock"], vals["notif_prix"], vals["notif_connexion"]))
        self.conn.commit()
        messagebox.showinfo("Succes", "Preferences de notification sauvegardees.")

    def _build_section_prix_tenant(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=9)
        section.pack(fill="x", pady=4)
        ctk.CTkLabel(section, text="\U0001f4b3  Prix par Tenant",
                     font=(FONT_FAMILY, 14, "bold"), text_color=GOLD_LIGHT).pack(anchor="w", padx=14, pady=(10, 6))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)

        self.cursor.execute("SELECT id, nom FROM tenants WHERE actif=1 ORDER BY id")
        tenants = self.cursor.fetchall()
        tenant_names = [t[1] for t in tenants]
        self._settings_tenant_map = {t[1]: t[0] for t in tenants}

        ctk.CTkLabel(row, text="Commerce :", font=(FONT_FAMILY, 11), text_color=TEXT_GRAY).pack(side="left")
        self._settings_tenant_var = ctk.StringVar(value=tenant_names[0] if tenant_names else "")
        ctk.CTkOptionMenu(row, variable=self._settings_tenant_var, values=tenant_names,
                          width=180, height=30, fg_color=DARK_CARD).pack(side="left", padx=6)

        ctk.CTkButton(row, text="Gerer les prix", width=130, height=30,
                      fg_color=ACCENT_GREEN, hover_color="#00a884", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.page_tenant_prices).pack(side="left", padx=6)

    def _build_section_honneur(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=9)
        section.pack(fill="x", pady=4)
        ctk.CTkLabel(section, text="\u2b50  Clients d'Honneur",
                     font=(FONT_FAMILY, 14, "bold"), text_color=HONOR_COLOR).pack(anchor="w", padx=14, pady=(10, 6))

        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"SELECT COUNT(*) FROM ventes WHERE est_client_honneur=1{cond}", params)
        nb = self.cursor.fetchone()[0]
        self.cursor.execute(f"SELECT COALESCE(SUM(total_usd),0), COALESCE(SUM(total_cdf),0) FROM ventes WHERE est_client_honneur=1{cond}", params)
        tot = self.cursor.fetchone()

        stats_row = ctk.CTkFrame(section, fg_color="transparent")
        stats_row.pack(fill="x", padx=14, pady=4)
        for lbl, val, col in [
            ("Total ventes", str(nb), HONOR_COLOR),
            ("Total USD", f"${tot[0]:,.2f}", GOLD_LIGHT),
            ("Total CDF", f"{tot[1]:,.0f} CDF", "#f4a261"),
        ]:
            card = ctk.CTkFrame(stats_row, fg_color=DARK_CARD, corner_radius=6, height=50)
            card.pack(side="left", fill="x", expand=True, padx=3)
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=lbl, font=(FONT_FAMILY, 9), text_color=TEXT_GRAY).pack(pady=(6, 0))
            ctk.CTkLabel(card, text=val, font=(FONT_FAMILY, 12, "bold"), text_color=col).pack(pady=(0, 4))

        ctk.CTkButton(section, text="Voir l'historique complet", width=200, height=30,
                      fg_color=DARK_CARD, command=self.page_honneur).pack(padx=14, pady=(4, 10))

    def _build_section_logs(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=9)
        section.pack(fill="x", pady=4)
        ctk.CTkLabel(section, text="\U0001f4dd  Journal d'Activite (Logs)",
                     font=(FONT_FAMILY, 14, "bold"), text_color=GOLD_LIGHT).pack(anchor="w", padx=14, pady=(10, 6))

        cond = "" if self.is_admin else " AND tenant_id=?"
        params = () if self.is_admin else (self.current_tenant_id,)
        self.cursor.execute(f"SELECT COUNT(*) FROM logs WHERE 1=1{cond}", params)
        nb_logs = self.cursor.fetchone()[0]
        self.cursor.execute(f"SELECT action, COUNT(*) FROM logs WHERE 1=1{cond} GROUP BY action ORDER BY COUNT(*) DESC LIMIT 5", params)
        top_actions = self.cursor.fetchall()

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row, text=f"Total logs : {nb_logs}", font=(FONT_FAMILY, 11, "bold"),
                     text_color=TEXT_WHITE).pack(side="left")

        if top_actions:
            actions_text = "  |  ".join([f"{a}: {c}" for a, c in top_actions])
            ctk.CTkLabel(row, text=actions_text, font=(FONT_FAMILY, 9),
                         text_color=TEXT_GRAY).pack(side="left", padx=10)

        ctk.CTkButton(section, text="Voir tous les logs", width=150, height=30,
                      fg_color=DARK_CARD, command=self.page_logs).pack(padx=14, pady=(4, 10))

    def _build_section_avances(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=9)
        section.pack(fill="x", pady=4)
        ctk.CTkLabel(section, text="\U0001f527  Parametres Avances",
                     font=(FONT_FAMILY, 14, "bold"), text_color=GOLD_LIGHT).pack(anchor="w", padx=14, pady=(10, 6))

        row_backup = ctk.CTkFrame(section, fg_color="transparent")
        row_backup.pack(fill="x", padx=14, pady=4)
        ctk.CTkButton(row_backup, text="\U0001f4be Sauvegarder la base", width=200, height=32,
                      fg_color=ACCENT_GREEN, hover_color="#00a884", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self._backup_db).pack(side="left", padx=4)
        ctk.CTkButton(row_backup, text="\U0001f504 Restaurer la base", width=200, height=32,
                      fg_color=ACCENT_ORANGE, hover_color="#e17055", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self._restore_db).pack(side="left", padx=4)

        row_export = ctk.CTkFrame(section, fg_color="transparent")
        row_export.pack(fill="x", padx=14, pady=4)
        ctk.CTkButton(row_export, text="\U0001f4e4 Exporter produits (CSV)", width=200, height=32,
                      fg_color=ACCENT_BLUE, hover_color="#0090b0", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self._export_produits_csv).pack(side="left", padx=4)
        ctk.CTkButton(row_export, text="\U0001f4e4 Exporter clients (CSV)", width=200, height=32,
                      fg_color=ACCENT_BLUE, hover_color="#0090b0", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self._export_clients_csv).pack(side="left", padx=4)

    def _backup_db(self):
        try:
            import shutil
            dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
            os.makedirs(dossier, exist_ok=True)
            fname = os.path.join(dossier, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            shutil.copy2("commerce.db", fname)
            messagebox.showinfo("Sauvegarde", f"Base sauvegardee:\n{fname}")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _restore_db(self):
        from tkinter import filedialog
        fname = filedialog.askopenfilename(
            title="Restaurer une sauvegarde",
            filetypes=[("SQLite", "*.db"), ("Tous", "*.*")])
        if fname:
            if messagebox.askyesno("Confirmer", "Restaurer cette sauvegarde?\nLa base actuelle sera ecrasee."):
                try:
                    import shutil
                    shutil.copy2(fname, "commerce.db")
                    messagebox.showinfo("Succes", "Base restauree. Redemarrez l'application.")
                    self.show_login()
                except Exception as e:
                    messagebox.showerror("Erreur", str(e))

    def _export_produits_csv(self):
        try:
            cond = "" if self.is_admin else " WHERE tenant_id=?"
            params = () if self.is_admin else (self.current_tenant_id,)
            self.cursor.execute(f"""SELECT p.id, p.nom, c.nom, p.prix_usd, p.prix_cdf, p.stock
                FROM produits p JOIN categories c ON p.categorie_id=c.id{cond} ORDER BY p.nom""", params)
            rows = self.cursor.fetchall()

            dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
            os.makedirs(dossier, exist_ok=True)
            fname = os.path.join(dossier, f"produits_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
            with open(fname, "w", encoding="utf-8-sig") as f:
                f.write("ID;Produit;Categorie;Prix USD;Prix CDF;Stock\n")
                for r in rows:
                    f.write(f"{r[0]};{r[1]};{r[2]};${r[3]:.2f};{r[4]:,.0f};{r[5]}\n")
            messagebox.showinfo("Export", f"Produits exportes:\n{fname}")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _export_clients_csv(self):
        try:
            cond = "" if self.is_admin else " WHERE tenant_id=?"
            params = () if self.is_admin else (self.current_tenant_id,)
            self.cursor.execute(f"""SELECT id, nom, telephone, nb_visites, total_usd, total_cdf
                FROM clients{cond} ORDER BY nom""", params)
            rows = self.cursor.fetchall()

            dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
            os.makedirs(dossier, exist_ok=True)
            fname = os.path.join(dossier, f"clients_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
            with open(fname, "w", encoding="utf-8-sig") as f:
                f.write("ID;Nom;Telephone;Visites;Total USD;Total CDF\n")
                for r in rows:
                    f.write(f"{r[0]};{r[1]};{r[2]};{r[3]};${r[4]:,.2f};{r[5]:,.0f}\n")
            messagebox.showinfo("Export", f"Clients exportes:\n{fname}")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    # ========================= LOGS =========================
    def page_logs(self):
        for w in self.content.winfo_children():
            w.destroy()

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(12, 8))
        ctk.CTkLabel(header, text="\U0001f4dd  Journal d'activite (Logs)",
                     font=(FONT_FAMILY, 20, "bold"), text_color=GOLD_LIGHT).pack(side="left")
        ctk.CTkButton(header, text="Rafraichir", width=100, height=30,
                      fg_color=ACCENT_BLUE, hover_color="#0090b0", text_color="#000",
                      font=(FONT_FAMILY, 11, "bold"),
                      command=self.afficher_logs).pack(side="right", padx=4)

        filter_bar = ctk.CTkFrame(self.content, fg_color="transparent")
        filter_bar.pack(fill="x", padx=18, pady=4)

        ctk.CTkLabel(filter_bar, text="Filtrer par tenant :", font=(FONT_FAMILY, 11),
                     text_color=TEXT_GRAY).pack(side="left")
        self.cursor.execute("SELECT id, nom FROM tenants ORDER BY id")
        tenant_opts = ["Tous"] + [f"{t[0]} - {t[1]}" for t in self.cursor.fetchall()]
        self.filtre_log_tenant = ctk.StringVar(value="Tous")
        ctk.CTkOptionMenu(filter_bar, variable=self.filtre_log_tenant,
                          values=tenant_opts, width=200, height=30, fg_color=DARK_CARD,
                          command=lambda e: self.afficher_logs()).pack(side="left", padx=6)

        ctk.CTkLabel(filter_bar, text="Action :", font=(FONT_FAMILY, 11),
                     text_color=TEXT_GRAY).pack(side="left", padx=(10, 0))
        self.filtre_log_action = ctk.StringVar(value="Toutes")
        ctk.CTkOptionMenu(filter_bar, variable=self.filtre_log_action,
                          values=["Toutes", "Connexion", "Vente", "Ajout produit",
                                  "Suppression", "Modification"],
                          width=140, height=30, fg_color=DARK_CARD,
                          command=lambda e: self.afficher_logs()).pack(side="left", padx=6)

        tree_frame = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=9)
        tree_frame.pack(fill="both", expand=True, padx=18, pady=(5, 10))

        from tkinter import ttk
        s = ttk.Style(); s.configure("L.Treeview", background=DARK_CARD, foreground="white",
                                      fieldbackground=DARK_CARD, rowheight=26, font=(FONT_FAMILY, 10))
        s.configure("L.Treeview.Heading", background=GOLD_DARK, foreground="#000",
                    font=(FONT_FAMILY, 10, "bold"))

        cols = ("ID", "Login", "Tenant", "Action", "Details", "Date/Heure")
        self.tree_logs = ttk.Treeview(tree_frame, columns=cols, show="headings", style="L.Treeview")
        for c in cols:
            self.tree_logs.heading(c, text=c)
        self.tree_logs.column("ID", width=35, anchor="center")
        self.tree_logs.column("Login", width=120)
        self.tree_logs.column("Tenant", width=130)
        self.tree_logs.column("Action", width=100)
        self.tree_logs.column("Details", width=250)
        self.tree_logs.column("Date/Heure", width=130, anchor="center")
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree_logs.yview)
        self.tree_logs.configure(yscrollcommand=sb.set)
        self.tree_logs.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.afficher_logs()

    def afficher_logs(self):
        for row in self.tree_logs.get_children():
            self.tree_logs.delete(row)

        filtre_tenant = self.filtre_log_tenant.get()
        filtre_action = self.filtre_log_action.get()

        query = """SELECT l.id, l.login, COALESCE(t.nom, 'Admin'), l.action, l.details, l.date_heure
                   FROM logs l LEFT JOIN tenants t ON l.tenant_id=t.id WHERE 1=1"""
        params = []

        if filtre_tenant != "Tous":
            tid = int(filtre_tenant.split(" - ")[0])
            query += " AND l.tenant_id=?"
            params.append(tid)

        if filtre_action != "Toutes":
            query += " AND l.action=?"
            params.append(filtre_action)

        query += " ORDER BY l.id DESC LIMIT 200"

        self.cursor.execute(query, params)
        for r in self.cursor.fetchall():
            action_colors = {
                "Connexion": ACCENT_GREEN, "Vente": GOLD,
                "Ajout produit": ACCENT_BLUE, "Suppression": ACCENT_RED,
                "Modification": ACCENT_ORANGE
            }
            self.tree_logs.insert("", "end", values=(r[0], r[1], r[2], r[3], r[4], r[5]))


if __name__ == "__main__":
    app = App()
    app.mainloop()
