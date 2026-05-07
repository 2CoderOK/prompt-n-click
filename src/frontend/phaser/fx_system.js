/**
 * Shared FX System
 * Handles rendering and animation for all visual effects.
 */
class FXSystem {
    static apply(scene, fxList, targetGroup, clearPrevious = true) {
        if (clearPrevious) {
            if (targetGroup) targetGroup.destroy(true);
            // Re-initialize group if it was destroyed
            targetGroup = scene.add.group();
            
            // Clear post-processing from room children
            if (scene.roomGroup) {
                scene.roomGroup.getChildren().forEach(child => {
                    if (child.postFX) child.postFX.clear();
                });
            }
        }

        if (!fxList || fxList.length === 0) return targetGroup;

        const depthBase = 1900;
        const getColor = (c, defaultHex) => typeof c === 'string' ? Number(c.replace('#', '0x')) : (c || defaultHex);

        fxList.forEach((fx, index) => {
            // Condition check (if scene has state)
            if (scene.state && fx.conditions && !scene.checkConditions(fx.conditions)) return;
            
            if (scene.state && fx.run_once) {
                if (scene.state.flags[fx.run_once]) return; 
                scene.state.flags[fx.run_once] = true;
            }

            let d = depthBase + index;
            
            switch(fx.type) {
                case 'vignette':
                    let v = scene.add.graphics().setDepth(d);
                    v.fillStyle(0x000000, fx.alpha || 0.6);
                    v.fillRect(0, 0, 1280, 100); 
                    v.fillRect(0, 620, 1280, 100); 
                    v.fillRect(0, 100, 100, 520); 
                    v.fillRect(1180, 100, 100, 520); 
                    targetGroup.add(v);
                    break;

                case 'scanlines':
                    let lineThickness = fx.thickness || 4;
                    let sl = scene.add.grid(640, 360, 1280, 1440, 1, lineThickness, 0x000000, 0, 0x000000, fx.alpha || 0.3)
                        .setDepth(d);
                    targetGroup.add(sl);
                    
                    if (fx.animated) {
                        scene.tweens.add({
                            targets: sl,
                            y: `+=${lineThickness}`, 
                            duration: fx.speed || 60,
                            repeat: -1,
                            onRepeat: () => { sl.y = 360; } 
                        });
                    }
                    break;

                case 'crt_rgb_split':
                    let bgNode = scene.roomGroup ? scene.roomGroup.getChildren()[0] : null;
                    if (bgNode && bgNode.texture) {
                        let shiftX = fx.shift || 4;
                        let ghostR = scene.add.image(bgNode.x - shiftX, bgNode.y, bgNode.texture.key).setOrigin(0,0).setAlpha(fx.alpha || 0.4).setTint(0xff0000).setBlendMode('ADD').setDepth(d);
                        let ghostB = scene.add.image(bgNode.x + shiftX, bgNode.y, bgNode.texture.key).setOrigin(0,0).setAlpha(fx.alpha || 0.4).setTint(0x0000ff).setBlendMode('ADD').setDepth(d);
                        targetGroup.add(ghostR);
                        targetGroup.add(ghostB);

                        if (fx.animated) {
                            scene.tweens.add({ targets: [ghostR, ghostB], x: '+=3', yoyo: true, duration: 50, repeat: -1 });
                        }
                    }
                    break;
                    
                case 'color_tint':
                    let tColor = getColor(fx.color, 0xff0000);
                    let t = scene.add.rectangle(640, 360, 1280, 720, tColor, fx.alpha || 0.3)
                        .setDepth(d)
                        .setBlendMode(Phaser.BlendModes.MULTIPLY); 
                    targetGroup.add(t);
                    break;

                case 'pulse_tint':
                    let ptColor = getColor(fx.color, 0xff0000);
                    let pt = scene.add.rectangle(640, 360, 1280, 720, ptColor, 1)
                        .setAlpha(0)
                        .setDepth(d)
                        .setBlendMode(Phaser.BlendModes.ADD); 
                    
                    targetGroup.add(pt);
                    scene.tweens.add({ 
                        targets: pt, 
                        alpha: fx.alpha || 0.5, 
                        duration: fx.speed || 1000, 
                        yoyo: true, 
                        repeat: -1,
                        ease: 'Sine.easeInOut'
                    });
                    break;

                case 'blur':
                    let targetStrength = fx.strength !== undefined ? fx.strength : 2;
                    let startStrength = fx.animated ? (fx.start_strength !== undefined ? fx.start_strength : 0) : targetStrength;
                    
                    let blurData = [];
                    if (scene.roomGroup) {
                        scene.roomGroup.getChildren().forEach(child => {
                            if (child.postFX) {
                                let p = child.postFX.addBlur(fx.quality || 1, fx.x || 1, fx.y || 1, startStrength);
                                blurData.push({ child: child, pipeline: p });
                            }
                        });
                    }

                    if (fx.animated && blurData.length > 0) {
                        scene.tweens.add({
                            targets: blurData.map(b => b.pipeline),
                            strength: targetStrength,
                            duration: fx.speed || 1000,
                            yoyo: fx.yoyo !== false,                 
                            repeat: fx.repeat !== undefined ? fx.repeat : -1, 
                            ease: fx.ease || 'Sine.easeInOut',
                            onComplete: () => {
                                if (targetStrength === 0) {
                                    blurData.forEach(b => {
                                        if (b.child && b.child.postFX) {
                                            b.child.postFX.remove(b.pipeline);
                                        }
                                    });
                                }
                            }
                        });
                    }
                    break;

                case 'strobe':
                    let str = scene.add.rectangle(640, 360, 1280, 720, parseInt(fx.color || '0x000000'), 0).setDepth(d);
                    targetGroup.add(str);
                    scene.tweens.add({ targets: str, alpha: fx.alpha || 0.8, duration: fx.speed || 50, hold: fx.hold || 50, yoyo: true, repeat: -1, repeatDelay: fx.delay || 100 });
                    break;

                case 'letterbox':
                    let lbTop = scene.add.rectangle(640, -100, 1280, 200, 0x000000).setDepth(d).setAlpha(fx.alpha || 0.7);
                    let lbBot = scene.add.rectangle(640, 820, 1280, 200, 0x000000).setDepth(d).setAlpha(fx.alpha || 0.7);
                    targetGroup.add(lbTop);
                    targetGroup.add(lbBot);
                    scene.tweens.add({ targets: lbTop, y: 100, duration: fx.duration || 1000, ease: 'Power2' });
                    scene.tweens.add({ targets: lbBot, y: 620, duration: fx.duration || 1000, ease: 'Power2' });
                    break;

                case 'shadow_gradient':
                    let grad = scene.add.graphics().setDepth(d);
                    grad.fillGradientStyle(0x000000, 0x000000, 0x000000, 0x000000, 0, 0, fx.alpha || 0.8, fx.alpha || 0.8);
                    grad.fillRect(0, 360, 1280, 360);
                    targetGroup.add(grad);
                    break;

                case 'hologram_lines':
                    let hg = scene.add.graphics().setDepth(d).setAlpha(fx.alpha || 0.15);
                    hg.fillStyle(parseInt(fx.color || '0x00ffff'), 1);
                    for(let i=0; i<720; i+=12) hg.fillRect(0, i, 1280, 2);
                    targetGroup.add(hg);
                    scene.tweens.add({ targets: hg, y: '+=12', duration: 150, repeat: -1 });
                    break;

                case 'flash':
                    let fl = scene.add.rectangle(640, 360, 1280, 720, parseInt(fx.color || '0xffffff'), fx.alpha || 1).setDepth(d);
                    targetGroup.add(fl);
                    scene.tweens.add({ targets: fl, alpha: 0, duration: fx.duration || 1000, ease: 'Power2' });
                    break;

                case 'fade_in':
                    if (scene.fadeRect) {
                        scene.fadeRect.setFillStyle(parseInt(fx.color || '0x000000'));
                        scene.fadeRect.setAlpha(fx.alpha !== undefined ? fx.alpha : 1).setVisible(true).setDepth(2000);
                        scene.tweens.add({ 
                            targets: scene.fadeRect, 
                            alpha: 0, 
                            duration: fx.duration || 1500,
                            onComplete: () => scene.fadeRect.setVisible(false) 
                        });
                    }
                    break;

                case 'fade_out':
                    if (scene.fadeRect) {
                        scene.fadeRect.setFillStyle(parseInt(fx.color || '0x000000'));
                        scene.fadeRect.setAlpha(0).setVisible(true).setDepth(2000);
                        scene.tweens.add({ 
                            targets: scene.fadeRect, 
                            alpha: fx.alpha !== undefined ? fx.alpha : 1, 
                            duration: fx.duration || 1500 
                        });
                    }
                    break;

                case 'shake':
                    if (scene.roomGroup) {
                        let targets = scene.roomGroup.getChildren();
                        let ox = targets.map(t => t.x);
                        let oy = targets.map(t => t.y);
                        let intensity = fx.intensity || 8;
                        
                        scene.tweens.addCounter({
                            from: 0, to: 1, 
							duration: fx.duration || 1000,
							yoyo: true, 
                            repeat: 0,
                            onUpdate: () => {
                                targets.forEach((t, i) => {
                                    t.x = ox[i] + Phaser.Math.Between(-intensity, intensity);
                                    t.y = oy[i] + Phaser.Math.Between(-intensity, intensity);
                                });
                            },
                            onComplete: () => {
                                targets.forEach((t, i) => { t.x = ox[i]; t.y = oy[i]; });
                            }
                        });
                    }
                    break;

                case 'glitch':
                    let bgImg = scene.roomGroup ? scene.roomGroup.getChildren()[0] : null; 
                    if (bgImg) {
                        scene.tweens.add({
                            targets: bgImg,
                            x: { value: () => Phaser.Math.Between(-15, 15), duration: 50 },
                            y: { value: () => Phaser.Math.Between(-5, 5), duration: 50 },
                            alpha: { value: () => Phaser.Math.FloatBetween(0.8, 1), duration: 50 },
                            yoyo: true,
                            repeat: -1,
                            repeatDelay: fx.speed || 500
                        });
                    }
                    break;

                case 'zoom_pan':
                    let bg = scene.roomGroup ? scene.roomGroup.getChildren()[0] : null;
                    if (bg) {
                        bg.setScale(fx.startScale || 1.05);
                        scene.tweens.add({
                            targets: bg,
                            x: fx.panX || -30,
                            y: fx.panY || -20,
                            scaleX: fx.endScale || 1.15,
                            scaleY: fx.endScale || 1.15,
                            duration: fx.duration || 10000,
                            ease: 'Sine.easeInOut',
                            yoyo: true,
                            repeat: -1
                        });
                    }
                    break;

                case 'particles': 
                case 'fog':
                case 'sparks':
                case 'snow':
                case 'rain':
                    FXSystem.createParticles(scene, fx, d, targetGroup);
                    break;
            }
        });

        return targetGroup;
    }

    static createParticles(scene, fx, depth, group) {
        let config = {};
        const asset = fx.asset || 'fx_circle';

        switch(fx.type) {
            case 'fog':
                config = { 
                    x: { min: -100, max: 1280 },
					y: { min: 200, max: 720 }, 
                    lifespan: fx.lifespan || 10000,
					speedX: { min: fx.speedMin || 10, max: fx.speedMax || 30 },
					speedY: { min: fx.speedMinY || -5, max: fx.speedMaxY || 5 },
                    scale: { min: fx.scaleStart || 3 , max: fx.scaleEnd || 6 },
					alpha: { start: fx.alpha || 0.2, end: 0 }, 
                    frequency: fx.frequency || 700,
					blendMode: 'NORMAL' 
                };
                break;
            case 'snow':
                config = { 
                    x: { min: 0, max: 1280 },
					y: -50, 
                    lifespan: fx.lifespan || 6000,
					speedY: { min: fx.speedMinY || 50, max: fx.speedMaxY || 100 },
					speedX: { min: fx.speedMin || -20, max: fx.speedMax || 20 },
                    scale: { min: fx.scaleStart || 0.05, max: fx.scaleEnd || 0.2 },
					alpha: { start: fx.alpha || 0.8, end: 0 }, 
                    frequency: 50,
					blendMode: 'NORMAL' 
                };
                break;
            case 'rain':
                config = { 
                    x: { min: 0, max: 1280 },
					y: -50, 
                    lifespan: fx.lifespan || 1500,
					speedY: { min: fx.speedMinY || 400, max: fx.speedMaxY || 600 },
					speedX: { min: fx.speedMin || -20, max: fx.speedMax || 20 },
                    scaleY: { min: fx.scaleStart || 1, max: fx.scaleEnd || 3 },
					scaleX: 0.1,
					alpha: { start: fx.alpha || 0.4, end: 0 }, 
                    frequency: fx.frequency || 10,
					blendMode: 'ADD' 
                };
                break;
            case 'sparks':
                config = { 
                    x: fx.x || 640,
					y: fx.y || 360, 
					speed: { min: fx.speedMin || 100, max: fx.speedMax || 400 }, 
					angle: { min: 240, max: 300 },
                    gravityY: 500,
					lifespan: fx.lifespan || 1200,
					scale: { start: fx.scaleStart || 0.1, end: fx.scaleEnd || 0 },
                    alpha: { start: 1, end: 0 },
					frequency: fx.frequency || 50, 
					blendMode: 'ADD' 
                };
                break;
            default: // standard particles
                config = { 
                    x: { min: 0, max: 1280 },
					y: { min: 0, max: 720 }, 
                    lifespan: fx.lifespan || 4000,
					speed: { min: fx.speedMin || 10, max: fx.speedMax || 50 }, 
                    scale: { start: fx.scaleStart || 0.1, end: fx.scaleEnd || 0 }, 
                    alpha: { start: fx.alphaStart || 0.5, end: 0 }, 
                    frequency: fx.frequency || 100,
					blendMode: fx.blendMode || 'ADD' 
                };
        }

        let p = scene.add.particles(0, 0, asset, config).setDepth(depth);
        group.add(p);
    }
}