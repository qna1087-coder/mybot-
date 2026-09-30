import base64,re,pathlib
fs='node_modules/@fontsource/ibm-plex-sans-arabic/'
def rng(css,subset):
    m=re.search(r'/\* ibm-plex-sans-arabic-'+subset+r'-\d+-normal \*/.*?unicode-range:\s*([^;]+);',css,re.S);return m.group(1)
css3=open(fs+'300.css').read()
ranges={'arabic':rng(css3,'arabic'),'latin':rng(css3,'latin')}
b=lambda p:base64.b64encode(open(p,'rb').read()).decode()
out=[]
for sub,ws in [('arabic',[300,500,700]),('latin',[200,300,500,700])]:
    for w in ws:
        out.append(f"@font-face{{font-family:'BRSans';font-style:normal;font-weight:{w};font-display:block;src:url(data:font/woff2;base64,{b(fs+f'files/ibm-plex-sans-arabic-{sub}-{w}-normal.woff2')}) format('woff2');unicode-range:{ranges[sub]}}}")
out.append(f"@font-face{{font-family:'BRMono';font-style:normal;font-weight:400;font-display:block;src:url(data:font/woff2;base64,{b('node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2')}) format('woff2')}}")
src=open('film.src.html').read()
src=src.replace('/*@FONTS@*/','\n'.join(out)).replace('@BR@','data:image/png;base64,'+b('br.png')).replace('@PERA@','data:image/png;base64,'+b('pera.png'))
open('br-film.html','w').write(src)
open('br-film.render.html','w').write('<!doctype html><html><head><meta charset="utf-8"></head><body>'+src+'</body></html>')
print(len(src))
