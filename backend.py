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

app = Flask(__name__)
CORS(app)

# Configuration des logs
def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")
    sys.stdout.flush()

log("="*60)
log("🚀 DÉMARRAGE DU SELFBOT BACKEND", "SUCCESS")
log("="*60)

# Base de données
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
        log("✅ Base de données prête", "SUCCESS")
    except Exception as e:
        log(f"❌ Erreur BDD: {e}", "ERROR")

init_db()

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
    
    async def _join_voice(self, bot, channel_id):
        try:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                return False, "Channel introuvable"
            if not isinstance(channel, discord.VoiceChannel):
                return False, "Salon non vocal"
            
            if bot.voice_clients:
                for vc in bot.voice_clients:
                    await vc.disconnect()
            
            await channel.connect()
            log(f"✅ Connecté à {channel.name}", "SUCCESS")
            return True, f"Connecté à {channel.name}"
        except Exception as e:
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

bot_manager = BotManager()

def start_existing_bots():
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

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "SelfBot API",
        "version": "3.0"
    })

@app.route('/api/tokens', methods=['GET'])
def get_tokens():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM tokens ORDER BY id DESC")
        tokens = c.fetchall()
        conn.close()
        return jsonify([{
            'id': t[0], 'name': t[2], 'status': t[3],
            'user_id': t[4], 'username': t[5], 'in_voice': t[6],
            'last_seen': t[7]
        } for t in tokens])
    except Exception as e:
        return jsonify([])

@app.route('/api/tokens', methods=['POST'])
def add_token():
    data = request.json
    token = data.get('token')
    name = data.get('name', 'Bot')
    
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

@app.route('/api/tokens/<int:token_id>', methods=['DELETE'])
def delete_token(token_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM tokens WHERE id=?", (token_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'success': False}), 500

@app.route('/api/tokens/<int:token_id>/join', methods=['POST'])
def join_voice(token_id):
    data = request.json
    channel = data.get('channel')
    success, msg = bot_manager.join_voice(token_id, channel)
    return jsonify({'success': success, 'message': msg})

if __name__ == '__main__':
    threading.Thread(target=start_existing_bots, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
