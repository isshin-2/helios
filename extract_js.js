const fs = require('fs');
const html = fs.readFileSync('static/app.html', 'utf8');
const scriptRegex = /<script>([\s\S]*?)<\/script>/g;
let match;
let scripts = '';
while ((match = scriptRegex.exec(html)) !== null) {
    scripts += match[1] + '\n';
}
fs.writeFileSync('test_extracted.js', scripts);
console.log('Extracted scripts');
