import os

path = 'templates/public/profile.html'
html = open(path, encoding='utf-8').read()

html = html.replace(
    '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>', 
    '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>'
)

btn_html = '''    <div style="text-align:center; margin-top:1rem;">
        <button id="btnExport" class="btn btn-primary" style="width:100%; font-size:0.9rem; padding: 0.8rem;">📸 DESCARGAR CREDENCIAL</button>
    </div>'''
html = html.replace('</aside>', btn_html + '\n    </aside>')

js_logic = '''
    document.getElementById('btnExport').addEventListener('click', function() {
        const cred = document.querySelector('.digital-credential');
        html2canvas(cred, { scale: 3, backgroundColor: "#000" }).then(canvas => {
            const link = document.createElement('a');
            link.download = 'Credencial_{{ player.slug }}.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        });
    });
'''
html = html.replace('</script>\n{% endblock %}', js_logic + '</script>\n{% endblock %}')

open(path, 'w', encoding='utf-8').write(html)
print('Updated profile.html successfully.')
