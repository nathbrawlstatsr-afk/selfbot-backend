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

# ==================== CONFIGURATION ====================
app = Flask(__name__)
# CORS large pour accepter toutes les requêtes Netlify
CORS(app, origins=["https://*.netlify.app", "https://tokens-discord.netlify.app", "http://localhost:3000"])

# Configuration des logs
def log(msg, level="INFO", color=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")
    sys.stdout.flush()

log("="*60)
log("🚀 DÉMARRAGE DU SELFBOT BACKEND - VERSION FINALE", "SUCCESS")
log("="*60)

# ==================== BASE DE DONNÉES ====================
DB_PATH = 'tokens.db'

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS tokens
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      token TEXT UNIQUE,
                      name TEXT,
                      status TEXT DEFAULT 'offline',
                      user_id TEXT,
                      username TEXT,
                      in_voice INTEGER DEFAULT 0,
                      last_seen TIMESTAMP)''')
        conn.commit()
        conn.close()
        log("✅ Base de données initialisée", "SUCCESS")
    except Exception as e:
        log(f"❌ Erreur BDD: {e}", "ERROR")

init_db()

# ==================== GESTIONNAIRE DE BOTS ====================
class BotManager:
    def __init__(self):
        self.bots = {}
        self.loops = {}
        log("🤖 BotManager initialisé", "INFO")
        
    def add_bot(self, token_id, token, name):
        log(f"➕ Ajout du bot {name} (ID: {token_id})...", "INFO")
        thread = threading.Thread(target=self._run_bot, args=(token_id, token, name))
        thread.daemon = True
        thread.start()
        return True
    
    def _run_bot(self, token_id, token, name):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loops[token_id] = loop
        
        class SelfBot(commands.Bot):
            async def on_ready(self):
                log(f"✅ {name} connecté: {self.user.name} (ID: {self.user.id})", "SUCCESS")
                try:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("UPDATE tokens SET status=?, user_id=?, username=?, last_seen=? WHERE id=?", 
                             ('online', str(self.user.id), str(self.user), datetime.now(), token_id))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    log(f"❌ Erreur BDD: {e}", "ERROR")
            
            async def on_voice_state_update(self, member, before, after):
                if member == self.user:
                    in_voice = 1 if after.channel else 0
                    log(f"🔊 {name} {'en vocal' if in_voice else 'hors vocal'}", "INFO")
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("UPDATE tokens SET in_voice=? WHERE id=?", (in_voice, token_id))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        log(f"❌ Erreur BDD: {e}", "ERROR")
        
        # Configuration des intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        bot = SelfBot(command_prefix="!", intents=intents, self_bot=True)
        self.bots[token_id] = bot
        
        try:
            log(f"🔄 Connexion de {name}...", "INFO")
            loop.run_until_complete(bot.start(token))
        except discord.LoginFailure:
            log(f"❌ {name}: Token invalide", "ERROR")
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE tokens SET status=? WHERE id=?", ('invalid', token_id))
                conn.commit()
                conn.close()
            except: pass
        except Exception as e:
            log(f"❌ {name}: Erreur {type(e).__name__}", "ERROR")
            log(traceback.format_exc())
    
    async def _join_voice(self, bot, channel_id):
        try:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                return False, "Channel introuvable"
            if not isinstance(channel, discord.VoiceChannel):
                return False, "Salon non vocal"
            
            log(f"🔊 Connexion à {channel.name}...", "INFO")
            if bot.voice_clients:
                for vc in bot.voice_clients:
                    await vc.disconnect()
            
            await channel.connect()
            log(f"✅ Connecté à {channel.name}", "SUCCESS")
            return True, f"Connecté à {channel.name}"
        except Exception as e:
            log(f"❌ Erreur join: {e}", "ERROR")
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
                log(f"✅ Déconnecté", "SUCCESS")
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
            log(f"✅ Statut changé en {status}", "SUCCESS")
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
    """Démarre les bots existants après le lancement du serveur"""
    time.sleep(3)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, token, name FROM tokens")
        existing_tokens = c.fetchall()
        conn.close()
        
        log(f"📊 {len(existing_tokens)} token(s) trouvé(s)", "INFO")
        for token_id, token, name in existing_tokens:
            log(f"➕ Démarrage de {name} (ID: {token_id})...", "INFO")
            bot_manager.add_bot(token_id, token, name)
            time.sleep(1.5)
    except Exception as e:
        log(f"❌ Erreur démarrage bots: {e}", "ERROR")

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
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM tokens ORDER BY id DESC")
        tokens = c.fetchall()
        conn.close()
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
        log(f"❌ Erreur GET tokens: {e}", "ERROR")
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
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO tokens (token, name, last_seen) VALUES (?, ?, ?)",
                 (token, name, datetime.now()))
        conn.commit()
        token_id = c.lastrowid
        conn.close()
        
        log(f"✅ Token {name} ajouté (ID: {token_id})", "SUCCESS")
        bot_manager.add_bot(token_id, token, name)
        return jsonify({'success': True, 'id': token_id})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Token existe déjà'}), 400
    except Exception as e:
        log(f"❌ Erreur: {e}", "ERROR")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tokens/<int:token_id>', methods=['DELETE', 'OPTIONS'])
def delete_token(token_id):
    if request.method == 'OPTIONS':
        return '', 200
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM tokens WHERE id=?", (token_id,))
        conn.commit()
        conn.close()
        log(f"✅ Token {token_id} supprimé", "SUCCESS")
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
    # Démarrer les bots dans un thread séparé
    threading.Thread(target=start_existing_bots, daemon=True).start()
    
    # Démarrer le serveur Flask
    port = int(os.environ.get('PORT', 5000))
    log(f"🌍 Démarrage du serveur sur le port {port}", "INFO")
    app.run(host='0.0.0.0', port=port, debug=False)
