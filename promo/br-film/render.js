const {chromium}=require('/opt/node22/lib/node_modules/playwright');const fs=require('fs');const {spawn}=require('child_process');
const mode=process.argv[2]||'4k';const out=process.argv[3]||'BR_The_Return_4K.mp4';
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1920,height:1080}});
await p.goto('file://'+process.cwd()+'/br-film.render.html#render'+(mode==='4k'?'4k':''));
await p.waitForFunction(()=>window.__film&&window.__film.ready,null,{timeout:60000});
const {DUR,FPS,caps}=await p.evaluate(()=>({DUR:__film.DUR,FPS:__film.FPS,caps:__film.caps}));
const ts=s=>{const ms=Math.round(s*1000);const h=String(Math.floor(ms/3600000)).padStart(2,'0'),m=String(Math.floor(ms/60000)%60).padStart(2,'0'),sec=String(Math.floor(ms/1000)%60).padStart(2,'0'),r=String(ms%1000).padStart(3,'0');return`${h}:${m}:${sec},${r}`};
fs.writeFileSync('BR_voiceover.srt',caps.map((c,i)=>`${i+1}\n${ts(c[0])} --> ${ts(c[1])}\n${c[2]}\n`).join('\n'));
console.log('rendering score…');fs.writeFileSync('score.wav',Buffer.from(await p.evaluate(()=>__film.wav()),'base64'));
const ff=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-framerate',String(FPS),'-c:v','mjpeg','-i','-','-i','score.wav','-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-tune','film','-c:a','aac','-b:a','256k','-shortest','-movflags','+faststart',out],{stdio:['pipe','inherit','inherit']});
const n=Math.round(DUR*FPS);const t0=Date.now();
for(let i=0;i<n;i++){const d=await p.evaluate(t=>__film.shot(t,.95),i/FPS);if(!ff.stdin.write(Buffer.from(d,'base64')))await new Promise(r=>ff.stdin.once('drain',r));if(i%240===0)console.log(`frame ${i}/${n} ${((Date.now()-t0)/1000).toFixed(0)}s`)}
ff.stdin.end();await new Promise(r=>ff.on('close',r));await b.close();console.log('done',out,((Date.now()-t0)/1000).toFixed(0)+'s')})();
