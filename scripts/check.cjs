const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const root=path.join(__dirname,'..','extension');
for(const file of fs.readdirSync(root).filter(f=>f.endsWith('.js')))new vm.Script(fs.readFileSync(path.join(root,file),'utf8'),{filename:file});
new vm.Script(fs.readFileSync(path.join(__dirname,'..','gold_workspace','web','app.js'),'utf8'),{filename:'gold_workspace/web/app.js'});
for(const file of fs.readdirSync(root).filter(f=>f.endsWith('.mjs')))require('node:child_process').execFileSync(process.execPath,['--check',path.join(root,file)]);
const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
for(const script of manifest.content_scripts.flatMap(s=>s.js))if(!fs.existsSync(path.join(root,script)))throw new Error(`Missing ${script}`);
console.log('Extension and workspace JavaScript parse; manifest script paths exist.');

const appVersion=JSON.parse(fs.readFileSync(path.join(__dirname,'..','package.json'),'utf8')).version;
const appHtml=fs.readFileSync(path.join(__dirname,'..','gold_workspace','web','app.html'),'utf8');
if(!appHtml.includes(`id="app-version">v${appVersion}</span>`) || !appHtml.includes(`aria-label="Local app version ${appVersion}"`))throw new Error('Update the workspace version plate to match package.json');

for(const file of ['popup.html','library.html'])if(!fs.readFileSync(path.join(root,file),'utf8').includes(`v${manifest.version}</span>`))throw new Error(`Update ${file} version plate to match manifest.json`);
