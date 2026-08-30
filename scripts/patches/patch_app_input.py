import re

with open('static/app.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add HTML for input modal
input_modal_html = """
    <!-- Input Modal -->
    <div id="input-modal" class="modal-overlay" style="display: none; z-index: 2000;">
        <div class="modal">
            <h2>HELIOS asks...</h2>
            <p id="input-question" style="font-weight: bold; margin-bottom: 15px;">Question goes here?</p>
            <textarea id="input-answer" class="form-input" style="height: 100px; resize: vertical; margin-bottom: 15px;" placeholder="Your answer..."></textarea>
            <div style="display: flex; gap: 10px;">
                <button class="btn btn-primary" id="input-submit-btn" style="flex: 1;">Submit Answer</button>
                <button class="btn btn-secondary" id="input-cancel-btn" style="flex: 1;">Cancel</button>
            </div>
        </div>
    </div>
"""
html = html.replace('    <!-- Login Modal -->', input_modal_html + '\n    <!-- Login Modal -->')

# 2. Add websocket listener for input_request
ws_handler = """
                else if (data.type === 'input_request') {
                    showInputDialog(data);
                }
"""
html = html.replace("                else if (data.type === 'approval_request') {", ws_handler + "                else if (data.type === 'approval_request') {")

# 3. Add showInputDialog logic
show_input_js = """
        let currentInputRequestId = null;
        function showInputDialog(data) {
            currentInputRequestId = data.request_id;
            document.getElementById('input-question').innerText = data.question;
            document.getElementById('input-answer').value = '';
            document.getElementById('input-modal').style.display = 'flex';
            document.getElementById('input-answer').focus();
        }
        
        document.getElementById('input-submit-btn').addEventListener('click', () => {
            const answer = document.getElementById('input-answer').value.trim();
            if (ws && ws.readyState === WebSocket.OPEN && currentInputRequestId) {
                ws.send(JSON.stringify({
                    type: 'input_response',
                    request_id: currentInputRequestId,
                    text: answer || "User provided no answer."
                }));
            }
            document.getElementById('input-modal').style.display = 'none';
        });

        document.getElementById('input-cancel-btn').addEventListener('click', () => {
            if (ws && ws.readyState === WebSocket.OPEN && currentInputRequestId) {
                ws.send(JSON.stringify({
                    type: 'input_response',
                    request_id: currentInputRequestId,
                    text: "User cancelled."
                }));
            }
            document.getElementById('input-modal').style.display = 'none';
        });
"""
html = html.replace('        let currentApprovalRequestId = null;', show_input_js + '\n        let currentApprovalRequestId = null;')

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated app.html for input modal")
