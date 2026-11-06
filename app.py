import streamlit as st
import sqlite3, hashlib, secrets, io, json, smtplib, re, calendar
from email.message import EmailMessage
from datetime import datetime, timedelta
from datetime import date
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

st.set_page_config(page_title="SPORT PERFORMANCE MANAGER", page_icon="🏅", layout="wide")
st.markdown("""
<style>
:root { color-scheme: light; }
html, body, [data-testid="stAppViewContainer"], .stApp, [data-testid="stMain"] {
  background:#F7FAFF !important; color:#101828 !important;
}
[data-testid="stHeader"] { background:#F7FAFF !important; }
[data-testid="stMain"] * { color:#101828; }
h1,h2,h3,h4,h5,h6,p,label,.stMarkdown,[data-testid="stCaptionContainer"] { color:#101828 !important; }
h1 { color:#102A43 !important; font-weight:800 !important; letter-spacing:-.7px; }
h2,h3 { color:#0759C7 !important; font-weight:750 !important; }
[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#1264D8 0%,#168BFA 100%) !important;
  border-right:1px solid #24496B; padding-top:1rem;
}
[data-testid="stSidebar"] * { color:#FFFFFF !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] > label {
  color:#BFD7F2 !important; font-size:.78rem; font-weight:800;
  text-transform:uppercase; letter-spacing:1px;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] { gap:7px; }
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {
  background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.10);
  border-radius:11px; padding:9px 12px; transition:all .15s ease;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover {
  background:rgba(255,255,255,.15); border-color:#69A7FF;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
  background:#1677FF; border:1px solid #8AB4FF; box-shadow:0 3px 12px rgba(0,0,0,.18);
}
[data-testid="stSidebar"] button {
  background:#2585E8 !important; border:1px solid #70B7FF !important;
  border-radius:10px !important;
}
.stButton > button,.stDownloadButton > button,button[kind="primary"],[data-testid="stFormSubmitButton"] button {
  background:#155EEF !important; color:#FFFFFF !important; border:1px solid #155EEF !important;
  border-radius:10px !important; font-weight:700 !important; min-height:2.65rem;
}
.stButton > button:hover,.stDownloadButton > button:hover {
  background:#123B66 !important; border-color:#123B66 !important; color:#FFFFFF !important;
}
[data-testid="stMetric"] {
  background:#FFFFFF !important; border:1px solid #D7E3F0 !important;
  padding:16px !important; border-radius:14px !important;
  box-shadow:0 4px 14px rgba(16,42,67,.06);
}
[data-testid="stMetric"] label,[data-testid="stMetric"] [data-testid="stMetricValue"] { color:#102A43 !important; }
div[data-testid="stForm"],[data-testid="stExpander"] {
  background:#FFFFFF !important; border:1px solid #D7E3F0 !important; border-radius:14px !important;
}
div[data-testid="stForm"] * { color:#101828 !important; }
input,textarea,[data-baseweb="select"] > div {
  background:#FFFFFF !important; color:#101828 !important;
  border:1px solid #AABBD0 !important; border-radius:9px !important;
}
input::placeholder,textarea::placeholder { color:#667085 !important; opacity:1 !important; }
[data-baseweb="tab-list"] { gap:8px; border-bottom:1px solid #CBD5E1; }
[data-baseweb="tab"] { background:#FFF7CC !important; border-radius:9px 9px 0 0 !important; }
[data-baseweb="tab"] * { color:#102A43 !important; font-weight:700 !important; }
[data-baseweb="tab"][aria-selected="true"] { background:#155EEF !important; }
[data-baseweb="tab"][aria-selected="true"] * { color:#FFFFFF !important; }
[data-testid="stDataFrame"],[data-testid="stTable"] {
  background:#FFFFFF !important; border:1px solid #D7E3F0; border-radius:12px; overflow:hidden;
}
[data-testid="stAlert"] { border-radius:12px !important; }
hr { border-color:#D7E3F0 !important; }
</style>
""",unsafe_allow_html=True)
DB="sport_performance.db"

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, pwd TEXT, salt TEXT, role TEXT, athlete_id INTEGER, must_change_password INTEGER DEFAULT 0, email TEXT);
    CREATE TABLE IF NOT EXISTS coach_verifications(email TEXT PRIMARY KEY, username TEXT NOT NULL, pwd TEXT NOT NULL, salt TEXT NOT NULL, code_hash TEXT NOT NULL, expires_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS pending_email_changes(user_id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, code_hash TEXT NOT NULL, expires_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS athletes(id INTEGER PRIMARY KEY, first_name TEXT,last_name TEXT,birth TEXT,sex TEXT,weight REAL,height REAL,sport TEXT,team TEXT,hrmax REAL,hrrest REAL,ftp REAL,notes TEXT);
    CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY,athlete_id INTEGER,filename TEXT,sport TEXT,activity_date TEXT,duration REAL,distance REAL,avg_hr REAL,max_hr REAL,avg_power REAL,max_power REAL,avg_speed REAL,cadence REAL,elevation REAL,data TEXT);
    CREATE TABLE IF NOT EXISTS garmin_connections(id INTEGER PRIMARY KEY,athlete_id INTEGER UNIQUE,status TEXT DEFAULT 'pending_consent',consent_at TEXT,last_sync TEXT,external_user_id TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS garmin_sync_events(id INTEGER PRIMARY KEY,athlete_id INTEGER,event_key TEXT UNIQUE,received_at TEXT DEFAULT CURRENT_TIMESTAMP,status TEXT,payload TEXT);

    CREATE TABLE IF NOT EXISTS training_events(id INTEGER PRIMARY KEY, title TEXT NOT NULL, event_type TEXT NOT NULL DEFAULT 'Allenamento', event_date TEXT NOT NULL, start_time TEXT, end_time TEXT, location TEXT, notes TEXT, amount REAL, created_by INTEGER);
    CREATE TABLE IF NOT EXISTS event_attendance(id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, athlete_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'Da segnare', UNIQUE(event_id,athlete_id));
    """)
    for statement in ("ALTER TABLE training_events ADD COLUMN event_type TEXT NOT NULL DEFAULT 'Allenamento'", "ALTER TABLE training_events ADD COLUMN amount REAL"):
        try: c.execute(statement)
        except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except sqlite3.OperationalError: pass
    c.execute("CREATE TABLE IF NOT EXISTS app_settings(setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL)")
    seeded=c.execute("SELECT setting_value FROM app_settings WHERE setting_key='weekly_training_seed_v1'").fetchone()
    if not seeded:
        today=date.today()
        target_year=today.year if today.month<=5 else today.year+1
        end_date=date(target_year,5,31)
        schedule={
            0:("Allenamento","Allenamento pattinaggio","18:00","20:00","Pattinodromo","In caso di pioggia: 18:00–19:30 presso Scuola Villa."),
            1:("Allenamento","Allenamento pattinaggio","18:00","20:00","Pattinodromo",""),
            2:("Allenamento","Allenamento pattinaggio","19:00","20:00","Pattinodromo",""),
            3:("Allenamento","Allenamento pattinaggio","18:00","20:00","Pattinodromo",""),
            4:("Allenamento","Allenamento pattinaggio","18:00","20:00","Pattinodromo","In caso di pioggia: 18:00–19:30 presso Scuola Villa."),
            5:("Attività","Allenamento libero",None,None,"Libero","Attività libera; non conteggiata come presenza/assenza."),
            6:("Attività","Riposo / recupero",None,None,"","Riposo oppure recupero di allenamenti persi; non conteggiato come presenza/assenza.")
        }
        athletes=c.execute("SELECT id FROM athletes").fetchall()
        day=today
        while day<=end_date:
            typ,title,start_time,end_time,location,notes=schedule[day.weekday()]
            cur=c.execute("INSERT INTO training_events(title,event_type,event_date,start_time,end_time,location,notes,created_by) VALUES(?,?,?,?,?,?,?,?)",
                ("[PROGRAMMA] "+title,typ,day.isoformat(),start_time,end_time,location,notes,None))
            if typ=="Allenamento":
                c.executemany("INSERT OR IGNORE INTO event_attendance(event_id,athlete_id,status) VALUES(?,?,?)",
                    [(cur.lastrowid,int(a[0]),"Da segnare") for a in athletes])
            day+=timedelta(days=1)
        c.execute("INSERT INTO app_settings(setting_key,setting_value) VALUES('weekly_training_seed_v1',?)",(end_date.isoformat(),))
    c.execute("""INSERT OR IGNORE INTO event_attendance(event_id,athlete_id,status)
        SELECT e.id,a.id,'Da segnare' FROM training_events e CROSS JOIN athletes a
        WHERE e.title LIKE '[PROGRAMMA]%' AND e.event_type='Allenamento' AND e.event_date>=?""",(date.today().isoformat(),))
    return c
def pw_hash(p,s): return hashlib.pbkdf2_hmac("sha256",p.encode(),s.encode(),200000).hex()
def send_coach_code(to_email, code):
    """Invia codici a qualunque dominio usando il server SMTP configurato dal proprietario."""
    cfg=st.secrets.get("smtp", {})
    required=("host","port","from_email")
    if not all(cfg.get(k) for k in required):
        raise RuntimeError("Configurazione email incompleta: servono host, port e from_email nella sezione [smtp] dei Secrets.")
    host=str(cfg["host"]).strip()
    port=int(cfg["port"])
    security=str(cfg.get("security","starttls")).strip().lower()
    username=str(cfg.get("username","")).strip()
    password=str(cfg.get("password",""))
    msg=EmailMessage()
    msg["Subject"]="Codice di verifica · Sport Performance Manager"
    msg["From"]=str(cfg["from_email"]).strip()
    msg["To"]=to_email
    msg.set_content(f"Il tuo codice di verifica è {code}. Scade tra 10 minuti. Se non hai richiesto questa registrazione, ignora il messaggio.")
    timeout=int(cfg.get("timeout",30))
    if security=="ssl" or port==465:
        with smtplib.SMTP_SSL(host,port,timeout=timeout) as server:
            if username:
                server.login(username,password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host,port,timeout=timeout) as server:
            server.ehlo()
            if security=="starttls":
                server.starttls()
                server.ehlo()
            elif security!="none":
                raise RuntimeError("Valore smtp.security non valido: usa starttls, ssl oppure none.")
            if username:
                server.login(username,password)
            server.send_message(msg)

def render_profile_email(user):
    st.markdown("### Verifica della nuova email")
    st.caption("La nuova email viene salvata solo dopo la verifica del codice.")
    proposed=st.text_input("Nuovo indirizzo email",value=user.get("email") or "",key="profile_new_email",placeholder="nome@esempio.it")
    if st.button("Cambia mail",key="send_profile_email_code",use_container_width=True):
        address=proposed.strip().lower()
        if not address or "@" not in address or "." not in address.split("@")[-1] or any(ch.isspace() for ch in address):
            st.error("Inserisci un indirizzo email valido.")
        elif address == (user.get("email") or "").strip().lower():
            st.info("Questa è già la tua email attuale.")
        else:
            try:
                code=f"{secrets.randbelow(1000000):06d}"
                send_coach_code(address,code)
                with db() as conn:
                    conn.execute("DELETE FROM pending_email_changes WHERE email=? AND user_id<>?",(address,user["id"]))
                    conn.execute("INSERT OR REPLACE INTO pending_email_changes(user_id,email,code_hash,expires_at) VALUES(?,?,?,?)",(user["id"],address,pw_hash(code,"spm-profile-email"),(datetime.utcnow()+timedelta(minutes=10)).isoformat()))
                st.session_state.profile_email_pending=True
                st.success("Codice inviato al nuovo indirizzo. Controlla anche lo spam: scade tra 10 minuti.")
            except Exception as e:
                st.error(f"Invio non riuscito: {e}")
    if st.session_state.get("profile_email_pending"):
        with st.form("verify_profile_email_form"):
            code_input=st.text_input("Codice ricevuto sulla nuova email",max_chars=6)
            verify_email=st.form_submit_button("Verifica mail nuova",use_container_width=True)
        if verify_email:
            with db() as conn:
                pending=conn.execute("SELECT * FROM pending_email_changes WHERE user_id=?",(user["id"],)).fetchone()
                if pending and datetime.fromisoformat(pending["expires_at"])>datetime.utcnow() and secrets.compare_digest(pw_hash(code_input,"spm-profile-email"),pending["code_hash"]):
                    conn.execute("UPDATE users SET email=? WHERE id=?",(pending["email"],user["id"]))
                    conn.execute("DELETE FROM pending_email_changes WHERE user_id=?",(user["id"],))
                    st.session_state.user["email"]=pending["email"]
                    st.session_state.pop("profile_email_pending",None)
                    st.success("Nuova email verificata e salvata.")
                    st.rerun()
                else:
                    st.error("Codice errato o scaduto. Premi Cambia mail per richiederne uno nuovo.")

def q(sql,args=()): 
    with db() as c: return pd.read_sql_query(sql,c,params=args)
def parse(f):
    raw=f.getvalue(); n=f.name.lower()
    if n.endswith(".csv"): d=pd.read_csv(io.BytesIO(raw))
    elif n.endswith(".fit"):
        from fitparse import FitFile
        import tempfile,os
        t=tempfile.NamedTemporaryFile(delete=False,suffix=".fit"); t.write(raw); t.close()
        try: d=pd.DataFrame([{x.name:x.value for x in m} for m in FitFile(t.name).get_messages("record")])
        finally: os.unlink(t.name)
    else:
        import xml.etree.ElementTree as ET
        root=ET.fromstring(raw); rec=[]
        for el in root.iter():
            tag=el.tag.split("}")[-1].lower()
            if tag in ("trackpoint","trkpt"):
                r=dict(el.attrib)
                for x in el.iter():
                    k=x.tag.split("}")[-1].lower()
                    if k in ("time","heartratebpm","value","watts","cadence","altitudemeters","ele","distancemeters") and x.text: r[k]=x.text
                rec.append(r)
        d=pd.DataFrame(rec)
    aliases={"heart_rate":["heart_rate","heartrate","hr","heart_rate_bpm","value"],"power":["power","watts"],"speed":["speed","enhanced_speed"],"cadence":["cadence"],"altitude":["altitude","altitudemeters","ele"],"distance":["distance","distancemeters"],"timestamp":["timestamp","time"]}
    cols={str(x).lower():x for x in d.columns}; ren={}
    for target,opts in aliases.items():
        for k in opts:
            if k in cols: ren[cols[k]]=target; break
    d=d.rename(columns=ren)
    for k in ["heart_rate","power","speed","cadence","altitude","distance"]:
        if k in d: d[k]=pd.to_numeric(d[k],errors="coerce")
    if "timestamp" in d: d["timestamp"]=pd.to_datetime(d.timestamp,errors="coerce",utc=True)
    return d
def stats(d):
    m=lambda k: float(d[k].mean()) if k in d and d[k].notna().any() else None
    mx=lambda k: float(d[k].max()) if k in d and d[k].notna().any() else None
    duration=(d.timestamp.max()-d.timestamp.min()).total_seconds() if "timestamp" in d and d.timestamp.notna().sum()>1 else None
    distance=float(d.distance.max()-d.distance.min()) if "distance" in d and d.distance.notna().sum()>1 else (mx("distance"))
    elevation=float(d.altitude.diff().clip(lower=0).sum()) if "altitude" in d else None
    dt=str(d.timestamp.min().date()) if "timestamp" in d and d.timestamp.notna().any() else str(date.today())
    return [dt,duration,distance,m("heart_rate"),mx("heart_rate"),m("power"),mx("power"),m("speed"),m("cadence"),elevation]
def ftp_analysis(d, protocol, weight):
    if "power" not in d or d["power"].notna().sum() < 30:
        return {"error":"Il file non contiene abbastanza campioni di potenza validi."}
    p = pd.to_numeric(d["power"], errors="coerce").dropna().clip(lower=0)
    if "timestamp" in d and d["timestamp"].notna().sum() > 30:
        z = d[["timestamp","power"]].dropna().sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
        z = z.resample("1s").mean().interpolate(limit=5)
        p = z["power"].dropna()
    else:
        p = p.reset_index(drop=True)
    if len(p) < 30:
        return {"error":"Campioni insufficienti dopo la pulizia dei dati."}
    windows = {}
    for seconds in [5,15,30,60,300,600,1200,1800,3600]:
        if len(p) >= seconds:
            windows[seconds] = float(p.rolling(seconds).mean().max())
    mean_power = float(p.mean())
    max_power = float(p.max())
    ftp = None
    if protocol == "20 minuti (stima 95%)":
        ftp = windows.get(1200) * 0.95 if windows.get(1200) is not None else None
        method = "95% della migliore media su 20 minuti" if ftp else "Test troppo breve: servono almeno 20 minuti"
    elif protocol == "60 minuti":
        ftp = windows.get(3600)
        method = "Migliore media su 60 minuti" if ftp else "Servono almeno 60 minuti di dati"
    elif protocol == "FTP inserito manualmente":
        method = "FTP manuale: inserire il valore verificato nel profilo atleta"
    else:
        method = "Ramp test: nessuna conversione automatica; serve il protocollo specifico"
    wkg = ftp / weight if ftp and weight and weight > 0 else None
    zones = []
    if ftp:
        bounds = [("Z1 Recupero",0,.55),("Z2 Resistenza",.56,.75),("Z3 Tempo",.76,.90),("Z4 Soglia",.91,1.05),("Z5 VO2max",1.06,1.20),("Z6 Anaerobica",1.21,1.50),("Z7 Neuromuscolare",1.51,None)]
        for name, lo, hi in bounds:
            zones.append((name, round(ftp*lo), round(ftp*hi) if hi else "oltre"))
    notes = []
    if ftp:
        notes.append("FTP stimata: %.0f W%s" % (ftp, (" (%.2f W/kg)" % wkg) if wkg else ""))
        notes.append("La stima da 20 minuti è un'indicazione e va confermata con un test validato; non equivale a una misura diretta della soglia.")
    else:
        notes.append(method + ".")
    return {"ftp":ftp,"wkg":wkg,"method":method,"mean":mean_power,"peak":max_power,"duration":len(p),"windows":windows,"zones":zones,"notes":notes,"protocol":protocol}

def ftp_pdf(ath, activity, result, weight, comment):
    b = io.BytesIO()
    doc = SimpleDocTemplate(b, pagesize=A4, rightMargin=1.6*cm, leftMargin=1.6*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallSPM", parent=styles["BodyText"], fontSize=8, leading=11))
    story = [Paragraph("SPORT PERFORMANCE MANAGER", styles["Title"]), Paragraph("REPORT TEST FTP · ANALISI DELLA POTENZA", styles["Heading2"]), Spacer(1,8), Paragraph("<b>Atleta:</b> %s &nbsp;&nbsp; <b>Data:</b> %s &nbsp;&nbsp; <b>Peso:</b> %s kg" % (ath, activity[0], weight if weight else "n.d."), styles["BodyText"]), Spacer(1,12)]
    if result.get("error"):
        story.append(Paragraph(result["error"], styles["BodyText"]))
    else:
        rows = [["Indicatore","Risultato"],["Protocollo",result["protocol"]],["Metodo",result["method"]],["FTP",("%.0f W" % result["ftp"]) if result["ftp"] else "Non stimabile"],["FTP relativa",("%.2f W/kg" % result["wkg"]) if result["wkg"] else "Non disponibile"],["Potenza media","%.0f W" % result["mean"]],["Picco registrato","%.0f W" % result["peak"]],["Durata analizzata","%.1f min" % (result["duration"]/60)]]
        t = Table(rows, colWidths=[6*cm,10*cm])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#142B45")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#CBD5E1")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F1F5F9")]),("PADDING",(0,0),(-1,-1),7)]))
        story += [t, Spacer(1,12), Paragraph("Profilo di potenza",styles["Heading2"])]
        rows = [["Durata","Miglior media"]] + [[("%d sec" % s) if s < 60 else ("%d min" % (s//60)), "%.0f W" % v] for s,v in result["windows"].items()]
        t = Table(rows, colWidths=[6*cm,10*cm])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#142B45")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#CBD5E1")),("PADDING",(0,0),(-1,-1),6)]))
        story += [t, Spacer(1,12)]
        if result["zones"]:
            story.append(Paragraph("Zone di potenza calcolate sulla FTP",styles["Heading2"]))
            z = Table([["Zona","Intervallo"]] + [[n,"%s–%s W" % (lo,hi)] for n,lo,hi in result["zones"]], colWidths=[8*cm,8*cm])
            z.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#142B45")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#CBD5E1")),("PADDING",(0,0),(-1,-1),6)]))
            story += [z, Spacer(1,10)]
        story.append(Paragraph("Interpretazione e prossimi passi",styles["Heading2"]))
        for note in result["notes"]:
            story.append(Paragraph("• " + note, styles["SmallSPM"]))
    story += [Spacer(1,12), Paragraph("Commento allenatore",styles["Heading2"]), Paragraph(comment or "Nessun commento inserito.",styles["BodyText"]), Spacer(1,8), Paragraph("Nota metodologica: i valori sono calcolati sui campioni presenti nel file. Le finestre non disponibili non vengono stimate. Le zone sono un riferimento operativo da personalizzare.",styles["SmallSPM"])]
    doc.build(story)
    return b.getvalue()

def report(ath,activity,comment):
    b=io.BytesIO(); doc=SimpleDocTemplate(b,pagesize=A4); styles=getSampleStyleSheet()
    data=[["Parametro","Valore"],["Data",activity[0]],["Durata (s)",activity[1]],["Distanza (m)",activity[2]],["FC media / max",f"{activity[3]} / {activity[4]}"],["Potenza media / max",f"{activity[5]} / {activity[6]}"],["Velocità media (m/s)",activity[7]],["Cadenza",activity[8]],["Dislivello positivo (m)",activity[9]]]
    doc.build([Paragraph("SPORT PERFORMANCE MANAGER",styles["Title"]),Paragraph(f"Atleta: {ath}",styles["Heading2"]),Table(data),Spacer(1,16),Paragraph("Commento allenatore",styles["Heading2"]),Paragraph(comment or "Nessun commento inserito.",styles["BodyText"])])
    return b.getvalue()
db().close()
users=q("SELECT * FROM users")
if "user" not in st.session_state:
    st.title("🏅 SPORT PERFORMANCE MANAGER")
    st.caption("Allenamento, dati e performance in un unico spazio")
    coach_tab, athlete_tab = st.tabs(["👨‍🏫 Allenatore","🏃 Atleta"])
    with coach_tab:
        st.subheader("Area allenatore")
        login_col, signup_col = st.columns(2)
        with login_col:
            st.markdown("#### Accedi")
            with st.form("coach_login"):
                cu=st.text_input("Username allenatore")
                cp=st.text_input("Password",type="password")
                coach_login=st.form_submit_button("Accedi",use_container_width=True)
            if coach_login:
                row=users[users.username.astype(str).str.strip().str.casefold()==cu.strip().casefold()]
                if len(row) and str(row.iloc[0].role).lower() not in ("athlete","atleta") and secrets.compare_digest(pw_hash(cp,row.iloc[0].salt),row.iloc[0].pwd):
                    st.session_state.user=row.iloc[0].to_dict(); st.rerun()
                else: st.error("Credenziali non valide. Verifica username e password.")
        with signup_col:
            st.markdown("#### Crea account allenatore")
            with st.form("coach_signup"):
                nu=st.text_input("Username")
                np=st.text_input("Password (almeno 12 caratteri)",type="password")
                np2=st.text_input("Conferma password",type="password")
                create_account=st.form_submit_button("Crea account",use_container_width=True)
            if create_account:
                username=nu.strip().lower()
                if not username or not np or len(np)<12 or np!=np2:
                    st.error("Inserisci uno username e due password uguali di almeno 12 caratteri.")
                elif users.username.astype(str).str.strip().str.casefold().eq(username).any():
                    st.error("Username già utilizzato. Scegline un altro.")
                else:
                    salt=secrets.token_hex(16)
                    with db() as conn:
                        conn.execute("INSERT INTO users(username,pwd,salt,role,athlete_id,must_change_password,email) VALUES(?,?,?,'coach',NULL,0,NULL)",(username,pw_hash(np,salt),salt))
                    st.success("Account creato. Ora puoi accedere con username e password.")
                    st.rerun()
    with athlete_tab:
        st.subheader("Area atleta")
        st.info("L'allenatore crea il profilo e consegna le credenziali temporanee. Al primo accesso la password va cambiata.")
        with st.form("athlete_login"):
            au=st.text_input("Username atleta")
            ap=st.text_input("Password",type="password")
            athlete_login=st.form_submit_button("Accedi come atleta",use_container_width=True)
        if athlete_login:
            row=users[(users.username==au.strip().lower()) & (users.role=="athlete")]
            if len(row) and secrets.compare_digest(pw_hash(ap,row.iloc[0].salt),row.iloc[0].pwd):
                st.session_state.user=row.iloc[0].to_dict(); st.rerun()
            else: st.error("Credenziali atleta non valide.")
    st.stop()
user=st.session_state.user
if int(user.get("must_change_password") or 0)==1:
    st.title("Primo accesso · crea la tua password")
    st.info("La password provvisoria deve essere sostituita con una password personale di almeno 12 caratteri.")
    with st.form("force_password_change"):
        p1=st.text_input("Nuova password",type="password")
        p2=st.text_input("Ripeti nuova password",type="password")
        save=st.form_submit_button("Salva nuova password")
    if save:
        if len(p1)<12 or p1!=p2:
            st.error("Le password devono coincidere e contenere almeno 12 caratteri.")
        else:
            salt=secrets.token_hex(16)
            with db() as conn:
                conn.execute("UPDATE users SET pwd=?,salt=?,must_change_password=0 WHERE id=?",(pw_hash(p1,salt),salt,user["id"]))
            st.session_state.user["pwd"]=pw_hash(p1,salt)
            st.session_state.user["salt"]=salt
            st.session_state.user["must_change_password"]=0
            st.success("Password aggiornata.")
            st.rerun()
    st.stop()
with st.sidebar:
    st.title("🏅 SPM"); st.caption(user["username"]+" · "+user["role"])
    if st.button("Esci"): del st.session_state.user; st.rerun()
    menu=["Dashboard","Calendario","Registro presenze","Riepilogo mensile","Atleti","Carica attività","Garmin Connect","Archivio","Confronti","Backup","Profilo"] if user["role"]=="coach" else ["La mia dashboard","Le mie attività","Calendario","Registro presenze","Profilo"]
    page=st.radio("NAVIGAZIONE",menu)
if user["role"]=="athlete":
    aid=user["athlete_id"]
    a=q("SELECT * FROM athletes WHERE id=?",(aid,))
    if a.empty: st.error("Profilo non associato."); st.stop()
    if page=="Profilo":
        st.title("Il mio profilo")
        athlete=a.iloc[0]
        st.subheader(f"{athlete.first_name} {athlete.last_name}")
        st.caption("Dati anagrafici e impostazioni di accesso")
        c1,c2,c3=st.columns(3)
        c1.metric("Sport",athlete.sport or "Non indicato")
        c2.metric("Società",athlete.team or "Non indicata")
        c3.metric("Username",user["username"])
        st.divider()
        st.markdown("**Dati account**")
        with st.form("profile_settings"):
            st.markdown("**Modifica password**")
            new_password=st.text_input("Nuova password (lascia vuoto per non modificarla)",type="password")
            confirm_password=st.text_input("Conferma nuova password",type="password")
            save_profile=st.form_submit_button("Salva modifiche",use_container_width=True)
        if save_profile:
            if bool(new_password) != bool(confirm_password) or (new_password and (len(new_password)<12 or new_password!=confirm_password)):
                st.error("Per cambiare password inserisci due valori uguali di almeno 12 caratteri.")
            else:
                if new_password:
                    salt=secrets.token_hex(16)
                    with db() as conn:
                        conn.execute("UPDATE users SET pwd=?,salt=? WHERE id=?",(pw_hash(new_password,salt),salt,user["id"]))
                    st.session_state.user["pwd"]=pw_hash(new_password,salt)
                    st.session_state.user["salt"]=salt
                st.success("Password aggiornata." if new_password else "Nessuna modifica alla password.")
                st.rerun()
        st.info("I dati sportivi e anagrafici sono gestiti dall'allenatore.")
        st.stop()
    if page=="Calendario":
        st.title("Il mio calendario")
        events=q("SELECT e.*,COALESCE(a.status,'') AS presenza FROM training_events e JOIN event_attendance a ON a.event_id=e.id WHERE a.athlete_id=? ORDER BY e.event_date,e.start_time,e.id",(aid,))
        if events.empty:
            st.info("Non hai ancora eventi assegnati dall'allenatore.")
        else:
            events["event_date"]=pd.to_datetime(events["event_date"],errors="coerce").dt.date
            selected_day=st.date_input("Seleziona giorno",value=date.today(),key="athlete_calendar_day")
            daily=events[events["event_date"]==selected_day]
            st.subheader(selected_day.strftime("%A %d/%m/%Y"))
            if daily.empty: st.caption("Nessun evento assegnato in questa data.")
            for _,ev in daily.iterrows():
                with st.container(border=True):
                    st.markdown("**"+str(ev["event_type"])+" · "+str(ev["title"])+"**")
                    if ev["start_time"]: st.write(str(ev["start_time"])+" – "+str(ev["end_time"] or ""))
                    if ev["location"]: st.write("Luogo: "+str(ev["location"]))
                    if ev["event_type"] in ["Allenamento","Gara"]:
                        status=str(ev["presenza"] or "Da segnare")
                        if status=="Assente": st.error("Assenza registrata")
                        elif status=="Presente": st.success("Presenza registrata")
                        elif status=="In ritardo": st.warning("Presenza registrata · in ritardo")
                        elif status=="Giustificato": st.info("Assenza giustificata")
                        else: st.caption("Presenza non ancora registrata")
                        if selected_day==date.today():
                            now=datetime.now(ZoneInfo("Europe/Rome"))
                            cutoff=datetime.combine(selected_day,datetime.strptime("14:00","%H:%M").time(),tzinfo=ZoneInfo("Europe/Rome"))
                            if now<=cutoff:
                                with st.form("athlete_today_attendance_"+str(ev["id"])):
                                    current=status if status in ["Presente","Assente"] else "Presente"
                                    choice=st.radio("Presenza",["Presente","Assente"],horizontal=True,index=["Presente","Assente"].index(current))
                                    confirm=st.form_submit_button("Conferma")
                                if confirm:
                                    with db() as conn:
                                        conn.execute("UPDATE event_attendance SET status=? WHERE event_id=? AND athlete_id=?",(choice,int(ev["id"]),aid))
                                    st.success("Conferma salvata."); st.rerun()
                            else:
                                st.warning("Conferma chiusa: il limite è alle 14:00.")
                    if ev["notes"]: st.info(str(ev["notes"]))
            with st.expander("Tutti i miei eventi"):
                st.dataframe(events.drop(columns=["id","created_by"],errors="ignore"),use_container_width=True,hide_index=True)
        st.stop()
    if page=="Registro presenze":
        st.title("Il mio registro presenze")
        st.caption("Riepilogo delle presenze e delle assenze registrate dall'allenatore.")
        mode=st.radio("Periodo",["Settimana","Mese","Anno"],horizontal=True,key="ath_att_period")
        ref=st.date_input("Data di riferimento",value=date.today(),key="ath_att_ref")
        if mode=="Settimana":
            first=ref-timedelta(days=ref.weekday()); last=first+timedelta(days=6)
        elif mode=="Mese":
            first=ref.replace(day=1); last=(first+timedelta(days=32)).replace(day=1)-timedelta(days=1)
        else:
            first=date(ref.year,1,1); last=date(ref.year,12,31)
        data=q("SELECT e.event_date AS Data,e.start_time AS Ora,e.title AS Evento,a.status AS Esito FROM event_attendance a JOIN training_events e ON e.id=a.event_id WHERE a.athlete_id=? AND e.event_type IN ('Allenamento','Gara') AND e.event_date BETWEEN ? AND ? ORDER BY e.event_date DESC,e.start_time DESC",(aid,first.isoformat(),last.isoformat()))
        present=int(data["Esito"].isin(["Presente","In ritardo"]).sum()) if not data.empty else 0
        absent=int(data["Esito"].isin(["Assente","Giustificato"]).sum()) if not data.empty else 0
        c1,c2,c3=st.columns(3); c1.metric("Presenze",present); c2.metric("Assenze",absent); c3.metric("Da registrare",int(data["Esito"].isin(["Da segnare"]).sum()) if not data.empty else 0)
        if data.empty: st.info("Nessun allenamento o gara nel periodo.")
        else: st.dataframe(data,use_container_width=True,hide_index=True)
        st.stop()
    acts=q("SELECT * FROM activities WHERE athlete_id=? ORDER BY activity_date DESC",(aid,))
    st.title("La mia dashboard" if page=="La mia dashboard" else "Le mie attività")
    st.metric("Attività registrate",len(acts)); st.dataframe(acts.drop(columns=["data"],errors="ignore"),use_container_width=True); st.stop()
if page=="Calendario":
    st.title("Calendario allenamenti, gare e scadenze")
    st.caption("Crea eventi e assegna ciascun evento agli atleti interessati. Gli atleti vedranno solo gli eventi assegnati al proprio account.")
    athletes_list=q("SELECT id,first_name,last_name FROM athletes ORDER BY last_name,first_name")
    with st.expander("＋ Crea nuovo evento",expanded=True):
        with st.form("calendar_create_form"):
            kind=st.selectbox("Categoria",["Allenamento","Gara","Pagamento / quota","Visita / test","Riunione","Scadenza","Altro"])
            title=st.text_input("Titolo / descrizione *")
            event_day=st.date_input("Data",value=date.today())
            c1,c2=st.columns(2)
            start=c1.time_input("Ora inizio",value=datetime.strptime("17:00","%H:%M").time())
            end=c2.time_input("Ora fine",value=datetime.strptime("18:30","%H:%M").time())
            location=st.text_input("Luogo")
            notes=st.text_area("Dettagli, scadenze o istruzioni")
            chosen_athletes=st.multiselect("Assegna agli atleti",athletes_list.id.tolist(),format_func=lambda i: str(athletes_list[athletes_list.id==i].iloc[0].first_name)+" "+str(athletes_list[athletes_list.id==i].iloc[0].last_name))
            save_event=st.form_submit_button("Aggiungi al calendario",use_container_width=True)
        if save_event:
            is_training=kind in ["Allenamento","Gara"]
            if not title.strip(): st.error("Il titolo è obbligatorio.")
            elif not chosen_athletes: st.error("Seleziona almeno un atleta.")
            elif is_training and end<=start: st.error("L'ora di fine deve essere successiva all'inizio.")
            else:
                with db() as conn:
                    cur=conn.execute("INSERT INTO training_events(title,event_type,event_date,start_time,end_time,location,notes,created_by) VALUES(?,?,?,?,?,?,?,?)",(title.strip(),kind,event_day.isoformat(),start.strftime("%H:%M") if is_training else None,end.strftime("%H:%M") if is_training else None,location.strip(),notes.strip(),user["id"]))
                    status="Da segnare" if is_training else "N/A"
                    conn.executemany("INSERT INTO event_attendance(event_id,athlete_id,status) VALUES(?,?,?)",[(cur.lastrowid,int(aid),status) for aid in chosen_athletes])
                st.success("Evento creato e assegnato agli atleti.")
                st.rerun()
    events=q("SELECT e.*,COUNT(a.athlete_id) AS assegnati FROM training_events e LEFT JOIN event_attendance a ON a.event_id=e.id GROUP BY e.id ORDER BY e.event_date,e.start_time")
    st.subheader("Eventi in calendario")
    if "coach_cal_month" not in st.session_state: st.session_state.coach_cal_month=date.today().replace(day=1)
    month=st.session_state.coach_cal_month
    prev_col,month_col,next_col=st.columns([1,3,1])
    if prev_col.button("← Mese precedente",key="coach_month_prev"):
        st.session_state.coach_cal_month=(month-timedelta(days=1)).replace(day=1); st.rerun()
    month_col.markdown("### "+month.strftime("%B %Y").capitalize())
    if next_col.button("Mese successivo →",key="coach_month_next"):
        st.session_state.coach_cal_month=(month.replace(day=28)+timedelta(days=4)).replace(day=1); st.rerun()
    last_day=(month.replace(day=28)+timedelta(days=4)).replace(day=1)-timedelta(days=1)
    events=q("SELECT e.*,COUNT(a.athlete_id) AS assegnati FROM training_events e LEFT JOIN event_attendance a ON a.event_id=e.id WHERE e.event_date BETWEEN ? AND ? GROUP BY e.id ORDER BY e.event_date,e.start_time",(month.isoformat(),last_day.isoformat()))
    headers=st.columns(7)
    for col,label in zip(headers,["Lun","Mar","Mer","Gio","Ven","Sab","Dom"]): col.markdown("**"+label+"**")
    for week in calendar.monthcalendar(month.year,month.month):
        cols=st.columns(7)
        for col,daynum in zip(cols,week):
            with col:
                if not daynum:
                    st.markdown("<div style=\"height:105px\"></div>",unsafe_allow_html=True)
                    continue
                day=date(month.year,month.month,daynum)
                todays=events[events["event_date"].astype(str)==day.isoformat()]
                details=[]
                for _,ev in todays.iterrows():
                    details.append("<div style=\"font-size:11px;background:#FFF7CC;border-left:3px solid #1677FF;padding:4px;margin-top:3px;border-radius:4px\">"+str(ev["event_type"])+"<br>"+str(ev["title"])[:22]+"</div>")
                bg="#DBEAFE" if day==date.today() else "#FFFFFF"
                st.markdown("<div style=\"min-height:105px;border:1px solid #CBD5E1;border-radius:9px;padding:5px;background:"+bg+"\"><b>"+str(daynum)+"</b>"+"".join(details)+"</div>",unsafe_allow_html=True)
    st.subheader("Eventi del mese")
    if events.empty: st.info("Nessun evento nel mese selezionato.")
    else:
        for _,ev in events.iterrows():
            with st.container(border=True):
                st.markdown("**"+str(ev["event_date"])+" · "+str(ev["event_type"])+" · "+str(ev["title"])+"**")
                if ev["start_time"]: st.write(str(ev["start_time"])+" – "+str(ev["end_time"] or ""))
                if ev["location"]: st.write("Luogo: "+str(ev["location"]))
                st.caption(str(int(ev["assegnati"]))+" atleti assegnati")
                if ev["notes"]: st.write(str(ev["notes"]))
    with st.expander("Gestisci o elimina un evento"):
                selected=st.selectbox("Evento",events.id.tolist(),format_func=lambda i: str(events[events.id==i].iloc[0].event_date)+" · "+str(events[events.id==i].iloc[0].title))
                if st.button("Elimina evento selezionato",type="secondary"):
                    with db() as conn:
                        conn.execute("DELETE FROM event_attendance WHERE event_id=?",(selected,))
                        conn.execute("DELETE FROM training_events WHERE id=?",(selected,))
                    st.success("Evento eliminato."); st.rerun()
elif page=="Registro presenze":
    st.title("Registro presenze e assenze")
    st.caption("La modifica è consentita fino alle 14:00 (ora italiana) del giorno dell'allenamento o della gara. Dopo tale orario il registro è bloccato.")
    period=st.radio("Visualizzazione",["Settimana","Mese","Anno"],horizontal=True,key="coach_att_period")
    ref=st.date_input("Data di riferimento",value=date.today(),key="coach_att_ref")
    if period=="Settimana":
        first=ref-timedelta(days=ref.weekday()); last=first+timedelta(days=6)
    elif period=="Mese":
        first=ref.replace(day=1); last=(first+timedelta(days=32)).replace(day=1)-timedelta(days=1)
    else:
        first=date(ref.year,1,1); last=date(ref.year,12,31)
    st.caption("Periodo: "+first.strftime("%d/%m/%Y")+" – "+last.strftime("%d/%m/%Y"))
    events=q("SELECT id,event_date,start_time,title,event_type FROM training_events WHERE event_type IN ('Allenamento','Gara') AND event_date BETWEEN ? AND ? ORDER BY event_date,start_time",(first.isoformat(),last.isoformat()))
    if events.empty: st.info("Nessun allenamento o gara nel periodo selezionato.")
    else:
        selected=st.selectbox("Seleziona allenamento / gara",events.id.tolist(),format_func=lambda i: str(events[events.id==i].iloc[0].event_date)+" · "+str(events[events.id==i].iloc[0].title))
        event_row=events[events.id==selected].iloc[0]
        event_date_value=date.fromisoformat(str(event_row.event_date))
        cutoff=datetime.combine(event_date_value,datetime.strptime("14:00","%H:%M").time(),tzinfo=ZoneInfo("Europe/Rome"))
        now=datetime.now(ZoneInfo("Europe/Rome"))
        can_edit=now<=cutoff
        if not can_edit: st.warning("Orario limite superato: questo appuntamento non può più essere modificato.")
        roster=q("SELECT a.id,a.first_name,a.last_name,e.status FROM event_attendance e JOIN athletes a ON a.id=e.athlete_id WHERE e.event_id=? ORDER BY a.last_name,a.first_name",(selected,))
        if roster.empty: st.info("Nessun atleta è stato assegnato a questo evento.")
        else:
            with st.form("attendance_mark_form"):
                values={}
                options=["Da segnare","Presente","Assente","In ritardo","Giustificato"]
                for _,ath in roster.iterrows():
                    c1,c2=st.columns([2,2])
                    c1.write(str(ath["first_name"])+" "+str(ath["last_name"]))
                    current=ath["status"] if ath["status"] in options else "Da segnare"
                    values[int(ath["id"])]=c2.selectbox("Stato",options,index=options.index(current),key="attendance_"+str(selected)+"_"+str(ath["id"]),disabled=not can_edit)
                save=st.form_submit_button("Salva presenze e assenze",disabled=not can_edit,use_container_width=True)
            if save and can_edit:
                with db() as conn:
                    for athlete_id,status in values.items():
                        conn.execute("UPDATE event_attendance SET status=? WHERE event_id=? AND athlete_id=?",(status,selected,athlete_id))
                st.success("Registro presenze aggiornato."); st.rerun()
    totals=q("SELECT a.id,a.first_name||' '||a.last_name AS Atleta, SUM(CASE WHEN ea.status IN ('Presente','In ritardo') THEN 1 ELSE 0 END) AS Presenze, SUM(CASE WHEN ea.status IN ('Assente','Giustificato') THEN 1 ELSE 0 END) AS Assenze, SUM(CASE WHEN ea.status='Da segnare' THEN 1 ELSE 0 END) AS Da_segnare FROM athletes a LEFT JOIN event_attendance ea ON ea.athlete_id=a.id LEFT JOIN training_events te ON te.id=ea.event_id AND te.event_type IN ('Allenamento','Gara') AND te.event_date BETWEEN ? AND ? GROUP BY a.id ORDER BY a.last_name,a.first_name",(first.isoformat(),last.isoformat()))
    # Escludi eventi fuori periodo dai totali, mantenendo anche gli atleti a zero.
    totals=q("SELECT a.id,a.first_name||' '||a.last_name AS Atleta, SUM(CASE WHEN ea.status IN ('Presente','In ritardo') THEN 1 ELSE 0 END) AS Presenze, SUM(CASE WHEN ea.status IN ('Assente','Giustificato') THEN 1 ELSE 0 END) AS Assenze, SUM(CASE WHEN ea.status='Da segnare' THEN 1 ELSE 0 END) AS Da_segnare FROM athletes a LEFT JOIN event_attendance ea ON ea.athlete_id=a.id LEFT JOIN training_events te ON te.id=ea.event_id WHERE te.event_type IN ('Allenamento','Gara') AND te.event_date BETWEEN ? AND ? GROUP BY a.id ORDER BY a.last_name,a.first_name",(first.isoformat(),last.isoformat()))
    st.subheader("Totali del periodo per atleta")
    if totals.empty:
        st.info("Nessuna presenza o assenza registrata nel periodo.")
    else:
        st.dataframe(totals.drop(columns=["id"]),use_container_width=True,hide_index=True)
        p=int(totals["Presenze"].sum()); a=int(totals["Assenze"].sum())
        x,y=st.columns(2); x.metric("Presenze totali",p); y.metric("Assenze totali",a)
elif page=="Dashboard":
    aa=q("SELECT * FROM athletes"); acts=q("SELECT a.*,t.first_name||' '||t.last_name atleta FROM activities a JOIN athletes t ON t.id=a.athlete_id")
    st.title("Dashboard allenatore"); x,y,z=st.columns(3); x.metric("Atleti",len(aa)); y.metric("Attività",len(acts)); z.metric("Sport",aa.sport.nunique() if len(aa) else 0)
    st.dataframe(acts.drop(columns=["data"],errors="ignore"),use_container_width=True)
elif page=="Riepilogo mensile":
    st.title("Riepilogo mensile")
    st.caption("Volume di allenamento per atleta e disciplina, aggiornato con tutte le attività caricate")
    d=q("SELECT a.*,t.first_name||' '||t.last_name atleta FROM activities a JOIN athletes t ON t.id=a.athlete_id")
    if d.empty:
        st.info("Non ci sono ancora attività. Carica un file o collega Garmin quando l'integrazione sarà attiva.")
    else:
        d["data_dt"]=pd.to_datetime(d["activity_date"],errors="coerce")
        d=d.dropna(subset=["data_dt"]).copy()
        d["mese"]=d["data_dt"].dt.strftime("%Y-%m")
        months=sorted(d["mese"].dropna().unique(),reverse=True)
        month=st.selectbox("Mese",months,index=0)
        athletes=["Tutti gli atleti"]+sorted(d["atleta"].dropna().unique().tolist())
        who=st.selectbox("Atleta",athletes)
        v=d[d["mese"]==month].copy()
        if who!="Tutti gli atleti": v=v[v["atleta"]==who]
        def disciplina(x):
            s=str(x).strip().lower()
            if "patt" in s or "skate" in s: return "Pattinaggio"
            if "corr" in s or "run" in s: return "Corsa"
            if "cicl" in s or "bik" in s or "cycling" in s: return "Bici"
            if "pales" in s or "gym" in s or "strength" in s: return "Palestra"
            if "nuot" in s or "swim" in s: return "Nuoto"
            if "triathlon" in s: return "Triathlon"
            return str(x).strip() or "Altro"
        v["disciplina"]=v["sport"].apply(disciplina)
        for col in ["distance","duration","elevation","avg_hr","avg_power"]:
            if col in v: v[col]=pd.to_numeric(v[col],errors="coerce")
        v["km"]=v["distance"].clip(lower=0)/1000
        v["ore"]=v["duration"].clip(lower=0)/3600
        total_km=v["km"].sum(min_count=1)
        total_h=v["ore"].sum(min_count=1)
        total_elev=v["elevation"].clip(lower=0).sum(min_count=1)
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Attività",len(v))
        m2.metric("Distanza",f"{total_km:,.1f} km".replace(",", "X").replace(".", ",").replace("X",".") if pd.notna(total_km) else "N/D")
        m3.metric("Tempo",f"{total_h:,.1f} h".replace(",", "X").replace(".", ",").replace("X",".") if pd.notna(total_h) else "N/D")
        m4.metric("Dislivello positivo",f"{total_elev:,.0f} m".replace(",", ".") if pd.notna(total_elev) else "N/D")
        st.subheader("Volume per disciplina")
        agg=v.groupby("disciplina",dropna=False).agg(Attivita=("id","count"),Chilometri=("km","sum"),Ore=("ore","sum"),Dislivello_m=("elevation","sum"),FC_media=("avg_hr","mean"),Potenza_media=("avg_power","mean")).reset_index()
        agg=agg.rename(columns={"disciplina":"Disciplina","Dislivello_m":"Dislivello (m)","FC_media":"FC media (bpm)","Potenza_media":"Potenza media (W)"})
        st.dataframe(agg.round(1),use_container_width=True,hide_index=True)
        if len(agg):
            st.plotly_chart(px.bar(agg,x="Disciplina",y="Chilometri",color="Disciplina",title="Chilometri mensili per disciplina",text_auto=".1f"),use_container_width=True)
        st.subheader("Riepilogo per atleta")
        by_ath=v.groupby("atleta").agg(Attivita=("id","count"),Chilometri=("km","sum"),Ore=("ore","sum"),Dislivello_m=("elevation","sum")).reset_index().sort_values("Chilometri",ascending=False)
        st.dataframe(by_ath.round(1),use_container_width=True,hide_index=True)
        st.subheader("Dettaglio attività del mese")
        st.dataframe(v[["data_dt","atleta","sport","filename","km","ore","avg_hr","avg_power","elevation"]].rename(columns={"data_dt":"Data","atleta":"Atleta","sport":"Sport","filename":"File","km":"Km","ore":"Ore","avg_hr":"FC media","avg_power":"Potenza media","elevation":"Dislivello m"}).round(2),use_container_width=True,hide_index=True)
elif page=="Atleti":
    st.title("Anagrafica atleti")
    with st.form("ath"):
        a,b,c=st.columns(3); fn=a.text_input("Nome*"); ln=b.text_input("Cognome*"); birth=c.date_input("Data nascita",value=None,min_value=date(1950,1,1),max_value=date.today())
        a,b,c=st.columns(3); sex=a.selectbox("Sesso",["Non specificato","F","M","Altro"]); weight=b.number_input("Peso kg",0.,250.); height=c.number_input("Altezza cm",0.,250.)
        a,b,c=st.columns(3); sport=a.selectbox("Sport",["Ciclismo","Corsa","Pattinaggio","Palestra","Triathlon","Nuoto","Altro"]); team=b.text_input("Società"); ftp=c.number_input("FTP W",0.,2000.)
        a,b=st.columns(2); hrmax=a.number_input("FC max",0,250); hrrest=b.number_input("FC riposo",0,150); notes=st.text_area("Note")
        ok=st.form_submit_button("Salva atleta")
    if ok:
        if not fn or not ln: st.error("Nome e cognome obbligatori.")
        else:
            with db() as c: c.execute("INSERT INTO athletes(first_name,last_name,birth,sex,weight,height,sport,team,hrmax,hrrest,ftp,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(fn,ln,str(birth) if birth else None,sex,weight or None,height or None,sport,team,hrmax or None,hrrest or None,ftp or None,notes))
            st.success("Atleta salvato."); st.rerun()
    aa=q("SELECT * FROM athletes ORDER BY last_name"); st.dataframe(aa.drop(columns=["notes"],errors="ignore"),use_container_width=True)
    if len(aa):
        with st.expander("Crea account atleta"):
            with st.form("user"):
                aid=st.selectbox("Atleta",aa.id.tolist(),format_func=lambda i:f"{i} · {aa[aa.id==i].iloc[0].first_name} {aa[aa.id==i].iloc[0].last_name}")
                u=st.text_input("Nome utente"); p=st.text_input("Password iniziale (10+ caratteri)",type="password"); ok=st.form_submit_button("Crea account")
            if ok:
                if not u or len(p)<10: st.error("Inserisci username e password valida.")
                else:
                    s=secrets.token_hex(16)
                    try:
                        with db() as c: c.execute("INSERT INTO users(username,pwd,salt,role,athlete_id) VALUES(?,?,?,?,?)",(u.lower(),pw_hash(p,s),s,"athlete",aid))
                        st.success("Account creato.")
                    except sqlite3.IntegrityError: st.error("Username già utilizzato.")
elif page=="Carica attività":
    st.title("Carica e analizza attività"); aa=q("SELECT * FROM athletes ORDER BY last_name")
    if aa.empty: st.warning("Prima crea un atleta."); st.stop()
    with st.form("upload"):
        aid=st.selectbox("Atleta",aa.id.tolist(),format_func=lambda i:f"{i} · {aa[aa.id==i].iloc[0].first_name} {aa[aa.id==i].iloc[0].last_name}")
        sport=st.selectbox("Sport",["Ciclismo","Corsa","Pattinaggio","Palestra","Altro"]); protocol=st.selectbox("Tipo di test potenza",["Non è un test FTP","20 minuti (stima 95%)","60 minuti","Ramp test","FTP inserito manualmente"]); f=st.file_uploader("File FIT, TCX, GPX o CSV",type=["fit","tcx","gpx","csv"]); comment=st.text_area("Commento allenatore"); ok=st.form_submit_button("Analizza e salva")
    if ok:
        try:
            if f is None: raise ValueError("Seleziona un file.")
            d=parse(f); s=stats(d)
            with db() as c: c.execute("INSERT INTO activities(athlete_id,filename,sport,activity_date,duration,distance,avg_hr,max_hr,avg_power,max_power,avg_speed,cadence,elevation,data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,f.name,sport,*s,d.to_json(orient="records",date_format="iso")))
            athrow=aa[aa.id==aid].iloc[0]; athlete_weight=athrow.weight if pd.notna(athrow.weight) else None
            st.session_state.last={"aid":aid,"filename":f.name,"sport":sport,"stats":s,"df":d,"comment":comment,"protocol":protocol,"weight":athlete_weight}; st.success("Attività salvata.")
        except Exception as e: st.error("Errore durante la lettura: "+str(e))
    if "last" in st.session_state:
        r=st.session_state.last; s=r["stats"]; d=r["df"]; st.subheader("Analisi")
        st.write(dict(zip(["Data","Durata s","Distanza m","FC media","FC max","Potenza media","Potenza max","Velocità m/s","Cadenza","Dislivello m"],s)))
        for k in ["heart_rate","power","speed","cadence","altitude"]:
            if k in d and d[k].notna().any(): st.plotly_chart(px.line(d,y=k,title=k),use_container_width=True)
        ath=q("SELECT first_name,last_name FROM athletes WHERE id=?",(r["aid"],)).iloc[0]
        if r.get("protocol")!="Non è un test FTP":
            result=ftp_analysis(d,r["protocol"],r.get("weight"))
            st.divider(); st.header("Analisi professionale del test FTP")
            if result.get("error"): st.warning(result["error"])
            else:
                a1,a2,a3,a4=st.columns(4)
                a1.metric("FTP",f'{result["ftp"]:.0f} W' if result["ftp"] else "N/D")
                a2.metric("FTP relativa",f'{result["wkg"]:.2f} W/kg' if result["wkg"] else "N/D")
                a3.metric("Potenza media",f'{result["mean"]:.0f} W')
                a4.metric("Picco",f'{result["peak"]:.0f} W')
                st.caption(result["method"])
                if result["windows"]:
                    pw=pd.DataFrame([{"Durata":f"{s}s" if s<60 else f"{s//60} min","Watt":v} for s,v in result["windows"].items()])
                    st.plotly_chart(px.line(pw,x="Durata",y="Watt",markers=True,title="Migliore potenza media per durata"),use_container_width=True)
                    st.dataframe(pw,use_container_width=True,hide_index=True)
                if result["zones"]:
                    st.subheader("Zone di potenza")
                    st.dataframe(pd.DataFrame(result["zones"],columns=["Zona","Da W","A W"]),use_container_width=True,hide_index=True)
                st.subheader("Valutazione tecnica")
                for note in result["notes"]: st.write("• "+note)
            pdf=ftp_pdf(ath.first_name+" "+ath.last_name,r["stats"],result,r.get("weight"),r["comment"])
            st.download_button("Scarica report FTP professionale (PDF)",pdf,file_name="report_test_FTP.pdf",mime="application/pdf")
        else:
            st.download_button("Scarica report PDF",report(ath.first_name+" "+ath.last_name,r["stats"],r["comment"]),file_name="report_attivita.pdf",mime="application/pdf")
elif page=="Garmin Connect":
    st.title("Garmin Connect")
    st.caption("Sincronizzazione centralizzata delle attività degli atleti")
    st.info("Questa sezione prepara il portale alla connessione ufficiale Garmin. La sincronizzazione automatica non è ancora attiva: occorre prima ottenere l'accesso Business alle API Garmin e configurare il servizio server-to-server.")
    st.subheader("Stato collegamenti atleti")
    aa=q("SELECT id,first_name,last_name,sport FROM athletes ORDER BY last_name")
    conns=q("SELECT athlete_id,status,consent_at,last_sync FROM garmin_connections")
    if aa.empty:
        st.warning("Aggiungi prima gli atleti nella sezione Atleti.")
    else:
        view=aa.merge(conns,on="id",how="left",left_on="id",right_on="athlete_id")
        view["Connessione Garmin"]=view["status"].fillna("Da collegare").replace({"pending_consent":"In attesa del consenso","connected":"Collegato","error":"Da verificare"})
        view["Ultima sincronizzazione"]=view["last_sync"].fillna("Mai")
        st.dataframe(view[["first_name","last_name","sport","Connessione Garmin","Ultima sincronizzazione"]].rename(columns={"first_name":"Nome","last_name":"Cognome","sport":"Sport"}),use_container_width=True,hide_index=True)
    st.subheader("Come funzionerà")
    st.markdown("1. L'atleta riceve un invito personale e autorizza il collegamento Garmin Connect.\n2. Quando sincronizza orologio o dispositivo, Garmin invia al portale la nuova attività.\n3. Il portale importa il file FIT, evita duplicati e aggiorna automaticamente il diario dell'atleta.\n4. Dashboard e analisi mostrano carico, durata, distanza, frequenza cardiaca, potenza, cadenza e altri campi realmente presenti nel file.")
    st.warning("Non inserire password Garmin o token in questa pagina. Le credenziali API dovranno essere conservate in segreti server-side, mai nel database in chiaro o nel repository.")
    st.markdown("**Vincolo attuale:** Garmin distingue l'API personale (solo dati del proprietario) dall'accesso Business multiutente. L'API Activity con file FIT è disponibile tramite il programma Business; l'accesso e le condizioni devono essere confermati da Garmin prima di attivare i collegamenti.")
    st.markdown("[Documentazione ufficiale Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/)")
elif page=="Archivio":
    st.title("Archivio attività"); d=q("SELECT a.*,t.first_name||' '||t.last_name atleta FROM activities a JOIN athletes t ON t.id=a.athlete_id ORDER BY activity_date DESC"); st.dataframe(d.drop(columns=["data"],errors="ignore"),use_container_width=True)
elif page=="Confronti":
    st.title("Confronto storico"); aa=q("SELECT * FROM athletes")
    if len(aa):
        aid=st.selectbox("Atleta",aa.id.tolist(),format_func=lambda i:f"{i} · {aa[aa.id==i].iloc[0].first_name} {aa[aa.id==i].iloc[0].last_name}")
        d=q("SELECT * FROM activities WHERE athlete_id=? ORDER BY activity_date",(aid,))
        if len(d):
            metric=st.selectbox("Parametro",["avg_hr","max_hr","avg_power","max_power","avg_speed","cadence","distance","duration"]); st.dataframe(d[["activity_date","sport",metric]]); st.plotly_chart(px.line(d,x="activity_date",y=metric,markers=True))
        else: st.info("Nessuna attività registrata.")
elif page=="Backup":
    st.title("Backup database"); st.warning("Questa versione usa SQLite locale: non pubblicarla con dati reali di atleti. Il database può andare perso su hosting con storage temporaneo.")
    import os
    if os.path.exists(DB): st.download_button("Scarica backup SQLite",open(DB,"rb").read(),file_name=DB)
elif page=="Profilo":
    st.title("Profilo allenatore")
    st.caption("Gestisci i dati del tuo account e le credenziali di accesso.")
    st.metric("Username",user["username"])
    st.divider()
    with st.form("profile_settings"):
        st.markdown("**Modifica password**")
        new_password=st.text_input("Nuova password (lascia vuoto per non modificarla)",type="password")
        confirm_password=st.text_input("Conferma nuova password",type="password")
        save_profile=st.form_submit_button("Salva modifiche",use_container_width=True)
    if save_profile:
        if bool(new_password) != bool(confirm_password) or (new_password and (len(new_password)<12 or new_password!=confirm_password)):
            st.error("Per cambiare password inserisci due valori uguali di almeno 12 caratteri.")
        else:
            if new_password:
                salt=secrets.token_hex(16)
                with db() as conn:
                    conn.execute("UPDATE users SET pwd=?,salt=? WHERE id=?",(pw_hash(new_password,salt),salt,user["id"]))
                st.session_state.user["pwd"]=pw_hash(new_password,salt)
                st.session_state.user["salt"]=salt
            st.success("Password aggiornata." if new_password else "Nessuna modifica alla password.")
            st.rerun()
