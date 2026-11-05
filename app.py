import streamlit as st
import sqlite3, hashlib, secrets, io, json
from datetime import date
import pandas as pd
import plotly.express as px
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="SPORT PERFORMANCE MANAGER", page_icon="🏅", layout="wide")
DB="sport_performance.db"

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, pwd TEXT, salt TEXT, role TEXT, athlete_id INTEGER);
    CREATE TABLE IF NOT EXISTS athletes(id INTEGER PRIMARY KEY, first_name TEXT,last_name TEXT,birth TEXT,sex TEXT,weight REAL,height REAL,sport TEXT,team TEXT,hrmax REAL,hrrest REAL,ftp REAL,notes TEXT);
    CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY,athlete_id INTEGER,filename TEXT,sport TEXT,activity_date TEXT,duration REAL,distance REAL,avg_hr REAL,max_hr REAL,avg_power REAL,max_power REAL,avg_speed REAL,cadence REAL,elevation REAL,data TEXT);
    """)
    return c
def pw_hash(p,s): return hashlib.pbkdf2_hmac("sha256",p.encode(),s.encode(),200000).hex()
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
def report(ath,activity,comment):
    b=io.BytesIO(); doc=SimpleDocTemplate(b,pagesize=A4); styles=getSampleStyleSheet()
    data=[["Parametro","Valore"],["Data",activity[0]],["Durata (s)",activity[1]],["Distanza (m)",activity[2]],["FC media / max",f"{activity[3]} / {activity[4]}"],["Potenza media / max",f"{activity[5]} / {activity[6]}"],["Velocità media (m/s)",activity[7]],["Cadenza",activity[8]],["Dislivello positivo (m)",activity[9]]]
    doc.build([Paragraph("SPORT PERFORMANCE MANAGER",styles["Title"]),Paragraph(f"Atleta: {ath}",styles["Heading2"]),Table(data),Spacer(1,16),Paragraph("Commento allenatore",styles["Heading2"]),Paragraph(comment or "Nessun commento inserito.",styles["BodyText"])])
    return b.getvalue()
db().close()
users=q("SELECT * FROM users")
if "user" not in st.session_state:
    st.title("🏅 SPORT PERFORMANCE MANAGER")
    if users.empty:
        st.info("Prima configurazione: crea l'account allenatore.")
        with st.form("setup"):
            u=st.text_input("Nome utente"); p=st.text_input("Password (almeno 10 caratteri)",type="password"); p2=st.text_input("Ripeti password",type="password"); ok=st.form_submit_button("Crea account")
        if ok:
            if not u or len(p)<10 or p!=p2: st.error("Controlla i dati e la password.")
            else:
                s=secrets.token_hex(16)
                with db() as c: c.execute("INSERT INTO users(username,pwd,salt,role) VALUES(?,?,?,?)",(u.lower(),pw_hash(p,s),s,"coach"))
                st.success("Account creato. Ricarica la pagina per accedere.")
    else:
        with st.form("login"):
            u=st.text_input("Nome utente"); p=st.text_input("Password",type="password"); ok=st.form_submit_button("Accedi")
        if ok:
            row=users[users.username==u.lower()]
            if len(row) and secrets.compare_digest(pw_hash(p,row.iloc[0].salt),row.iloc[0].pwd): st.session_state.user=row.iloc[0].to_dict(); st.rerun()
            else: st.error("Credenziali non valide.")
    st.stop()
user=st.session_state.user
with st.sidebar:
    st.title("🏅 SPM"); st.caption(user["username"]+" · "+user["role"])
    if st.button("Esci"): del st.session_state.user; st.rerun()
    menu=["Dashboard","Atleti","Carica attività","Archivio","Confronti","Backup"] if user["role"]=="coach" else ["La mia dashboard","Le mie attività"]
    page=st.radio("Menu",menu)
if user["role"]=="athlete":
    aid=user["athlete_id"]
    a=q("SELECT * FROM athletes WHERE id=?",(aid,))
    if a.empty: st.error("Profilo non associato."); st.stop()
    acts=q("SELECT * FROM activities WHERE athlete_id=? ORDER BY activity_date DESC",(aid,))
    st.title("La mia dashboard" if page=="La mia dashboard" else "Le mie attività")
    st.metric("Attività registrate",len(acts)); st.dataframe(acts.drop(columns=["data"],errors="ignore"),use_container_width=True); st.stop()
if page=="Dashboard":
    aa=q("SELECT * FROM athletes"); acts=q("SELECT a.*,t.first_name||' '||t.last_name atleta FROM activities a JOIN athletes t ON t.id=a.athlete_id")
    st.title("Dashboard allenatore"); x,y,z=st.columns(3); x.metric("Atleti",len(aa)); y.metric("Attività",len(acts)); z.metric("Sport",aa.sport.nunique() if len(aa) else 0)
    st.dataframe(acts.drop(columns=["data"],errors="ignore"),use_container_width=True)
elif page=="Atleti":
    st.title("Anagrafica atleti")
    with st.form("ath"):
        a,b,c=st.columns(3); fn=a.text_input("Nome*"); ln=b.text_input("Cognome*"); birth=c.date_input("Data nascita",value=None)
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
        sport=st.selectbox("Sport",["Ciclismo","Corsa","Pattinaggio","Palestra","Altro"]); f=st.file_uploader("File FIT, TCX, GPX o CSV",type=["fit","tcx","gpx","csv"]); comment=st.text_area("Commento allenatore"); ok=st.form_submit_button("Analizza e salva")
    if ok:
        try:
            if f is None: raise ValueError("Seleziona un file.")
            d=parse(f); s=stats(d)
            with db() as c: c.execute("INSERT INTO activities(athlete_id,filename,sport,activity_date,duration,distance,avg_hr,max_hr,avg_power,max_power,avg_speed,cadence,elevation,data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,f.name,sport,*s,d.to_json(orient="records",date_format="iso")))
            st.session_state.last={"aid":aid,"filename":f.name,"sport":sport,"stats":s,"df":d,"comment":comment}; st.success("Attività salvata.")
        except Exception as e: st.error("Errore durante la lettura: "+str(e))
    if "last" in st.session_state:
        r=st.session_state.last; s=r["stats"]; d=r["df"]; st.subheader("Analisi")
        st.write(dict(zip(["Data","Durata s","Distanza m","FC media","FC max","Potenza media","Potenza max","Velocità m/s","Cadenza","Dislivello m"],s)))
        for k in ["heart_rate","power","speed","cadence","altitude"]:
            if k in d and d[k].notna().any(): st.plotly_chart(px.line(d,y=k,title=k),use_container_width=True)
        ath=q("SELECT first_name,last_name FROM athletes WHERE id=?",(r["aid"],)).iloc[0]
        st.download_button("Scarica report PDF",report(ath.first_name+" "+ath.last_name,r["stats"],r["comment"]),file_name="report_attivita.pdf",mime="application/pdf")
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
