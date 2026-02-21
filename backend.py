import os
import json
import subprocess
import sys
import threading
import time
import asyncio
import random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import discord
from discord.ext import commands

# ==================== CONFIG ====================
PORT = int(os.environ.get('PORT', 3000))
TOKENS_FILE = 'tokens.json'
BOTS = {}  # Stockage des bots {token_id: {"client": bot, "status": {...}}}
COMMANDS_USED = 0

# ==================== SERVEUR WEB/API ====================
class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        routes = {
            '/': self.serve_site,
            '/api/tokens': self.get_tokens,
            '/api/stats': self.get_stats,
            '/health': self.health_check
        }
        
        if path in routes:
            routes[path]()
        else:
            self.send_error(404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/api/tokens':
            self.add_token()
        elif path == '/api/command':
            self.execute_command()
        else:
            self.send_error(404)
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path.startswith('/api/tokens/'):
            token_id = path.split('/')[-1]
            self.delete_token(token_id)
        else:
            self.send_error(404)
    
    def serve_site(self):
        html = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SelfBot Panel - ULTIMATE EDITION</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        :root {
            --primary: #00ffff;
            --secondary: #ff00ff;
            --bg-dark: #0a0a0f;
            --bg-card: rgba(20, 20, 30, 0.8);
            --text: #ffffff;
            --success: #00ff00;
            --error: #ff0000;
            --warning: #ffff00;
        }

        body {
            background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            min-height: 100vh;
            padding: 20px;
        }

        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
        }

        .glass-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            transition: transform 0.3s, box-shadow 0.3s;
            animation: cardFloat 3s ease-in-out infinite;
        }

        .glass-card:hover {
            transform: translateY(-10px) scale(1.02);
            box-shadow: 0 15px 45px rgba(0, 255, 255, 0.3);
        }

        @keyframes cardFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }

        .title {
            font-size: 3em;
            font-weight: 800;
            text-transform: uppercase;
            background: linear-gradient(45deg, #00ffff, #ff00ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: titlePulse 2s ease-in-out infinite;
            text-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
        }

        @keyframes titlePulse {
            0%, 100% { filter: brightness(1); }
            50% { filter: brightness(1.2); }
        }

        .stats-container {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 20px 0;
        }

        .stat-card {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
            animation: statGlow 2s ease-in-out infinite;
        }

        @keyframes statGlow {
            0%, 100% { box-shadow: 0 0 20px rgba(0, 255, 255, 0.2); }
            50% { box-shadow: 0 0 40px rgba(255, 0, 255, 0.4); }
        }

        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            color: var(--primary);
            text-shadow: 0 0 20px var(--primary);
        }

        .stat-label {
            color: var(--text);
            font-size: 0.9em;
            opacity: 0.8;
        }

        .add-token {
            background: rgba(0, 0, 0, 0.5);
            border-radius: 20px;
            padding: 25px;
            margin: 30px 0;
            border: 1px solid var(--primary);
            animation: borderPulse 3s ease-in-out infinite;
        }

        @keyframes borderPulse {
            0%, 100% { border-color: var(--primary); }
            50% { border-color: var(--secondary); }
        }

        .form-group {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
        }

        .input-field {
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid rgba(255, 255, 255, 0.2);
            padding: 15px;
            border-radius: 10px;
            color: white;
            font-size: 16px;
            transition: all 0.3s;
        }

        .input-field:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 30px var(--primary);
            transform: scale(1.02);
        }

        .btn {
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            color: white;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }

        .btn:hover {
            transform: scale(1.05);
            box-shadow: 0 0 40px var(--primary);
        }

        .btn::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }

        .btn:hover::before {
            width: 300px;
            height: 300px;
        }

        .bots-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 25px;
            margin: 30px 0;
        }

        .bot-card {
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.5s;
            animation: cardAppear 0.5s ease-out;
        }

        @keyframes cardAppear {
            from {
                opacity: 0;
                transform: translateY(50px) rotate(5deg);
            }
            to {
                opacity: 1;
                transform: translateY(0) rotate(0);
            }
        }

        .bot-card:hover {
            transform: translateY(-10px) scale(1.02);
            border-color: var(--primary);
            box-shadow: 0 0 50px rgba(0, 255, 255, 0.3);
        }

        .bot-header {
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .bot-avatar {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: 3px solid white;
            animation: rotate 10s linear infinite;
        }

        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .bot-status {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            animation: statusPulse 2s ease-in-out infinite;
        }

        @keyframes statusPulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        .status-online {
            background: var(--success);
            box-shadow: 0 0 20px var(--success);
        }

        .status-idle {
            background: var(--warning);
            color: black;
            box-shadow: 0 0 20px var(--warning);
        }

        .status-dnd {
            background: var(--error);
            box-shadow: 0 0 20px var(--error);
        }

        .console-container {
            background: rgba(0, 0, 0, 0.8);
            border-radius: 20px;
            padding: 20px;
            margin: 30px 0;
            border: 2px solid var(--primary);
            animation: consoleGlow 3s ease-in-out infinite;
        }

        @keyframes consoleGlow {
            0%, 100% { box-shadow: 0 0 30px var(--primary); }
            50% { box-shadow: 0 0 60px var(--secondary); }
        }

        .console-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .console-title {
            font-size: 1.5em;
            color: var(--primary);
            text-shadow: 0 0 20px var(--primary);
        }

        .console-output {
            background: #000;
            padding: 20px;
            border-radius: 10px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            border: 1px solid var(--primary);
            box-shadow: inset 0 0 30px rgba(0, 255, 255, 0.1);
        }

        .console-line {
            margin: 5px 0;
            padding: 5px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from {
                transform: translateX(-20px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        .log-success { color: var(--success); }
        .log-error { color: var(--error); }
        .log-info { color: var(--warning); }
        .log-command { color: var(--primary); font-weight: bold; }

        .console-input-area {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }

        .console-input {
            flex: 1;
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid var(--primary);
            padding: 15px;
            border-radius: 10px;
            color: white;
            font-size: 16px;
            font-family: 'Courier New', monospace;
        }

        .console-input:focus {
            outline: none;
            box-shadow: 0 0 30px var(--primary);
        }

        .commands-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
            margin: 20px 0;
        }

        .command-btn {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid var(--primary);
            color: white;
            padding: 10px;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 12px;
        }

        .command-btn:hover {
            background: var(--primary);
            color: black;
            transform: scale(1.05);
            box-shadow: 0 0 20px var(--primary);
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(10px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }

        .modal.active {
            display: flex;
            animation: modalFadeIn 0.3s;
        }

        @keyframes modalFadeIn {
            from { opacity: 0; transform: scale(0.8); }
            to { opacity: 1; transform: scale(1); }
        }

        .modal-content {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            padding: 30px;
            border-radius: 20px;
            border: 2px solid var(--primary);
            max-width: 500px;
            width: 90%;
        }

        .spinner {
            width: 50px;
            height: 50px;
            border: 5px solid rgba(255, 255, 255, 0.1);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        #particles {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            pointer-events: none;
        }

        .particle {
            position: absolute;
            width: 2px;
            height: 2px;
            background: white;
            border-radius: 50%;
            animation: particleFloat 10s linear infinite;
        }

        @keyframes particleFloat {
            from { transform: translateY(100vh) rotate(0deg); }
            to { transform: translateY(-100vh) rotate(360deg); }
        }
    </style>
</head>
<body>
    <div id="particles"></div>
    
    <div class="container">
        <div class="header">
            <h1 class="title">⚡ SELFBOT ULTIMATE ⚡</h1>
            <div>
                <button class="btn" onclick="showHelp()">📚 AIDE</button>
                <button class="btn" onclick="exportData()">📤 EXPORT</button>
                <button class="btn" onclick="importData()">📥 IMPORT</button>
                <button class="btn" onclick="clearAll()">🗑️ CLEAR</button>
            </div>
        </div>

        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-value" id="totalBots">0</div>
                <div class="stat-label">TOTAL BOTS</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="onlineBots">0</div>
                <div class="stat-label">EN LIGNE</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="voiceBots">0</div>
                <div class="stat-label">EN VOCAL</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="commandsUsed">0</div>
                <div class="stat-label">COMMANDES</div>
            </div>
        </div>

        <div class="add-token">
            <h2 style="color: var(--primary); margin-bottom: 20px;">➕ AJOUTER UN TOKEN</h2>
            <div class="form-group">
                <input type="text" class="input-field" id="tokenInput" placeholder="Token Discord">
                <input type="text" class="input-field" id="nameInput" placeholder="Nom du bot">
                <select class="input-field" id="statusSelect">
                    <option value="online">En ligne</option>
                    <option value="idle">Absent</option>
                    <option value="dnd">Ne pas déranger</option>
                    <option value="invisible">Invisible</option>
                </select>
                <button class="btn" onclick="addToken()">AJOUTER</button>
            </div>
        </div>

        <div id="botsGrid" class="bots-grid"></div>

        <div class="console-container">
            <div class="console-header">
                <span class="console-title">💻 CONSOLE DE COMMANDE [50+ COMMANDES]</span>
                <span>
                    <button class="command-btn" onclick="clearConsole()">CLEAR</button>
                    <button class="command-btn" onclick="showAllCommands()">COMMANDS</button>
                </span>
            </div>
            
            <div class="console-output" id="consoleOutput">
                <div class="console-line log-info">🚀 Console initialisée...</div>
                <div class="console-line log-success">✅ Connecté au backend</div>
            </div>

            <div class="console-input-area">
                <input type="text" class="console-input" id="commandInput" placeholder="Entrez une commande..." onkeypress="handleCommandKey(event)">
                <button class="btn" onclick="executeCommand()">EXÉCUTER</button>
            </div>

            <div class="commands-grid" id="commandsGrid"></div>
        </div>
    </div>

    <div class="modal" id="multiJoinModal">
        <div class="modal-content">
            <h2 style="color: var(--primary); margin-bottom: 20px;">🔊 MULTI-JOIN</h2>
            <input type="text" class="input-field" id="multiChannel" placeholder="ID du salon vocal" style="margin-bottom: 10px;">
            <input type="text" class="input-field" id="multiAudio" placeholder="Lien YouTube ou fichier" style="margin-bottom: 10px;">
            <div style="display: flex; gap: 10px;">
                <button class="btn" onclick="executeMultiJoin()">EXÉCUTER</button>
                <button class="btn" onclick="closeModal()">FERMER</button>
            </div>
        </div>
    </div>

    <script>
        const SERVER_URL = window.location.origin;
        let tokens = [];
        let selectedTokens = new Set();
        let commandHistory = [];
        let historyIndex = -1;
        let commandsUsed = 0;

        const commands = [
            { name: 'help', desc: 'Affiche l\'aide', category: 'base' },
            { name: 'clear', desc: 'Efface la console', category: 'base' },
            { name: 'tokens', desc: 'Liste tous les tokens', category: 'base' },
            { name: 'stats', desc: 'Affiche les statistiques', category: 'base' },
            { name: 'select all', desc: 'Sélectionne tous les tokens', category: 'select' },
            { name: 'select none', desc: 'Désélectionne tout', category: 'select' },
            { name: 'select online', desc: 'Sélectionne les tokens en ligne', category: 'select' },
            { name: 'select voice', desc: 'Sélectionne les tokens en vocal', category: 'select' },
            { name: 'join <channel>', desc: 'Rejoint un vocal', category: 'voice' },
            { name: 'leave', desc: 'Quitte le vocal', category: 'voice' },
            { name: 'leave all', desc: 'Quitte tous les vocaux', category: 'voice' },
            { name: 'move <channel>', desc: 'Change de salon vocal', category: 'voice' },
            { name: 'mute', desc: 'Mute le bot', category: 'voice' },
            { name: 'unmute', desc: 'Unmute le bot', category: 'voice' },
            { name: 'deafen', desc: 'Sourdine', category: 'voice' },
            { name: 'undeafen', desc: 'Enlève la sourdine', category: 'voice' },
            { name: 'status online', desc: 'Met le statut en ligne', category: 'status' },
            { name: 'status idle', desc: 'Met le statut absent', category: 'status' },
            { name: 'status dnd', desc: 'Met le statut ne pas déranger', category: 'status' },
            { name: 'status invisible', desc: 'Met le statut invisible', category: 'status' },
            { name: 'info', desc: 'Info du bot sélectionné', category: 'info' },
            { name: 'ping', desc: 'Latence', category: 'info' },
            { name: 'uptime', desc: 'Temps de fonctionnement', category: 'info' },
            { name: 'export', desc: 'Exporte les tokens', category: 'manage' },
            { name: 'import', desc: 'Importe les tokens', category: 'manage' },
            { name: 'delete <id>', desc: 'Supprime un token', category: 'manage' },
            { name: 'rename <id> <name>', desc: 'Renomme un token', category: 'manage' },
            { name: 'test', desc: 'Test la connexion', category: 'debug' },
            { name: 'reload', desc: 'Recharge les tokens', category: 'debug' }
        ];

        window.onload = function() {
            createParticles();
            renderCommandsGrid();
            loadTokens();
            startAnimations();
        };

        function createParticles() {
            const particles = document.getElementById('particles');
            for (let i = 0; i < 100; i++) {
                const particle = document.createElement('div');
                particle.className = 'particle';
                particle.style.left = Math.random() * 100 + '%';
                particle.style.animationDelay = Math.random() * 10 + 's';
                particle.style.animationDuration = 10 + Math.random() * 10 + 's';
                particles.appendChild(particle);
            }
        }

        function renderCommandsGrid() {
            const grid = document.getElementById('commandsGrid');
            grid.innerHTML = '';
            commands.slice(0, 20).forEach(cmd => {
                const btn = document.createElement('button');
                btn.className = 'command-btn';
                btn.textContent = cmd.name;
                btn.onclick = () => insertCommand(cmd.name);
                grid.appendChild(btn);
            });
        }

        function insertCommand(cmd) {
            document.getElementById('commandInput').value = cmd;
        }

        async function apiRequest(endpoint, method = 'GET', data = null) {
            const url = `${SERVER_URL}${endpoint}`;
            const options = {
                method,
                headers: { 'Content-Type': 'application/json' }
            };
            if (data) options.body = JSON.stringify(data);
            
            try {
                const response = await fetch(url, options);
                return await response.json();
            } catch (error) {
                console.error('API Error:', error);
                logToConsole('❌ Erreur de connexion au backend', 'error');
                return null;
            }
        }

        async function loadTokens() {
            const data = await apiRequest('/api/tokens');
            if (data && data.tokens) {
                tokens = data.tokens;
                renderBots();
                updateStats();
            }
        }

        function renderBots() {
            const grid = document.getElementById('botsGrid');
            grid.innerHTML = '';
            
            tokens.forEach(token => {
                const card = document.createElement('div');
                card.className = 'bot-card';
                
                const statusClass = `status-${token.status || 'offline'}`;
                const avatarUrl = token.avatar || `https://ui-avatars.com/api/?name=${token.name || 'Bot'}&background=random&color=fff&size=128`;
                
                card.innerHTML = `
                    <div class="bot-header">
                        <img src="${avatarUrl}" class="bot-avatar">
                        <span class="bot-status ${statusClass}">${token.status || 'offline'}</span>
                    </div>
                    <div style="padding: 20px;">
                        <h3 style="color: var(--primary); margin-bottom: 10px;">${token.name || 'Sans nom'}</h3>
                        <p style="color: white; opacity: 0.7; margin-bottom: 5px;">👤 ${token.username || 'Inconnu'}</p>
                        <p style="color: white; opacity: 0.7; margin-bottom: 5px;">🆔 ${token.id || 'N/A'}</p>
                        <p style="color: white; opacity: 0.7; margin-bottom: 15px;">🔊 ${token.in_voice ? 'En vocal' : 'Pas en vocal'}</p>
                        
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px;">
                            <button class="command-btn" onclick="event.stopPropagation(); quickAction('${token.id}', 'join')">🔊 Join</button>
                            <button class="command-btn" onclick="event.stopPropagation(); quickAction('${token.id}', 'leave')">⏹️ Leave</button>
                            <button class="command-btn" onclick="event.stopPropagation(); quickAction('${token.id}', 'status')">🔄 Status</button>
                            <button class="command-btn" onclick="event.stopPropagation(); deleteToken('${token.id}')">🗑️ Delete</button>
                        </div>
                    </div>
                `;
                
                grid.appendChild(card);
            });
        }

        async function addToken() {
            const token = document.getElementById('tokenInput').value;
            const name = document.getElementById('nameInput').value || `Bot ${tokens.length + 1}`;
            const status = document.getElementById('statusSelect').value;
            
            if (!token) {
                logToConsole('❌ Token requis', 'error');
                return;
            }
            
            const result = await apiRequest('/api/tokens', 'POST', { token, name });
            if (result && result.success) {
                logToConsole(`✅ Token "${name}" ajouté!`, 'success');
                document.getElementById('tokenInput').value = '';
                document.getElementById('nameInput').value = '';
                await loadTokens();
                commandsUsed++;
                updateStats();
            }
        }

        async function deleteToken(tokenId) {
            if (confirm('Supprimer ce token ?')) {
                const result = await apiRequest(`/api/tokens/${tokenId}`, 'DELETE');
                if (result && result.success) {
                    logToConsole(`✅ Token supprimé`, 'success');
                    await loadTokens();
                }
            }
        }

        function quickAction(tokenId, action) {
            if (action === 'join') {
                const channel = prompt('ID du salon vocal:');
                if (channel) logToConsole(`🔊 Token ${tokenId} rejoint ${channel}`, 'success');
            } else if (action === 'leave') {
                logToConsole(`⏹️ Token ${tokenId} quitte le vocal`, 'info');
            } else if (action === 'status') {
                const status = prompt('Status (online/idle/dnd/invisible):');
                if (status) logToConsole(`🔄 Token ${tokenId} status: ${status}`, 'success');
            }
        }

        async function executeCommand() {
            const input = document.getElementById('commandInput');
            const cmd = input.value.trim().toLowerCase();
            if (!cmd) return;
            
            logToConsole(`> ${cmd}`, 'command');
            commandHistory.push(cmd);
            historyIndex = commandHistory.length;
            commandsUsed++;
            updateStats();
            
            const args = cmd.split(' ');
            const mainCmd = args[0];
            
            switch(mainCmd) {
                case 'help':
                    showHelp();
                    break;
                case 'clear':
                    clearConsole();
                    break;
                case 'tokens':
                    listTokens();
                    break;
                case 'stats':
                    showStats();
                    break;
                case 'select':
                    handleSelect(args);
                    break;
                case 'test':
                    logToConsole('✅ Connexion OK', 'success');
                    break;
                default:
                    logToConsole(`❌ Commande inconnue: ${mainCmd}`, 'error');
            }
            
            input.value = '';
        }

        function showHelp() {
            const categories = [...new Set(commands.map(c => c.category))];
            logToConsole('=== LISTE DES COMMANDES ===', 'info');
            categories.forEach(cat => {
                logToConsole(`\n[${cat.toUpperCase()}]`, 'info');
                commands.filter(c => c.category === cat).forEach(cmd => {
                    logToConsole(`  ${cmd.name.padEnd(20)} - ${cmd.desc}`, 'command');
                });
            });
        }

        function listTokens() {
            logToConsole('=== TOKENS ===', 'info');
            tokens.forEach((t, i) => {
                const status = t.status || 'offline';
                const voice = t.in_voice ? '🔊' : '🔇';
                logToConsole(`[${i+1}] ${t.name} - ${status} ${voice}`, status === 'online' ? 'success' : 'info');
            });
        }

        function showStats() {
            const total = tokens.length;
            const online = tokens.filter(t => t.status === 'online').length;
            const voice = tokens.filter(t => t.in_voice).length;
            
            logToConsole('=== STATISTIQUES ===', 'info');
            logToConsole(`Total: ${total}`, 'info');
            logToConsole(`En ligne: ${online}`, 'success');
            logToConsole(`En vocal: ${voice}`, 'info');
            logToConsole(`Commandes: ${commandsUsed}`, 'info');
        }

        function handleSelect(args) {
            if (args[1] === 'all') {
                tokens.forEach(t => selectedTokens.add(t.id));
                logToConsole(`✅ ${tokens.length} tokens sélectionnés`, 'success');
            } else if (args[1] === 'none') {
                selectedTokens.clear();
                logToConsole('✅ Sélection vidée', 'success');
            } else if (args[1] === 'online') {
                selectedTokens.clear();
                tokens.filter(t => t.status === 'online').forEach(t => selectedTokens.add(t.id));
                logToConsole(`✅ ${selectedTokens.size} tokens en ligne sélectionnés`, 'success');
            }
        }

        function logToConsole(message, type = 'info') {
            const output = document.getElementById('consoleOutput');
            const line = document.createElement('div');
            line.className = `console-line log-${type}`;
            const timestamp = new Date().toLocaleTimeString();
            line.textContent = `[${timestamp}] ${message}`;
            output.appendChild(line);
            output.scrollTop = output.scrollHeight;
        }

        function clearConsole() {
            document.getElementById('consoleOutput').innerHTML = '';
            logToConsole('✅ Console effacée', 'success');
        }

        function showAllCommands() {
            showHelp();
        }

        function handleCommandKey(event) {
            if (event.key === 'Enter') executeCommand();
            else if (event.key === 'ArrowUp') navigateHistory(-1);
            else if (event.key === 'ArrowDown') navigateHistory(1);
        }

        function navigateHistory(direction) {
            if (commandHistory.length === 0) return;
            historyIndex += direction;
            if (historyIndex < 0) historyIndex = 0;
            if (historyIndex >= commandHistory.length) historyIndex = commandHistory.length - 1;
            document.getElementById('commandInput').value = commandHistory[historyIndex];
        }

        function exportData() {
            const dataStr = JSON.stringify(tokens, null, 2);
            const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
            const link = document.createElement('a');
            link.setAttribute('href', dataUri);
            link.setAttribute('download', `tokens_${new Date().toISOString()}.json`);
            link.click();
            logToConsole('✅ Données exportées', 'success');
        }

        function importData() {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';
            input.onchange = async function(e) {
                const file = e.target.files[0];
                const text = await file.text();
                try {
                    const imported = JSON.parse(text);
                    tokens = imported;
                    localStorage.setItem('tokens', JSON.stringify(tokens));
                    renderBots();
                    updateStats();
                    logToConsole(`✅ ${tokens.length} tokens importés`, 'success');
                } catch {
                    logToConsole('❌ Fichier invalide', 'error');
                }
            };
            input.click();
        }

        function clearAll() {
            if (confirm('Supprimer TOUS les tokens ?')) {
                tokens = [];
                selectedTokens.clear();
                localStorage.removeItem('tokens');
                renderBots();
                updateStats();
                logToConsole('🗑️ Tous les tokens supprimés', 'warning');
            }
        }

        function updateStats() {
            document.getElementById('totalBots').textContent = tokens.length;
            document.getElementById('onlineBots').textContent = tokens.filter(t => t.status === 'online').length;
            document.getElementById('voiceBots').textContent = tokens.filter(t => t.in_voice).length;
            document.getElementById('commandsUsed').textContent = commandsUsed;
        }

        function startAnimations() {
            setInterval(() => {
                document.querySelectorAll('.stat-card').forEach((card, i) => {
                    card.style.transform = `translateY(${Math.sin(Date.now() / 1000 + i) * 10}px)`;
                });
            }, 50);
        }

        function executeMultiJoin() {
            const channel = document.getElementById('multiChannel').value;
            const audio = document.getElementById('multiAudio').value;
            if (channel && audio) {
                logToConsole(`🔊 Multi-join: ${selectedTokens.size} tokens rejoignent ${channel}`, 'success');
                closeModal();
            }
        }

        function closeModal() {
            document.getElementById('multiJoinModal').classList.remove('active');
        }

        setInterval(loadTokens, 30000);
    </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def get_tokens(self):
        tokens_data = []
        for token_id, bot_data in BOTS.items():
            tokens_data.append({
                'id': token_id,
                'name': bot_data.get('name', 'Sans nom'),
                'username': str(bot_data.get('client').user) if bot_data.get('client') and bot_data.get('client').user else 'Inconnu',
                'status': bot_data.get('status', 'offline'),
                'in_voice': bot_data.get('in_voice', False),
                'avatar': f"https://cdn.discordapp.com/avatars/{bot_data.get('user_id')}/{bot_data.get('avatar')}.png" if bot_data.get('user_id') else None
            })
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'tokens': tokens_data}).encode())

    def get_stats(self):
        stats = {
            'total': len(BOTS),
            'online': sum(1 for b in BOTS.values() if b.get('status') == 'online'),
            'voice': sum(1 for b in BOTS.values() if b.get('in_voice')),
            'commands': COMMANDS_USED
        }
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(stats).encode())

    def health_check(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'healthy'}).encode())

    def add_token(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        token = data.get('token')
        name = data.get('name', 'Bot')
        
        if not token:
            self.send_error(400)
            return
        
        # Démarrer le bot dans un thread
        token_id = str(int(time.time() * 1000))
        thread = threading.Thread(target=start_bot, args=(token_id, token, name))
        thread.daemon = True
        thread.start()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'success': True, 'id': token_id}).encode())

    def delete_token(self, token_id):
        if token_id in BOTS:
            bot_data = BOTS[token_id]
            if bot_data.get('client'):
                asyncio.run_coroutine_threadsafe(bot_data['client'].close(), bot_data['loop'])
            del BOTS[token_id]
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'success': True}).encode())

    def execute_command(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        global COMMANDS_USED
        COMMANDS_USED += 1
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'success': True}).encode())

    def log_message(self, format, *args):
        pass

# ==================== BOT DISCORD ====================
class SelfBot(commands.Bot):
    def __init__(self, token_id, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token_id = token_id
        self.bot_name = name
        self.in_voice = False
        
    async def on_ready(self):
        print(f"✅ {self.bot_name} connecté: {self.user}")
        BOTS[self.token_id]['status'] = 'online'
        BOTS[self.token_id]['user_id'] = str(self.user.id)
        BOTS[self.token_id]['username'] = str(self.user)
        BOTS[self.token_id]['avatar'] = self.user.avatar.key if self.user.avatar else None
        
        # Status personnalisé
        await self.change_presence(activity=discord.Game(name="🎵 Selfbot Ultimate"))
    
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.user.id:
            self.in_voice = after.channel is not None
            BOTS[self.token_id]['in_voice'] = self.in_voice

def start_bot(token_id, token, name):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    
    bot = SelfBot(
        token_id=token_id,
        name=name,
        command_prefix='!',
        self_bot=True,
        intents=intents
    )
    
    BOTS[token_id] = {
        'client': bot,
        'loop': loop,
        'name': name,
        'status': 'connecting',
        'in_voice': False,
        'user_id': None,
        'avatar': None
    }
    
    try:
        loop.run_until_complete(bot.start(token))
    except Exception as e:
        print(f"❌ Erreur {name}: {e}")
        BOTS[token_id]['status'] = 'error'
    finally:
        loop.run_until_complete(bot.close())

# ==================== MAIN ====================
def start_server():
    server = HTTPServer(('0.0.0.0', PORT), APIHandler)
    print(f"🌐 Serveur démarré sur le port {PORT}")
    print(f"🔗 URL: http://localhost:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    # Installation des dépendances si nécessaire
    try:
        import discord
    except:
        print("📦 Installation de discord.py-self...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'discord.py-self', 'PyNaCl'])
        print("✅ Installation terminée")
    
    start_server()
