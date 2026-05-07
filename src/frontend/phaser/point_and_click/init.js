class BootScene extends Phaser.Scene {
    constructor() { super('BootScene'); }
    preload() {
        // Support both the editor page (EDITOR_*) and the game page (GAME_*) variable names.
        const projectId = window.EDITOR_PROJECT_ID || window.GAME_PROJECT_ID;
        const apiUrl    = window.EDITOR_API_URL    || window.GAME_API_URL;
        if (projectId && apiUrl) {
            this.load.json('gameConfig', `${apiUrl}/static/projects/${projectId}/game_config.json`);
            this.load.json('assetsConfig', `${apiUrl}/static/projects/${projectId}/assets_config.json`);
            this.load.json('musicTracks', `${apiUrl}/static/projects/${projectId}/music_tracks.json`);
        } else {
            this.load.json('gameConfig', 'game_config.json');
            this.load.json('assetsConfig', 'assets_config.json');
            this.load.json('musicTracks', 'music_tracks.json');
        }
    }
    create() { this.scene.start('PreloadScene'); }
}

class PreloadScene extends Phaser.Scene {
    constructor() { super('PreloadScene'); }
    preload() {
        this.statusText = this.add.text(640, 360, 'Prompt-N-Click initializing...', { fontSize: '24px', fill: 'rgb(255, 255, 255)', fontFamily: 'monospace' }).setOrigin(0.5);
        
        let cleanConfig = this.cache.json.get('gameConfig');
        if (!cleanConfig) { console.error("Config not found!"); return; }

        let assetsConfig = this.cache.json.get('assetsConfig');
        if (!assetsConfig) { console.error("Assets config not found!"); return; }
        
        // Build a merged copy WITHOUT mutating the cached gameConfig.
        // The editor reads gameConfig directly (clean, no assets fields) so
        // saveJSON only writes back pure game logic — never assets metadata.
        let db = JSON.parse(JSON.stringify(cleanConfig));
        db.actors      = Object.assign({}, assetsConfig.actors);
        db.items       = Object.assign({}, assetsConfig.items);
        db.backgrounds = Object.assign({}, assetsConfig.backgrounds);
        db.dialogs     = Object.assign({}, assetsConfig.dialogs);
        this.cache.json.add('mergedConfig', db);
        const projectId = window.EDITOR_PROJECT_ID || window.GAME_PROJECT_ID;
        const apiUrl    = window.EDITOR_API_URL    || window.GAME_API_URL;
        const assetBase = (projectId && apiUrl) ? `${apiUrl}/static/projects/${projectId}/img/` : '';
        const audioAssetBase = (projectId && apiUrl) ? `${apiUrl}/static/projects/${projectId}/audio/` : '';

        for (let bg_id in db.backgrounds) {
            let bg = db.backgrounds[bg_id];
            if (bg.image) this.load.image(bg_id, assetBase + bg.image);
        }
        for (let id in db.actors) {
            if (db.actors[id].image) this.load.image(id, assetBase + db.actors[id].image);
        }
        for (let id in db.items) {
            if (db.items[id].image) this.load.image(id, assetBase + db.items[id].image);
        }        

        for (let id in db.dialogs) {
            let dlgData = db.dialogs[id];
            if (Array.isArray(dlgData)) {
                // New Array Format: Loop through sequential lines
                dlgData.forEach((line, index) => {
                    let audioFile = line.voice || line.audio_file;
                    if (audioFile) {
                        // Create a unique cache key: e.g., "Hero_PrismGrab_01_0"
                        this.load.audio(`${id}_${index}`, audioAssetBase + audioFile);
                    }
                });
            } else {
                // Old Format fallback
                if (dlgData.voice) this.load.audio(id, audioAssetBase + dlgData.voice);
            }
        }

        // Preload background music track if configured
        if (cleanConfig.music && cleanConfig.music.track && cleanConfig.music.track !== 'none') {
            this.load.audio('bg_music', audioAssetBase + cleanConfig.music.track);
        }

        // Preload predefined FX assets — use base64 data URLs when embedded, else file paths
        const fxList = [
            'fx_drop', 'fx_smoke', 'fx_flake', 'fx_circle', 'fx_star', 'fx_oval', 
            'fx_square', 'fx_triangle', 'fx_line', 'fx_dot', 'fx_rhombus', 'fx_fog'
        ];
        
        const sfxBase = (apiUrl) ? `${apiUrl}/static/phaser/sfx/` : 'sfx/';

        this.load.audio('sfx_click', sfxBase + 'click.mp3');

        const fxBase = (apiUrl) ? `${apiUrl}/static/phaser/fx/` : 'fx/';
        
        // Load natively via URL (no more base64!)
        fxList.forEach(fx => {
            this.load.image(fx, fxBase + fx + '.png');
        });

        this.load.crossOrigin = 'anonymous';
        this.load.video('game_logo_video', fxBase + 'intro.mp4');
    }
    create() { 
        if (window.IS_EDITOR) {
            console.log("Preload complete. Starting LevelEditor...");
            this.scene.start('LevelEditor'); 
        } else {
            console.log("Preload complete. Starting LogoScene...");
            this.scene.start('LogoScene');
        } 
    }
}

class LogoScene extends Phaser.Scene {
    constructor() { super('LogoScene'); }

    create() {
        // Black background
        this.add.rectangle(640, 360, 1280, 720, 0x000000).setDepth(0);

        // Check if the video actually loaded into the cache
        if (!this.cache.video.exists('game_logo_video')) {
            console.warn("Video intro missing or failed to load. Skipping to GameScene.");
            this.scene.start('GameScene');
            return;
        }

        // Add the video
        const video = this.add.video(0, 25, 'game_logo_video')
            .setOrigin(0)
            .setDepth(1)
            .setAlpha(0);

        // Grab your actual Phaser canvas dimensions
        const gameWidth = this.scale.width;   // Should be 1280
        const gameHeight = this.scale.height; // Should be 720

        video.on('play', () => {
            const actualWidth = video.width; 
            const actualHeight = video.height;

            let uniformScale = 0.62; // scale for 1920 videos to fit 1280x720

            console.log(`Scaling video to ${uniformScale} (game: ${gameWidth}x${gameHeight}, video: ${actualWidth}x${actualHeight})`);
            video.setScale(uniformScale);
            video.setAlpha(1); 
        });

        // Command it to play
        video.play();

        // Automatically transition to the game when the video finishes
        video.on('complete', () => {
            this.scene.start('GameScene');
        });

        // Let the player click anywhere to skip the intro
        this.input.once('pointerdown', () => {
            video.stop(); 
            this.scene.start('GameScene');
        });
    }
}