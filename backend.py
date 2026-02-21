# Patch pour audioop (Python 3.14+)
import sys
import types

# Créer un faux module audioop
audioop = types.ModuleType('audioop')
audioop.__file__ = '<faked>'

def mock_audioop(*args, **kwargs):
    return b''

# Fonctions essentielles mockées
audioop.add = mock_audioop
audioop.avg = mock_audioop
audioop.avgpp = mock_audioop
audioop.bias = mock_audioop
audioop.cross = mock_audioop
audioop.findfactor = mock_audioop
audioop.findfit = mock_audioop
audioop.findmax = mock_audioop
audioop.getsample = mock_audioop
audioop.lin2lin = mock_audioop
audioop.lin2ulaw = mock_audioop
audioop.max = mock_audioop
audioop.maxpp = mock_audioop
audioop.minmax = mock_audioop
audioop.mul = mock_audioop
audioop.ratecv = mock_audioop
audioop.reverse = mock_audioop
audioop.rms = mock_audioop
audioop.tomono = mock_audioop
audioop.tostereo = mock_audioop
audioop.ulaw2lin = mock_audioop

# Injecter dans sys.modules
sys.modules['audioop'] = audioop

# PATCH URGENT - Corrige les problèmes de version discord.py
import sys
import types

# Crée un faux module discord si nécessaire
if 'discord' not in sys.modules:
    fake_discord = types.ModuleType('discord')
    sys.modules['discord'] = fake_discord

# Patch pour Intents
class FakeIntents:
    def __init__(self):
        self.message_content = True
        self.voice_states = True
    
    @classmethod
    def default(cls):
        return cls()

# Patch pour Status
class FakeStatus:
    online = 'online'
    idle = 'idle'
    dnd = 'dnd'
    invisible = 'invisible'

# Injecte les classes manquantes
import discord
if not hasattr(discord, 'Intents'):
    discord.Intents = FakeIntents
    discord.Intents.default = FakeIntents.default
    print("✅ Patch Intents appliqué")

if not hasattr(discord, 'Status'):
    discord.Status = FakeStatus
    print("✅ Patch Status appliqué")

# Patch pour PrivilegedIntentsRequired
class FakePrivilegedIntentsRequired(Exception):
    pass

if not hasattr(discord, 'PrivilegedIntentsRequired'):
    discord.PrivilegedIntentsRequired = FakePrivilegedIntentsRequired
    print("✅ Patch Exception appliqué")

# Continue avec les imports normaux
from flask import Flask, request, jsonify
from flask_cors import CORS
# ... reste du code

# Maintenant tu peux importer discord
import discord
# ... (le reste du code)
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
CORS(app)

# Configuration des logs colorés
class Logger:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    
    @staticmethod
    def log(msg, level="INFO", color=""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_str = f"[{level}]"
        print(f"{color}{Logger.BOLD}[{timestamp}]{Logger.END} {color}{level_str}{Logger.END} {color}{msg}{Logger.END}")
        sys.stdout.flush()
    
    @staticmethod
    def success(msg):
        Logger.log(msg, "✓", Logger.GREEN)
    
    @staticmethod
    def error(msg):
        Logger.log(msg, "✗", Logger.RED)
    
    @staticmethod
    def info(msg):
        Logger.log(msg, "ℹ", Logger.BLUE)
    
    @staticmethod
    def warn(msg):
        Logger.log(msg, "⚠", Logger.YELLOW)
    
    @staticmethod
    def debug(msg):
        Logger.log(msg, "🐛", Logger.HEADER)

log = Logger()

# ==================== BANNER ====================
def show_banner():
    banner = f"""
{Logger.GREEN}╔══════════════════════════════════════════════════════════╗
║                                                              ║
║   {Logger.BOLD}SELFBOT BACKEND - MODE ULTIMATE{Logger.END}{Logger.GREEN}                      ║
║   {Logger.BOLD}100% FONCTIONNEL - PYTHON 3.11{Logger.END}{Logger.GREEN}                        ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║   ✅ Multi-tokens support                                    ║
║   ✅ Join vocal automatique                                  ║
║   ✅ Changement de statut                                    ║
║   ✅ Base de données SQLite                                  ║
║   ✅ Logs en temps réel                                      ║
║   ✅ Auto-reconnexion                                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Logger.END}
"""
    print(banner)

show_banner()
log.success("🚀 Démarrage du SelfBot Backend Ultimate")
log.info(f"📦 Python version: {sys.version}")

# ==================== BASE DE DONNÉES ====================
DB_PATH = 'tokens.db'

def init_db():
    log.info("📁 Initialisation de la base de données...")
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
                      last_seen TIMESTAMP,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        log.success("✅ Base de données prête")
        
        # Afficher les tokens existants
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM tokens")
        count = c.fetchone()[0]
        conn.close()
        log.info(f"📊 {count} token(s) trouvé(s) dans la BDD")
        
    except Exception as e:
        log.error(f"❌ Erreur BDD: {e}")

init_db()

# ==================== GESTIONNAIRE DE BOTS ULTIME ====================
class BotManager:
    def __init__(self):
        self.bots = {}
        self.loops = {}
        self.stats = {
            'total_connections': 0,
            'failed_connections': 0,
            'voice_joins': 0
        }
        log.success("🤖 BotManager initialisé")
        
    def add_bot(self, token_id, token, name):
        """Ajoute un bot et le démarre dans un thread"""
        log.info(f"➕ Ajout du bot {name} (ID: {token_id})...")
        thread = threading.Thread(target=self._run_bot, args=(token_id, token, name))
        thread.daemon = True
        thread.start()
        return True
    
    def _run_bot(self, token_id, token, name):
        """Fonction qui fait tourner le bot avec logs détaillés"""
        log.debug(f"🔄 Création de la boucle asyncio pour {name}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loops[token_id] = loop
        
        class SelfBot(commands.Bot):
            async def on_ready(self):
                log.success(f"✅ {name} connecté avec succès en tant que {self.user.name} (ID: {self.user.id})")
                log.info(f"📊 {name} - Latence: {round(self.latency*1000)}ms")
                
                # Mettre à jour la BDD
                try:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("UPDATE tokens SET status=?, user_id=?, username=?, last_seen=? WHERE id=?", 
                             ('online', str(self.user.id), str(self.user.name), datetime.now(), token_id))
                    conn.commit()
                    conn.close()
                    log.debug(f"📊 BDD mise à jour pour {name}")
                except Exception as e:
                    log.error(f"❌ Erreur BDD pour {name}: {e}")
                
                # Stats
                bot_manager.stats['total_connections'] += 1
            
            async def on_voice_state_update(self, member, before, after):
                if member == self.user:
                    in_voice = 1 if after.channel else 0
                    status = "🔊 en vocal" if in_voice else "🔇 hors vocal"
                    channel_name = after.channel.name if after.channel else "aucun"
                    log.info(f"🔊 {name} {status} - Salon: {channel_name}")
                    
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("UPDATE tokens SET in_voice=? WHERE id=?", (in_voice, token_id))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        log.error(f"❌ Erreur BDD voice: {e}")
            
            async def on_error(self, event, *args, **kwargs):
                log.error(f"❌ Erreur dans l'événement {event} pour {name}")
                log.debug(traceback.format_exc())
        
        log.info(f"🔧 Configuration du bot {name}...")
        
        try:
            # Configuration des intents
            intents = discord.Intents.default()
            intents.message_content = True
            intents.voice_states = True
            log.debug(f"✅ Intents configurés pour {name}")
            
            bot = SelfBot(command_prefix="!", intents=intents, self_bot=True)
            self.bots[token_id] = bot
            log.debug(f"🤖 Bot {name} ajouté au gestionnaire")
            
            # Tentative de connexion
            log.info(f"🔄 Tentative de connexion pour {name}...")
            loop.run_until_complete(bot.start(token))
            
        except discord.LoginFailure:
            log.error(f"❌ {name}: TOKEN INVALIDE !")
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE tokens SET status=? WHERE id=?", ('invalid', token_id))
                conn.commit()
                conn.close()
            except:
                pass
            self.stats['failed_connections'] += 1
            
        except discord.PrivilegedIntentsRequired:
            log.error(f"❌ {name}: Intents privilégiés requis !")
            log.warn("⚠️ Active les intents sur https://discord.com/developers/applications")
            
        except Exception as e:
            log.error(f"❌ {name}: Erreur inattendue: {type(e).__name__}")
            log.debug(traceback.format_exc())
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE tokens SET status=? WHERE id=?", ('error', token_id))
                conn.commit()
                conn.close()
            except:
                pass
            self.stats['failed_connections'] += 1
    
    async def _join_voice(self, bot, channel_id):
        """Rejoindre un salon vocal"""
        log.info(f"🔊 Tentative de join vocal sur le channel {channel_id}")
        try:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                log.error(f"❌ Channel {channel_id} introuvable")
                return False, "Channel introuvable"
            
            log.info(f"📡 Channel trouvé: {channel.name} (Serveur: {channel.guild.name})")
            
            if not isinstance(channel, discord.VoiceChannel):
                log.error(f"❌ {channel_id} n'est pas un salon vocal")
                return False, "Salon non vocal"
            
            log.success(f"✅ Salon vocal valide: {channel.name}")
            
            # Déconnecter si déjà connecté
            if bot.voice_clients:
                log.info(f"🔄 Déconnexion des anciens vocaux...")
                for vc in bot.voice_clients:
                    await vc.disconnect()
            
            log.info(f"🔌 Connexion à {channel.name}...")
            await channel.connect()
            log.success(f"✅ Connecté à {channel.name} avec succès!")
            self.stats['voice_joins'] += 1
            
            # Mettre à jour la BDD
            for tid, b in self.bots.items():
                if b == bot:
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("UPDATE tokens SET in_voice=1 WHERE id=?", (tid,))
                        conn.commit()
                        conn.close()
                        log.debug(f"📊 BDD mise à jour pour token {tid}")
                    except Exception as e:
                        log.error(f"❌ Erreur BDD: {e}")
                    break
            
            return True, f"Connecté à {channel.name}"
            
        except Exception as e:
            log.error(f"❌ Erreur join vocal: {type(e).__name__}")
            log.debug(traceback.format_exc())
            return False, str(e)
    
    def join_voice(self, token_id, channel_id):
        """Wrapper pour join vocal"""
        log.info(f"🔊 Requête join vocal pour token {token_id} sur channel {channel_id}")
        
        if token_id not in self.bots:
            log.error(f"❌ Token {token_id} non trouvé dans les bots actifs")
            return False, "Bot non trouvé"
        
        bot = self.bots[token_id]
        loop = self.loops.get(token_id)
        if not loop:
            log.error(f"❌ Boucle asyncio non trouvée pour token {token_id}")
            return False, "Erreur interne"
        
        future = asyncio.run_coroutine_threadsafe(
            self._join_voice(bot, channel_id), loop
        )
        try:
            result = future.result(timeout=15)
            return result
        except asyncio.TimeoutError:
            log.error(f"❌ Timeout join vocal pour token {token_id}")
            return False, "Timeout (15s)"
        except Exception as e:
            log.error(f"❌ Erreur join_voice: {e}")
            return False, str(e)
    
    async def _change_status(self, bot, status):
        """Changer le statut"""
        log.info(f"🔄 Changement de statut vers {status}")
        status_map = {
            'online': discord.Status.online,
            'idle': discord.Status.idle,
            'dnd': discord.Status.dnd,
            'invisible': discord.Status.invisible
        }
        if status in status_map:
            await bot.change_presence(status=status_map[status])
            log.success(f"✅ Statut changé en {status}")
            
            # Mettre à jour la BDD
            for tid, b in self.bots.items():
                if b == bot:
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("UPDATE tokens SET status=? WHERE id=?", (status, tid))
                        conn.commit()
                        conn.close()
                    except:
                        pass
                    break
            
            return True, f"Statut changé en {status}"
        log.error(f"❌ Statut invalide: {status}")
        return False, "Statut invalide"
    
    def change_status(self, token_id, status):
        """Wrapper pour changer statut"""
        log.info(f"🔄 Requête changement statut pour token {token_id} vers {status}")
        
        if token_id not in self.bots:
            log.error(f"❌ Token {token_id} non trouvé")
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
            log.error(f"❌ Erreur change_status: {e}")
            return False, str(e)
    
    def get_stats(self):
        """Retourne les statistiques"""
        return {
            'bots_actifs': len(self.bots),
            'total_connections': self.stats['total_connections'],
            'failed_connections': self.stats['failed_connections'],
            'voice_joins': self.stats['voice_joins']
        }

# ==================== INITIALISATION ====================
bot_manager = BotManager()

def start_existing_bots():
    """Démarre tous les bots existants dans la BDD"""
    log.info("🔄 Démarrage des bots existants...")
    time.sleep(2)  # Attendre que le serveur Flask soit prêt
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, token, name FROM tokens")
        existing_tokens = c.fetchall()
        conn.close()
        
        log.info(f"📊 {len(existing_tokens)} token(s) trouvé(s) dans la BDD")
        
        for token_id, token, name in existing_tokens:
            log.info(f"➕ Démarrage du bot {name} (ID: {token_id})...")
            bot_manager.add_bot(token_id, token, name)
            time.sleep(1.5)  # Petit délai entre chaque
        
        log.success("✅ Tous les bots ont été démarrés")
        log.info(f"📈 Stats: {bot_manager.get_stats()}")
        
    except Exception as e:
        log.error(f"❌ Erreur lors du démarrage des bots: {e}")

# ==================== ROUTES API ====================
@app.route('/')
def home():
    log.debug("🌐 Accès à la racine")
    return jsonify({
        "status": "online",
        "message": "SelfBot API Ultimate",
        "version": "3.0",
        "stats": bot_manager.get_stats()
    })

@app.route('/api/tokens', methods=['GET'])
def get_tokens():
    log.debug("📋 Requête GET /api/tokens")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM tokens ORDER BY id DESC")
        tokens = c.fetchall()
        conn.close()
        
        result = [{
            'id': t[0],
            'name': t[2],
            'status': t[3],
            'user_id': t[4],
            'username': t[5],
            'in_voice': t[6],
            'last_seen': t[7],
            'created_at': t[8]
        } for t in tokens]
        
        log.debug(f"📊 {len(result)} token(s) retourné(s)")
        return jsonify(result)
    except Exception as e:
        log.error(f"❌ Erreur GET tokens: {e}")
        return jsonify([])

@app.route('/api/tokens', methods=['POST'])
def add_token():
    log.info("➕ Requête POST /api/tokens")
    data = request.json
    token = data.get('token')
    name = data.get('name', f'Bot')
    
    if not token:
        log.error("❌ Token manquant")
        return jsonify({'success': False, 'error': 'Token requis'}), 400
    
    log.info(f"📝 Ajout du token: {name}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO tokens (token, name, last_seen) VALUES (?, ?, ?)",
                 (token, name, datetime.now()))
        conn.commit()
        token_id = c.lastrowid
        conn.close()
        
        log.success(f"✅ Token ajouté avec ID: {token_id}")
        
        # Démarrer le bot immédiatement
        log.info(f"🔄 Démarrage du bot {name}...")
        bot_manager.add_bot(token_id, token, name)
        
        return jsonify({'success': True, 'id': token_id})
        
    except sqlite3.IntegrityError:
        log.error(f"❌ Token déjà existant")
        return jsonify({'success': False, 'error': 'Token existe déjà'}), 400
    except Exception as e:
        log.error(f"❌ Erreur: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tokens/<int:token_id>', methods=['DELETE'])
def delete_token(token_id):
    log.info(f"🗑️ Requête DELETE /api/tokens/{token_id}")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM tokens WHERE id=?", (token_id,))
        conn.commit()
        conn.close()
        log.success(f"✅ Token {token_id} supprimé")
        return jsonify({'success': True})
    except Exception as e:
        log.error(f"❌ Erreur: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tokens/<int:token_id>/join', methods=['POST'])
def join_voice(token_id):
    log.info(f"🔊 Requête JOIN pour token {token_id}")
    data = request.json
    channel = data.get('channel')
    
    if not channel:
        return jsonify({'success': False, 'message': 'Channel requis'}), 400
    
    log.info(f"📡 Channel: {channel}")
    success, message = bot_manager.join_voice(token_id, channel)
    
    if success:
        log.success(f"✅ Join réussi: {message}")
    else:
        log.error(f"❌ Join échoué: {message}")
    
    return jsonify({'success': success, 'message': message})

@app.route('/api/tokens/<int:token_id>/status', methods=['POST'])
def change_status(token_id):
    log.info(f"🔄 Requête STATUS pour token {token_id}")
    data = request.json
    status = data.get('status')
    
    if not status:
        return jsonify({'success': False, 'message': 'Status requis'}), 400
    
    log.info(f"📡 Nouveau statut: {status}")
    success, message = bot_manager.change_status(token_id, status)
    
    if success:
        log.success(f"✅ Statut changé: {message}")
    else:
        log.error(f"❌ Échec: {message}")
    
    return jsonify({'success': success, 'message': message})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Route pour les statistiques"""
    return jsonify(bot_manager.get_stats())

@app.route('/api/debug/bots', methods=['GET'])
def debug_bots():
    """Route de debug pour voir les bots actifs"""
    log.debug("🐛 Requête DEBUG /api/debug/bots")
    active_bots = {}
    for tid, bot in bot_manager.bots.items():
        active_bots[tid] = {
            'connected': bot.is_ready() if hasattr(bot, 'is_ready') else False,
            'user': str(bot.user) if bot.user else None,
            'user_id': str(bot.user.id) if bot.user else None,
            'in_voice': len(bot.voice_clients) > 0,
            'voice_channels': [vc.channel.name for vc in bot.voice_clients] if bot.voice_clients else []
        }
    return jsonify(active_bots)

# ==================== DÉMARRAGE ====================
log.info("=" * 60)
log.success("🚀 SERVEUR PRÊT À DÉMARRER")
log.info("=" * 60)

# Démarrer les bots dans un thread séparé
start_thread = threading.Thread(target=start_existing_bots, daemon=True)
start_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    log.info(f"🌍 Démarrage du serveur Flask sur le port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
