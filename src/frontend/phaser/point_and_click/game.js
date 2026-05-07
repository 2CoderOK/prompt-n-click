class GameScene extends Phaser.Scene {
    constructor() { super('GameScene'); }

    create() {
        console.log("GameScene Created");

        // mergedConfig = gameConfig + assetsConfig (built by PreloadScene)
        this.db = this.cache.json.get('mergedConfig');
        if (!this.db) { console.error("Merged config not found!"); return; }
        this.resetState();
        this.createUI();
        this.activeTimers = {};
        
        // Attempt immediate autoplay — first click acts as fallback if browser blocks.
        if (this.sound.context.state === 'suspended') {
            this.sound.context.resume().then(() => this.startMusic());
        } else {
            this.startMusic();
        }
        this.input.once('pointerdown', () => {
            if (this.sound.context.state === 'suspended') {
                this.sound.context.resume().then(() => this.startMusic());
            } else {
                this.startMusic();
            }
        });
            
        this.time.addEvent({ delay: 1000, callback: this.checkTimers, callbackScope: this, loop: true });
        
        this.renderRoom(this.state.current_room);
    }

    resetState() {
        this.state = JSON.parse(JSON.stringify(this.db.initial_state));
        this.activeTimers = {};
        this.timerUIElements = {};
        this.pendingEffects = null;
        this.textQueue = []; 
        if (this.timerGroup) this.timerGroup.destroy(true); 
    }

    startMusic() {
        if (!this.cache.audio.exists('bg_music')) return;
        let music = this.sound.get('bg_music');
        
        if (!music) {
            const vol = (this.db.music && this.db.music.volume !== undefined) ? this.db.music.volume : 0.5;
            music = this.sound.add('bg_music', {
                volume: vol,
                loop: true
            });
            this.music = music;
        }

        if (this.sound.context.state === 'running') {
            if (!music.isPlaying) {
                music.play();
                console.log("Music started successfully.");
            }
        }
    }
    
    renderRoom(roomId) {
        this.state.current_room = roomId;
        let roomData = this.db.rooms[roomId];
        const isSystem = this.isSystemRoom(roomId);
        const ui = this.db.ui_styles || {};
        const color = parseInt(ui.highlight_color || '0x00ff00');

        this.timerUIElements = {};
    
        if (this.roomGroup) this.roomGroup.destroy(true);
        this.roomGroup = this.add.group();

        const bgKey = roomData.background_ref ? roomData.background_ref : roomId;
        this.roomGroup.add(this.add.image(0, 0, bgKey).setOrigin(0, 0));

        if (this.continueHint) this.continueHint.destroy();
        this.continueHint = null;

        if (isSystem && !roomId.startsWith('menu')) {
            this.continueHint = this.add.text(640, 680, "— CLICK TO CONTINUE —", {
                fontSize: '18px',
                fill: ui.text_panel?.font_color || '#0f0',
                fontFamily: 'monospace'
            }).setOrigin(0.5).setDepth(2000).setAlpha(0.7);
        }

        let autoTriggers = [];

        if (roomData.clickables) {
            roomData.clickables.forEach(clickData => {
                // 1. Skip if explicitly set to inactive
                if (clickData.active === false) return;

                // 2. Queue auto-triggers regardless of render_conditions:
                //    auto-triggers fire based on their own interaction conditions,
                //    not on whether the clickable is visually rendered.
                if (clickData['auto-trigger'] && clickData.interactions) {
                    autoTriggers.push(clickData);
                }

                // 3. Skip visual rendering if render_conditions not met, or item already in inventory
                if (!this.checkConditions(clickData.render_conditions)) return;
                if (clickData.item_ref && this.state.inventory && this.state.inventory.includes(clickData.item_ref)) return;

                // 4. Render actor/item sprite when the clickable carries a reference
                if (clickData.actor_ref) {
                    const sprite = this.add.image(clickData.x, clickData.y, clickData.actor_ref)
                        .setOrigin(0, 0).setDepth(5);
                    const s = clickData.scale || 1;
                    const baseW = clickData.width || sprite.width;
                    const baseH = clickData.height || sprite.height;
                    sprite.setDisplaySize(baseW * s, baseH * s);
                    sprite.setRotation(clickData.rotation || 0);
                    if (clickData.flipX) sprite.setFlipX(true);
                    this.roomGroup.add(sprite);
                }
                if (clickData.item_ref) {
                    const sprite = this.add.image(clickData.x, clickData.y, clickData.item_ref)
                        .setOrigin(0, 0).setDepth(5);
                    const s = clickData.scale || 1;
                    const baseW = clickData.width || sprite.width;
                    const baseH = clickData.height || sprite.height;
                    sprite.setDisplaySize(baseW * s, baseH * s);
                    sprite.setRotation(clickData.rotation || 0);
                    if (clickData.flipX) sprite.setFlipX(true);
                    this.roomGroup.add(sprite);
                }

                const radius = clickData.radius || 5;
                const rotation = clickData.rotation || 0;
                let highlight = null;

                // 5. Check for Text Buttons mapping
                if (this.db.text_buttons && this.db.text_buttons[clickData.id]) {
                    let tb = this.db.text_buttons[clickData.id];
                    let tbText = this.add.text(clickData.x + clickData.width/2, clickData.y + clickData.height/2, tb.text, {
                        fontSize: '24px',
                        fill: tb.color || '#ffffff',
                        fontFamily: 'monospace'
                    }).setOrigin(0.5).setAlpha(tb.alpha ?? 1).setDepth(10);
                    
                    tbText.setRotation(rotation);
                    if (clickData.flip) tbText.setFlipX(true);
                    
                    this.roomGroup.add(tbText);
                }

                const scale = clickData.scale || 1;
                const baseW = clickData.width || 100;
                const baseH = clickData.height || 100;
                const displayW = Math.round(baseW * scale);
                const displayH = Math.round(baseH * scale);

                if (!isSystem) {
                    highlight = this.add.graphics();
                    highlight.fillStyle(color, ui.highlight_alpha_fill ?? 0.1);
                    highlight.fillRoundedRect(0, 0, displayW, displayH, radius);
                    highlight.lineStyle(ui.stroke_width ?? 1, color, ui.highlight_alpha_stroke ?? 0.4);
                    highlight.strokeRoundedRect(0, 0, displayW, displayH, radius);
                    highlight.setPosition(clickData.x, clickData.y).setDepth(11).setVisible(false);
                    highlight.setRotation(rotation);
                    this.roomGroup.add(highlight);
                }

                let zone = this.add.rectangle(clickData.x, clickData.y, displayW, displayH)
                    .setOrigin(0, 0).setDepth(1000).setInteractive({ useHandCursor: true });
                zone.setRotation(rotation);
                this.roomGroup.add(zone);

                if (!isSystem && highlight) {
                    zone.on('pointerover', () => highlight.setVisible(true));
                    zone.on('pointerout', () => highlight.setVisible(false));
                }
                zone.on('pointerdown', () => {
                    if (clickData.interactions) this.handleInteraction(clickData.interactions);
                });
            });
        }
        
        if (this.fadeRect) {
            let willFadeIn = roomData.fx && roomData.fx.some(f => {
                if (f.type !== 'fade_in') return false;
                if (f.conditions && !this.checkConditions(f.conditions)) return false;
                if (f.run_once && this.state.flags[f.run_once]) return false; 
                return true; 
            });
            
            if (!willFadeIn) {
                this.fadeRect.setAlpha(0).setVisible(false);
            }
        }

        this.applyRoomEffects(roomData.fx);
        this.renderInventory();
        this.renderTimers();

        // Trigger any auto-execute clickables instantly after rendering is complete
        autoTriggers.forEach(c => this.handleInteraction(c.interactions));
    }

    applyRoomEffects(fxList, clearPrevious = true) {
        // Call the static shared system
		this.fxGroup = FXSystem.apply(this, fxList, this.fxGroup, clearPrevious);
    }

    createUI() {
        const ui = this.db.ui_styles || {};
        const panel = ui.text_panel || {};
        
        const bgColor = parseInt(panel.bg_color || '0x000000');
        const bgAlpha = panel.bg_alpha ?? 0.9;
        const strokeColor = parseInt(panel.stroke_color || ui.highlight_color || '0x00ff00');
        const strokeAlpha = panel.stroke_alpha ?? 0.8;
        const strokeWidth = panel.stroke_thickness ?? 2;

        this.fadeRect = this.add.rectangle(640, 360, 1280, 720, 0x000000, 0)
            .setDepth(1999)
            .setVisible(false);

        this.textBlocker = this.add.rectangle(640, 360, 1280, 720, 0x000000, 0.001)
            .setDepth(2000)
            .setVisible(false)
            .setInteractive();

        this.textBlocker.on('pointerdown', (pointer, localX, localY, event) => {
            if (event) event.stopPropagation(); 
            
            if (this.sound.context.state === 'suspended') {
                this.sound.context.resume().then(() => {
                    console.log("AudioContext Resumed via Blocker");
                    this.startMusic();
                });
            }
            
            this.hideText();
        });
        
        this.textBoxBg = this.add.rectangle(640, 650, 1000, 100, bgColor, bgAlpha)
            .setDepth(2001)
            .setVisible(false)
            .setStrokeStyle(strokeWidth, strokeColor, strokeAlpha);

        this.textBoxText = this.add.text(180, 620, "", { 
            fontSize: panel.font_size || '20px', 
            fill: panel.font_color || '#ffffff', 
            wordWrap: { width: 920 }, 
            fontFamily: 'monospace' 
        }).setDepth(2002).setVisible(false);
    }

    handleInteraction(interactions) {
        if (this.sound.context.state === 'suspended') {
            this.sound.context.resume().then(() => {
                this.startMusic(); 
            });
        }
        
        if (this.textBoxBg.visible) return;

        // print debug info about the interactions being process and conditions
        console.log("Processing interactions:", interactions);
        interactions.forEach(i => {
            console.log("Interaction conditions:", i.conditions, "Current flags:", this.state.flags);
        });
        let valid = interactions.find(i => this.checkConditions(i.conditions));
        if (valid) {
            if (this.cache.audio.exists('sfx_click')) this.sound.play('sfx_click', { volume: 0.5 });
            
            let allEffects = [];
            if (valid.effects) allEffects = [...valid.effects];

            const dialogRefKey = valid.dialogue_ref || valid.dialog_ref;
            if (dialogRefKey || valid.text) {
                // Pass the reference directly so processEffects can handle the array
                this.processEffects([{ dialogue_ref: dialogRefKey, show_text: valid.text, play_voice: valid.voice, effects: allEffects }]);
            } else {
                this.processEffects(allEffects);
            }

            if (this.textQueue.length > 0 && !this.textBoxBg.visible) {
                this.showNextQueuedText();
            }
        }
    }

    showText(text, effects = []) {
        this.pendingEffects = effects;
        this.textBoxBg.setVisible(true);
        this.textBoxText.setVisible(true).setText(text);
        this.textBlocker.setVisible(true);

        if (this.continueHint) this.continueHint.setVisible(false);
    }

    showNextQueuedText() {
        if (this.textQueue.length > 0) {
            const nextData = this.textQueue.shift();
            this.pendingEffects = nextData.effects; 

            if (nextData.fx) {
                this.applyRoomEffects(nextData.fx, false);
            }

            if (this.currentVoice) {
                this.currentVoice.stop();
                this.currentVoice.destroy();
            }

            if (nextData.voice) {
                if (!this.cache.audio.exists(nextData.voice)) {
                    console.warn(`Voice audio not in cache: "${nextData.voice}" — check that the dialog key matches what was loaded in PreloadScene.`);
                } else {
                    const doPlay = () => {
                        try {
                            this.currentVoice = this.sound.add(nextData.voice, { volume: 1 });
                            this.currentVoice.play();
                            console.log(`Playing voice: ${nextData.voice}`);
                        } catch(e) { console.warn('Voice playback error:', e); }
                    };
                    if (this.sound.context.state === 'suspended') {
                        this.sound.context.resume().then(doPlay);
                    } else {
                        doPlay();
                    }
                }
            }

            this.textBoxBg.setVisible(true);
            this.textBoxText.setVisible(true).setText(nextData.text);
            this.textBlocker.setVisible(true);
            if (this.continueHint) this.continueHint.setVisible(false);
        }
    }

    hideText() {
        if (!this.textBoxBg.visible) return;

        if (this.textQueue && this.textQueue.length > 0) {
            this.showNextQueuedText();
            return; 
        } 

        // Hide the UI elements FIRST! 
        this.textBoxBg.setVisible(false);
        this.textBoxText.setVisible(false);
        this.textBlocker.setVisible(false);
        
        if (this.continueHint) this.continueHint.setVisible(true);

        if (this.currentVoice) {
            this.currentVoice.stop();
            this.currentVoice = null;
        }

        // Now process effects (like changing rooms)
        if (this.pendingEffects && this.pendingEffects.length > 0) {
            let eff = this.pendingEffects;
            this.pendingEffects = null;
            
            // processEffects() will handle everything! If it fires an auto-trigger 
            // that adds text to the queue, processEffects() will automatically 
            // call showNextQueuedText() to display the first line.
            this.processEffects(eff);
        }
    }

    processEffects(effects) {
        if (!effects || effects.length === 0) return;
        if (this.sound.context.state === 'suspended') this.sound.context.resume();

        let textItems = [];
        let stateEffects = [];

        effects.forEach(e => {
            const dlgRef = e.dialogue_ref || e.dialog_ref;
            
            if (dlgRef && this.db.dialogs && this.db.dialogs[dlgRef]) {
                const dlgData = this.db.dialogs[dlgRef];
                
                if (Array.isArray(dlgData)) {
                    // Push each sequential line into the text queue
                    dlgData.forEach((line, index) => {
                        textItems.push({
                            text: line.text,
                            voice: (line.voice || line.audio_file) ? `${dlgRef}_${index}` : null,
                            fx: (index === 0) ? (e.fx || null) : null,
                            effects: [] // Real effects are attached to the LAST line below
                        });
                    });
                } else {
                    // Fallback for old single-object format
                    textItems.push({
                        text: dlgData.text,
                        voice: dlgRef,
                        fx: e.fx || null,
                        effects: []
                    });
                }
                
                // Keep the actual game state effects to append to the end of the dialog sequence
                if (e.effects && e.effects.length > 0) {
                    stateEffects = stateEffects.concat(e.effects);
                }
                
            } else if (e.show_text || e.text) {
                textItems.push({
                    text: e.show_text || e.text,
                    voice: e.play_voice || e.voice,
                    fx: e.fx || null,
                    effects: e.effects || []
                });
            } else {
                stateEffects.push(e);
            }
        });

        if (textItems.length > 0) {
            let lastItem = textItems[textItems.length - 1];
            lastItem.effects = lastItem.effects.concat(stateEffects);

            textItems.forEach(item => this.textQueue.push(item));
        } else {
            this.runStateEffects(stateEffects);
        }

        if (this.textQueue.length > 0 && !this.textBoxBg.visible) {
            this.showNextQueuedText();
        }
    }

    runStateEffects(effects) {
        let needsFxRefresh = false;

        effects.forEach(e => {
            if (e.set_flag) {
                this.state.flags[e.set_flag] = e.value;
                needsFxRefresh = true; 
            }
            if (e.change_room) {
                this.renderRoom(e.change_room);
                needsFxRefresh = false; 
            }
            if (e.apply_fx) {
                this.applyRoomEffects(e.apply_fx, false);
            }
            if (e.move_item_to_inventory) {
                this.state.inventory.push(e.move_item_to_inventory);
                this.renderRoom(this.state.current_room);
                needsFxRefresh = false;
            }
            if (e.remove_from_inventory) {
                this.state.inventory = this.state.inventory.filter(i => i !== e.remove_from_inventory);
                this.renderInventory();
            }
            if (e.reset_game_state) { 
                this.resetState(); 
                this.renderRoom(this.state.current_room); 
                needsFxRefresh = false;
            }
        });

        if (needsFxRefresh) {
            // Re-render the whole room so render_conditions on clickables are
            // re-evaluated with the updated flags (e.g. revealing hidden items).
            this.renderRoom(this.state.current_room);
        }
    }

    checkTimers() {
        if (!this.db.timers) return;
        let needsRender = false;

        this.db.timers.forEach(timer => {
            if (this.activeTimers[timer.id] === -1) return;

            if (timer.stop_conditions && timer.stop_conditions.length > 0 && this.checkConditions(timer.stop_conditions)) {
                if (this.activeTimers[timer.id] !== undefined) {
                    this.activeTimers[timer.id] = -1; 
                    needsRender = true; 
                }
                return;
            }

            if (this.checkConditions(timer.start_conditions)) {
                if (this.activeTimers[timer.id] === undefined) {
                    this.activeTimers[timer.id] = (timer.direction === 'up' ? 0 : timer.delay_seconds);
                    needsRender = true;
                }

                let inScope = (timer.scope === 'global' || timer.scope === this.state.current_room);
                
                if (inScope && this.activeTimers[timer.id] !== -1) {
                    this.activeTimers[timer.id] += (timer.direction === 'up' ? 1 : -1);
                    
                    if (this.timerUIElements[timer.id] && this.timerUIElements[timer.id].text && this.timerUIElements[timer.id].text.active) {
                        this.timerUIElements[timer.id].text.setText(this.formatTime(this.activeTimers[timer.id], timer.format));
                    }
                    
                    let isTimeout = (timer.direction === 'up' && this.activeTimers[timer.id] >= timer.delay_seconds) || 
                                    (timer.direction !== 'up' && this.activeTimers[timer.id] <= 0);
                                    
                    if (isTimeout) {
                        this.processEffects(timer.timeout_effects);
                        this.activeTimers[timer.id] = -1; 
                    }
                }
            }
        });

        if (needsRender) this.renderTimers();
    }

    formatTime(s, f) {
        if (f === 'mm:ss') return `${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toString().padStart(2,'0')}`;
        return s.toString();
    }

    renderTimers() {
        if (this.timerGroup) this.timerGroup.destroy(true);
        if (this.isSystemRoom(this.state.current_room)) return;
        
        this.timerGroup = this.add.group();
        this.timerUIElements = {}; 

        if (!this.db.timers) return;

        this.db.timers.forEach(t => {
            let inScope = (t.scope === 'global' || t.scope === this.state.current_room);
            
            if (t.show_ui && inScope && this.activeTimers[t.id] !== undefined && this.activeTimers[t.id] !== -1) {
                
                const textStyle = {
                    fontSize: t.font_size || '24px',
                    fill: t.font_color || '#f00',
                    fontFamily: 'monospace',
                    fontStyle: 'bold'
                };

                let txt = this.add.text(
                    t.ui_x, 
                    t.ui_y, 
                    this.formatTime(this.activeTimers[t.id], t.format), 
                    textStyle
                ).setDepth(1500).setAlpha(t.alpha ?? 1.0);

                this.timerGroup.add(txt);
                this.timerUIElements[t.id] = { text: txt };

                if (t.icon) {
                    const iconX = (t.icon_position === 'right') ? t.ui_x + txt.width + 20 : t.ui_x - 35;
                    let img = this.add.image(iconX, t.ui_y + (parseInt(textStyle.fontSize)/2), t.icon)
                        .setScale(t.icon_scale).setDepth(1500).setAlpha(t.alpha ?? 1.0);
                    this.timerGroup.add(img);
                }
            }
        });
    }

    renderInventory() {
        if (this.inventoryGroup) this.inventoryGroup.destroy(true);
        if (this.isSystemRoom(this.state.current_room)) return;
        this.inventoryGroup = this.add.group();
        // icons are actual items that are scaled based on config from ui_styles-> icons_scale
        let iconsScale = 0.05;
        if (this.db.ui_styles && this.db.ui_styles.icons_scale) {
            iconsScale = this.db.ui_styles.icons_scale;
        }
        // read from config highlight_color for inventory text color
        let textColor = this.db.ui_styles.highlight_color;
        // convert textColor to #RRGGBB format if it's in 0xRRGGBB format
        if (textColor && textColor.startsWith('0x')) {
            textColor = '#' + textColor.substring(2);
        }
        console.log("Rendering inventory with color:", textColor);
        this.inventoryGroup.add(this.add.text(1050, 15, "INVENTORY", { fontSize: '14px', fill: textColor, fontFamily: 'monospace' }).setDepth(1500));
        this.state.inventory.forEach((id, i) => this.inventoryGroup.add(this.add.image(1070 + (i * 60), 60, id).setScale(iconsScale).setDepth(1501)));
    }

    isSystemRoom(r) { return r.startsWith('menu') || r.startsWith('intro') || r.startsWith('game_over') || r.startsWith('victory'); }
    checkConditions(c) { return !c || c.length === 0 || c.every(cond => (this.state.flags[cond.flag] || false) === cond.is); }
}

const config = {
    type: Phaser.WEBGL,
    width: 1280, height: 720,
    parent: 'game-container',
    scene: [BootScene, PreloadScene, LogoScene, GameScene]
};
const game = new Phaser.Game(config);