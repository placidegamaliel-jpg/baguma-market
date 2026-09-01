import psycopg
import sys

urls = [
    "postgresql://baguma_db_fofl_user:TtrQRIGavjCg52PAHMqHHRZuVN97LswJ@dpg-dabevntcqm1c73dcqlk0-a/baguma_db_fofl",
    "postgresql://baguma_db_fofl_user:TtrQRIGavjCg52PAHMqHHRZuVN97LswJ@dpg-dabevntcqm1c73dcqlk0-a.render.com/baguma_db_fofl",
]
modes = ["disable", "allow", "prefer", "require"]
for url in urls:
    host = url.split("@")[1].split("/")[0]
    for mode in modes:
        try:
            u = url + "?sslmode=" + mode
            c = psycopg.connect(u, connect_timeout=10)
            r = c.execute("SELECT 1").fetchone()
            print("OK sslmode=" + mode + " host=" + host)
            c.close()
            sys.exit(0)
        except Exception as e:
            print("FAIL sslmode=" + mode + " host=" + host + " -> " + str(e)[:80])
print("ALL FAILED")
