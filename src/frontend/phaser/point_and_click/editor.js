class LevelEditor extends Phaser.Scene {
    constructor() {
        super('LevelEditor');
        this.selectedObject = null;
        this.currentMode = 'MOVE';
        this.uiButtons = [];
        this.gameOffsetY = 70; // Top UI Gutter height
    }

    create() {
        // gameConfig is kept clean (no assetsConfig fields) so saveJSON writes
        // only pure game logic. assetsConfig is available separately for display.
        this.originalConfig = this.cache.json.get('gameConfig');
        if (!this.originalConfig) { console.error("Game config not found!"); return; }
        this.assetsConfig = this.cache.json.get('assetsConfig');

        this.workingConfig = JSON.parse(JSON.stringify(this.originalConfig));
        this.roomKeys = Object.keys(this.workingConfig.rooms);
        this.currentRoomIndex = 0;
        
        // 1. Setup Containers
        this.bgLayer = this.add.container(0, this.gameOffsetY);
        this.objectLayer = this.add.container(0, this.gameOffsetY);
        this.uiLayer = this.add.container(0, 0).setDepth(9000);

        // 2. POLYFILL FOR FX SYSTEM COMPATIBILITY
        // fx_system.js expects 'roomGroup' to exist and have a 'getChildren()' method
        this.bgLayer.getChildren = function() { return this.list; };
        this.roomGroup = this.bgLayer; 
        
        this.createPropertyPanel();
        this.setupDragLogic();
        this.buildUI();
        this.loadRoom(this.roomKeys[this.currentRoomIndex]);
    }

    getRelativeY(screenY) {
        return screenY - this.gameOffsetY;
    }
    
    createPropertyPanel() {
        let existing = document.getElementById('editor-prop-panel');
        if (existing) existing.remove();
        
        this.panel = document.createElement('div');
        this.panel.id = 'editor-prop-panel';
        this.panel.style.cssText = "position:absolute; left:1280px; top:0; width:300px; height:920px; background:rgba(15,15,15,0.95); color:#0f0; padding:15px; font-family:monospace; box-sizing:border-box; overflow-y:auto; border-left: 2px solid #0f0; z-index:9999; display:none;";
        
        ['pointerdown', 'mousedown', 'mouseup', 'click', 'wheel'].forEach(evt => {
            this.panel.addEventListener(evt, (e) => e.stopPropagation());
        });

        this.panel.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h2 style="margin-top:0; color:#fff;">Inspector</h2>
                <button onclick="window.closeInspector()" style="background:#555; color:#fff; border:none; padding:5px 10px; cursor:pointer; font-weight:bold;">X</button>
            </div>
            <div id="prop-fields" style="margin-bottom:20px; font-size:14px; color:#aaa;">Select an object on the canvas.</div>
            <hr style="border-color:#0f0;">
            <button id="add-fx-btn" onclick="window.addFX()" style="width:100%; padding:8px; background:#222; color:#0f0; border:1px solid #0f0; margin-bottom:10px; cursor:pointer;">+ ADD FX TO ROOM</button>
            <button id="edit-music-btn" onclick="window.editMusic()" style="width:100%; padding:8px; background:#222; color:#0af; border:1px solid #0af; cursor:pointer;">&#9836; EDIT MUSIC</button>
        `;
        
        document.body.appendChild(this.panel);

        window.editMusic = () => {
            const musicObj = this.objectLayer.list.find(child => child.typeTag === 'MUSIC');
            if (musicObj) this.selectObject(musicObj);
        };

        window.addFX = () => {
            const roomId = this.roomKeys[this.currentRoomIndex];
            if (!this.workingConfig.rooms[roomId].fx) this.workingConfig.rooms[roomId].fx = [];
            this.workingConfig.rooms[roomId].fx.push({ type: 'color_tint', color: '#ff0000', alpha: 0.5 });
            this.loadRoom(roomId);
        };

        window.removeCurrentFX = () => {
            if (this.selectedObject && this.selectedObject.typeTag === 'FX') {
                const roomId = this.roomKeys[this.currentRoomIndex];
                let fxArr = this.workingConfig.rooms[roomId].fx;
                const idx = fxArr.indexOf(this.selectedObject.configRef);
                if (idx > -1) {
                    fxArr.splice(idx, 1);
                    this.selectObject(null);
                    this.loadRoom(roomId);
                }
            }
        };

        window.closeInspector = () => this.selectObject(null);
        window.stopFX = () => this.stopAllFX();
        window.startMusicPreview = () => {
            this.stopMusicPreview();
            if (!this.selectedObject || this.selectedObject.typeTag !== 'MUSIC') return;
            const ref = this.selectedObject.configRef;
            if (!ref.track || ref.track === 'none') return;
            const url = `${window.EDITOR_API_URL}/static/projects/${window.EDITOR_PROJECT_ID}/audio/${ref.track}`;
            this.musicPreviewAudio = new Audio(url);
            this.musicPreviewAudio.volume = ref.volume !== undefined ? parseFloat(ref.volume) : 0.5;
            this.musicPreviewAudio.loop = true;
            this.musicPreviewAudio.play().catch(e => console.warn('[music preview]', e));
        };
        window.stopMusicPreview = () => this.stopMusicPreview();
        this.musicPreviewAudio = null;
    }

    updatePropPanel(obj) {
        let container = document.getElementById('prop-fields');
        if (!container) return;
        if (!obj) { container.innerHTML = "Select an object on the canvas."; return; }

        let ref = obj.configRef;
        let html = `<h3 style="color:#fff; margin-top:0;">[ ${obj.typeTag} ]</h3>`;
        
        const makeInput = (label, key, type='text', options=[]) => {
            let val = ref[key] !== undefined ? ref[key] : '';
            
            if (type === 'color') {
                let hexVal = val;
                if (typeof val === 'number') hexVal = '#' + val.toString(16).padStart(6, '0');
                if (typeof val === 'string' && val.startsWith('0x')) hexVal = '#' + val.substring(2);
                if (!hexVal || !hexVal.startsWith('#')) hexVal = '#ffffff';

                return `<div style="margin-bottom:8px;">
                    <label style="display:block;font-size:12px;color:#ccc;margin-bottom:2px;">${label}</label>
                    <div style="display:flex; gap:5px;">
                        <input type="text" id="txt_${key}" value="${val}" onchange="window.updateProp('${key}', this.value, 'text')" style="flex-grow:1; background:#000; color:#0f0; border:1px solid #0f0; padding:6px; box-sizing:border-box;">
                        <input type="color" value="${hexVal}" oninput="document.getElementById('txt_${key}').value=this.value; window.updateProp('${key}', this.value, 'text')" style="width:40px; height:30px; border:none; padding:0; background:none; cursor:pointer;">
                    </div>
                </div>`;
            }

            if (type === 'select') {
                let opts = options.map(o => `<option value="${o}" ${String(val)===String(o)?'selected':''}>${o}</option>`).join('');
                return `<div style="margin-bottom:8px;"><label style="display:block;font-size:12px;color:#ccc;margin-bottom:2px;">${label}</label><select onchange="window.updateProp('${key}', this.value, 'select')" style="width:100%; background:#000; color:#0f0; border:1px solid #0f0; padding:6px;">${opts}</select></div>`;
            }
            return `<div style="margin-bottom:8px;"><label style="display:block;font-size:12px;color:#ccc;margin-bottom:2px;">${label}</label><input type="${type}" value="${val}" onchange="window.updateProp('${key}', this.value, '${type}')" style="width:100%; background:#000; color:#0f0; border:1px solid #0f0; padding:6px; box-sizing:border-box;"></div>`;
        };

        if (obj.typeTag === 'TIMER') {
            html += makeInput('Timer ID', 'id');
            html += makeInput('Scope', 'scope');
            html += makeInput('Format', 'format', 'select', ['mm:ss', 'seconds']);
            html += makeInput('Delay (sec)', 'delay_seconds', 'number');
            html += makeInput('Font Size', 'font_size');
            html += makeInput('Font Color Hex', 'font_color', 'color');
            html += makeInput('Alpha', 'alpha', 'number');
            html += makeInput('Icon Scale', 'icon_scale', 'number'); // FIXED TYPO & TYPE
            html += makeInput('Icon Item ID', 'icon');
            html += makeInput('Icon Pos', 'icon_position', 'select', ['left', 'right']);
        } 
        else if (obj.typeTag === 'FX') {
            html += makeInput('FX Type', 'type', 'select', ['vignette','scanlines','crt_rgb_split','color_tint','pulse_tint','blur','strobe','letterbox','shadow_gradient','hologram_lines','flash','fade_in','fade_out','shake','glitch','zoom_pan','particles','fog','sparks','snow','rain']);
            
            let t = ref.type;
            
            if (!['shake','glitch','zoom_pan'].includes(t)) {
                html += makeInput('Alpha / Opacity', 'alpha', 'number');
            }

            if (['color_tint','pulse_tint','strobe','hologram_lines','flash','fade_in','fade_out'].includes(t)) {
                html += makeInput('Color', 'color', 'color');
            }
		
            if (['particles','fog','sparks','snow','rain'].includes(t)) {
                html += makeInput('Asset', 'asset', 'select', ['', 'fx_drop', 'fx_smoke', 'fx_flake', 'fx_circle', 'fx_star', 'fx_oval', 'fx_square', 'fx_triangle', 'fx_line', 'fx_dot', 'fx_rhombus', 'fx_fog']);
                html += makeInput('Lifespan', 'lifespan', 'number');
                html += makeInput('Frequency', 'frequency', 'number');
				html += makeInput('ScaleStart', 'scaleStart', 'number');
				html += makeInput('ScaleEnd', 'scaleEnd', 'number');
				html += makeInput('SpeedMin (X)', 'speedMin', 'number');
				html += makeInput('SpeedMax (X)', 'speedMax', 'number');
				html += makeInput('SpeedMin (Y)', 'speedMinY', 'number');
				html += makeInput('SpeedMax (Y)', 'speedMaxY', 'number');
            }

            if (['pulse_tint','strobe','flash','fade_in','fade_out','shake','glitch','scanlines','blur','zoom_pan', 'letterbox'].includes(t)) {
                let label = ['flash','fade_in','fade_out','zoom_pan', 'shake', 'letterbox'].includes(t) ? 'Duration (ms)' : 'Speed';
                let key = ['flash','fade_in','fade_out','zoom_pan','shake', 'letterbox'].includes(t) ? 'duration' : 'speed';
                html += makeInput(label, key, 'number');
            }

			if (t === 'strobe')
			{
				html += makeInput('Delay (ms)', 'delay', 'number');
				html += makeInput('Hold (ms)', 'hold', 'number');
			}
			
			if (t === 'blur') { 
				html += makeInput('Start Strength', 'start_strength', 'number');
				html += makeInput('Strength', 'strength', 'number');
				html += makeInput('Animated', 'animated', 'select', ['true','false']);
			}
			
            if (t === 'scanlines') html += makeInput('Thickness', 'thickness', 'number');
            if (t === 'crt_rgb_split') { html += makeInput('Shift', 'shift', 'number'); html += makeInput('Animated', 'animated', 'select', ['true','false']); }            
            if (t === 'shake') html += makeInput('Intensity', 'intensity', 'number');
            if (t === 'zoom_pan') {
                html += makeInput('Start Scale', 'startScale', 'number');
                html += makeInput('End Scale', 'endScale', 'number');
                html += makeInput('Pan X', 'panX', 'number');
                html += makeInput('Pan Y', 'panY', 'number');
            }

            html += `<div style="display:flex; gap:5px; margin-top:15px;">
                    <button onclick="window.previewCurrentFX()" style="flex:1; padding:8px; background:#0f0; color:#000; font-weight:bold; border:none; cursor:pointer;">START FX</button>
                    <button onclick="window.stopFX()" style="flex:1; padding:8px; background:#555; color:#fff; font-weight:bold; border:none; cursor:pointer;">STOP</button>
                </div>
                <button onclick="window.removeCurrentFX()" style="width:100%; padding:8px; background:#aa0000; color:#fff; font-weight:bold; border:none; cursor:pointer; margin-top:10px;">REMOVE FX</button>
            `;
        }
        else if (obj.typeTag === 'MUSIC') {
            const musicData = this.cache.json.get('musicTracks');
            const trackOptions = ['none'];
            if (musicData && musicData.tracks) {
                musicData.tracks.forEach(t => trackOptions.push(t.filename));
            }
            html += makeInput('Track', 'track', 'select', trackOptions);
            html += makeInput('Volume (0-1)', 'volume', 'number');
            html += `<div style="display:flex; gap:5px; margin-top:15px;">
                <button onclick="window.startMusicPreview()" style="flex:1; padding:8px; background:#0af; color:#000; font-weight:bold; border:none; cursor:pointer;">&#9654; PLAY</button>
                <button onclick="window.stopMusicPreview()" style="flex:1; padding:8px; background:#555; color:#fff; font-weight:bold; border:none; cursor:pointer;">&#9632; STOP</button>
            </div>`;
        }
        else {
            html += makeInput('ID', 'id');
            html += makeInput('Active', 'active', 'select', ['true', 'false']);
            // auto-trigger, if not set default false
            if (obj.configRef['auto-trigger'] === undefined) obj.configRef['auto-trigger'] = false;
            html += makeInput('Auto-Trigger', 'auto-trigger', 'select', ['true', 'false']);
            html += makeInput('Width', 'width', 'number');
            html += makeInput('Height', 'height', 'number');
            html += makeInput('Scale', 'scale', 'number');
            html += makeInput('Rotation', 'rotation', 'number');
            html += makeInput('Flip X', 'flipX', 'select', ['true', 'false']);
        }

        container.innerHTML = html;

        window.updateProp = (key, val, type) => {
            if (type === 'number') val = parseFloat(val);
            if (val === 'true') val = true;
            if (val === 'false') val = false;
            
            if (val === '' || (isNaN(val) && type === 'number')) delete obj.configRef[key];
            else obj.configRef[key] = val;
            
            // --- FIXED: REAL-TIME CONTAINER REBUILD ---
            if (obj.typeTag === 'TIMER') {
                // Clear the container contents dynamically
                obj.removeAll(true);
                
                let t = obj.configRef;
                const displayTime = this.formatTime(t.delay_seconds || 0, t.format);
                
                let txt = this.add.text(0, 0, displayTime, { 
                    fontSize: t.font_size || '24px', 
                    fill: t.font_color || '#f00',
                    fontFamily: 'monospace', 
                    fontStyle: 'bold', 
                    backgroundColor: '#00000088'
                });
                obj.add(txt);

                if (t.icon) {
                    let assetKey = this.getAssetKey(t.icon);
                    if (assetKey) {
                        const iconX = (t.icon_position === 'right') ? txt.width + 20 : -35;
                        const iconY = (parseInt(t.font_size) || 24) / 2;
                        let img = this.add.image(iconX, iconY, assetKey)
                            .setScale(t.icon_scale !== undefined ? t.icon_scale : 0.4) 
                            .setAlpha(t.alpha ?? 1.0);
                        obj.add(img);
                    }
                }
                
                obj.setSize(txt.width + (t.icon ? 50 : 0), txt.height);
                obj.setAlpha(t.alpha ?? 1.0);

            } else if (obj.typeTag === 'FX') {
                obj.setText("FX: " + (obj.configRef.type || 'unknown'));
                this.previewFX(obj.configRef);
                if (key === 'type') this.updatePropPanel(obj);
            } else if (obj.typeTag === 'MUSIC') {
                const trackLabel = obj.configRef.track && obj.configRef.track !== 'none' ? obj.configRef.track : '(none)';
                obj.setText('\u266a MUSIC: ' + trackLabel);
            } else if (obj.typeTag === 'CLICKABLE') {
                this._applyDisplaySize(obj, obj.configRef);
                if (obj.configRef.rotation !== undefined) obj.setRotation(obj.configRef.rotation);
                if (obj.configRef.flipX !== undefined) obj.setFlipX(obj.configRef.flipX);
            }
            this.updateSelectionUI(obj);
        };

        window.previewCurrentFX = () => {
            if (obj.typeTag === 'FX') this.previewFX(obj.configRef);
        };
    }

    setupDragLogic() {
        this.input.on('dragstart', (pointer, gameObject) => {
            gameObject.dragStartX = pointer.x;
            gameObject.dragStartY = pointer.y;
            gameObject.initScale = gameObject.configRef.scale || 1;
            gameObject.initRot = gameObject.configRef.rotation || 0;
            const s = gameObject.configRef.scale || 1;
            gameObject.initW = gameObject.configRef.width || Math.round(gameObject.displayWidth / s);
            gameObject.initH = gameObject.configRef.height || Math.round(gameObject.displayHeight / s);
        });

        this.input.on('drag', (pointer, gameObject, dragX, dragY) => {
            const dx = pointer.x - gameObject.dragStartX;
            const dy = pointer.y - gameObject.dragStartY;
            const ref = gameObject.configRef;

            if (this.currentMode === 'MOVE') {
                gameObject.x = dragX;
                gameObject.y = dragY;

                if (gameObject.typeTag === 'TIMER') {
                    ref.ui_x = Math.round(dragX);
                    ref.ui_y = Math.round(dragY);
                } else if (gameObject.typeTag === 'FX') {
                    // Save without the gameOffsetY so that loadRoom can add it back
                    // consistently, keeping FX labels below the top nav panel.
                    ref._editorX = Math.round(dragX);
                    ref._editorY = Math.round(dragY) - this.gameOffsetY;
                } else {
                    ref.x = Math.round(dragX);
                    ref.y = Math.round(dragY);
                }
            }
            else if (this.currentMode === 'SCALE') {
                ref.scale = Math.max(0.05, gameObject.initScale + (dx * 0.005));
                this._applyDisplaySize(gameObject, ref);
            } 
            else if (this.currentMode === 'RESIZE') {
                ref.width = Math.max(10, Math.round(gameObject.initW + dx));
                ref.height = Math.max(10, Math.round(gameObject.initH + dy));
                this._applyDisplaySize(gameObject, ref);
            } 
            else if (this.currentMode === 'ROTATE') {
                ref.rotation = gameObject.initRot + (dx * 0.01);
                gameObject.setRotation(ref.rotation);
            }
            this.updateSelectionUI(gameObject);
        });
    }

    loadRoom(roomId) {
        this.stopAllFX();
        this.stopMusicPreview();
        this.objectLayer.removeAll(true);
        this.bgLayer.removeAll(true);
        this.selectObject(null);

        // Show EDIT MUSIC button only in first room
        const musicBtn = document.getElementById('edit-music-btn');
        if (musicBtn) musicBtn.style.display = (this.currentRoomIndex === 0) ? '' : 'none';

        const room = this.workingConfig.rooms[roomId];
        this.roomLabel.setText(`ROOM: ${roomId} (${this.currentRoomIndex + 1}/${this.roomKeys.length})`);

        let bgHit = this.add.rectangle(640, 360, 1280, 720, 0x000, 0).setInteractive();
        bgHit.on('pointerdown', () => this.selectObject(null));
        this.bgLayer.add(bgHit);

        if (room.background_ref) {
            let bgKey = this.getAssetKey(room.background_ref);
            if (bgKey) {
                let bgImg = this.add.image(640, 360, bgKey).setAlpha(0.7).setInteractive();
                bgImg.on('pointerdown', () => this.selectObject(null));
                this.bgLayer.add(bgImg);
            }
        }

        if (room.clickables) {
            room.clickables.forEach(item => {
                let obj;
                // check item.actor_ref, then item.item_ref
                let refId = item.actor_ref || item.item_ref;
                let assetKey = this.getAssetKey(refId);
                console.log("Loading clickable: %o, refId: %o, assetKey: %o", item, refId, assetKey);
                item.x = item.x || 640; item.y = item.y || 360;
                if (assetKey) {
                    obj = this.add.image(item.x, item.y, assetKey).setOrigin(0, 0);
                    // Populate base dimensions from texture if not set in config
                    if (!item.width) item.width = obj.texture.realWidth;
                    if (!item.height) item.height = obj.texture.realHeight;
                    if (item.scale === undefined) item.scale = 1;
                    obj.setRotation(item.rotation || 0).setFlipX(item.flipX || false);
                    this._applyDisplaySize(obj, item);
                } else {
                    obj = this.add.rectangle(item.x, item.y, item.width || 100, item.height || 100, 0x00ff00, 0.3).setStrokeStyle(2, 0xff0000).setOrigin(0, 0);
                }
                obj.setInteractive({ draggable: true }).configRef = item;
                obj.typeTag = 'CLICKABLE';
                obj.on('pointerdown', () => this.selectObject(obj));
                this.objectLayer.add(obj);

                if (this._hasChangeRoom(item)) {
                    const w = obj.displayWidth || item.width || 100;
                    const h = obj.displayHeight || item.height || 100;
                    const exitLabel = this.add.text(
                        item.x + w / 2,
                        item.y + h / 2,
                        'EXIT',
                        { fontSize: '14px', fill: '#ffff00', backgroundColor: '#000000bb', padding: { x: 5, y: 3 }, fontFamily: 'monospace', fontStyle: 'bold' }
                    ).setOrigin(0.5).setDepth(1);
                    this.objectLayer.add(exitLabel);
                }
            });
        }

        if (this.workingConfig.timers) {
            this.workingConfig.timers.forEach(t => {
                if (t.scope === roomId || t.scope === 'global') {
                    const displayTime = this.formatTime(t.delay_seconds || 0, t.format);
                    let timerContainer = this.add.container(t.ui_x || 0, t.ui_y || 0);
                    
                    let txt = this.add.text(0, 0, displayTime, { 
                        fontSize: t.font_size || '24px', 
                        fill: t.font_color || '#f00',
                        fontFamily: 'monospace', 
                        fontStyle: 'bold', 
                        backgroundColor: '#00000088'
                    });

                    timerContainer.add(txt);

                    if (t.icon) {
                        let assetKey = this.getAssetKey(t.icon);
                        if (assetKey) {
                            const iconX = (t.icon_position === 'right') ? txt.width + 20 : -35;
                            const iconY = (parseInt(t.font_size) || 24) / 2;
                            let img = this.add.image(iconX, iconY, assetKey)
                                .setScale(t.icon_scale !== undefined ? t.icon_scale : 0.4) // FIXED
                                .setAlpha(t.alpha ?? 1.0);
                            timerContainer.add(img);
                        }
                    }

                    timerContainer.setSize(txt.width + (t.icon ? 50 : 0), txt.height);
                    timerContainer.setInteractive({ draggable: true });
                    timerContainer.typeTag = 'TIMER';
                    timerContainer.configRef = t;
                    timerContainer.on('pointerdown', () => this.selectObject(timerContainer));
                    
                    this.objectLayer.add(timerContainer);
                }
            });
        }

        if (room.fx) {
            room.fx.forEach((fx, idx) => {
                // _editorY is stored without the gameOffsetY; add it here so FX
                // labels always appear below the top navigation panel.
                const fxX = fx._editorX !== undefined ? fx._editorX : 20;
                const fxY = (fx._editorY !== undefined ? fx._editorY : 80 + (idx * 40)) + this.gameOffsetY;
                let txt = this.add.text(fxX, fxY, "FX: " + (fx.type || 'new'), {
                    fontSize: '16px', fill: '#0ff', backgroundColor: '#333', padding: 5
                }).setInteractive({ draggable: true });
                txt.typeTag = 'FX';
                txt.configRef = fx;
                txt.on('pointerdown', () => this.selectObject(txt));
                this.objectLayer.add(txt);
            });
        }

        // Global MUSIC config object — visible only in the first room (menu).
        if (this.currentRoomIndex === 0) {
            if (!this.workingConfig.music) this.workingConfig.music = { track: 'none', volume: 0.5 };
            const musicCfg = this.workingConfig.music;
            const musicTrackLabel = musicCfg.track && musicCfg.track !== 'none' ? musicCfg.track : '(none)';
            let musicTxt = this.add.text(20, this.gameOffsetY + 8, '\u266a MUSIC: ' + musicTrackLabel, {
                fontSize: '16px', fill: '#0af', backgroundColor: '#113', padding: 5
            }).setInteractive();
            musicTxt.typeTag = 'MUSIC';
            musicTxt.configRef = musicCfg;
            musicTxt.on('pointerdown', () => this.selectObject(musicTxt));
            this.objectLayer.add(musicTxt);
        }
    }

    _applyDisplaySize(obj, ref) {
        const s = ref.scale || 1;
        if (obj.type === 'Image') {
            const baseW = ref.width || obj.texture.realWidth;
            const baseH = ref.height || obj.texture.realHeight;
            obj.setDisplaySize(baseW * s, baseH * s);
        } else if (obj.type === 'Rectangle') {
            const w = Math.max(10, (ref.width || 100) * s);
            const h = Math.max(10, (ref.height || 100) * s);
            obj.setSize(w, h).setDisplaySize(w, h);
        } else {
            // Container (timer) or text
            obj.setScale(s);
        }
    }

    _hasChangeRoom(item) {
        if (!item.interactions) return false;
        return item.interactions.some(interaction => {
            const effects = interaction.effects;
            if (!effects) return false;
            if (Array.isArray(effects)) {
                return effects.some(e => e && typeof e === 'object' && 'change_room' in e);
            }
            return typeof effects === 'object' && 'change_room' in effects;
        });
    }

    formatTime(s, f) {
        if (f === 'mm:ss') return `${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toString().padStart(2,'0')}`;
        return s.toString();
    }

    stopAllFX() {
		
		this.fadeRect.setVisible(false);
		
        if (this.fxPreviewGroup) {
            if (this.fxPreviewGroup.clear) {
                this.fxPreviewGroup.clear(true, true);
            }
            this.fxPreviewGroup.destroy(true);
            this.fxPreviewGroup = null; 
        }

        this.tweens.killAll();

        if (this.cameras.main) {
            this.cameras.main.resetFX();
            this.cameras.main.stopFollow();
            this.cameras.main.setZoom(1);
        }

        if (this.bgLayer) {
            this.bgLayer.each(child => {
                if (child.postFX) child.postFX.clear();
                child.x = 640;
                child.y = 360;
                child.setScale(1);
            });
            this.bgLayer.setScale(1);
            this.bgLayer.setAlpha(1);
            this.bgLayer.setPosition(0, this.gameOffsetY);
        }
    }

    stopMusicPreview() {
        if (this.musicPreviewAudio) {
            this.musicPreviewAudio.pause();
            this.musicPreviewAudio.currentTime = 0;
            this.musicPreviewAudio = null;
        }
    }

    getAssetKey(id) {
        if (!id) return null;
        if (this.textures.exists(id)) return id;
        return null; 
    }

    selectObject(obj) {
        if (this.musicPreviewAudio && (!obj || obj.typeTag !== 'MUSIC')) this.stopMusicPreview();
        if (this.selectedObject && this.selectedObject.type === 'Rectangle') {
            this.selectedObject.setFillStyle(0x00ff00, 0.3);
        } else if (this.selectedObject && this.selectedObject.typeTag !== 'TIMER' && this.selectedObject.typeTag !== 'FX' && this.selectedObject.typeTag !== 'MUSIC') {
            this.selectedObject.clearTint();
        }

        if (this.fxPreviewGroup) {
            this.stopAllFX();
        }

        this.selectedObject = obj;
        
        if (!obj) {
            this.infoLabel.setText("Select an object to edit");
            if (this.panel) this.panel.style.display = 'none';
            return;
        }

        this.panel.style.display = 'block';
        this.updatePropPanel(obj);
        
        if (obj.type === 'Rectangle') {
            obj.setFillStyle(0xffff00, 0.5); 
        } else if (obj.typeTag !== 'TIMER' && obj.typeTag !== 'FX' && obj.typeTag !== 'MUSIC') {
            obj.setTint(0x55ff55); 
        }

        this.updateSelectionUI(obj);
    }

    updateSelectionUI(obj) {
        this.infoLabel.setText(
            `Type: ${obj.typeTag} | Mode: [${this.currentMode}]\n` +
            `X: ${Math.round(obj.x)}, Y: ${Math.round(obj.y)} | W: ${Math.round(obj.displayWidth)}, H: ${Math.round(obj.displayHeight)}\n` +
            `Scale: ${obj.scale.toFixed(2)} | Rot: ${obj.rotation.toFixed(2)} | Flip: ${obj.configRef.flipX || false}`
        );
    }

    previewFX(fx) {
        this.stopAllFX();
        
        if (!fx) return;

        try {
            this.fxPreviewGroup = FXSystem.apply(this, [fx], this.fxPreviewGroup, true);
        } catch(e) { 
            console.warn('Preview FX Error:', e); 
        }
    }

    buildUI() {
		 this.fadeRect = this.add.rectangle(640, 360, 1280, 720, 0x000000, 0)
            .setDepth(1999)
            .setVisible(false);

        this.uiLayer.add(this.add.rectangle(640, 35, 1280, 70, 0x000000, 1).setOrigin(0.5));
        this.roomLabel = this.add.text(20, 20, "ROOM: ", { fill: '#0f0', fontSize: '20px', fontFamily: 'monospace' });
        this.uiLayer.add(this.roomLabel);

        this.createBtn(430, 35, "< PREV", () => this.navigate(-1));
        this.createBtn(520, 35, "NEXT >", () => this.navigate(1));
        this.createBtn(750, 35, "RESET ROOM", () => this.resetRoom(), '#880000');
        this.createBtn(920, 35, "SAVE JSON", () => this.saveJSON(), '#0055ff');

        const bottomY = 70 + 720 + 35; 
        this.uiLayer.add(this.add.rectangle(640, bottomY, 1280, 70, 0x000000, 1).setOrigin(0.5));
        
        let b1 = this.createBtn(150, bottomY, "MOVE", () => this.setMode('MOVE'), '#00aa00'); b1.modeTag = 'MOVE';
        let b2 = this.createBtn(260, bottomY, "SCALE", () => this.setMode('SCALE')); b2.modeTag = 'SCALE';
        let b3 = this.createBtn(360, bottomY, "RESIZE", () => this.setMode('RESIZE')); b3.modeTag = 'RESIZE';
        let b4 = this.createBtn(460, bottomY, "ROTATE", () => this.setMode('ROTATE')); b4.modeTag = 'ROTATE';
        
        this.createBtn(750, bottomY, "Center X", () => this.centerObject('X'), '#333');
        this.createBtn(850, bottomY, "Center Y", () => this.centerObject('Y'), '#333');
        this.createBtn(960, bottomY, "Flip Image", () => this.toggleFlip(), '#333');

        this.infoLabel = this.add.text(20, bottomY + 30, "", { fill: '#aaa', fontSize: '12px', fontFamily: 'monospace' });
        this.uiLayer.add(this.infoLabel);
    }   

    setMode(newMode) {
        this.currentMode = newMode;
        this.uiButtons.forEach(b => {
            if (b.modeTag) b.setStyle({ backgroundColor: b.modeTag === newMode ? '#00aa00' : '#222' });
        });
        if (this.selectedObject) this.updateSelectionUI(this.selectedObject);
    }

    centerObject(axis) {
        if (!this.selectedObject) return;
        let ref = this.selectedObject.configRef;
        if (axis === 'X') {
            const cx = Math.round(640 - this.selectedObject.displayWidth / 2);
            this.selectedObject.x = cx; ref.x = cx;
        }
        if (axis === 'Y') {
            const cy = Math.round(360 - this.selectedObject.displayHeight / 2);
            this.selectedObject.y = cy; ref.y = cy;
        }
        this.updateSelectionUI(this.selectedObject);
    }

    toggleFlip() {
        if (!this.selectedObject || this.selectedObject.type === 'Rectangle') return;
        let ref = this.selectedObject.configRef;
        ref.flipX = !ref.flipX;
        this.selectedObject.setFlipX(ref.flipX);
        this.updateSelectionUI(this.selectedObject);
    }

    createBtn(x, y, text, callback, bgColor = '#222') {
        let btn = this.add.text(x, y, text, { backgroundColor: bgColor, padding: {x: 10, y: 5}, fill: '#fff', fontSize: '16px' })
            .setOrigin(0.5).setInteractive({ useHandCursor: true }).on('pointerdown', callback);
        this.uiLayer.add(btn);
        this.uiButtons.push(btn);
        return btn;
    }

    navigate(dir) {
        this.stopAllFX();
        this.currentRoomIndex = (this.currentRoomIndex + dir + this.roomKeys.length) % this.roomKeys.length;
        this.loadRoom(this.roomKeys[this.currentRoomIndex]);
    }

    resetRoom() {
        const roomId = this.roomKeys[this.currentRoomIndex];
        this.workingConfig.rooms[roomId] = JSON.parse(JSON.stringify(this.originalConfig.rooms[roomId]));
        this.loadRoom(roomId);
    }

    async saveJSON() {
        // Clean up editor-specific variables before saving
        let cleanConfig = JSON.parse(JSON.stringify(this.workingConfig));
        for (let r in cleanConfig.rooms) {
            if (cleanConfig.rooms[r].fx) {
                cleanConfig.rooms[r].fx.forEach(f => {
                    delete f._editorX;
                    delete f._editorY;
                });
            }
        }

        const projectId = window.EDITOR_PROJECT_ID;
        const apiUrl = window.EDITOR_API_URL;

        // If we are running inside the Streamlit/API ecosystem, send to backend
        if (projectId && apiUrl) {
            try {
                // Find the Save button to give visual feedback
                let saveBtn = this.uiButtons.find(b => b.text === "SAVE JSON");
                if (saveBtn) saveBtn.setText("SAVING...").setStyle({ backgroundColor: '#ffaa00' });

                const response = await fetch(`${apiUrl}/projects/${projectId}/game-config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(cleanConfig)
                });

                if (response.ok) {
                    console.log("Config successfully overwritten on server!");
                    if (saveBtn) {
                        saveBtn.setText("SAVED!").setStyle({ backgroundColor: '#00aa00' });
                        setTimeout(() => saveBtn.setText("SAVE JSON").setStyle({ backgroundColor: '#0055ff' }), 2000);
                    }
                } else {
                    console.error("Failed to save:", response.statusText);
                    if (saveBtn) saveBtn.setText("ERROR!").setStyle({ backgroundColor: '#aa0000' });
                }
            } catch (err) {
                console.error("Network error while saving:", err);
                alert("Network error: Could not save to backend.");
            }
        } 
        // Fallback: If not connected to the API, just download it like before
        else {
            const blob = new Blob([JSON.stringify(cleanConfig, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'game_config.json';
            a.click();
            URL.revokeObjectURL(url);
        }
    }
    
    shutdown() {
        if (this.panel) this.panel.remove();
        this.stopMusicPreview();
    }
}

const config = {
    type: Phaser.WEBGL,
    width: 1280, height: 920,
    parent: 'game-container',
    scene: [BootScene, PreloadScene, LevelEditor]
};
const game = new Phaser.Game(config);