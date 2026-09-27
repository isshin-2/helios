import re

with open('static/app.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Make glowing effects and backgrounds monochrome (white)
html = html.replace("rgba(0, 229, 255,", "rgba(255, 255, 255,")
html = html.replace("rgba(255, 204, 0,", "rgba(255, 255, 255,")
html = html.replace("rgba(50, 150, 250,", "rgba(255, 255, 255,")
html = html.replace("rgba(50,150,250,", "rgba(255, 255, 255,")
html = html.replace("rgba(139, 92, 246,", "rgba(255, 255, 255,")
html = html.replace("rgba(6, 182, 212,", "rgba(255, 255, 255,")
html = html.replace("rgba(59, 130, 246,", "rgba(255, 255, 255,")
html = html.replace("rgba(16, 185, 129,", "rgba(255, 255, 255,") # also green? The user said match the BW scheme. I'll make it monochrome too.
html = html.replace("rgba(239, 68, 68,", "rgba(255, 255, 255,") # also red? Yes.
html = html.replace("rgba(16,185,129,", "rgba(255, 255, 255,")
html = html.replace("rgba(239,68,68,", "rgba(255, 255, 255,")

# Also the widget border colors which had hex colors:
html = html.replace("border-color: rgba(0, 229, 255, 0.3);", "border-color: rgba(255, 255, 255, 0.3);")
# Already handled by the rgba replacements

# Any stray blue accents in hex?
html = html.replace("#3296fa", "#FFFFFF")
html = html.replace("#00e5ff", "#FFFFFF")
html = html.replace("#FFCC00", "#FFFFFF")

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Applied monochrome rgba values!")
