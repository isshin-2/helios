import re

with open('static/app.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace("#8b5cf6", "#a1a5ab")
html = html.replace("#1a1c23", "#15171c") # pure grayscale dark 

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("done")
