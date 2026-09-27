import re

with open('static/app.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Make Tensura state accents monochrome
html = html.replace("--accent-amber: #FFCC00;", "--accent-amber: #EBF0F5;")
html = html.replace("--accent-blue: #3296fa;", "--accent-blue: #FFFFFF;")
html = html.replace("--accent-cyan: #00e5ff;", "--accent-cyan: #a1a5ab;")

# Make UI accents monochrome
html = html.replace("--accent-blue: #3b82f6;", "--accent-blue: #FFFFFF;")
html = html.replace("--accent-cyan: #22d3ee;", "--accent-cyan: #EBF0F5;")

# Replace button primary colors which might use --accent-blue directly or have their own blue.
# Let's check for any remaining #3b82f6 or similar in the document just in case.
html = html.replace("#3b82f6", "#FFFFFF")
html = html.replace("#2563eb", "#EBF0F5") # hover state for blue button

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Applied monochrome to accents!")
