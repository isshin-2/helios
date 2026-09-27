import re

with open('static/app.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace variables
html = html.replace("--bg-primary: #0a0e1a;", "--bg-primary: #050507;")
html = html.replace("--bg-secondary: #111827;", "--bg-secondary: #0D0E12;")
html = html.replace("--bg-card: #1a2236;", "--bg-card: #15171c;")
html = html.replace("--bg-card-hover: #1f2a42;", "--bg-card-hover: #1c1e25;")
html = html.replace("--bg-input: #0f1629;", "--bg-input: #0A0B0E;")
html = html.replace("--border-subtle: #1e2d4a;", "--border-subtle: #2C3038;")
html = html.replace("--border-active: #3b82f6;", "--border-active: #EBF0F5;")

# Strip background image gradient from body
html = re.sub(r'background-image:\s*radial-gradient[^;]+;', '', html, flags=re.DOTALL)

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Updated to black and white color scheme!")
