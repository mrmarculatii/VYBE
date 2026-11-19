import os, json, time, random, secrets, hashlib, hmac, sqlite3, threading, urllib.request, uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT=Path(__file__).parent; DATA=Path(os.getenv('VYBE_DATA_DIR',str(ROOT/'data'))); DATA.mkdir(exist_ok=True,parents=True)
DB=str(DATA/'vybe.sqlite3'); SECRET=os.getenv('VYBE_PASSWORD',''); TOKEN_SECRET=os.getenv('VYBE_SESSION_SECRET','')
app=FastAPI(title='VYBE'); app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
lock=threading.RLock()
CAST=[('Mira Ashford','C','Wind','Sociable, independent, ambitious. Celestia roommate.','Arcane Studies'),('Elara Thorne','D','Restoration & Plant','Kind, observant, stubborn.','Botanical Restoration'),('Vivienne Laurent','A','Crystal','Proud aristocrat, competitive.','Crystal Arts'),('Lucien Draven','S','Gravity','Disciplined, intimidating, Apex Council vice president.','Gravitational Theory'),('Serena Valcrest','S','Spatial','Intelligent, politically capable, Apex Council president.','Spatial Arts'),('Kaia Ren','B','Lightning','Witty competitive scholarship student.','Combat Magic'),('Liora Noctis','C','Illusion','Quiet and academically focused.','Illusion Studies'),('Freya Bellamy','D','Fire','Social, dramatic, campus media enthusiast.','Media & Flame'),('Theo Mercer','E','Barrier','Friendly engineering student.','Arcane Engineering'),('Isabella Moreau','A','Bloodline Flame','Charismatic aristocrat with complicated history involving Vivienne.','Flame Arts'),('Amara Solenne','S','Solar','Disciplined senior combat specialist.','Combat Magic'),('Cassian Rook','B','Shadow','Charming, politically connected information trader.','Political Arcana'),('Rosalie Everhart','C','Water','Compassionate medical student.','Medical Magic'),('Nessa Vale','E','Water','Reserved photography hobbyist.','Visual Arcana'),('Juno Kestrel','C','Metal','Night owl and robotics club organizer.','Arcane Engineering'),('Talia Wren','D','Wind','Pragmatic student journalist.','Campus Journalism')]

def connect():
 c=sqlite3.connect(DB,timeout=15,check_same_thread=False); c.row_factory=sqlite3.Row; c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA foreign_keys=ON'); return c

def init():
 with lock:
  c=connect(); c.executescript('''CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT); CREATE TABLE IF NOT EXISTS characters(id INTEGER PRIMARY KEY,name TEXT UNIQUE,handle TEXT,rank TEXT,magic TEXT,personality TEXT,major TEXT,avatar TEXT DEFAULT '',bio TEXT DEFAULT '',schedule TEXT DEFAULT '{}'); CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY,author INTEGER,body TEXT,media TEXT DEFAULT '',created TEXT,kind TEXT DEFAULT 'post',channel TEXT DEFAULT 'general',expires TEXT,verified INTEGER DEFAULT 0, FOREIGN KEY(author) REFERENCES characters(id)); CREATE TABLE IF NOT EXISTS reactions(user INTEGER,post INTEGER,kind TEXT,PRIMARY KEY(user,post,kind)); CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY,post INTEGER,author INTEGER,body TEXT,created TEXT,parent INTEGER); CREATE TABLE IF NOT EXISTS follows(follower INTEGER,followed INTEGER,PRIMARY KEY(follower,followed)); CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,sender INTEGER,recipient INTEGER,body TEXT,created TEXT,read_at TEXT,group_id TEXT); CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,kind TEXT,payload TEXT,due TEXT,status TEXT DEFAULT 'pending',created TEXT); CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY,character INTEGER,summary TEXT,source TEXT,created TEXT); CREATE TABLE IF NOT EXISTS worldlog(id INTEGER PRIMARY KEY,source TEXT,summary TEXT,visibility TEXT,created TEXT,imported INTEGER DEFAULT 0); CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,body TEXT,created TEXT,seen INTEGER DEFAULT 0); CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,expires REAL); CREATE TABLE IF NOT EXISTS uploads(id INTEGER PRIMARY KEY,filename TEXT,created TEXT);''')
  if not c.execute("SELECT 1 FROM meta WHERE k='clock'").fetchone():
   for k,v in [('clock','2027-09-06T08:00:00'),('speed','1'),('paused','1'),('last_tick',str(time.time()))]: c.execute('INSERT INTO meta VALUES (?,?)',(k,v))
  if not c.execute('SELECT 1 FROM characters').fetchone():
   c.execute("INSERT INTO characters(name,handle,rank,magic,personality,major,bio) VALUES (?,?,?,?,?,?,?)",('Celestia Veyne','celestiaveyne','F (provisional)','Arcane Theory','Player-controlled. No NPC agency.','Arcane Theory','Aster Hall · Room 314'))
   for name,rank,magic,pers,major in CAST: c.execute('INSERT INTO characters(name,handle,rank,magic,personality,major,bio) VALUES (?,?,?,?,?,?,?)',(name,''.join(name.lower().split()),rank,magic,pers,major,major+' · Eidolon University'))
   t='2027-09-06T08:00:00'
   seed=[('Mira Ashford','Aster Hall orientation is at 10. Whoever designed this campus map deserves an F in navigation.','general'),('Freya Bellamy','Freshman week. New faces, new rumors, and I already lost my student card.','general'),('Kaia Ren','Reminder: the training hall is for training. Not showing off for three hours.','general'),('Liora Noctis','Library west wing is open again. Please keep it quiet this time.','academics'),('Serena Valcrest','Welcome to Eidolon University. Official orientation begins at 10:00.','announcements'),('Nessa Vale','Morning light over the eastern courtyard. The architecture here is unreal.','photography'),('Theo Mercer','Does anyone know if the barrier lab allows first years to borrow equipment?','academics')]
   for name,body,ch in seed:
    uid=c.execute('SELECT id FROM characters WHERE name=?',(name,)).fetchone()[0]; c.execute('INSERT INTO posts(author,body,created,channel,verified) VALUES (?,?,?,?,?)',(uid,body,t,ch,int(name=='Serena Valcrest')))
  c.executescript("""CREATE TABLE IF NOT EXISTS canon_events(event_id TEXT PRIMARY KEY,fictional_time TEXT NOT NULL,event_type TEXT NOT NULL,participants TEXT NOT NULL DEFAULT '[]',location TEXT,visibility TEXT NOT NULL,source TEXT NOT NULL,canon_status TEXT NOT NULL,summary TEXT NOT NULL,effects TEXT NOT NULL DEFAULT '{}',created_real TEXT NOT NULL); CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY,created_real TEXT NOT NULL,fictional_time TEXT NOT NULL,filename TEXT NOT NULL); CREATE TABLE IF NOT EXISTS npc_schedule(character INTEGER NOT NULL,weekday INTEGER NOT NULL,start_hour INTEGER NOT NULL,end_hour INTEGER NOT NULL,activity TEXT NOT NULL,location TEXT NOT NULL,priority INTEGER DEFAULT 1,PRIMARY KEY(character,weekday,start_hour)); CREATE TABLE IF NOT EXISTS npc_state(character INTEGER PRIMARY KEY,location TEXT,mood TEXT DEFAULT 'neutral',updated TEXT);""")
  if not c.execute("SELECT 1 FROM meta WHERE k='story_mode'").fetchone():
   c.execute("INSERT INTO meta VALUES ('story_mode','sandbox')");c.execute("UPDATE meta SET v='1' WHERE k='paused' OR k='speed'")
  if not c.execute('SELECT 1 FROM npc_schedule').fetchone():
   for ch in c.execute('SELECT id,name,major FROM characters WHERE id>1').fetchall():
    uid=ch['id']; offset=uid%3
    for wd in range(7):
     activities=[(0,7+offset,'sleep','Residence'),(8+offset,9+offset,'breakfast','Dining Hall'),(10+offset,12+offset,'lecture',ch['major']+' Department'),(13+offset,14+offset,'lunch','Dining Hall'),(15+offset,17+offset,'study','Library'),(23,24,'sleep','Residence')]
     if wd>=5:activities=[(0,8+offset,'sleep','Residence'),(10,12,'free time','Campus'),(13,15,'social time','Courtyard'),(23,24,'sleep','Residence')]
     for start,end,activity,location in activities:c.execute('INSERT OR IGNORE INTO npc_schedule(character,weekday,start_hour,end_hour,activity,location) VALUES (?,?,?,?,?,?)',(uid,wd,start,end,activity,location))
  c.executescript("""CREATE TABLE IF NOT EXISTS relationships(character INTEGER PRIMARY KEY, affinity INTEGER DEFAULT 0, familiarity INTEGER DEFAULT 0, last_interaction TEXT); CREATE TABLE IF NOT EXISTS social_activity(id INTEGER PRIMARY KEY,actor INTEGER,action TEXT,target INTEGER,created TEXT);""")
  c.commit();c.close()
init()

def getmeta(c,k):return c.execute('SELECT v FROM meta WHERE k=?',(k,)).fetchone()[0]
def setmeta(c,k,v):c.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(k,str(v)))
def now(c):return getmeta(c,'clock')
def stamp():return datetime.now(timezone.utc).isoformat()
def user(c):return c.execute('SELECT * FROM characters WHERE id=1').fetchone()
def rows(c,sql,args=()):return [dict(x) for x in c.execute(sql,args).fetchall()]
def auth(request:Request):
 if not SECRET or not TOKEN_SECRET:raise HTTPException(503,'Set VYBE_PASSWORD and VYBE_SESSION_SECRET on the server before use')
 token=request.cookies.get('vybe_session',''); c=connect(); good=bool(c.execute('SELECT 1 FROM sessions WHERE token_hash=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()) if token else False;c.close()
 if not good:raise HTTPException(401,'Sign in to VYBE')
@app.get('/')
def index():return FileResponse(ROOT/'static'/'index.html')
class Login(BaseModel):password:str
@app.post('/api/login')
def login(body:Login):
 if not SECRET or not TOKEN_SECRET:raise HTTPException(503,'Server credentials are not configured')
 if not hmac.compare_digest(body.password,SECRET):raise HTTPException(401,'Incorrect password')
 token=secrets.token_urlsafe(36); c=connect();c.execute('INSERT INTO sessions VALUES (?,?)',(hashlib.sha256(token.encode()).hexdigest(),time.time()+86400*14));c.commit();c.close()
 from fastapi.responses import JSONResponse
 r=JSONResponse({'ok':True});r.set_cookie('vybe_session',token,httponly=True,secure=os.getenv('VYBE_COOKIE_SECURE','0')=='1',samesite='strict',max_age=86400*14);return r
@app.post('/api/logout')
def logout(request:Request):
 auth(request);c=connect();c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(request.cookies['vybe_session'].encode()).hexdigest(),));c.commit();c.close();from fastapi.responses import JSONResponse
 r=JSONResponse({'ok':True});r.delete_cookie('vybe_session');return r
@app.get('/api/state')
def state(request:Request):
 auth(request);c=connect();result={'clock':now(c),'story_mode':getmeta(c,'story_mode'),'speed':float(getmeta(c,'speed')),'paused':getmeta(c,'paused')=='1','characters':rows(c,'SELECT id,name,handle,rank,magic,major,bio,avatar FROM characters'),'posts':rows(c,'''SELECT p.*,a.name,a.handle,a.rank,(SELECT COUNT(*) FROM reactions r WHERE r.post=p.id AND r.kind='like') likes,(SELECT COUNT(*) FROM comments cm WHERE cm.post=p.id) comments,(SELECT COUNT(*) FROM reactions r WHERE r.post=p.id AND r.user=1 AND r.kind='like') liked,(SELECT COUNT(*) FROM reactions r WHERE r.post=p.id AND r.user=1 AND r.kind='save') saved FROM posts p JOIN characters a ON a.id=p.author WHERE p.expires IS NULL OR p.expires>? ORDER BY p.id DESC LIMIT 150''',(now(c),)),'schedule':rows(c,'SELECT * FROM npc_schedule ORDER BY character,weekday,start_hour'),'canon_events':rows(c,'SELECT * FROM canon_events ORDER BY created_real DESC LIMIT 80'),'notifications':rows(c,'SELECT * FROM notifications ORDER BY id DESC LIMIT 30'),'events':rows(c,'SELECT * FROM events ORDER BY id DESC LIMIT 50'),'log':rows(c,'SELECT * FROM worldlog ORDER BY id DESC LIMIT 40'),'relationships':rows(c,'SELECT * FROM relationships'),'activity':rows(c,'SELECT * FROM social_activity ORDER BY id DESC LIMIT 40'),'following':[x['followed'] for x in rows(c,'SELECT followed FROM follows WHERE follower=1')]};c.close();return result
class PostIn(BaseModel):body:str;channel:str='general';kind:str='post';media:str=''
@app.post('/api/posts')
def post(body:PostIn,request:Request):
 auth(request)
 if not body.body.strip() and not body.media:raise HTTPException(400,'Empty post')
 if len(body.body)>3000:raise HTTPException(400,'Post too long')
 if body.kind not in ('post','story'):raise HTTPException(400,'Invalid kind')
 c=connect();t=now(c);expiry=(datetime.fromisoformat(t)+timedelta(hours=24)).isoformat() if body.kind=='story' else None
 c.execute('INSERT INTO posts(author,body,media,created,kind,channel,expires) VALUES (?,?,?,?,?,?,?)',(1,body.body.strip(),body.media,t,body.kind,body.channel,expiry));c.commit();c.close();return {'ok':True}
class React(BaseModel):post:int;kind:str
@app.post('/api/react')
def react(body:React,request:Request):
 auth(request)
 if body.kind not in ('like','save'):raise HTTPException(400,'Invalid reaction')
 c=connect();r=c.execute('SELECT 1 FROM reactions WHERE user=1 AND post=? AND kind=?',(body.post,body.kind)).fetchone()
 if r:c.execute('DELETE FROM reactions WHERE user=1 AND post=? AND kind=?',(body.post,body.kind))
 else:c.execute('INSERT INTO reactions VALUES (1,?,?)',(body.post,body.kind))
 c.execute('INSERT INTO social_activity(actor,action,target,created) VALUES (?,?,?,?)',(1,'unliked' if r else 'liked',body.post,now(c)));c.commit();c.close();return {'active':not bool(r)}
class Comment(BaseModel):post:int;body:str;parent:int|None=None
@app.post('/api/comments')
def comment(body:Comment,request:Request):
 auth(request)
 if not body.body.strip() or len(body.body)>1000:raise HTTPException(400,'Invalid comment')
 c=connect()
 if not c.execute('SELECT 1 FROM posts WHERE id=?',(body.post,)).fetchone():c.close();raise HTTPException(404,'Post not found')
 if body.parent is not None and not c.execute('SELECT 1 FROM comments WHERE id=? AND post=?',(body.parent,body.post)).fetchone():c.close();raise HTTPException(400,'Reply must belong to this post')
 c.execute('INSERT INTO comments(post,author,body,created,parent) VALUES (?,?,?,?,?)',(body.post,1,body.body.strip(),now(c),body.parent));c.execute('INSERT INTO social_activity(actor,action,target,created) VALUES (?,?,?,?)',(1,'commented',body.post,now(c)));c.commit();c.close();return {'ok':True}
@app.get('/api/comments/{pid}')
def comments(pid:int,request:Request):
 auth(request);c=connect();r=rows(c,'SELECT cm.*,a.name,a.handle FROM comments cm JOIN characters a ON cm.author=a.id WHERE post=? ORDER BY cm.id',(pid,));c.close();return r
@app.post('/api/follow/{uid}')
def follow(uid:int,request:Request):
 auth(request)
 if uid==1:raise HTTPException(400,'Cannot follow yourself')
 c=connect();r=c.execute('SELECT 1 FROM follows WHERE follower=1 AND followed=?',(uid,)).fetchone()
 if r:c.execute('DELETE FROM follows WHERE follower=1 AND followed=?',(uid,))
 else:c.execute('INSERT INTO follows VALUES (1,?)',(uid,))
 c.execute('INSERT INTO social_activity(actor,action,target,created) VALUES (?,?,?,?)',(1,'unfollowed' if r else 'followed',uid,now(c)));c.commit();c.close();return {'following':not bool(r)}
@app.get('/api/messages/{uid}')
def messages(uid:int,request:Request):
 auth(request);c=connect();r=rows(c,'SELECT * FROM messages WHERE (sender=1 AND recipient=?) OR (sender=? AND recipient=1) ORDER BY id',(uid,uid));c.execute('UPDATE messages SET read_at=? WHERE sender=? AND recipient=1 AND read_at IS NULL',(now(c),uid));c.commit();c.close();return r
class Msg(BaseModel):recipient:int;body:str
@app.post('/api/messages')
def send(body:Msg,request:Request):
 auth(request)
 if body.recipient==1 or not body.body.strip() or len(body.body)>2000:raise HTTPException(400,'Invalid message')
 c=connect();ch=c.execute('SELECT * FROM characters WHERE id=?',(body.recipient,)).fetchone()
 if not ch:raise HTTPException(404,'Student not found')
 t=now(c);c.execute('INSERT INTO messages(sender,recipient,body,created) VALUES (1,?,?,?)',(body.recipient,body.body.strip(),t))
 c.execute('INSERT INTO memories(character,summary,source,created) VALUES (?,?,?,?)',(body.recipient,'Celestia sent: '+body.body[:300],'message',t))
 c.execute('INSERT INTO relationships(character,affinity,familiarity,last_interaction) VALUES (?,?,?,?) ON CONFLICT(character) DO UPDATE SET familiarity=MIN(100,familiarity+1),last_interaction=excluded.last_interaction',(body.recipient,0,1,t))
 # Scheduling is deterministic in availability class, variable in precise timing; no reply is guaranteed.
 hour=datetime.fromisoformat(t).hour; base=(8-hour)*60 if hour<8 else (32-hour)*60 if hour>=23 else 0
 rng=random.SystemRandom();delay=base+rng.choice([8,24,45,90,180,300,480]);chance=.6 if 8<=hour<23 else .32
 schedule=c.execute('SELECT activity FROM npc_schedule WHERE character=? AND weekday=? AND start_hour<=? AND end_hour>? ORDER BY priority DESC LIMIT 1',(body.recipient,datetime.fromisoformat(t).weekday(),hour,hour)).fetchone()
 if schedule and schedule['activity']=='sleep':chance*=.15;delay+=rng.randint(120,360)
 elif schedule and schedule['activity'] in ('lecture','study'):chance*=.65;delay+=rng.randint(30,150)
 if rng.random()<chance:
  due=(datetime.fromisoformat(t)+timedelta(minutes=delay)).isoformat();c.execute('INSERT INTO events(kind,payload,due,created) VALUES (?,?,?,?)',('reply',json.dumps({'sender':body.recipient,'recipient':1,'source':body.body[:500]}),due,t))
 c.commit();c.close();return {'ok':True,'reply_guaranteed':False}
class Clock(BaseModel):paused:bool|None=None;speed:float|None=None;advance_minutes:int|None=None
@app.post('/api/clock')
def clock(body:Clock,request:Request):
 auth(request);c=connect()
 if body.paused is not None:setmeta(c,'paused','1' if body.paused else '0')
 if body.speed is not None:
  if body.speed!=1:raise HTTPException(400,'Real-time mode is fixed at 1x; use controlled advance for fast-forward')
  setmeta(c,'speed',body.speed)
 if body.advance_minutes is not None:
  if not 0<=body.advance_minutes<=10080:raise HTTPException(400,'Advance 0–10080 minutes')
  setmeta(c,'clock',(datetime.fromisoformat(now(c))+timedelta(minutes=body.advance_minutes)).isoformat())
 setmeta(c,'last_tick',time.time());c.commit();c.close();return {'ok':True}
class Sync(BaseModel):summary:str;visibility:str='public';source:str='roleplay';apply:bool=False
@app.post('/api/sync')
def sync(body:Sync,request:Request):
 auth(request)
 if body.visibility not in ('public','private','author'):raise HTTPException(400,'Invalid visibility')
 if not body.summary.strip():raise HTTPException(400,'Empty sync')
 c=connect();c.execute('INSERT INTO worldlog(source,summary,visibility,created,imported) VALUES (?,?,?,?,?)',(body.source,body.summary.strip(),body.visibility,now(c),int(body.apply)));c.commit();c.close();return {'ok':True,'staged':not body.apply}
@app.post('/api/sync/approve/{lid}')
def approve(lid:int,request:Request):
 auth(request);c=connect();c.execute('UPDATE worldlog SET imported=1 WHERE id=?',(lid,));c.commit();c.close();return {'ok':True}
@app.delete('/api/sync/{lid}')
def delete_sync(lid:int,request:Request):
 auth(request);c=connect();c.execute('DELETE FROM worldlog WHERE id=?',(lid,));c.commit();c.close();return {'ok':True}
@app.get('/api/export')
def export(request:Request):
 auth(request);c=connect();out={t:rows(c,'SELECT * FROM '+t) for t in ['meta','characters','posts','reactions','comments','follows','messages','events','memories','worldlog','notifications']};c.close();return out
@app.get('/api/story-export')
def story_export(request:Request):
 auth(request);c=connect();out={'in_world_time':now(c),'celestia_messages':rows(c,'SELECT m.*,a.name AS recipient_name FROM messages m JOIN characters a ON a.id=m.recipient WHERE m.sender=1'),'npc_replies':rows(c,'SELECT m.*,a.name AS sender_name FROM messages m JOIN characters a ON a.id=m.sender WHERE m.recipient=1'),'world_events':rows(c,'SELECT * FROM worldlog WHERE imported=1'),'pending_events':rows(c,"SELECT * FROM events WHERE status='pending'")};c.close();return out
@app.post('/api/upload')
async def upload(request:Request,file:UploadFile=File(...)):
 auth(request);ext=Path(file.filename or '').suffix.lower()
 if ext not in ('.png','.jpg','.jpeg','.webp'):raise HTTPException(400,'Only image uploads allowed')
 raw=await file.read(5_000_001)
 if len(raw)>5_000_000:raise HTTPException(413,'5MB maximum')
 sig=raw[:12];valid=(ext=='.png' and sig.startswith(b'\x89PNG\r\n\x1a\n')) or (ext in ('.jpg','.jpeg') and sig.startswith(b'\xff\xd8\xff')) or (ext=='.webp' and sig[:4]==b'RIFF' and sig[8:12]==b'WEBP')
 if not valid:raise HTTPException(400,'Invalid image bytes')
 name=secrets.token_hex(16)+ext;folder=DATA/'media';folder.mkdir(exist_ok=True);(folder/name).write_bytes(raw);return {'url':'/api/media/'+name}
@app.get('/api/media/{name}')
def media(name:str,request:Request):
 auth(request)
 if name!=Path(name).name:raise HTTPException(404)
 p=DATA/'media'/name
 if not p.exists():raise HTTPException(404)
 return FileResponse(p)

@app.post('/api/notifications/read')
def notifications_read(request:Request):
 auth(request);c=connect();c.execute('UPDATE notifications SET seen=1');c.commit();c.close();return {'ok':True}

@app.get('/api/campus-live')
def campus_live(request:Request):
 auth(request);c=connect();t=datetime.fromisoformat(now(c));result=[]
 for ch in rows(c,'SELECT id,name,major,rank FROM characters WHERE id>1'):
  sched=c.execute('SELECT activity,location FROM npc_schedule WHERE character=? AND weekday=? AND start_hour<=? AND end_hour>? ORDER BY priority DESC LIMIT 1',(ch['id'],t.weekday(),t.hour,t.hour)).fetchone()
  activity=sched['activity'] if sched else 'free time';location=sched['location'] if sched else 'Campus'
  result.append({'id':ch['id'],'name':ch['name'],'rank':ch['rank'],'activity':activity,'location':location,'available':activity not in ('sleep','lecture')})
 c.close();return {'clock':t.isoformat(),'students':result}

def ai_reply(character,source,memories):
 key=os.getenv('OPENAI_API_KEY');model=os.getenv('VYBE_AI_MODEL','gpt-4.1-mini')
 if not key:return None
 prompt='You are a fictional Eidolon University student in a private pre-chapter-one sandbox. Stay in character, remember your independent life and boundaries. Never speak for Celestia or assume her choices, divine nature, or secrets. Do not invent confirmed canon. Be distinctive, casual, and sometimes terse. Reply naturally in 1-3 sentences, or output exactly [IGNORE] if you would not respond. Student: '+character['name']+'. Traits: '+character['personality']+'. Prior accessible memory: '+str(memories)[-1500:]+' Message from Celestia: '+source
 data=json.dumps({'model':model,'messages':[{'role':'system','content':'Roleplay as the named fictional student, with realistic boundaries and no access to hidden canon.'},{'role':'user','content':prompt}],'max_tokens':160}).encode()
 try:
  req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data,{'Authorization':'Bearer '+key,'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=25) as res:return json.load(res)['choices'][0]['message']['content'].strip()
 except Exception as e:print('AI unavailable:',type(e).__name__);return None

def tick():
 with lock:
  c=connect()
  try:
   last=float(getmeta(c,'last_tick'));elapsed=min(max(time.time()-last,0),3600);setmeta(c,'last_tick',time.time())
   if getmeta(c,'paused')=='0':setmeta(c,'clock',(datetime.fromisoformat(now(c))+timedelta(seconds=elapsed*float(getmeta(c,'speed')))).isoformat())
   due=rows(c,"SELECT * FROM events WHERE status='pending' AND due<=? ORDER BY id LIMIT 10",(now(c),)) if getmeta(c,'paused')=='0' else []
   for e in due:
    c.execute("UPDATE events SET status='processing' WHERE id=? AND status='pending'",(e['id'],));c.commit()
    if e['kind']=='reply':
     payload=json.loads(e['payload']);ch=c.execute('SELECT * FROM characters WHERE id=?',(payload['sender'],)).fetchone();mem=rows(c,'SELECT summary FROM memories WHERE character=? ORDER BY id DESC LIMIT 8',(payload['sender'],));answer=ai_reply(dict(ch),payload['source'],mem)
     if answer and answer!='[IGNORE]':
      c.execute('INSERT INTO messages(sender,recipient,body,created) VALUES (?,?,?,?)',(payload['sender'],1,answer,now(c)));c.execute('INSERT INTO notifications(body,created) VALUES (?,?)',(ch['name']+' sent you a message',now(c)))
    c.execute("UPDATE events SET status='done' WHERE id=?",(e['id'],))
   c.commit()
  finally:c.close()

def worker():
 while True:
  try:tick()
  except Exception as e:print('Worker error',str(e))
  time.sleep(15)
@app.on_event('startup')
def startup():
 if os.getenv('VYBE_WORKER','1')=='1':threading.Thread(target=worker,daemon=True).start()

# Director-only routes: all require the private owner session.
class DirectorMode(BaseModel):activate:bool
@app.post('/api/director/story-mode')
def story_mode(body:DirectorMode,request:Request):
 auth(request)
 with lock:
  c=connect();setmeta(c,'story_mode','pending_canon' if body.activate else 'sandbox');setmeta(c,'paused','1');c.commit();c.close()
 return {'mode':'pending_canon' if body.activate else 'sandbox','paused':True,'note':'Activation never auto-confirms events'}
class ManualTime(BaseModel):fictional_time:datetime
@app.post('/api/director/set-time')
def set_time(body:ManualTime,request:Request):
 auth(request)
 if not datetime(2027,9,6)<=body.fictional_time.replace(tzinfo=None)<=datetime(2037,12,31):raise HTTPException(400,'Outside supported fictional calendar')
 with lock:
  c=connect();setmeta(c,'clock',body.fictional_time.replace(tzinfo=None).isoformat());setmeta(c,'last_tick',time.time());c.commit();c.close()
 return {'ok':True}
@app.get('/api/director/schedules')
def schedules(request:Request):
 auth(request);c=connect();result=rows(c,'SELECT s.*,ch.name FROM npc_schedule s JOIN characters ch ON ch.id=s.character ORDER BY character,weekday,start_hour');c.close();return result
class CanonIn(BaseModel):event_id:str|None=None;fictional_time:datetime|None=None;event_type:str;participants:list[int]=[];location:str|None=None;visibility:str='public';source:str='roleplay';summary:str;effects:dict={}
@app.post('/api/director/canon-events')
def canon_create(body:CanonIn,request:Request):
 auth(request)
 if body.visibility not in ('public','private','author') or not body.summary.strip():raise HTTPException(400,'Invalid event')
 if 1 in body.participants and body.source not in ('player','roleplay'):raise HTTPException(400,'Celestia events require player or roleplay source')
 with lock:
  c=connect();eid=body.event_id or str(uuid.uuid4());status='sandbox' if getmeta(c,'story_mode')=='sandbox' else 'pending_canon'
  try:c.execute('INSERT INTO canon_events VALUES (?,?,?,?,?,?,?,?,?,?,?)',(eid,(body.fictional_time.replace(tzinfo=None).isoformat() if body.fictional_time else now(c)),body.event_type,json.dumps(body.participants),body.location,body.visibility,body.source,status,body.summary,json.dumps(body.effects),stamp()));c.commit()
  except sqlite3.IntegrityError:raise HTTPException(409,'Duplicate event ID')
  finally:c.close()
 return {'event_id':eid,'canon_status':status}
@app.post('/api/director/canon-events/{event_id}/approve')
def canon_approve(event_id:str,request:Request):
 auth(request)
 with lock:
  c=connect();event=c.execute('SELECT * FROM canon_events WHERE event_id=?',(event_id,)).fetchone()
  if not event:c.close();raise HTTPException(404,'Event not found')
  if event['canon_status']=='sandbox':c.close();raise HTTPException(409,'Sandbox events must be explicitly promoted before approval')
  c.execute("UPDATE canon_events SET canon_status='confirmed_canon' WHERE event_id=? AND canon_status='pending_canon'",(event_id,));c.commit();c.close()
 return {'ok':True}
@app.post('/api/director/canon-events/{event_id}/promote')
def canon_promote(event_id:str,request:Request):
 auth(request)
 with lock:
  c=connect();changed=c.execute("UPDATE canon_events SET canon_status='pending_canon' WHERE event_id=? AND canon_status='sandbox'",(event_id,)).rowcount;c.commit();c.close()
 if not changed:raise HTTPException(409,'Event not in sandbox')
 return {'ok':True}
@app.get('/api/director/canon-export')
def canon_export(request:Request):
 auth(request);c=connect();out={'fictional_time':now(c),'story_mode':getmeta(c,'story_mode'),'events':rows(c,"SELECT * FROM canon_events WHERE canon_status='confirmed_canon' ORDER BY fictional_time,event_id")};c.close();return out
@app.post('/api/director/snapshot')
def snapshot(request:Request):
 auth(request)
 with lock:
  c=connect();folder=DATA/'snapshots';folder.mkdir(exist_ok=True);filename=str(uuid.uuid4())+'.sqlite3';dest=sqlite3.connect(str(folder/filename));c.backup(dest);dest.close();c.execute('INSERT INTO snapshots(created_real,fictional_time,filename) VALUES (?,?,?)',(stamp(),now(c),filename));sid=c.execute('SELECT last_insert_rowid()').fetchone()[0];c.commit();c.close()
 return {'snapshot_id':sid,'note':'Database snapshot saved; media files are not included'}
@app.get('/api/director/snapshots')
def list_snapshots(request:Request):
 auth(request);c=connect();r=rows(c,'SELECT id,created_real,fictional_time FROM snapshots ORDER BY id DESC');c.close();return r
@app.post('/api/director/snapshots/{sid}/restore')
def restore_snapshot(sid:int,request:Request):
 auth(request)
 with lock:
  c=connect();r=c.execute('SELECT filename FROM snapshots WHERE id=?',(sid,)).fetchone();c.close()
  if not r:raise HTTPException(404,'Snapshot not found')
  path=DATA/'snapshots'/r['filename']
  if not path.exists():raise HTTPException(404,'Snapshot file missing')
  source=sqlite3.connect(str(path));target=connect();source.backup(target);source.close();target.close()
  c=connect();setmeta(c,'paused','1');setmeta(c,'last_tick',time.time());c.execute("UPDATE events SET status='pending' WHERE status='processing'");c.commit();c.close()
 return {'ok':True,'paused':True}
