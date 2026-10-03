/**
 * HELIOS Character Add-On — 3D Rig & Model Studio (Section 12)
 * ============================================================================
 * Provides an interactive in-browser Rigging & Model Inspector/Editor:
 * 1. 3D SkeletonHelper & glowing joint visualizer overlay on the live character.
 * 2. X-Ray mesh transparency and wireframe toggles.
 * 3. Real-time bone joint inspection, position offsets (X/Y/Z), and rotation tweaks.
 * 4. Skinning weights & binding tuning (lateral partition threshold, falloff power).
 * 5. Material & aesthetic customization (palette, roughness, metalness, emissive neon).
 * 6. Model scaling and floor height calibration.
 * 7. Rig profile saving, loading, export, and import via localStorage.
 */
import * as THREE from 'three';

export class RigEditor {
    constructor(context) {
        this.scene = context.scene;
        this.camera = context.camera;
        this.renderer = context.renderer;
        this.controls = context.controls;
        this.getCurrentVrm = context.getCurrentVrm;
        this.onStatus = context.onStatus || console.log;

        this.skeletonHelper = null;
        this.jointGroup = new THREE.Group();
        this.jointGroup.name = 'HELIOS_Rig_Joint_Markers';
        this.scene.add(this.jointGroup);

        this.isSkeletonVisible = false;
        this.isXRayActive = false;
        this.isWireframeActive = false;

        this.selectedBoneName = 'rightUpperArm';
        this.activeOffsets = {};
        this.defaultBoneConfig = [
            'hips', 'spine', 'chest', 'neck', 'head',
            'leftUpperArm', 'leftLowerArm', 'leftHand',
            'rightUpperArm', 'rightLowerArm', 'rightHand',
            'leftUpperLeg', 'leftLowerLeg', 'leftFoot',
            'rightUpperLeg', 'rightLowerLeg', 'rightFoot'
        ];

        this.storageKey = 'helios_character_rig_profile_v1';
        this.initUI();
    }

    attachToModel(vrm) {
        this.cleanupVisualizers();
        if (!vrm || !vrm.scene) return;

        // Create SkeletonHelper
        this.skeletonHelper = new THREE.SkeletonHelper(vrm.scene);
        this.skeletonHelper.visible = this.isSkeletonVisible;
        if (this.skeletonHelper.material) {
            this.skeletonHelper.material.linewidth = 2;
            this.skeletonHelper.material.depthTest = false;
            this.skeletonHelper.material.transparent = true;
            this.skeletonHelper.material.opacity = 0.85;
        }
        this.scene.add(this.skeletonHelper);

        // Populate Joint Markers
        this.createJointMarkers(vrm);

        // Update UI based on model type (FBX vs VRM)
        this.updateModelTypeUI(vrm);

        // Apply saved profile if available
        this.loadProfileFromStorage(false);
    }

    createJointMarkers(vrm) {
        if (this.jointMarkers) {
            this.jointMarkers.forEach((m) => {
                if (m.parent) m.parent.remove(m);
            });
        }
        this.jointMarkers = [];
        this.jointGroup.clear();
        if (!vrm || !vrm.humanoid) return;

        const jointGeo = new THREE.SphereGeometry(0.016, 12, 12);
        const jointMat = new THREE.MeshBasicMaterial({
            color: 0x00e5ff,
            wireframe: true,
            depthTest: false,
            transparent: true,
            opacity: 0.85,
        });

        this.defaultBoneConfig.forEach((bName) => {
            const bone = vrm.humanoid.getNormalizedBoneNode(bName);
            if (bone) {
                const marker = new THREE.Mesh(jointGeo, jointMat);
                marker.name = `joint_marker_${bName}`;
                marker.visible = this.isSkeletonVisible;
                bone.add(marker);
                this.jointMarkers.push(marker);
            }
        });
        this.jointGroup.visible = this.isSkeletonVisible;
    }

    cleanupVisualizers() {
        if (this.skeletonHelper) {
            this.scene.remove(this.skeletonHelper);
            if (this.skeletonHelper.geometry) this.skeletonHelper.geometry.dispose();
            this.skeletonHelper = null;
        }
        if (this.jointMarkers) {
            this.jointMarkers.forEach((m) => {
                if (m.parent) m.parent.remove(m);
            });
            this.jointMarkers = [];
        }
        this.jointGroup.clear();
    }

    toggleSkeleton(forceState = null) {
        this.isSkeletonVisible = forceState !== null ? forceState : !this.isSkeletonVisible;
        if (this.skeletonHelper) {
            this.skeletonHelper.visible = this.isSkeletonVisible;
        }
        if (this.jointMarkers) {
            this.jointMarkers.forEach((m) => {
                m.visible = this.isSkeletonVisible;
            });
        }
        this.jointGroup.visible = this.isSkeletonVisible;
        const btn = document.getElementById('btn-toggle-skeleton');
        const modalBtn = document.getElementById('rig-toggle-skeleton');
        const label = this.isSkeletonVisible ? '🦴 Skeleton: ON' : '🦴 Skeleton: OFF';
        if (btn) {
            btn.innerText = label;
            btn.classList.toggle('active', this.isSkeletonVisible);
        }
        if (modalBtn) {
            modalBtn.innerText = label;
            modalBtn.classList.toggle('active', this.isSkeletonVisible);
        }
        this.onStatus(`Rig Visualizer: Skeleton ${this.isSkeletonVisible ? 'Enabled' : 'Disabled'}`);
    }

    toggleXRay(forceState = null) {
        this.isXRayActive = forceState !== null ? forceState : !this.isXRayActive;
        const vrm = this.getCurrentVrm();
        if (vrm && vrm.scene) {
            vrm.scene.traverse((obj) => {
                if (obj.isMesh && obj.material) {
                    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
                    mats.forEach((m) => {
                        m.transparent = this.isXRayActive || (m.opacity < 0.99);
                        m.opacity = this.isXRayActive ? 0.38 : (vrm.isFBXModel ? (vrm.options?.opacity || 1.0) : 1.0);
                        m.depthWrite = !this.isXRayActive;
                        m.needsUpdate = true;
                    });
                }
            });
        }
        const btn = document.getElementById('btn-toggle-xray');
        const modalBtn = document.getElementById('rig-toggle-xray');
        const label = this.isXRayActive ? '🩻 X-Ray: ON' : '🩻 X-Ray: OFF';
        if (btn) {
            btn.innerText = label;
            btn.classList.toggle('active', this.isXRayActive);
        }
        if (modalBtn) {
            modalBtn.innerText = label;
            modalBtn.classList.toggle('active', this.isXRayActive);
        }
        this.onStatus(`Rig Visualizer: X-Ray Mesh ${this.isXRayActive ? 'ON' : 'OFF'}`);
    }

    toggleWireframe(forceState = null) {
        this.isWireframeActive = forceState !== null ? forceState : !this.isWireframeActive;
        const vrm = this.getCurrentVrm();
        if (vrm && vrm.scene) {
            vrm.scene.traverse((obj) => {
                if (obj.isMesh && obj.material) {
                    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
                    mats.forEach((m) => {
                        m.wireframe = this.isWireframeActive;
                        m.needsUpdate = true;
                    });
                }
            });
        }
        const modalBtn = document.getElementById('rig-toggle-wireframe');
        if (modalBtn) {
            modalBtn.innerText = this.isWireframeActive ? '🕸️ Wireframe: ON' : '🕸️ Wireframe: OFF';
            modalBtn.classList.toggle('active', this.isWireframeActive);
        }
        this.onStatus(`Rig Visualizer: Wireframe ${this.isWireframeActive ? 'ON' : 'OFF'}`);
    }

    update() {
        if (this.skeletonHelper && this.skeletonHelper.visible && typeof this.skeletonHelper.update === 'function') {
            this.skeletonHelper.update();
        }
    }

    updateModelTypeUI(vrm) {
        const isFBX = Boolean(vrm && vrm.isFBXModel);
        const skinningTabBtn = document.getElementById('tab-btn-skinning');
        const fbxBadge = document.getElementById('rig-model-badge');
        if (fbxBadge) {
            fbxBadge.innerText = isFBX ? '🦾 FBX Skinned Model (Meshy Techwear)' : '⚡ VRM Modular Model';
            fbxBadge.style.color = isFBX ? '#00e5ff' : '#00ff88';
        }
        if (skinningTabBtn) {
            skinningTabBtn.style.opacity = isFBX ? '1.0' : '0.6';
            skinningTabBtn.title = isFBX ? 'FBX GPU Skinning & Binding Parameters' : 'Skinning re-bind is active on FBX models';
        }
    }

    initUI() {
        // Quick sidebar buttons
        const btnToggleSkel = document.getElementById('btn-toggle-skeleton');
        if (btnToggleSkel) btnToggleSkel.onclick = () => this.toggleSkeleton();

        const btnToggleXRay = document.getElementById('btn-toggle-xray');
        if (btnToggleXRay) btnToggleXRay.onclick = () => this.toggleXRay();

        const btnOpenStudio = document.getElementById('btn-open-rig-studio');
        if (btnOpenStudio) btnOpenStudio.onclick = () => this.openStudioModal();

        // Modal controls
        const btnClose = document.getElementById('btn-close-rig-studio');
        if (btnClose) btnClose.onclick = () => this.closeStudioModal();

        const modalToggleSkel = document.getElementById('rig-toggle-skeleton');
        if (modalToggleSkel) modalToggleSkel.onclick = () => this.toggleSkeleton();

        const modalToggleXRay = document.getElementById('rig-toggle-xray');
        if (modalToggleXRay) modalToggleXRay.onclick = () => this.toggleXRay();

        const modalToggleWire = document.getElementById('rig-toggle-wireframe');
        if (modalToggleWire) modalToggleWire.onclick = () => this.toggleWireframe();

        // Tab switching
        const tabs = ['bones', 'skinning', 'material', 'profile'];
        tabs.forEach((tabName) => {
            const btn = document.getElementById(`tab-btn-${tabName}`);
            const content = document.getElementById(`tab-content-${tabName}`);
            if (btn && content) {
                btn.onclick = () => {
                    tabs.forEach((t) => {
                        document.getElementById(`tab-btn-${t}`)?.classList.remove('active');
                        const pane = document.getElementById(`tab-content-${t}`);
                        if (pane) pane.style.display = 'none';
                    });
                    btn.classList.add('active');
                    content.style.display = 'block';
                };
            }
        });

        // Bone dropdown selection
        const boneSelect = document.getElementById('rig-bone-select');
        if (boneSelect) {
            boneSelect.onchange = () => {
                this.selectedBoneName = boneSelect.value;
                this.syncBoneSliders();
            };
        }

        // Bone Offset sliders
        const sliderX = document.getElementById('slider-bone-x');
        const sliderY = document.getElementById('slider-bone-y');
        const sliderZ = document.getElementById('slider-bone-z');

        const updateBoneFromSliders = () => {
            const x = Number(sliderX?.value || 0) / 100; // cm -> meters
            const y = Number(sliderY?.value || 0) / 100;
            const z = Number(sliderZ?.value || 0) / 100;

            document.getElementById('val-bone-x').innerText = `${sliderX.value} cm`;
            document.getElementById('val-bone-y').innerText = `${sliderY.value} cm`;
            document.getElementById('val-bone-z').innerText = `${sliderZ.value} cm`;

            this.applyBoneOffset(this.selectedBoneName, { x, y, z });
        };

        if (sliderX) sliderX.oninput = updateBoneFromSliders;
        if (sliderY) sliderY.oninput = updateBoneFromSliders;
        if (sliderZ) sliderZ.oninput = updateBoneFromSliders;

        const btnResetBone = document.getElementById('btn-reset-bone');
        if (btnResetBone) {
            btnResetBone.onclick = () => {
                if (sliderX) sliderX.value = 0;
                if (sliderY) sliderY.value = 0;
                if (sliderZ) sliderZ.value = 0;
                updateBoneFromSliders();
            };
        }

        const btnResetAllBones = document.getElementById('btn-reset-all-bones');
        if (btnResetAllBones) {
            btnResetAllBones.onclick = () => {
                this.activeOffsets = {};
                const vrm = this.getCurrentVrm();
                if (vrm && vrm.isFBXModel) {
                    this.defaultBoneConfig.forEach((bName) => {
                        vrm.setBoneOffset(bName, { x: 0, y: 0, z: 0 });
                    });
                    vrm.rebindSkinning();
                }
                this.syncBoneSliders();
                this.onStatus('Reset all bone offsets to rest pose');
            };
        }

        // Skinning Tab controls (FBX)
        const sliderPartition = document.getElementById('slider-lateral-partition');
        const sliderFalloff = document.getElementById('slider-falloff-power');
        const sliderInfluences = document.getElementById('slider-max-influences');
        const btnRebind = document.getElementById('btn-rebind-skinning');

        if (sliderPartition) {
            sliderPartition.oninput = () => {
                document.getElementById('val-lateral-partition').innerText = `${sliderPartition.value} m`;
            };
        }
        if (sliderFalloff) {
            sliderFalloff.oninput = () => {
                document.getElementById('val-falloff-power').innerText = `${sliderFalloff.value}`;
            };
        }
        if (sliderInfluences) {
            sliderInfluences.oninput = () => {
                document.getElementById('val-max-influences').innerText = `${sliderInfluences.value}`;
            };
        }

        if (btnRebind) {
            btnRebind.onclick = () => {
                const vrm = this.getCurrentVrm();
                if (!vrm || !vrm.isFBXModel) {
                    this.onStatus('⚠️ Re-binding skinning is specifically for FBX character meshes.');
                    return;
                }
                const lateralPartitionX = Number(sliderPartition?.value || 0.22);
                const falloffPower = Number(sliderFalloff?.value || 2.0);
                const maxInfluences = parseInt(sliderInfluences?.value || 4, 10);

                vrm.rebindSkinning({
                    lateralPartitionX,
                    falloffPower,
                    maxInfluences,
                });
                this.onStatus(`⚡ Re-bound FBX Skinning! (Arm |X|: ${lateralPartitionX}m, Falloff: ${falloffPower}, Bones: ${maxInfluences})`);
            };
        }

        // Material Tab controls
        const matColorPicker = document.getElementById('rig-mat-color');
        const sliderRoughness = document.getElementById('slider-mat-roughness');
        const sliderMetalness = document.getElementById('slider-mat-metalness');
        const emissivePicker = document.getElementById('rig-emissive-color');
        const sliderEmissiveInt = document.getElementById('slider-emissive-intensity');
        const sliderHeight = document.getElementById('slider-model-height');
        const sliderFloor = document.getElementById('slider-floor-offset');

        const updateMatAppearance = () => {
            const vrm = this.getCurrentVrm();
            if (!vrm) return;
            const color = matColorPicker?.value || '#3e4758';
            const roughness = Number(sliderRoughness?.value || 0.48);
            const metalness = Number(sliderMetalness?.value || 0.32);
            const emissiveColor = emissivePicker?.value || '#00e5ff';
            const emissiveIntensity = Number(sliderEmissiveInt?.value || 0.08);

            document.getElementById('val-mat-roughness').innerText = `${roughness}`;
            document.getElementById('val-mat-metalness').innerText = `${metalness}`;
            document.getElementById('val-emissive-intensity').innerText = `${emissiveIntensity}`;

            if (vrm.isFBXModel && vrm.updateMaterial) {
                vrm.updateMaterial({
                    materialColor: color,
                    roughness,
                    metalness,
                    emissiveColor,
                    emissiveIntensity,
                });
            } else if (vrm.scene) {
                // VRM material update fallback
                vrm.scene.traverse((obj) => {
                    if (obj.isMesh && obj.material && obj.material.roughness !== undefined) {
                        obj.material.roughness = roughness;
                        obj.material.metalness = metalness;
                        obj.material.needsUpdate = true;
                    }
                });
            }
        };

        if (matColorPicker) matColorPicker.oninput = updateMatAppearance;
        if (sliderRoughness) sliderRoughness.oninput = updateMatAppearance;
        if (sliderMetalness) sliderMetalness.oninput = updateMatAppearance;
        if (emissivePicker) emissivePicker.oninput = updateMatAppearance;
        if (sliderEmissiveInt) sliderEmissiveInt.oninput = updateMatAppearance;

        // Palette presets
        const palettes = {
            'preset-graphite': '#3e4758',
            'preset-stealth': '#181a20',
            'preset-cyan': '#153243',
            'preset-white': '#d1d5db',
            'preset-olive': '#2c3529',
        };
        Object.entries(palettes).forEach(([btnId, hex]) => {
            const pBtn = document.getElementById(btnId);
            if (pBtn) {
                pBtn.onclick = () => {
                    if (matColorPicker) matColorPicker.value = hex;
                    updateMatAppearance();
                };
            }
        });

        // Height & Floor Offset
        if (sliderHeight) {
            sliderHeight.oninput = () => {
                const targetH = Number(sliderHeight.value);
                document.getElementById('val-model-height').innerText = `${targetH.toFixed(2)} m`;
                const vrm = this.getCurrentVrm();
                if (vrm && vrm.isFBXModel) {
                    vrm.options.targetHeight = targetH;
                    vrm.rebindSkinning({ targetHeight: targetH });
                } else if (vrm && vrm.scene) {
                    const s = targetH / 1.72;
                    vrm.scene.scale.set(s, s, s);
                }
            };
        }

        if (sliderFloor) {
            sliderFloor.oninput = () => {
                const floorY = Number(sliderFloor.value);
                document.getElementById('val-floor-offset').innerText = `${floorY.toFixed(2)} m`;
                const vrm = this.getCurrentVrm();
                if (vrm && vrm.scene) {
                    vrm.scene.position.y = floorY;
                }
            };
        }

        // Profile Tab controls
        const btnSave = document.getElementById('btn-save-rig-profile');
        if (btnSave) btnSave.onclick = () => this.saveProfileToStorage();

        const btnLoad = document.getElementById('btn-load-rig-profile');
        if (btnLoad) btnLoad.onclick = () => this.loadProfileFromStorage(true);

        const btnResetFactory = document.getElementById('btn-reset-rig-factory');
        if (btnResetFactory) btnResetFactory.onclick = () => this.resetFactoryDefaults();

        const btnExportJson = document.getElementById('btn-export-rig-json');
        if (btnExportJson) btnExportJson.onclick = () => this.exportProfileJson();

        const btnImportJson = document.getElementById('btn-import-rig-json');
        if (btnImportJson) btnImportJson.onclick = () => this.importProfileJson();
    }

    applyBoneOffset(boneName, offset) {
        if (!boneName) return;
        this.activeOffsets[boneName] = offset;
        const vrm = this.getCurrentVrm();
        if (vrm && vrm.isFBXModel && vrm.setBoneOffset) {
            vrm.setBoneOffset(boneName, offset);
        } else if (vrm && vrm.humanoid) {
            const bone = vrm.humanoid.getNormalizedBoneNode(boneName);
            if (bone) {
                bone.position.x += offset.x * 0.05;
                bone.position.y += offset.y * 0.05;
                bone.position.z += offset.z * 0.05;
            }
        }
        if (this.skeletonHelper && this.skeletonHelper.visible && typeof this.skeletonHelper.update === 'function') {
            this.skeletonHelper.update();
        }
    }

    syncBoneSliders() {
        const off = this.activeOffsets[this.selectedBoneName] || { x: 0, y: 0, z: 0 };
        const sx = document.getElementById('slider-bone-x');
        const sy = document.getElementById('slider-bone-y');
        const sz = document.getElementById('slider-bone-z');

        const cmX = Math.round(off.x * 100);
        const cmY = Math.round(off.y * 100);
        const cmZ = Math.round(off.z * 100);

        if (sx) sx.value = cmX;
        if (sy) sy.value = cmY;
        if (sz) sz.value = cmZ;

        document.getElementById('val-bone-x').innerText = `${cmX} cm`;
        document.getElementById('val-bone-y').innerText = `${cmY} cm`;
        document.getElementById('val-bone-z').innerText = `${cmZ} cm`;

        const vrm = this.getCurrentVrm();
        const info = document.getElementById('rig-bone-info');
        if (info && vrm && vrm.humanoid) {
            const bone = vrm.humanoid.getNormalizedBoneNode(this.selectedBoneName);
            if (bone) {
                const wp = new THREE.Vector3();
                bone.getWorldPosition(wp);
                info.innerText = `Bone: ${this.selectedBoneName} | Parent: ${bone.parent?.name || 'none'} | World: (${wp.x.toFixed(2)}, ${wp.y.toFixed(2)}, ${wp.z.toFixed(2)})`;
            } else {
                info.innerText = `Bone: ${this.selectedBoneName} (Not mapped in active avatar)`;
            }
        }
    }

    openStudioModal() {
        const modal = document.getElementById('rig-studio-modal');
        if (modal) {
            modal.style.display = 'flex';
            const vrm = this.getCurrentVrm();
            this.updateModelTypeUI(vrm);
            this.syncBoneSliders();
        }
    }

    closeStudioModal() {
        const modal = document.getElementById('rig-studio-modal');
        if (modal) modal.style.display = 'none';
    }

    saveProfileToStorage() {
        const vrm = this.getCurrentVrm();
        const profile = {
            version: 1,
            savedAt: new Date().toISOString(),
            isFBX: Boolean(vrm?.isFBXModel),
            boneOffsets: this.activeOffsets,
            skinning: {
                lateralPartitionX: Number(document.getElementById('slider-lateral-partition')?.value || 0.22),
                falloffPower: Number(document.getElementById('slider-falloff-power')?.value || 2.0),
                maxInfluences: parseInt(document.getElementById('slider-max-influences')?.value || 4, 10),
            },
            material: {
                color: document.getElementById('rig-mat-color')?.value || '#3e4758',
                roughness: Number(document.getElementById('slider-mat-roughness')?.value || 0.48),
                metalness: Number(document.getElementById('slider-mat-metalness')?.value || 0.32),
                emissiveColor: document.getElementById('rig-emissive-color')?.value || '#00e5ff',
                emissiveIntensity: Number(document.getElementById('slider-emissive-intensity')?.value || 0.08),
            },
        };
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(profile));
            this.onStatus('💾 Rig & Model Profile saved to browser storage!');
        } catch (e) {
            console.error('Failed to save rig profile:', e);
        }
    }

    loadProfileFromStorage(showStatus = true) {
        try {
            const raw = localStorage.getItem(this.storageKey);
            if (!raw) return;
            const profile = JSON.parse(raw);
            if (profile.boneOffsets) {
                this.activeOffsets = profile.boneOffsets;
                const vrm = this.getCurrentVrm();
                if (vrm && vrm.isFBXModel) {
                    Object.entries(this.activeOffsets).forEach(([bName, off]) => {
                        vrm.setBoneOffset(bName, off);
                    });
                    if (profile.skinning) {
                        vrm.rebindSkinning(profile.skinning);
                    }
                    if (profile.material && vrm.updateMaterial) {
                        vrm.updateMaterial(profile.material);
                    }
                }
                this.syncBoneSliders();
                if (showStatus) this.onStatus('📂 Rig Profile loaded successfully from storage!');
            }
        } catch (e) {
            console.warn('Could not restore rig profile:', e);
        }
    }

    resetFactoryDefaults() {
        this.activeOffsets = {};
        const vrm = this.getCurrentVrm();
        if (vrm && vrm.isFBXModel) {
            this.defaultBoneConfig.forEach((bName) => {
                vrm.setBoneOffset(bName, { x: 0, y: 0, z: 0 });
            });
            vrm.rebindSkinning({
                lateralPartitionX: 0.22,
                falloffPower: 2.0,
                maxInfluences: 4,
            });
            if (vrm.updateMaterial) {
                vrm.updateMaterial({
                    materialColor: '#3e4758',
                    roughness: 0.48,
                    metalness: 0.32,
                    emissiveColor: '#00e5ff',
                    emissiveIntensity: 0.08,
                });
            }
        }
        try {
            localStorage.removeItem(this.storageKey);
        } catch (e) {}
        this.syncBoneSliders();
        this.onStatus('🔄 Reset Rig & Model parameters to factory defaults.');
    }

    exportProfileJson() {
        const vrm = this.getCurrentVrm();
        const profile = vrm?.isFBXModel && vrm.getRigConfiguration
            ? vrm.getRigConfiguration()
            : { boneOffsets: this.activeOffsets };
        const blob = new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `helios_rig_profile_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.onStatus('📤 Exported Rig Profile JSON file.');
    }

    importProfileJson() {
        const inp = document.createElement('input');
        inp.type = 'file';
        inp.accept = '.json';
        inp.onchange = (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (re) => {
                try {
                    const data = JSON.parse(re.target.result);
                    if (data.boneOffsets) this.activeOffsets = data.boneOffsets;
                    const vrm = this.getCurrentVrm();
                    if (vrm && vrm.isFBXModel) {
                        vrm.rebindSkinning(data);
                        if (vrm.updateMaterial && data.materialColor) {
                            vrm.updateMaterial(data);
                        }
                    }
                    this.syncBoneSliders();
                    this.onStatus(`📥 Imported Rig Profile from ${file.name}`);
                } catch (err) {
                    alert('Invalid Rig Profile JSON: ' + err.message);
                }
            };
            reader.readAsText(file);
        };
        inp.click();
    }
}
