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
def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")
    sys.stdout.flush()

def log_success(msg):
    log(msg, "✅")

def log_error(msg):
    log(msg, "❌")

def log_warn(msg):
    log(msg, "⚠️")

def log_info(msg):
    log(msg, "ℹ️")

def log_debug(msg):
    log(msg, "🐛")

log_info("="*60)
log_success("🚀 DÉMARRAGE DU SELFBOT BACKEND - VERSION FINALE")
log_info(f"📦 Python version: {sys.version}")
log_info("="*60)

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
        log_success("✅ Base de données initialisée")
    except Exception as e:
        log_error(f"❌ Erreur BDD: {e}")

init_db()

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
                
                # Mettre à jour la BDD
                try:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("UPDATE tokens SET status=?, user_id=?, username=?, last_seen=? WHERE id=?", 
                             ('online', str(self.user.id), str(self.user), datetime.now(), token_id))
                    conn.commit()
                    conn.close()
                    log_debug(f"📊 BDD mise à jour pour {name}")
                except Exception as e:
                    log_error(f"❌ Erreur BDD: {e}")
                
                # Stats
                bot_manager.stats['total_connections'] += 1
            
            async def on_voice_state_update(self, member, before, after):
                if member == self.user:
                    in_voice = 1 if after.channel else 0
                    channel_name = after.channel.name if after.channel else "aucun"
                    log_info(f"🔊 {name} {'en vocal' if in_voice else 'hors vocal'} - Salon: {channel_name}")
                    
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("UPDATE tokens SET in_voice=? WHERE id=?", (in_voice, token_id))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        log_error(f"❌ Erreur BDD voice: {e}")
            
            async def on_error(self, event, *args, **kwargs):
                log_error(f"❌ Erreur dans l'événement {event} pour {name}")
                log_debug(traceback.format_exc())
        
        # ========== CONFIGURATION DES INTENTS - VERSION CORRIGÉE ==========
        log_info(f"🔧 Configuration des intents pour {name}...")
        
        # Essayer différentes méthodes pour les intents
        intents = None
        methods_tried = []
        
        # Méthode 1: Intents.all() (la plus complète)
        try:
            intents = discord.Intents.all()
            methods_tried.append("Intents.all()")
            log_success(f"✅ Méthode 1 réussie: Intents.all() pour {name}")
        except AttributeError:
            log_warn(f"⚠️ Méthode 1 échouée: Intents.all()")
        
        # Méthode 2: Intents.default() avec configuration manuelle
        if intents is None:
            try:
                intents = discord.Intents.default()
                intents.message_content = True
                intents.voice_states = True
                methods_tried.append("Intents.default() + config")
                log_success(f"✅ Méthode 2 réussie: Intents.default() configuré pour {name}")
            except AttributeError:
                log_warn(f"⚠️ Méthode 2 échouée: Intents.default()")
        
        # Méthode 3: Intents.none() (mode minimal)
        if intents is None:
            try:
                intents = discord.Intents.none()
                methods_tried.append("Intents.none()")
                log_warn(f"⚠️ Méthode 3 utilisée: Intents.none() pour {name} (mode dégradé)")
            except AttributeError:
                log_error(f"❌ Aucune méthode d'intents n'a fonctionné pour {name}")
        
        # Si toutes les méthodes échouent, créer un objet intents manuellement
        if intents is None:
            log_warn(f"⚠️ Création manuelle d'intents pour {name}")
            intents = type('Intents', (), {
                'message_content': True,
                'voice_states': True,
                'guilds': True,
                'members': True
            })()
            methods_tried.append("Intents manuel")
        
        log_info(f"📊 Méthodes essayées: {', '.join(methods_tried)}")
        
        # Création du bot
        try:
            bot = SelfBot(command_prefix="!", intents=intents, self_bot=True)
            log_success(f"✅ Bot {name} créé avec succès")
        except Exception as e:
            log_error(f"❌ Erreur création bot {name}: {e}")
            log_debug(traceback.format_exc())
            return
        
        self.bots[token_id] = bot
        log_debug(f"🤖 Bot {name} ajouté au gestionnaire")
        
        # Tentative de connexion
        try:
            log_info(f"🔄 Tentative de connexion pour {name}...")
            loop.run_until_complete(bot.start(token))
        except discord.LoginFailure:
            log_error(f"❌ {name}: TOKEN INVALIDE !")
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE tokens SET status=? WHERE id=?", ('invalid', token_id))
                conn.commit()
                conn.close()
            except: pass
            self.stats['failed_connections'] += 1
        except discord.PrivilegedIntentsRequired:
            log_error(f"❌ {name}: Intents privilégiés requis !")
        except Exception as e:
            log_error(f"❌ {name}: Erreur inattendue: {type(e).__name__}")
            log_debug(traceback.format_exc())
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE tokens SET status=? WHERE id=?", ('error', token_id))
                conn.commit()
                conn.close()
            except: pass
            self.stats['failed_connections'] += 1
    
    async def _join_voice(self, bot, channel_id):
        """Rejoindre un salon vocal"""
        log_info(f"🔊 Tentative de join vocal sur le channel {channel_id}")
        try:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                log_error(f"❌ Channel {channel_id} introuvable")
                return False, "Channel introuvable"
            
            log_info(f"📡 Channel trouvé: {channel.name} (Serveur: {channel.guild.name})")
            
            if not isinstance(channel, discord.VoiceChannel):
                log_error(f"❌ {channel_id} n'est pas un salon vocal")
                return False, "Salon non vocal"
            
            log_success(f"✅ Salon vocal valide: {channel.name}")
            
            # Déconnecter si déjà connecté
            if bot.voice_clients:
                log_info(f"🔄 Déconnexion des anciens vocaux...")
                for vc in bot.voice_clients:
                    await vc.disconnect()
            
            log_info(f"🔌 Connexion à {channel.name}...")
            await channel.connect()
            log_success(f"✅ Connecté à {channel.name} avec succès!")
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
                        log_debug(f"📊 BDD mise à jour pour token {tid}")
                    except Exception as e:
                        log_error(f"❌ Erreur BDD: {e}")
                    break
            
            return True, f"Connecté à {channel.name}"
            
        except Exception as e:
            log_error(f"❌ Erreur join vocal: {type(e).__name__}")
            log_debug(traceback.format_exc())
            return False, str(e)
    
    def join_voice(self, token_id, channel_id):
        """Wrapper pour join vocal"""
        log_info(f"🔊 Requête join vocal pour token {token_id} sur channel {channel_id}")
        
        if token_id not in self.bots:
            log_error(f"❌ Token {token_id} non trouvé dans les bots actifs")
            return False, "Bot non trouvé"
        
        bot = self.bots[token_id]
        loop = self.loops.get(token_id)
        if not loop:
            log_error(f"❌ Boucle asyncio non trouvée pour token {token_id}")
            return False, "Erreur interne"
        
        future = asyncio.run_coroutine_threadsafe(
            self._join_voice(bot, channel_id), loop
        )
        try:
            result = future.result(timeout=15)
            return result
        except asyncio.TimeoutError:
            log_error(f"❌ Timeout join vocal pour token {token_id}")
            return False, "Timeout (15s)"
        except Exception as e:
            log_error(f"❌ Erreur join_voice: {e}")
            return False, str(e)
    
    async def _leave_voice(self, bot):
        """Quitter le salon vocal"""
        log_info(f"🔇 Tentative de leave vocal")
        try:
            if bot.voice_clients:
                channel_name = bot.voice_clients[0].channel.name
                log_info(f"🔄 Déconnexion de {channel_name}...")
                
                for vc in bot.voice_clients:
                    await vc.disconnect()
                
                log_success(f"✅ Déconnecté de {channel_name}")
                
                # Mettre à jour la BDD
                for tid, b in self.bots.items():
                    if b == bot:
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            c = conn.cursor()
                            c.execute("UPDATE tokens SET in_voice=0 WHERE id=?", (tid,))
                            conn.commit()
                            conn.close()
                        except: pass
                        break
                
                return True, "Déconnecté du vocal"
            log_warn(f"⚠️ Pas en vocal")
            return False, "Pas en vocal"
        except Exception as e:
            log_error(f"❌ Erreur leave vocal: {e}")
            return False, str(e)
    
    def leave_voice(self, token_id):
        """Wrapper pour leave vocal"""
        log_info(f"🔇 Requête leave vocal pour token {token_id}")
        
        if token_id not in self.bots:
            log_error(f"❌ Token {token_id} non trouvé")
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
            log_error(f"❌ Erreur leave_voice: {e}")
            return False, str(e)
    
    async def _change_status(self, bot, status):
        """Changer le statut"""
        log_info(f"🔄 Changement de statut vers {status}")
        status_map = {
            'online': discord.Status.online,
            'idle': discord.Status.idle,
            'dnd': discord.Status.dnd,
            'invisible': discord.Status.invisible
        }
        if status in status_map:
            await bot.change_presence(status=status_map[status])
            log_success(f"✅ Statut changé en {status}")
            return True, f"Statut changé en {status}"
        log_error(f"❌ Statut invalide: {status}")
        return False, "Statut invalide"
    
    def change_status(self, token_id, status):
        """Wrapper pour changer statut"""
        log_info(f"🔄 Requête changement statut pour token {token_id} vers {status}")
        
        if token_id not in self.bots:
            log_error(f"❌ Token {token_id} non trouvé")
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
            log_error(f"❌ Erreur change_status: {e}")
            return False, str(e)
    
    def get_stats(self):
        """Retourne les statistiques"""
        return {
            'bots_actifs': len(self.bots),
            'total_connections': self.stats['total_connections'],
            'failed_connections': self.stats['failed_connections'],
            'voice_joins': self.stats['voice_joins']
        }

bot_manager = BotManager()

def start_existing_bots():
    """Démarre tous les bots existants dans la BDD"""
    log_info("🔄 Démarrage des bots existants...")
    time.sleep(3)  # Attendre que le serveur Flask soit prêt
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, token, name FROM tokens")
        existing_tokens = c.fetchall()
        conn.close()
        
        log_info(f"📊 {len(existing_tokens)} token(s) trouvé(s) dans la BDD")
        
        for token_id, token, name in existing_tokens:
            log_info(f"➕ Démarrage du bot {name} (ID: {token_id})...")
            bot_manager.add_bot(token_id, token, name)
            time.sleep(1.5)  # Petit délai entre chaque
        
        log_success("✅ Tous les bots ont été démarrés")
        log_info(f"📈 Stats: {bot_manager.get_stats()}")
        
    except Exception as e:
        log_error(f"❌ Erreur lors du démarrage des bots: {e}")

# ==================== ROUTES API ====================
@app.route('/', methods=['GET', 'OPTIONS'])
def home():
    if request.method == 'OPTIONS':
        return '', 200
    log_debug("🌐 Accès à la racine")
    return jsonify({
        "status": "online",
        "message": "SelfBot API",
        "version": "3.0",
        "stats": bot_manager.get_stats()
    })

@app.route('/api/tokens', methods=['GET', 'OPTIONS'])
def get_tokens():
    if request.method == 'OPTIONS':
        return '', 200
    log_debug("📋 Requête GET /api/tokens")
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
            'last_seen': t[7]
        } for t in tokens]
        
        log_debug(f"📊 {len(result)} token(s) retourné(s)")
        return jsonify(result)
    except Exception as e:
        log_error(f"❌ Erreur GET tokens: {e}")
        return jsonify([])

@app.route('/api/tokens', methods=['POST', 'OPTIONS'])
def add_token():
    if request.method == 'OPTIONS':
        return '', 200
    log_info("➕ Requête POST /api/tokens")
    data = request.json
    token = data.get('token')
    name = data.get('name', 'Bot')
    
    if not token:
        log_error("❌ Token manquant")
        return jsonify({'success': False, 'error': 'Token requis'}), 400
    
    log_info(f"📝 Ajout du token: {name}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO tokens (token, name, last_seen) VALUES (?, ?, ?)",
                 (token, name, datetime.now()))
        conn.commit()
        token_id = c.lastrowid
        conn.close()
        
        log_success(f"✅ Token ajouté avec ID: {token_id}")
        
        # Démarrer le bot immédiatement
        log_info(f"🔄 Démarrage du bot {name}...")
        bot_manager.add_bot(token_id, token, name)
        
        return jsonify({'success': True, 'id': token_id})
        
    except sqlite3.IntegrityError:
        log_error(f"❌ Token déjà existant")
        return jsonify({'success': False, 'error': 'Token existe déjà'}), 400
    except Exception as e:
        log_error(f"❌ Erreur: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tokens/<int:token_id>', methods=['DELETE', 'OPTIONS'])
def delete_token(token_id):
    if request.method == 'OPTIONS':
        return '', 200
    log_info(f"🗑️ Requête DELETE /api/tokens/{token_id}")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM tokens WHERE id=?", (token_id,))
        conn.commit()
        conn.close()
        log_success(f"✅ Token {token_id} supprimé")
        return jsonify({'success': True})
    except Exception as e:
        log_error(f"❌ Erreur: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tokens/<int:token_id>/join', methods=['POST', 'OPTIONS'])
def join_voice(token_id):
    if request.method == 'OPTIONS':
        return '', 200
    log_info(f"🔊 Requête JOIN pour token {token_id}")
    data = request.json
    channel = data.get('channel')
    
    if not channel:
        return jsonify({'success': False, 'message': 'Channel requis'}), 400
    
    log_info(f"📡 Channel: {channel}")
    success, message = bot_manager.join_voice(token_id, channel)
    
    if success:
        log_success(f"✅ Join réussi: {message}")
    else:
        log_error(f"❌ Join échoué: {message}")
    
    return jsonify({'success': success, 'message': message})

@app.route('/api/tokens/<int:token_id>/leave', methods=['POST', 'OPTIONS'])
def leave_voice(token_id):
    if request.method == 'OPTIONS':
        return '', 200
    log_info(f"🔇 Requête LEAVE pour token {token_id}")
    success, message = bot_manager.leave_voice(token_id)
    
    if success:
        log_success(f"✅ Leave réussi: {message}")
    else:
        log_error(f"❌ Leave échoué: {message}")
    
    return jsonify({'success': success, 'message': message})

@app.route('/api/tokens/<int:token_id>/status', methods=['POST', 'OPTIONS'])
def change_status(token_id):
    if request.method == 'OPTIONS':
        return '', 200
    log_info(f"🔄 Requête STATUS pour token {token_id}")
    data = request.json
    status = data.get('status')
    
    if not status:
        return jsonify({'success': False, 'message': 'Status requis'}), 400
    
    log_info(f"📡 Nouveau statut: {status}")
    success, message = bot_manager.change_status(token_id, status)
    
    if success:
        log_success(f"✅ Statut changé: {message}")
    else:
        log_error(f"❌ Échec: {message}")
    
    return jsonify({'success': success, 'message': message})

@app.route('/api/stats', methods=['GET', 'OPTIONS'])
def get_stats():
    if request.method == 'OPTIONS':
        return '', 200
    """Route pour les statistiques"""
    return jsonify(bot_manager.get_stats())

@app.route('/api/debug/bots', methods=['GET', 'OPTIONS'])
def debug_bots():
    if request.method == 'OPTIONS':
        return '', 200
    """Route de debug pour voir les bots actifs"""
    log_debug("🐛 Requête DEBUG /api/debug/bots")
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
log_info("="*60)
log_success("🚀 SERVEUR PRÊT À DÉMARRER")
log_info("="*60)

# Démarrer les bots dans un thread séparé
start_thread = threading.Thread(target=start_existing_bots, daemon=True)
start_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    log_info(f"🌍 Démarrage du serveur Flask sur le port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
