#!/usr/bin/env node

// ============================================
// SCRIPT AUTO-INSTALL ET CONFIGURATION
// ============================================

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { createInterface } from 'readline';
import { fileURLToPath } from 'url';
import https from 'https';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const rl = createInterface({
    input: process.stdin,
    output: process.stdout
});

const question = (query) => new Promise((resolve) => rl.question(query, resolve));

// ============================================
// FONCTIONS D'INSTALLATION
// ============================================

async function checkNodeVersion() {
    const version = process.version;
    console.log(`📌 Node.js version: ${version}`);
    
    const majorVersion = parseInt(version.slice(1).split('.')[0]);
    if (majorVersion < 16) {
        console.log('⚠️ Version de Node.js trop ancienne. Installez Node.js 16+');
        console.log('📥 Téléchargez: https://nodejs.org/');
        process.exit(1);
    }
}

async function installDependencies() {
    console.log('\n📦 Installation des dépendances...');
    
    const packages = [
        'discord.js-selfbot-v13',
        '@discordjs/voice',
        '@discordjs/opus',
        'ffmpeg-static',
        'libsodium-wrappers'
    ];

    try {
        // Initialisation du package.json si nécessaire
        if (!fs.existsSync(path.join(__dirname, 'package.json'))) {
            execSync('npm init -y', { stdio: 'inherit', cwd: __dirname });
        }

        // Installation des packages
        console.log('⏳ Téléchargement et installation...');
        execSync(`npm install ${packages.join(' ')}`, { 
            stdio: 'inherit', 
            cwd: __dirname 
        });
        
        console.log('✅ Dépendances installées avec succès!');
        return true;
    } catch (error) {
        console.error('❌ Erreur installation:', error.message);
        return false;
    }
}

// ============================================
// FONCTIONS DE CONFIGURATION
// ============================================

async function validateToken(token) {
    // Validation basique du token Discord
    const tokenRegex = /^[MN][A-Za-z0-9_-]{23,25}\.[A-Za-z0-9_-]{6,7}\.[A-Za-z0-9_-]{27,}$/;
    return tokenRegex.test(token);
}

async function setupConfig() {
    console.log('\n' + '='.repeat(50));
    console.log('⚙️ CONFIGURATION DU SELFBOT');
    console.log('='.repeat(50));
    
    console.log('\n📝 Veuillez entrer vos informations:');
    console.log('(Pour obtenir les IDs, active le mode développeur Discord)');
    
    let token = '';
    while (!token) {
        token = await question('\n🔑 Token Discord: ');
        if (!await validateToken(token)) {
            console.log('⚠️ Token invalide! Vérifie le format.');
            token = '';
        }
    }
    
    const guildId = await question('🏠 ID du serveur (Guild): ');
    const channelId = await question('🎤 ID du salon vocal: ');
    
    // Test optionnel
    const test = await question('\n🧪 Tester la connexion? (oui/non): ');
    
    const config = {
        Token: token.trim(),
        Guild: guildId.trim(),
        Channel: channelId.trim(),
        TestConnection: test.toLowerCase() === 'oui',
        CreatedAt: new Date().toISOString(),
        Version: '1.0.0'
    };
    
    fs.writeFileSync(
        path.join(__dirname, 'config.json'), 
        JSON.stringify(config, null, 4)
    );
    
    console.log('\n✅ Fichier config.json créé avec succès!');
    
    return config;
}

// ============================================
// FONCTIONS DE TEST
// ============================================

async function testConnection(config) {
    console.log('\n🔍 Test de connexion...');
    
    return new Promise((resolve) => {
        const req = https.get(`https://discord.com/api/v9/guilds/${config.Guild}`, {
            headers: {
                'Authorization': config.Token
            }
        }, (res) => {
            if (res.statusCode === 200) {
                console.log('✅ Token valide et serveur accessible');
                resolve(true);
            } else {
                console.log(`❌ Erreur ${res.statusCode}: Token ou serveur invalide`);
                resolve(false);
            }
        });
        
        req.on('error', () => {
            console.log('❌ Impossible de contacter Discord');
            resolve(false);
        });
        
        req.end();
    });
}

// ============================================
// MAIN
// ============================================

async function main() {
    console.log('\n' + '='.repeat(50));
    console.log('🤖 SELFBOT DISCORD - INSTALLATION AUTO');
    console.log('='.repeat(50));
    
    // Vérification Node.js
    await checkNodeVersion();
    
    // Installation des dépendances
    const installed = await installDependencies();
    if (!installed) {
        console.log('\n❌ Échec de l\'installation. Veuillez réessayer.');
        process.exit(1);
    }
    
    // Configuration
    const configPath = path.join(__dirname, 'config.json');
    let config;
    
    if (fs.existsSync(configPath)) {
        console.log('\n📁 Fichier config.json existant trouvé!');
        const useExisting = await question('Utiliser la configuration existante? (oui/non): ');
        
        if (useExisting.toLowerCase() === 'oui') {
            try {
                const configFile = fs.readFileSync(configPath, 'utf8');
                config = JSON.parse(configFile);
                console.log('✅ Configuration chargée');
            } catch {
                console.log('⚠️ Fichier corrompu, recréation...');
                config = await setupConfig();
            }
        } else {
            config = await setupConfig();
        }
    } else {
        config = await setupConfig();
    }
    
    // Test de connexion
    if (config.TestConnection) {
        const valid = await testConnection(config);
        if (!valid) {
            const retry = await question('\n🔄 Voulez-vous reconfigurer? (oui/non): ');
            if (retry.toLowerCase() === 'oui') {
                config = await setupConfig();
            }
        }
    }
    
    rl.close();
    
    // ============================================
    // DÉMARRAGE DU BOT
    // ============================================
    
    console.log('\n' + '='.repeat(50));
    console.log('🚀 DÉMARRAGE DU SELFBOT');
    console.log('='.repeat(50) + '\n');
    
    // Import des modules après installation
    const { Client } = await import('discord.js-selfbot-v13');
    const { joinVoiceChannel } = await import('@discordjs/voice');
    
    const client = new Client({ 
        checkUpdate: false,
        intents: [
            'GUILDS',
            'GUILD_VOICE_STATES'
        ]
    });
    
    // ============================================
    // EVENTS
    // ============================================
    
    client.on('ready', async () => {
        console.log(`✅ Connecté en tant que ${client.user.tag}!`);
        console.log(`🆔 ID: ${client.user.id}`);
        console.log(`📡 Surveillance du salon: ${config.Channel}`);
        
        // Connexion initiale
        await joinVC(client, config);
        
        // Status personnalisé
        client.user.setActivity('🎵 Auto VC', { type: 'LISTENING' });
    });
    
    client.on('voiceStateUpdate', async (oldState, newState) => {
        const oldVoice = oldState.channelId;
        const newVoice = newState.channelId;
    
        if (oldVoice !== newVoice) {
            if (!oldVoice) {
                // empty
            } else if (!newVoice) {
                if (oldState.member.id !== client.user.id) return;
                console.log('🔄 Déconnecté, reconnexion...');
                await joinVC(client, config);
            } else {
                if (oldState.member.id !== client.user.id) return;
                if (newVoice !== config.Channel) {
                    console.log('🔄 Retour au salon vocal principal...');
                    await joinVC(client, config);
                }
            }
        }
    });
    
    client.on('error', (error) => {
        console.error('❌ Erreur client:', error.message);
    });
    
    client.on('disconnect', () => {
        console.log('⚠️ Déconnecté, tentative de reconnexion dans 5s...');
        setTimeout(() => {
            client.login(config.Token).catch(console.error);
        }, 5000);
    });
    
    // ============================================
    // FONCTIONS UTILS
    // ============================================
    
    async function joinVC(client, config) {
        try {
            const guild = client.guilds.cache.get(config.Guild);
            if (!guild) {
                console.error('❌ Serveur non trouvé!');
                return;
            }
            
            const voiceChannel = guild.channels.cache.get(config.Channel);
            if (!voiceChannel) {
                console.error('❌ Salon vocal non trouvé!');
                return;
            }
            
            const connection = joinVoiceChannel({
                channelId: voiceChannel.id,
                guildId: guild.id,
                adapterCreator: guild.voiceAdapterCreator,
                selfDeaf: false,
                selfMute: true
            });
            
            console.log(`🎤 Connecté à: ${voiceChannel.name} (${voiceChannel.id})`);
            
            connection.on('error', (error) => {
                console.error('❌ Erreur connexion vocale:', error.message);
            });
            
            connection.on('stateChange', (oldState, newState) => {
                if (newState.status === 'disconnected') {
                    console.log('🔄 Reconnexion vocale...');
                    setTimeout(() => joinVC(client, config), 2000);
                }
            });
            
        } catch (error) {
            console.error('❌ Erreur de connexion vocale:', error.message);
            setTimeout(() => joinVC(client, config), 5000);
        }
    }
    
    // ============================================
    // LANCEMENT
    // ============================================
    
    try {
        await client.login(config.Token);
        console.log('🎯 Selfbot démarré avec succès!');
        console.log('📝 Appuie sur Ctrl+C pour arrêter\n');
    } catch (error) {
        console.error('❌ Erreur de connexion:', error.message);
        console.log('\n🔧 Solutions possibles:');
        console.log('1. Vérifie que le token est correct');
        console.log('2. Vérifie que le token n\'a pas expiré');
        console.log('3. Vérifie que le bot a accès au serveur');
        process.exit(1);
    }
}

// ============================================
// GESTION DES ERREURS
// ============================================

process.on('unhandledRejection', (error) => {
    console.error('❌ Erreur non gérée:', error);
});

process.on('SIGINT', () => {
    console.log('\n\n👋 Arrêt du selfbot...');
    process.exit(0);
});

// ============================================
// DÉMARRAGE
// ============================================

main().catch(console.error);
