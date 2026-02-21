from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os
import threading
import asyncio
import discord
from discord.ext import commands
import time
import sys
import traceback
from contextlib import contextmanager

# ==================== CONFIGURATION ====================
app = Flask(__name__)
CORS(app, origins=["https://*.netlify.app", "https://tokens-discord.netlify.app", "http://localhost:3000"])

# Configuration des logs
def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")
    sys.stdout.flush()

def log_success(msg): log(msg, "✅")
def log_error(msg): log(msg, "❌")
def log_warn(msg): log(msg, "⚠️")
def log_info(msg): log(msg, "ℹ️")
def log_debug(msg): log(msg, "🐛")

log_info("="*60)
log_success("🚀 DÉMARRAGE DU SELFBOT BACKEND - VERSION ULTIME")
log_info(f"📦 Python version: {sys.version}")
log_info("="*60)

# ==================== GESTIONNAIRE BDD THREAD-SAFE ====================
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.local = threading.local()
        self.init_db()
    
    def get_connection(self):
        if not hasattr(self.local, 'connection'):
            self.local.connection = sqlite3.connect(self.db_path, timeout=30)
            self.local.connection.execute("PRAGMA journal_mode=WAL")
            self.local.connection.execute("PRAGMA synchronous=NORMAL")
        return self.local.connection
    
    @contextmanager
    def cursor(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            log_error(f"❌ Erreur BDD: {e}")
            raise e
        finally:
            cursor.close()
    
    def init_db(self):
        with self.cursor() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS tokens
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          token TEXT UNIQUE,
                          name TEXT,
                          status TEXT DEFAULT 'offline',
                          user_id TEXT,
                          username TEXT,
                          in_voice INTEGER DEFAULT 0,
                          last_seen TIMESTAMP)''')
        log_success("✅ Base de données initialisée")

db = DatabaseManager('tokens.db')

# ==================== GESTIONNAIRE DE BOTS ====================
class BotManager:
    def __init__(self):
        self.bots = {}
        self.loops = {}
        self.stats = {
            'total_connections': 0,
            'failed_connections': 0,
            'voice_joins': 0
        }
        log_success("🤖 BotManager initialisé")
        
    def add_bot(self, token_id, token, name):
        log_info(f"➕ Ajout du bot {name} (ID: {token_id})...")
        thread = threading.Thread(target=self._run_bot, args=(token_id, token, name))
        thread.daemon = True
        thread.start()
        return True
    
    def _run_bot(self, token_id, token, name):
        log_debug(f"🔄 Création de la boucle asyncio pour {name}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loops[token_id] = loop
        
        class SelfBot(commands.Bot):
            async def on_ready(self):
                log_success(f"✅ {name} connecté: {self.user.name} (ID: {self.user.id})")
                log_info(f"📊 Latence: {round(self.latency*1000)}ms")
                
                with db.cursor() as c:
                    c.execute("UPDATE tokens SET status=?, user_id=?, username=?, last_seen=? WHERE id=?", 
                             ('online', str(self.user.id), str(self.user.name), datetime.now(), token_id))
                
                bot_manager.stats['total_connections'] += 1
            
            async def on_voice_state_update(self, member, before, after):
                if member == self.user:
                    in_voice = 1 if after.channel else 0
                    channel_name = after.channel.name if after.channel else "aucun"
                    log_info(f"🔊 {name} {'en vocal' if in_voice else 'hors vocal'} - Salon: {channel_name}")
                    
                    with db.cursor() as c:
                        c.execute("UPDATE tokens SET in_voice=? WHERE id=?", (in_voice, token_id))
            
            async def on_error(self, event, *args, **kwargs):
                log_error(f"❌ Erreur dans l'événement {event} pour {name}")
                log_debug(traceback.format_exc())
        
        # ========== CONFIGURATION DES INTENTS - VERSION CORRIGÉE ==========
        log_info(f"🔧 Configuration des intents pour {name}...")
        
        intents = None
        methods_tried = []
        
        # Méthode 1: Intents.all()
        try:
            intents = discord.Intents.all()
            methods_tried.append("Intents.all()")
            log_success(f"✅ Méthode 1 réussie: Intents.all()")
        except AttributeError:
            log_warn(f"⚠️ Méthode 1 échouée")
        
        # Méthode 2: Intents.default() + config
        if intents is None:
            try:
                intents = discord.Intents.default()
                intents.message_content = True
                intents.voice_states = True
                methods_tried.append("Intents.default() + config")
                log_success(f"✅ Méthode 2 réussie")
            except AttributeError:
                log_warn(f"⚠️ Méthode 2 échouée")
        
        # Méthode 3: Intents.none()
        if intents is None:
            try:
                intents = discord.Intents.none()
                methods_tried.append("Intents.none()")
                log_warn(f"⚠️ Méthode 3 utilisée (mode dégradé)")
            except AttributeError:
                log_error(f"❌ Aucune méthode d'intents n'a fonctionné")
        
        log_info(f"📊 Méthodes essayées: {', '.join(methods_tried)}")
        
        try:
            bot = SelfBot(command_prefix="!", intents=intents, self_bot=True)
            log_success(f"✅ Bot {name} créé avec succès")
        except Exception as e:
            log_error(f"❌ Erreur création bot: {e}")
            log_debug(traceback.format_exc())
            return
        
        self.bots[token_id] = bot
        
        try:
            log_info(f"🔄 Connexion de {name}...")
            loop.run_until_complete(bot.start(token))
        except discord.LoginFailure:
            log_error(f"❌ {name}: TOKEN INVALIDE !")
            with db.cursor() as c:
                c.execute("UPDATE tokens SET status=? WHERE id=?", ('invalid', token_id))
            self.stats['failed_connections'] += 1
        except Exception as e:
            log_error(f"❌ {name}: Erreur {type(e).__name__}")
            log_debug(traceback.format_exc())
            with db.cursor() as c:
                c.execute("UPDATE tokens SET status=? WHERE id=?", ('error', token_id))
            self.stats['failed_connections'] += 1
    
    async def _join_voice(self, bot, channel_id):
        log_info(f"🔊 Tentative de join vocal sur {channel_id}")
        try:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                return False, "Channel introuvable"
            if not isinstance(channel, discord.VoiceChannel):
                return False, "Salon non vocal"
            
            log_info(f"📡 Channel: {channel.name}")
            
            if bot.voice_clients:
                for vc in bot.voice_clients:
                    await vc.disconnect()
            
            await channel.connect()
            log_success(f"✅ Connecté à {channel.name}")
            self.stats['voice_joins'] += 1
            
            for tid, b in self.bots.items():
                if b == bot:
                    with db.cursor() as c:
                        c.execute("UPDATE tokens SET in_voice=1 WHERE id=?", (tid,))
                    break
            
            return True, f"Connecté à {channel.name}"
        except Exception as e:
            log_error(f"❌ Erreur join: {e}")
            return False, str(e)
    
    def join_voice(self, token_id, channel_id):
        if token_id not in self.bots:
            return False, "Bot non trouvé"
        
        bot = self.bots[token_id]
        loop = self.loops.get(token_id)
        if not loop:
            return False, "Erreur interne"
        
        future = asyncio.run_coroutine_threadsafe(
            self._join_voice(bot, channel_id), loop
        )
        try:
            return future.result(timeout=15)
        except Exception as e:
            return False, str(e)
    
    async def _leave_voice(self, bot):
        try:
            if bot.voice_clients:
                for vc in bot.voice_clients:
                    await vc.disconnect()
                
                for tid, b in self.bots.items():
                    if b == bot:
                        with db.cursor() as c:
                            c.execute("UPDATE tokens SET in_voice=0 WHERE id=?", (tid,))
                        break
                
                return True, "Déconnecté"
            return False, "Pas en vocal"
        except Exception as e:
            return False, str(e)
    
    def leave_voice(self, token_id):
        if token_id not in self.bots:
            return False, "Bot non trouvé"
        
        bot = self.bots[token_id]
        loop = self.loops.get(token_id)
        if not loop:
            return False, "Erreur interne"
        
        future = asyncio.run_coroutine_threadsafe(
            self._leave_voice(bot), loop
        )
        try:
            return future.result(timeout=10)
        except Exception as e:
            return False, str(e)
    
    async def _change_status(self, bot, status):
        status_map = {
            'online': discord.Status.online,
            'idle': discord.Status.idle,
            'dnd': discord.Status.dnd,
            'invisible': discord.Status.invisible
        }
        if status in status_map:
            await bot.change_presence(status=status_map[status])
            return True, f"Statut changé en {status}"
        return False, "Statut invalide"
    
    def change_status(self, token_id, status):
        if token_id not in self.bots:
            return False, "Bot non trouvé"
        
        bot = self.bots[token_id]
        loop = self.loops.get(token_id)
        if not loop:
            return False, "Erreur interne"
        
        future = asyncio.run_coroutine_threadsafe(
            self._change_status(bot, status), loop
        )
        try:
            return future.result(timeout=10)
        except Exception as e:
            return False, str(e)

bot_manager = BotManager()

def start_existing_bots():
    time.sleep(3)
    try:
        with db.cursor() as c:
            c.execute("SELECT id, token, name FROM tokens")
            existing_tokens = c.fetchall()
        
        log_info(f"📊 {len(existing_tokens)} token(s) trouvé(s)")
        
        for token_id, token, name in existing_tokens:
            log_info(f"➕ Démarrage de {name} (ID: {token_id})...")
            bot_manager.add_bot(token_id, token, name)
            time.sleep(1.5)
        
        log_success("✅ Tous les bots démarrés")
    except Exception as e:
        log_error(f"❌ Erreur: {e}")

# ==================== ROUTES API ====================
@app.route('/', methods=['GET', 'OPTIONS'])
def home():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({
        "status": "online",
        "message": "SelfBot API",
        "version": "3.0"
    })

@app.route('/api/tokens', methods=['GET', 'OPTIONS'])
def get_tokens():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        with db.cursor() as c:
            c.execute("SELECT * FROM tokens ORDER BY id DESC")
            tokens = c.fetchall()
        
        return jsonify([{
            'id': t[0],
            'name': t[2],
            'status': t[3],
            'user_id': t[4],
            'username': t[5],
            'in_voice': t[6],
            'last_seen': t[7]
        } for t in tokens])
    except Exception as e:
        log_error(f"❌ Erreur: {e}")
        return jsonify([])

@app.route('/api/tokens', methods=['POST', 'OPTIONS'])
def add_token():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json
    token = data.get('token')
    name = data.get('name', 'Bot')
    
    if not token:
        return jsonify({'success': False, 'error': 'Token requis'}), 400
    
    try:
        with db.cursor() as c:
            c.execute("INSERT INTO tokens (token, name, last_seen) VALUES (?, ?, ?)",
                     (token, name, datetime.now()))
            token_id = c.lastrowid
        
        log_success(f"✅ Token {name} ajouté (ID: {token_id})")
        bot_manager.add_bot(token_id, token, name)
        return jsonify({'success': True, 'id': token_id})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Token existe déjà'}), 400
    except Exception as e:
        log_error(f"❌ Erreur: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tokens/<int:token_id>', methods=['DELETE', 'OPTIONS'])
def delete_token(token_id):
    if request.method == 'OPTIONS':
        return '', 200
    try:
        with db.cursor() as c:
            c.execute("DELETE FROM tokens WHERE id=?", (token_id,))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tokens/<int:token_id>/join', methods=['POST', 'OPTIONS'])
def join_voice(token_id):
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json
    channel = data.get('channel')
    
    if not channel:
        return jsonify({'success': False, 'message': 'Channel requis'}), 400
    
    success, message = bot_manager.join_voice(token_id, channel)
    return jsonify({'success': success, 'message': message})

@app.route('/api/tokens/<int:token_id>/leave', methods=['POST', 'OPTIONS'])
def leave_voice(token_id):
    if request.method == 'OPTIONS':
        return '', 200
    success, message = bot_manager.leave_voice(token_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/tokens/<int:token_id>/status', methods=['POST', 'OPTIONS'])
def change_status(token_id):
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json
    status = data.get('status')
    
    if not status:
        return jsonify({'success': False, 'message': 'Status requis'}), 400
    
    success, message = bot_manager.change_status(token_id, status)
    return jsonify({'success': success, 'message': message})

# ==================== DÉMARRAGE ====================
if __name__ == '__main__':
    threading.Thread(target=start_existing_bots, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    log_info(f"🌍 Démarrage sur le port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
