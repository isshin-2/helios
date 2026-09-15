
        const chatContainer = document.getElementById('chat-container');
        const promptInput = document.getElementById('prompt-input');
        const sendBtn = document.getElementById('send-btn');
        const stopBtn = document.getElementById('stop-btn');
        const sessionsList = document.getElementById('sessions-list');
        const modelIndicator = document.getElementById('model-indicator');
        const modelNameDisplay = document.getElementById('model-name');
        
        let ws = null;
        let currentUser = null;
        let currentSessionId = null;
        let messageHistory = [];
        
        // System Access State
        let systemAccess = {
            locations: [],
            terminal_enabled: false,
            terminal_commands: []
        };
        
        const TIPS = [
            'HELIOS dynamically routes each request to the best model for the task.',
            'System tools run in a sandbox â€” every path and command is validated.',
            'Long-term memory lets HELIOS remember facts across sessions.',
            'You can add custom skills as Markdown files from the Skills Manager.',
            'HELIOS uses isolated tools without unrestricted filesystem access.',
            'The router classifies requests by category, complexity, and required tools.',
            'File reading is restricted to approved directories only.',
            'All system operations are logged in an audit trail.'
        ];

        let tipInterval = null;
        let currentApprovalRequest = null;

        promptInput.addEventListener('input', function() {
            this.style.height = '48px';
            this.style.height = (this.scrollHeight) + 'px';
        });

        // System Access API calls
        async function loadSystemAccess() {
            try {
                const res = await fetch(`/api/users/${currentUser.id}/system-access`);
                if (res.ok) {
                    systemAccess = await res.json();
                    updateSandboxIndicator();
                }
            } catch (e) { console.error('Failed to load system access', e); }
        }

        async function saveSystemAccess() {
            try {
                await fetch(`/api/users/${currentUser.id}/system-access`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(systemAccess)
                });
                updateSandboxIndicator();
            } catch (e) { console.error('Failed to save system access', e); }
        }

                // --- Settings Modal ---
        let currentPersonalityRaw = "";
        
        async function openSettingsModal() {
            document.getElementById('settings-modal').style.display = 'flex';
            
            // Fetch voices
            fetch('/api/settings/voices').then(res => res.json()).then(data => {
                const select = document.getElementById('settings-voice-select');
                select.innerHTML = '';
                data.voices.forEach(voice => {
                    const opt = document.createElement('option');
                    opt.value = voice;
                    opt.textContent = voice;
                    if(voice === data.current) opt.selected = true;
                    select.appendChild(opt);
                });
            });
            
            // Fetch personalities
            fetch('/api/settings/personalities').then(res => res.json()).then(data => {
                const select = document.getElementById('settings-personality-select');
                select.innerHTML = '';
                
                // Add standard ones
                data.personalities.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.prompt;
                    opt.textContent = p.name;
                    select.appendChild(opt);
                });
                
                // Add custom option
                const customOpt = document.createElement('option');
                customOpt.value = 'custom';
                customOpt.textContent = 'Custom...';
                select.appendChild(customOpt);
                
                currentPersonalityRaw = data.current;
                
                // Try to select existing
                let found = false;
                for(let i=0; i<select.options.length; i++) {
                    if(select.options[i].value === data.current) {
                        select.selectedIndex = i;
                        found = true;
                        break;
                    }
                }
                
                if(!found) {
                    select.value = 'custom';
                    document.getElementById('settings-custom-personality').value = data.current;
                }
                
                handlePersonalityChange();
            });
        }
        
        function closeSettingsModal() {
            document.getElementById('settings-modal').style.display = 'none';
        }
        
        function handlePersonalityChange() {
            const select = document.getElementById('settings-personality-select');
            const customContainer = document.getElementById('custom-personality-container');
            
            if (select.value === 'custom') {
                customContainer.style.display = 'block';
                if (!document.getElementById('settings-custom-personality').value) {
                     document.getElementById('settings-custom-personality').value = currentPersonalityRaw;
                }
            } else {
                customContainer.style.display = 'none';
            }
        }
        
        async function saveSettings() {
            const voice = document.getElementById('settings-voice-select').value;
            const persSelect = document.getElementById('settings-personality-select');
            let personality = persSelect.value;
            
            if (personality === 'custom') {
                personality = document.getElementById('settings-custom-personality').value;
            }
            
            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ voice, personality })
                });
                if(res.ok) {
                    closeSettingsModal();
                    // Just show a quick visual confirmation
                    const btn = document.querySelector('#settings-modal .btn-primary');
                    const oldText = btn.textContent;
                    btn.textContent = 'Saved!';
                    setTimeout(() => { btn.textContent = oldText; }, 2000);
                }
            } catch (e) {
                console.error("Failed to save settings", e);
            }
        }
        // -----------------------
        // Privacy Modals & API Calls
        async function openPrivacyModal() {
            document.getElementById('privacy-modal').style.display = 'flex';
            if (!currentUser) return;
            const ml = document.getElementById('memory-list');
            if (ml) {
                ml.innerHTML = '<span style="color:var(--text-muted)">Loading memory...</span>';
                try {
                    const res = await fetch(`/api/users/${currentUser.id}/memory`);
                    const mems = await res.json();
                    if (mems.length === 0) {
                        ml.innerHTML = '<div style="color:var(--text-muted)">No extracted memory found.</div>';
                    } else {
                        ml.innerHTML = mems.map(m => `<div style="margin-bottom:6px; line-height: 1.4;">&bull; ${m.fact} <span style="color:var(--text-muted); margin-left: 8px;">(${new Date(m.created_at).toLocaleDateString()})</span></div>`).join('');
                    }
                } catch (e) {
                    ml.innerHTML = '<span style="color:var(--accent-red)">Error loading memory.</span>';
                }
            }
        }

        function closePrivacyModal() {
            document.getElementById('privacy-modal').style.display = 'none';
        }

        async function confirmDelete(type) {
            let message = "";
            if (type === 'history') message = "Are you sure you want to delete all chat history? This cannot be undone.";
            if (type === 'memory') message = "Are you sure you want to wipe all persistent memory? HELIOS will forget learned facts.";
            if (type === 'data') message = "WARNING: Are you sure you want to NUKE ALL DATA? This will wipe history, memory, permissions, and logs.";
            
            if (confirm(message)) {
                try {
                    const res = await fetch(`/api/users/${currentUser.id}/${type}`, { method: 'DELETE' });
                    if (res.ok) {
                        alert(type.charAt(0).toUpperCase() + type.slice(1) + " deleted successfully.");
                        if (type === 'history' || type === 'data') {
                            loadSessions();
                            messageHistory = [];
                            chatContainer.innerHTML = '<div class="message bot-message">Data cleared. How can I help you today?</div>';
                            currentSessionId = null;
                        }
                    } else {
                        alert("Failed to delete " + type);
                    }
                } catch (e) {
                    console.error('Failed to delete', e);
                    alert("Error deleting " + type);
                }
            }
        }

        // â”€â”€â”€ Self-Modification Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        let selfModInterval = null;

        function toggleSelfModDrawer() {
            const drawer = document.getElementById('selfmod-drawer');
            if (drawer.classList.contains('open')) {
                drawer.classList.remove('open');
                if (selfModInterval) { clearInterval(selfModInterval); selfModInterval = null; }
            } else {
                drawer.classList.add('open');
                loadExperiments();
                if (!selfModInterval) selfModInterval = setInterval(loadExperiments, 10000);
            }
        }

        async function loadExperiments() {
            const container = document.getElementById('selfmod-list');
            try {
                const res = await fetch('/api/experiments');
                const experiments = await res.json();
                if (!experiments.length) {
                    container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 24px;">No experiments yet. HELIOS will create experiments when it identifies improvements.</div>';
                    return;
                }
                
                // Save open states for diff and audit
                const openDiffs = new Set(Array.from(document.querySelectorAll('.diff-container[style*="display: block"]')).map(el => el.id.replace('diff-', '')));
                const openAudits = new Set(Array.from(document.querySelectorAll('.audit-timeline[style*="display: block"]')).map(el => el.id.replace('audit-', '')));

                container.innerHTML = experiments.map(exp => {
                    const statusColors = {
                        'DRAFT': 'var(--text-muted)', 'EXPERIMENTING': 'var(--accent-blue)',
                        'EVALUATING': '#f59e0b', 'READY_FOR_REVIEW': '#a855f7',
                        'APPROVED': 'var(--accent-green)', 'DEPLOYED': '#4ade80',
                        'FAILED': 'var(--accent-red)', 'REJECTED': 'var(--accent-red)',
                        'SECURITY_VIOLATION': '#7f1d1d',
                        'DISCARDED': '#334155', 'ROLLED_BACK': '#eab308',
                        'INCONCLUSIVE': 'var(--text-muted)'
                    };
                    const riskColors = { 'LOW': 'var(--accent-green)', 'MEDIUM': '#f59e0b', 'HIGH': 'var(--accent-red)' };
                    const statusColor = statusColors[exp.status] || 'var(--text-muted)';
                    const riskColor = riskColors[exp.risk_level] || 'var(--text-muted)';
                    
                    let actions = '';
                    if (exp.status === 'READY_FOR_REVIEW') {
                        actions = `
                            <button class="btn btn-primary" style="width:auto;font-size:11px;padding:4px 10px;background:var(--accent-green);" onclick="approveExperiment('${exp.experiment_id}')">Approve</button>
                            <button class="btn btn-danger" style="width:auto;font-size:11px;padding:4px 10px;" onclick="rejectExperiment('${exp.experiment_id}')">Reject</button>
                        `;
                    } else if (exp.status === 'DEPLOYED') {
                        actions = `<button class="btn btn-secondary" style="width:auto;font-size:11px;padding:4px 10px;" onclick="rollbackExperiment('${exp.experiment_id}')">Rollback</button>`;
                    } else if (exp.status === 'DRAFT' || exp.status === 'EXPERIMENTING') {
                        actions = `<button class="btn btn-danger" style="width:auto;font-size:11px;padding:4px 10px;" onclick="discardExperiment('${exp.experiment_id}')">Discard</button>`;
                    }
                    
                    actions = `<button class="btn btn-secondary" style="width:auto;font-size:11px;padding:4px 10px;" onclick="viewDiff('${exp.experiment_id}')">View Diff</button>
                               <button class="btn btn-secondary" style="width:auto;font-size:11px;padding:4px 10px;" onclick="toggleAudit('${exp.experiment_id}')">History</button> ` + actions;
                    
                    const timeAgo = Math.floor((new Date() - new Date(exp.created_at || Date.now())) / 60000);
                    const timeText = timeAgo < 60 ? `${timeAgo} min ago` : `${Math.floor(timeAgo/60)} hrs ago`;
                    
                    let statsHtml = '';
                    if (exp.diff_stats) {
                        statsHtml += `<div style="font-size: 11px; margin-bottom: 8px; color: var(--text-muted);">
                            <strong>Diff:</strong> ${exp.diff_stats.files_changed} files changed 
                            (<span style="color:var(--accent-green)">+${exp.diff_stats.lines_added}</span> / 
                            <span style="color:var(--accent-red)">-${exp.diff_stats.lines_removed}</span>)
                        </div>`;
                    }

                    if (['READY_FOR_REVIEW', 'APPROVED', 'DEPLOYED', 'REJECTED', 'ROLLED_BACK'].includes(exp.status) && exp.evaluation && exp.evaluation.comparisons) {
                        let evalColor = 'var(--text-primary)';
                        if (exp.evaluation.classification === 'IMPROVEMENT') evalColor = 'var(--accent-green)';
                        else if (exp.evaluation.classification === 'REGRESSION') evalColor = '#f59e0b';
                        else if (exp.evaluation.classification === 'CRITICAL_REGRESSION') evalColor = 'var(--accent-red)';
                        else if (exp.evaluation.classification === 'UNSTABLE') evalColor = '#f59e0b';
                        else if (exp.evaluation.classification === 'INCONCLUSIVE') evalColor = '#eab308';
                        else if (exp.evaluation.classification === 'NEUTRAL') evalColor = 'var(--text-muted)';
                        
                        statsHtml += `<div style="margin-bottom: 8px; font-size:11px;">
                            <div style="font-weight: 600; margin-bottom: 4px;">Overall: <span style="color:${evalColor}">${exp.evaluation.classification}</span></div>
                            <table class="eval-table">
                                <tr><th>Metric</th><th>Baseline</th><th>Experiment</th><th>Change</th><th>Result</th></tr>`;
                                
                        for (const [metric, cmp] of Object.entries(exp.evaluation.comparisons)) {
                            const b_mean = cmp.baseline.mean !== null ? cmp.baseline.mean.toFixed(2) : '--';
                            const e_mean = cmp.experiment.mean !== null ? cmp.experiment.mean.toFixed(2) : '--';
                            
                            let changeHtml = '--';
                            if (cmp.change_percent !== null) {
                                const arrow = cmp.change_percent < 0 ? 'â†“' : 'â†‘';
                                changeHtml = `${arrow} ${Math.abs(cmp.change_percent).toFixed(1)}%`;
                            }
                            
                            let resColor = 'var(--text-muted)';
                            if (cmp.result === 'IMPROVEMENT') resColor = 'var(--accent-green)';
                            else if (cmp.result === 'REGRESSION') resColor = '#f59e0b';
                            else if (cmp.result === 'CRITICAL_REGRESSION') resColor = 'var(--accent-red)';
                            else if (cmp.result === 'UNSTABLE') resColor = '#f59e0b';
                            else if (cmp.result === 'INCONCLUSIVE') resColor = '#eab308';
                            else if (cmp.result === 'NEUTRAL') resColor = 'var(--text-muted)';

                            statsHtml += `<tr>
                                <td>${metric}</td>
                                <td>${b_mean}</td>
                                <td>${e_mean}</td>
                                <td>${changeHtml}</td>
                                <td style="color:${resColor}; font-weight:600;">${cmp.result}</td>
                            </tr>`;
                        }
                        statsHtml += `</table></div>`;
                    }
                    
                    const isDiffOpen = openDiffs.has(exp.experiment_id) ? 'display: block;' : 'display: none;';
                    const isAuditOpen = openAudits.has(exp.experiment_id) ? 'display: block;' : 'display: none;';

                    return `
                        <div style="background:var(--bg-card);padding:16px;border-radius:var(--radius-md);border:1px solid var(--border-subtle);">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                                <span style="font-weight:600;font-size:13px;">${exp.experiment_id}</span>
                                <div style="display:flex;gap:6px;align-items:center;">
                                    <span style="font-size:11px;padding:2px 8px;border-radius:99px;background:${riskColor}20;color:${riskColor};">${exp.risk_level}</span>
                                    <span style="font-size:11px;padding:2px 8px;border-radius:99px;background:${statusColor}20;color:${statusColor};font-weight:600;">${exp.status}</span>
                                </div>
                            </div>
                            <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">Created: ${timeText}</div>
                            <div style="font-size:13px;color:var(--text-secondary);margin-bottom:8px;">${exp.objective}</div>
                            ${statsHtml}
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;flex-wrap:wrap;gap:8px;">
                                <span style="font-size:11px;color:var(--text-muted);">${exp.files ? exp.files.length : 0} file(s) modified</span>
                                <div style="display:flex;gap:6px;flex-wrap:wrap;">${actions}</div>
                            </div>
                            <div id="diff-${exp.experiment_id}" class="diff-container" style="${isDiffOpen} margin-top:12px; max-height: 300px; overflow-y: auto; background: var(--bg-input); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); font-family: 'Fira Code', monospace; font-size: 11px; white-space: pre-wrap; line-height: 1.5;"></div>
                            <div id="audit-${exp.experiment_id}" class="audit-timeline" style="${isAuditOpen}">Loading...</div>
                        </div>
                    `;
                }).join('');
                
                // Re-fetch diffs/audits for open ones
                openDiffs.forEach(id => viewDiff(id, true));
                openAudits.forEach(id => toggleAudit(id, true));

            } catch (e) {
                container.innerHTML = '<div style="color:var(--accent-red);text-align:center;padding:24px;">Failed to load experiments.</div>';
            }
        }

        async function viewDiff(experimentId, reload = false) {
            const diffEl = document.getElementById(`diff-${experimentId}`);
            if (!diffEl) return;
            if (!reload && diffEl.style.display === 'block') {
                diffEl.style.display = 'none';
                return;
            }
            diffEl.style.display = 'block';
            diffEl.innerHTML = '<div style="color:var(--text-muted);">Loading diff...</div>';
            try {
                const res = await fetch(`/api/experiments/${experimentId}/diff`);
                const data = await res.json();
                diffEl.innerHTML = (data.diff || 'No diff available.').split('\n').map(line => {
                    if (line.startsWith('+') && !line.startsWith('+++')) return `<span style="color:var(--accent-green);background:rgba(16,185,129,0.1);display:block;">${escapeHtml(line)}</span>`;
                    if (line.startsWith('-') && !line.startsWith('---')) return `<span style="color:var(--accent-red);background:rgba(239,68,68,0.1);display:block;">${escapeHtml(line)}</span>`;
                    if (line.startsWith('@@')) return `<span style="color:var(--accent-blue);display:block;">${escapeHtml(line)}</span>`;
                    if (line.startsWith('---') || line.startsWith('+++')) return `<span style="font-weight:bold;display:block;">${escapeHtml(line)}</span>`;
                    return `<span>${escapeHtml(line)}</span>\n`;
                }).join('');
            } catch (e) { diffEl.innerHTML = '<span style="color:var(--accent-red)">Failed to load diff.</span>'; }
        }

        async function toggleAudit(experimentId, reload = false) {
            const auditEl = document.getElementById(`audit-${experimentId}`);
            if (!auditEl) return;
            if (!reload && auditEl.style.display === 'block') {
                auditEl.style.display = 'none';
                return;
            }
            auditEl.style.display = 'block';
            if (reload && auditEl.innerHTML !== '<div style="color:var(--text-muted);">Loading audit history...</div>') return; // Skip fetch if just polling and it's already there
            auditEl.innerHTML = '<div style="color:var(--text-muted);">Loading audit history...</div>';
            try {
                const res = await fetch(`/api/experiments/${experimentId}/audit`);
                const data = await res.json();
                if (!data.length) {
                    auditEl.innerHTML = '<div style="font-size:11px;color:var(--text-muted);">No history available.</div>';
                    return;
                }
                auditEl.innerHTML = data.map(log => {
                    const timeAgo = Math.floor((new Date() - new Date(log.timestamp)) / 60000);
                    let relTime = timeAgo < 1 ? 'Just now' : (timeAgo < 60 ? `${timeAgo} min ago` : `${Math.floor(timeAgo/60)} hrs ago`);
                    return `
                        <div class="audit-item">
                            <div class="audit-time">${relTime}</div>
                            <div style="display:flex;align-items:center;margin-top:4px;">
                                <span class="audit-badge">${log.actor}</span>
                                <span style="font-size:11px;color:var(--text-primary);">${log.previous_state} â†’ ${log.new_state}</span>
                            </div>
                            <div class="audit-text">${log.reason}</div>
                        </div>
                    `;
                }).join('');
            } catch (e) { auditEl.innerHTML = '<span style="color:var(--accent-red)">Failed to load history.</span>'; }
        }

        function escapeHtml(text) {
            const d = document.createElement('div'); d.textContent = text; return d.innerHTML;
        }

        async function approveExperiment(experimentId) {
            if (!confirm(`Approve and deploy experiment ${experimentId}? This will modify production files.`)) return;
            try {
                const res = await fetch(`/api/experiments/${experimentId}/approve?user_id=${currentUser.id}`, {method: 'POST'});
                if (res.ok) { alert('Experiment approved and deployed!'); loadExperiments(); }
                else { const d = await res.json(); alert('Failed: ' + (d.detail || 'Unknown error')); }
            } catch (e) { alert('Error approving experiment.'); }
        }

        async function rejectExperiment(experimentId) {
            if (!confirm(`Reject experiment ${experimentId}?`)) return;
            try {
                const res = await fetch(`/api/experiments/${experimentId}/reject?user_id=${currentUser.id}`, {method: 'POST'});
                if (res.ok) { alert('Experiment rejected.'); loadExperiments(); }
                else { const d = await res.json(); alert('Failed: ' + (d.detail || 'Unknown error')); }
            } catch (e) { alert('Error rejecting experiment.'); }
        }

        async function rollbackExperiment(experimentId) {
            if (!confirm(`Roll back experiment ${experimentId}? Production files will be restored to pre-deployment state.`)) return;
            try {
                const res = await fetch(`/api/experiments/${experimentId}/rollback?user_id=${currentUser.id}`, {method: 'POST'});
                if (res.ok) { alert('Experiment rolled back successfully.'); loadExperiments(); }
                else { const d = await res.json(); alert('Failed: ' + (d.detail || 'Unknown error')); }
            } catch (e) { alert('Error rolling back experiment.'); }
        }

        async function discardExperiment(experimentId) {
            if (!confirm(`Discard experiment ${experimentId}? This will cancel the experiment.`)) return;
            try {
                const res = await fetch(`/api/experiments/${experimentId}/reject?user_id=${currentUser.id}`, {method: 'POST'});
                if (res.ok) { alert('Experiment discarded.'); loadExperiments(); }
                else { const d = await res.json(); alert('Failed: ' + (d.detail || 'Unknown error')); }
            } catch (e) { alert('Error discarding experiment.'); }
        }



        async function validatePath(path) {
            try {
                const res = await fetch(`/api/users/${currentUser.id}/system-access/validate-path?path=${encodeURIComponent(path)}`);
                return await res.json();
            } catch (e) { return { valid: false }; }
        }

        async function resetPermissions() {
            try {
                const res = await fetch(`/api/users/${currentUser.id}/system-access/reset`, {method: 'POST'});
                if (res.ok) {
                    systemAccess = await res.json();
                    renderSystemAccessModal();
                    updateSandboxIndicator();
                }
            } catch (e) { console.error('Failed to reset permissions', e); }
        }

        function updateSandboxIndicator() {
            const count = systemAccess.locations ? systemAccess.locations.length : 0;
            document.getElementById('sandbox-count').innerText = `${count} location${count === 1 ? '' : 's'}`;
            
            let hasRead = false, hasWrite = false;
            if (systemAccess.locations) {
                systemAccess.locations.forEach(loc => {
                    if (loc.read) hasRead = true;
                    if (loc.write) hasWrite = true;
                });
            }
            
            const term = systemAccess.terminal_enabled;
            document.getElementById('sandbox-perms').innerHTML = `
                Read ${hasRead ? 'âœ“' : 'âœ—'} &nbsp; Write ${hasWrite ? 'âœ“' : 'âœ—'} &nbsp; Terminal ${term ? 'âœ“' : 'âœ—'}
            `;
        }

        function openSystemAccessModal() {
            renderSystemAccessModal();
            document.getElementById('system-access-modal').style.display = 'flex';
        }
        
        function closeSystemAccessModal() {
            document.getElementById('system-access-modal').style.display = 'none';
        }

        function renderSystemAccessModal() {
            const locationsList = document.getElementById('locations-list');
            locationsList.innerHTML = '';
            
            if (systemAccess.locations) {
                systemAccess.locations.forEach((loc, index) => {
                    const parts = loc.path.split(/[/\\]/);
                    const displayName = parts[parts.length - 1] || loc.path;
                    
                    const div = document.createElement('div');
                    div.className = 'location-card';
                    div.innerHTML = `
                        <div class="location-card-header">
                            <div class="location-card-title">ðŸ“ ${displayName}</div>
                        </div>
                        <div class="location-card-path">${loc.path}</div>
                        <div class="location-card-actions">
                            <label class="toggle-wrapper">Read 
                                <label class="toggle-switch"><input type="checkbox" onchange="updateLocationPerm(${index}, 'read', this.checked)" ${loc.read ? 'checked' : ''}><span class="slider"></span></label>
                            </label>
                            <label class="toggle-wrapper">Write 
                                <label class="toggle-switch"><input type="checkbox" onchange="updateLocationPerm(${index}, 'write', this.checked)" ${loc.write ? 'checked' : ''}><span class="slider"></span></label>
                            </label>
                            <label class="toggle-wrapper">Exec 
                                <label class="toggle-switch"><input type="checkbox" onchange="updateLocationPerm(${index}, 'exec', this.checked)" ${loc.exec ? 'checked' : ''}><span class="slider"></span></label>
                            </label>
                            <button class="btn-remove" onclick="removeLocation(${index})">[Remove]</button>
                        </div>
                    `;
                    locationsList.appendChild(div);
                });
            }
            
            document.getElementById('new-location-path').value = '';
            document.getElementById('new-location-perms').style.display = 'none';

            document.getElementById('terminal-enabled-toggle').checked = systemAccess.terminal_enabled;
            toggleTerminal(systemAccess.terminal_enabled, false);
            
            renderCommands();
        }

        function updateLocationPerm(index, type, value) {
            if (systemAccess.locations[index]) {
                systemAccess.locations[index][type] = value;
                saveSystemAccess();
            }
        }

        function removeLocation(index) {
            systemAccess.locations.splice(index, 1);
            saveSystemAccess();
            renderSystemAccessModal();
        }

        async function validateAndAddPath() {
            const path = document.getElementById('new-location-path').value.trim();
            if (!path) return;
            const res = await validatePath(path);
            if (res.valid !== false) { // Assuming backend returns {valid: true} or similar
                document.getElementById('new-location-perms').style.display = 'flex';
            } else {
                alert('Invalid or unapproved path');
            }
        }

        function confirmAddLocation() {
            const path = document.getElementById('new-location-path').value.trim();
            const read = document.getElementById('new-loc-read').checked;
            const write = document.getElementById('new-loc-write').checked;
            const exec = document.getElementById('new-loc-exec').checked;
            
            if (!systemAccess.locations) systemAccess.locations = [];
            systemAccess.locations.push({ path, read, write, exec });
            
            saveSystemAccess();
            renderSystemAccessModal();
        }

        function toggleTerminal(enabled, save = true) {
            systemAccess.terminal_enabled = enabled;
            document.getElementById('terminal-section').style.display = enabled ? 'block' : 'none';
            if (save) saveSystemAccess();
        }

        function renderCommands() {
            const list = document.getElementById('commands-list');
            list.innerHTML = '';
            if (systemAccess.terminal_commands) {
                systemAccess.terminal_commands.forEach((cmd, idx) => {
                    const chip = document.createElement('div');
                    chip.className = 'chip';
                    chip.innerHTML = `${cmd} <span class="chip-remove" onclick="removeCommand(${idx})">Ã—</span>`;
                    list.appendChild(chip);
                });
            }
        }

        function addCommand() {
            const cmd = document.getElementById('new-command-input').value.trim();
            if (!cmd) return;
            if (!systemAccess.terminal_commands) systemAccess.terminal_commands = [];
            if (!systemAccess.terminal_commands.includes(cmd)) {
                systemAccess.terminal_commands.push(cmd);
                saveSystemAccess();
                renderCommands();
            }
            document.getElementById('new-command-input').value = '';
        }

        function removeCommand(idx) {
            systemAccess.terminal_commands.splice(idx, 1);
            saveSystemAccess();
            renderCommands();
        }

        function promptResetPermissions() {
            if (confirm('Are you sure you want to reset all permissions to default?')) {
                resetPermissions();
            }
        }

        // Skills Manager Logic
        const skillsModal = document.getElementById('skills-modal');
        const uploadZone = document.getElementById('upload-zone');
        const fileInput = document.getElementById('file-input');

        function openSkillsModal() { skillsModal.style.display = 'flex'; }
        function closeSkillsModal() { 
            skillsModal.style.display = 'none'; 
            document.getElementById('skill-name').value = '';
            document.getElementById('skill-content').value = '';
        }

        uploadZone.addEventListener('click', () => fileInput.click());
        
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('drag-over');
        });
        uploadZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('drag-over');
        });
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                handleFileUpload(e.dataTransfer.files[0]);
            }
        });
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileUpload(e.target.files[0]);
            }
        });

        async function handleFileUpload(file) {
            if (!file.name.endsWith('.md')) {
                alert('Only .md files are supported!');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            
            const res = await fetch('/api/skills/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.status === 'success') {
                alert(data.message);
                closeSkillsModal();
            } else {
                alert('Upload failed.');
            }
        }

        async function saveSkill() {
            const name = document.getElementById('skill-name').value.trim();
            const content = document.getElementById('skill-content').value.trim();
            if (!name || !content) return alert('Name and Content are required!');

            const res = await fetch('/api/skills', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, content })
            });
            const data = await res.json();
            if (data.status === 'success') {
                alert(data.message);
                closeSkillsModal();
            }
        }

        // Initialize App automatically
        async function initApp() {
            const username = "krithik";
            
            const res = await fetch('/api/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username })
            });
            currentUser = await res.json();
            
            document.getElementById('user-display').innerText = `HELIOS`;
            
            await loadSessions();
            await loadSystemAccess();
        }

        window.addEventListener('DOMContentLoaded', initApp);

        // Sessions Logic
        async function loadSessions() {
            if (!currentUser) return;
            const res = await fetch(`/api/users/${currentUser.id}/sessions`);
            const sessions = await res.json();
            
            sessionsList.innerHTML = '';
            sessions.forEach(s => {
                const div = document.createElement('div');
                div.className = `nav-item ${s.id === currentSessionId ? 'active' : ''}`;
                div.innerText = s.title || `Session ${s.id.substring(0,6)}...`;
                div.onclick = () => selectSession(s.id);
                sessionsList.appendChild(div);
            });

            if (sessions.length > 0 && !currentSessionId) {
                selectSession(sessions[0].id);
            } else if (sessions.length === 0) {
                createNewSession();
            }
        }

        async function createNewSession() {
            if (!currentUser) return;
            const res = await fetch(`/api/users/${currentUser.id}/sessions`, { method: 'POST' });
            const session = await res.json();
            await loadSessions();
            selectSession(session.id);
        }

        async function selectSession(sessionId) {
            currentSessionId = sessionId;
            chatContainer.innerHTML = '';
            messageHistory = [];
            modelIndicator.style.display = 'none';
            
            Array.from(sessionsList.children).forEach(c => c.classList.remove('active'));
            const activeEl = Array.from(sessionsList.children).find(c => c.innerText.includes(sessionId) || c.innerText.includes('Session ' + sessionId.substring(0,6)));
            if (activeEl) activeEl.classList.add('active');

            const res = await fetch(`/api/sessions/${sessionId}/messages`);
            const messages = await res.json();

            if (messages.length === 0) {
                const intro = document.createElement('div');
                intro.className = 'message bot-message';
                intro.innerText = "I am HELIOS. Awaiting instructions.";
                chatContainer.appendChild(intro);
            } else {
                messages.forEach(m => {
                    const msgDiv = document.createElement('div');
                    msgDiv.className = `message ${m.role === 'user' ? 'user-message' : 'bot-message'}`;
                    let html = m.content;
                    if (m.role !== 'user') {
                        html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                        html = html.replace(/\n/g, '<br>');
                        html = html.replace(/&lt;think&gt;/g, '<details class="think-block" open><summary>Reasoning Process</summary><div class="think-content">');
                        html = html.replace(/&lt;\/think&gt;/g, '</div></details>');
                        if (html.includes('<details') && !html.includes('</details>')) {
                            html += '</div></details>';
                        }
                    } else {
                        html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
                    }
                    msgDiv.innerHTML = html;
                    chatContainer.appendChild(msgDiv);
                    messageHistory.push({ role: m.role, content: m.content });
                });
            }
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        // Approval Logic
        function showApprovalDialog(data) {
            currentApprovalRequest = data.request_id;
            document.getElementById('approval-op').innerText = data.operation;
            document.getElementById('approval-target').innerText = data.target;
            document.getElementById('approval-modal').style.display = 'flex';
        }

        function submitApproval(scope) {
            if (!currentApprovalRequest || !ws) return;
            
            const approved = scope !== 'deny';
            ws.send(JSON.stringify({
                type: 'approval_response',
                request_id: currentApprovalRequest,
                approved: approved,
                scope: scope
            }));
            
            document.getElementById('approval-modal').style.display = 'none';
            currentApprovalRequest = null;
        }

        // WebSocket Logic
        let currentBotMessage = null;
        let currentBotContent = null;
        let loadingCardElement = null;
        let firstChunkReceived = false;

        function connectWebSocket() {
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'status') {
                    if (loadingCardElement) {
                        const statusEl = loadingCardElement.querySelector('.loading-status');
                        if (statusEl) statusEl.innerText = data.message || 'Processing...';
                    }
                }

                else if (data.type === 'input_request') {
                    showInputDialog(data);
                }
                else if (data.type === 'approval_request') {
                    showApprovalDialog(data);
                }
                else if (data.type === 'meta') {
                    modelIndicator.style.display = 'flex';
                    modelIndicator.classList.add('active');
                    modelNameDisplay.innerText = data.route.model;
                    
                    const confBadge = document.getElementById('confidence-badge');
                    if (data.route.confidence && data.route.confidence >= 0.6) {
                        confBadge.style.display = 'inline';
                        const confLevel = data.route.confidence >= 0.85 ? "High Conf" : "Mid Conf";
                        confBadge.innerText = confLevel;
                    } else {
                        confBadge.style.display = 'none';
                    }
                    
                    const detailBadge = document.getElementById('detail-badge');
                    if (data.route.detail_level && data.route.detail_level !== 'normal') {
                        detailBadge.style.display = 'inline';
                        detailBadge.innerText = data.route.detail_level.toUpperCase();
                        detailBadge.style.color = data.route.detail_level === 'high' ? 'var(--accent-red)' : 'var(--accent-green)';
                    } else {
                        detailBadge.style.display = 'none';
                    }

                    currentBotMessage = document.createElement('div');
                    currentBotMessage.className = 'message bot-message';
                    
                    const metaDiv = document.createElement('div');
                    metaDiv.className = `router-meta ${data.memory_injected ? 'memory-active' : ''}`;
                    const memStr = data.memory_injected ? '<span style="color:var(--accent-cyan)">[Memory]</span> ' : '';
                    metaDiv.innerHTML = `
                        ${memStr}
                        <div class="meta-item">Route: <span>${data.route.route}</span></div>
                        <div class="meta-item">Context: <span>${data.route.context_size}</span></div>
                        <div class="meta-item" style="flex-basis: 100%; color: var(--text-muted);">Reason: ${data.route.reason}</div>
                    `;
                    currentBotMessage.appendChild(metaDiv);
                    
                    currentBotContent = document.createElement('div');
                    currentBotMessage.appendChild(currentBotContent);
                    
                    chatContainer.appendChild(currentBotMessage);
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                } 
                else if (data.type === 'chunk') {
                    if (loadingCardElement && !firstChunkReceived) {
                        loadingCardElement.classList.add('fade-out');
                        setTimeout(() => {
                            if (loadingCardElement && loadingCardElement.parentNode) {
                                loadingCardElement.parentNode.removeChild(loadingCardElement);
                            }
                            loadingCardElement = null;
                        }, 300);
                        if (tipInterval) {
                            clearInterval(tipInterval);
                            tipInterval = null;
                        }
                        firstChunkReceived = true;
                    }

                    if (currentBotContent) {
                        currentBotContent.dataset.raw = (currentBotContent.dataset.raw || '') + data.content;
                        let html = currentBotContent.dataset.raw;
                        html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                        html = html.replace(/\n/g, '<br>');
                        html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%; border-radius: 8px; margin: 8px 0; border: 1px solid var(--border-light);" />');
                        html = html.replace(/&lt;think&gt;/g, '<details class="think-block" open><summary>Reasoning Process</summary><div class="think-content">');
                        html = html.replace(/&lt;\/think&gt;/g, '</div></details>');
                        
                        // Parse Option Buttons
                        html = html.replace(/&lt;button&gt;(.*?)&lt;\/button&gt;/gi, '<button class="llm-option-btn" onclick="handleOptionClick(\'$1\')">$1</button>');
                        
                        if (html.includes('<details') && !html.includes('</details>')) {
                            html += '</div></details>';
                        }

                        // Extract code blocks and put them in Workspace
                        let codeBlocks = [];
                        html = html.replace(/```(?:[a-zA-Z0-9\-_]+)?(?:<br>)?([\s\S]*?)```/g, (match, code) => {
                            codeBlocks.push(code);
                            return '<div style="padding: 12px; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 8px; font-size: 12px; margin: 8px 0; color: var(--accent-blue); display: flex; align-items: center; gap: 8px;"><svg viewBox="0 0 24 24" style="width: 16px; height: 16px; fill: currentColor;"><path d="M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z"/></svg> Artifact rendered in Workspace</div>';
                        });
                        
                        if (codeBlocks.length > 0) {
                            const wsContent = document.getElementById('workspace-content');
                            wsContent.innerHTML = '';
                            wsContent.style.display = 'block'; // override flex centering
                            codeBlocks.forEach(code => {
                                const pre = document.createElement('pre');
                                pre.style.background = 'var(--bg-card)';
                                pre.style.padding = '16px';
                                pre.style.borderRadius = '8px';
                                pre.style.width = '100%';
                                pre.style.overflowX = 'auto';
                                pre.style.fontFamily = "'Fira Code', monospace";
                                pre.style.fontSize = '13px';
                                pre.style.lineHeight = '1.5';
                                pre.style.border = '1px solid var(--border-subtle)';
                                pre.style.marginBottom = '16px';
                                pre.style.color = 'var(--text-primary)';
                                // Replace <br> back to \n and decode HTML entities since it's inside <pre>
                                let rawCode = code.replace(/<br>/g, '\n').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
                                pre.innerText = rawCode.trim();
                                wsContent.appendChild(pre);
                            });
                        }
                        
                        currentBotContent.innerHTML = html;
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }
                }
                else if (data.type === 'done') {
                    stopBtn.style.display = 'none';
                    enableInput();
                    modelIndicator.classList.remove('active');
                    if (currentBotContent) {
                        messageHistory.push({ role: "assistant", content: currentBotContent.dataset.raw || '' });
                    }
                    if (loadingCardElement && !firstChunkReceived) {
                        loadingCardElement.classList.add('fade-out');
                        setTimeout(() => {
                            if (loadingCardElement && loadingCardElement.parentNode) {
                                loadingCardElement.parentNode.removeChild(loadingCardElement);
                            }
                            loadingCardElement = null;
                        }, 300);
                    }
                }
                else if (data.type === 'error') {
                    if (loadingCardElement && !firstChunkReceived) {
                        loadingCardElement.querySelector('.loading-orb').style.display = 'none';
                        loadingCardElement.querySelector('.loading-status').innerText = 'Error';
                        loadingCardElement.querySelector('.loading-status').style.color = 'var(--accent-red)';
                        loadingCardElement.querySelector('.loading-tip').innerText = data.message || 'An error occurred';
                        setTimeout(() => {
                            if (loadingCardElement) loadingCardElement.classList.add('fade-out');
                            enableInput();
                        }, 3000);
                    }
                }
            };
            
            ws.onclose = () => setTimeout(connectWebSocket, 1000);
        }
        
        function handleOptionClick(optionText) {
            promptInput.value = optionText;
            sendPrompt();
        }
        
        function sendPrompt() {
            const text = promptInput.value.trim();
            if (!text || !ws || ws.readyState !== WebSocket.OPEN || !currentUser || !currentSessionId) return;
            
            const userMsg = document.createElement('div');
            userMsg.className = 'message user-message';
            userMsg.innerText = text;
            chatContainer.appendChild(userMsg);
            
            messageHistory.push({ role: "user", content: text });
            
            // Inject Loading Card
            firstChunkReceived = false;
            loadingCardElement = document.createElement('div');
            loadingCardElement.className = 'loading-card';
            loadingCardElement.id = 'loading-card';
            loadingCardElement.innerHTML = `
                <div class="loading-orb"></div>
                <div class="loading-status">Analyzing your request...</div>
                <div class="loading-tip">
                    <span class="tip-label">Did you know?</span>
                    <span class="tip-text">${TIPS[Math.floor(Math.random() * TIPS.length)]}</span>
                </div>
            `;
            chatContainer.appendChild(loadingCardElement);
            stopBtn.style.display = 'flex';
            chatContainer.scrollTop = chatContainer.scrollHeight;

            if (tipInterval) clearInterval(tipInterval);
            tipInterval = setInterval(() => {
                if (loadingCardElement) {
                    const tipText = loadingCardElement.querySelector('.tip-text');
                    if (tipText) {
                        tipText.style.opacity = 0;
                        setTimeout(() => {
                            tipText.innerText = TIPS[Math.floor(Math.random() * TIPS.length)];
                            tipText.style.opacity = 1;
                        }, 200);
                    }
                }
            }, 4000);
            
            const sendHistory = messageHistory.slice(-10);
            
            modelIndicator.style.display = 'flex';
            modelIndicator.classList.remove('active');
            modelNameDisplay.innerText = "Routing...";

            ws.send(JSON.stringify({
                messages: sendHistory,
                user_id: currentUser.id,
                session_id: currentSessionId,
                agent_mode: true
            }));
            
            promptInput.value = '';
            promptInput.style.height = '48px';
            disableInput();
        }
        
        function disableInput() { promptInput.disabled = true; sendBtn.disabled = true; }
        function enableInput() { promptInput.disabled = false; sendBtn.disabled = false; promptInput.focus(); }
        
        async function updateHealth() {
            try {
                const res = await fetch('/health');
                const data = await res.json();
                const statusEl = document.getElementById('status-ollama');
                
                const isOnline = data.ollama === 'online';
                statusEl.className = 'status-value ' + (isOnline ? 'status-online' : 'status-offline');
                statusEl.innerHTML = `<span class="status-dot"></span> <span class="text">${data.ollama.toUpperCase()}</span>`;
                
                const specsEl = document.getElementById('status-specs');
                if (data.available_ram_mb !== undefined) {
                    specsEl.style.display = 'flex';
                    document.getElementById('ram-val').innerText = `${Math.round(data.available_ram_mb/1024)}GB`;
                    document.getElementById('vram-val').innerText = `${Math.round(data.vram_used_mb)}MB`;
                    if (data.status === 'warning_critical_ram') {
                        document.getElementById('ram-val').style.color = 'var(--accent-red)';
                    } else {
                        document.getElementById('ram-val').style.color = 'var(--text-primary)';
                    }
                }
            } catch (e) {
                console.error('Health check failed', e);
            }
        }
        
        
        stopBtn.addEventListener('click', () => {
            if (ws && ws.readyState === WebSocket.OPEN && currentSessionId) {
                ws.send(JSON.stringify({ type: 'stop', session_id: currentSessionId }));
                stopBtn.style.display = 'none';
                if (loadingCardElement) loadingCardElement.remove();
            }
        });

        sendBtn.addEventListener('click', sendPrompt);
        promptInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendPrompt(); }
        });
        
        connectWebSocket();
        updateHealth();
        setInterval(updateHealth, 5000);
    
