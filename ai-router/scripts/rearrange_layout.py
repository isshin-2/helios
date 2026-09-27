import re

with open('static/app.html', 'r', encoding='utf-8') as f:
    app_html = f.read()

# 1. Extract the tensura-bg block
tensura_bg_match = re.search(r'<div id="tensura-bg"[\s\S]*?</div>\s*</div>\s*</div>', app_html)
if tensura_bg_match:
    tensura_bg_html = tensura_bg_match.group(0)
    # Remove it from #main
    app_html = app_html.replace(tensura_bg_html, '')
    
    # 2. Modify it to be tensura-pane
    # It used to be position: absolute. We need it to be a normal flex item.
    tensura_pane = f"""
    <!-- CENTER PANE: Tensura -->
    <div id="tensura-pane" style="flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; background: var(--bg-primary); position: relative; overflow: hidden;">
        <div style="position: absolute; top: 16px; left: 16px; color: var(--text-muted); font-size: 11px; letter-spacing: 2px; font-weight: 600;">HELIOS AI CORE</div>
        
        {tensura_bg_html.replace('position: absolute;', 'position: relative;').replace('opacity: 0.4;', 'opacity: 1;').replace('scale(0.85)', 'scale(1.0)')}
    </div>
    """
    
    # 3. Insert it between #main and #workspace-pane
    app_html = app_html.replace('<!-- Workspace Pane (OpenHands Style) -->', tensura_pane + '\n    <!-- Workspace Pane (OpenHands Style) -->')

# 4. Modify workspace-pane to be a side panel (flex: 0 0 350px)
app_html = app_html.replace('<div id="workspace-pane" style="flex: 1;', '<div id="workspace-pane" style="flex: 0 0 400px; border-left: 1px solid var(--border-subtle);')

# 5. Fix chat container if it has transparent issues
app_html = app_html.replace('<div id="main" style="flex: 0 0 400px; display: flex; flex-direction: column; position: relative; background: var(--bg-secondary);', '<div id="main" style="flex: 0 0 350px; display: flex; flex-direction: column; position: relative; background: var(--bg-secondary);')

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(app_html)

print("Re-arranged app.html to have Tensura as main center pane!")
