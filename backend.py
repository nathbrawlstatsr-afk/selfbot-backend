# backend.py (version allégée sans dépendances audio)
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

# Patch pour éviter audioop
import sys
sys.modules['audioop'] = type('Mock', (), {'__file__': None})()
import builtins
builtins.audioop = sys.modules['audioop']

app = Flask(__name__)
CORS(app)

def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")
    sys.stdout.flush()

log("🚀 Démarrage du SelfBot Backend", "INFO")

# Base de données
def init_db():
    conn = sqlite3.connect('tokens.db')
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

init_db()

class BotManager:
    def __init__(self):
        self.bots = {}
        self.loops = {}
        
    def add_bot(self, token_id, token, name):
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
                log(f"✅ {name} connecté: {self.user.name}", "SUCCESS")
                conn = sqlite3.connect('tokens.db')
                c = conn.cursor()
                c.execute("UPDATE tokens SET status=?, user_id=?, username=?, last_seen=? WHERE id=?", 
                         ('online', str(self.user.id), str(self.user), datetime.now(), token_id))
                conn.commit()
                conn.close()
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        bot = SelfBot(command_prefix="!", intents=intents, self_bot=True)
        self.bots[token_id] = bot
        
        try:
            loop.run_until_complete(bot.start(token))
        except discord.LoginFailure:
            log(f"❌ {name}: Token invalide", "ERROR")
        except Exception as e:
            log(f"❌ {name}: Erreur {e}", "ERROR")
    
    async def _join_voice(self, bot, channel_id):
        try:
            channel = bot.get_channel(int(channel_id))
            if not channel or not isinstance(channel, discord.VoiceChannel):
                return False, "Salon invalide"
            
            if bot.voice_clients:
                for vc in bot.voice_clients:
                    await vc.disconnect()
            
            await channel.connect()
            return True, "Connecté"
        except Exception as e:
            return False, str(e)
    
    def join_voice(self, token_id, channel_id):
        if token_id not in self.bots:
            return False, "Bot non trouvé"
        
        bot = self.bots[token_id]
        loop = self.loops.get(token_id)
        if not loop:
            return False, "Erreur"
        
        future = asyncio.run_coroutine_threadsafe(
            self._join_voice(bot, channel_id), loop
        )
        try:
            return future.result(timeout=15)
        except:
            return False, "Timeout"

bot_manager = BotManager()

def start_existing_bots():
    conn = sqlite3.connect('tokens.db')
    c = conn.cursor()
    c.execute("SELECT id, token, name FROM tokens")
    existing_tokens = c.fetchall()
    conn.close()
    
    for token_id, token, name in existing_tokens:
        log(f"➕ Démarrage de {name}", "INFO")
        bot_manager.add_bot(token_id, token, name)
        time.sleep(1)

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "SelfBot API"})

@app.route('/api/tokens', methods=['GET'])
def get_tokens():
    conn = sqlite3.connect('tokens.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tokens ORDER BY id DESC")
    tokens = c.fetchall()
    conn.close()
    return jsonify([{
        'id': t[0],
        'name': t[2],
        'status': t[3],
        'username': t[5],
        'in_voice': t[6]
    } for t in tokens])

@app.route('/api/tokens', methods=['POST'])
def add_token():
    data = request.json
    token = data.get('token')
    name = data.get('name', 'Bot')
    
    conn = sqlite3.connect('tokens.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO tokens (token, name, last_seen) VALUES (?, ?, ?)",
                 (token, name, datetime.now()))
        conn.commit()
        token_id = c.lastrowid
        conn.close()
        bot_manager.add_bot(token_id, token, name)
        return jsonify({'success': True, 'id': token_id})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': 'Token existe déjà'}), 400

@app.route('/api/tokens/<int:token_id>/join', methods=['POST'])
def join_voice(token_id):
    data = request.json
    channel = data.get('channel')
    success, msg = bot_manager.join_voice(token_id, channel)
    return jsonify({'success': success, 'message': msg})

if __name__ == '__main__':
    threading.Thread(target=lambda: [time.sleep(3), start_existing_bots()], daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
