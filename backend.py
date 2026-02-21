import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { createInterface } from 'readline';
import { fileURLToPath } from 'url';
import http from 'http';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const rl = createInterface({
    input: process.stdin,
    output: process.stdout
});

const question = (query) => new Promise((resolve) => rl.question(query, resolve));

function startWebServer() {
    const port = process.env.PORT || 3000;
    const server = http.createServer((req, res) => {
        if (req.url === '/') {
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(`<html><body><h1>Selfbot OK</h1></body></html>`);
        } else {
            res.writeHead(200);
            res.end('OK');
        }
    });
    server.listen(port, '0.0.0.0', () => {
        console.log(`Serveur web sur port ${port}`);
    });
    return server;
}

async function checkNodeVersion() {
    const version = process.version;
    console.log(`Node.js: ${version}`);
    const majorVersion = parseInt(version.slice(1).split('.')[0]);
    if (majorVersion < 16) {
        console.log('Node.js 16+ requis');
        process.exit(1);
    }
}

async function installDependencies() {
    console.log('Installation des dépendances...');
    const packages = [
        'discord.js-selfbot-v13',
        '@discordjs/voice',
        '@discordjs/opus',
        'ffmpeg-static',
        'libsodium-wrappers'
    ];
    try {
        if (!fs.existsSync(path.join(__dirname, 'package.json'))) {
            execSync('npm init -y', { stdio: 'inherit', cwd: __dirname });
            const pkgPath = path.join(__dirname, 'package.json');
            const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
            pkg.scripts = { start: "node index.js" };
            fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2));
        }
        execSync(`npm install ${packages.join(' ')}`, { stdio: 'inherit', cwd: __dirname });
        console.log('Dépendances installées');
        return true;
    } catch (error) {
        console.error('Erreur installation:', error.message);
        return false;
    }
}

async function validateToken(token) {
    const tokenRegex = /^[MN][A-Za-z0-9_-]{23,25}\.[A-Za-z0-9_-]{6,7}\.[A-Za-z0-9_-]{27,}$/;
    return tokenRegex.test(token);
}

async function setupConfig() {
    console.log('\nConfiguration du selfbot');
    let token = '';
    while (!token) {
        token = await question('Token Discord: ');
        if (!await validateToken(token)) {
            console.log('Token invalide');
            token = '';
        }
    }
    const guildId = await question('ID du serveur: ');
    const channelId = await question('ID du salon vocal: ');
    
    const config = {
        Token: token.trim(),
        Guild: guildId.trim(),
        Channel: channelId.trim()
    };
    
    fs.writeFileSync(path.join(__dirname, 'config.json'), JSON.stringify(config, null, 4));
    console.log('Config sauvegardée');
    return config;
}

async function main() {
    startWebServer();
    await checkNodeVersion();
    await installDependencies();
    
    const configPath = path.join(__dirname, 'config.json');
    let config;
    
    if (fs.existsSync(configPath)) {
        const useExisting = await question('Utiliser config existante? (oui/non): ');
        if (useExisting.toLowerCase() === 'oui') {
            try {
                config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
                console.log('Config chargée');
            } catch {
                config = await setupConfig();
            }
        } else {
            config = await setupConfig();
        }
    } else {
        config = await setupConfig();
    }
    
    rl.close();
    
    const { Client } = await import('discord.js-selfbot-v13');
    const { joinVoiceChannel } = await import('@discordjs/voice');
    
    const client = new Client({ checkUpdate: false });
    
    client.on('ready', async () => {
        console.log(`Connecté en tant que ${client.user.tag}`);
        await joinVC(client, config);
    });
    
    client.on('voiceStateUpdate', async (oldState, newState) => {
        const oldVoice = oldState.channelId;
        const newVoice = newState.channelId;
        if (oldVoice !== newVoice) {
            if (!oldVoice) {
            } else if (!newVoice) {
                if (oldState.member.id !== client.user.id) return;
                await joinVC(client, config);
            } else {
                if (oldState.member.id !== client.user.id) return;
                if (newVoice !== config.Channel) {
                    await joinVC(client, config);
                }
            }
        }
    });
    
    async function joinVC(client, config) {
        try {
            const guild = client.guilds.cache.get(config.Guild);
            if (!guild) {
                console.error('Serveur non trouvé');
                return;
            }
            const voiceChannel = guild.channels.cache.get(config.Channel);
            if (!voiceChannel) {
                console.error('Salon non trouvé');
                return;
            }
            joinVoiceChannel({
                channelId: voiceChannel.id,
                guildId: guild.id,
                adapterCreator: guild.voiceAdapterCreator,
                selfDeaf: false,
                selfMute: true
            });
            console.log(`Connecté à ${voiceChannel.name}`);
        } catch (error) {
            console.error('Erreur:', error.message);
        }
    }
    
    try {
        await client.login(config.Token);
        console.log('Selfbot démarré');
    } catch (error) {
        console.error('Erreur login:', error.message);
    }
}

process.on('unhandledRejection', console.error);
process.on('SIGINT', () => process.exit(0));

main();
