const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
  const root=path.resolve(__dirname,'..');
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:2,isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const csv=fs.readFileSync(path.join(root,'tests/roads.csv'),'utf8');
  const weather=JSON.parse(fs.readFileSync(path.join(root,'tests/weather.json'),'utf8'));
  await page.addInitScript(({csv,weather})=>{
    window.testMode='valid';window.savedRoads='';window.openedLink='';
    window.AndroidApp={
      roads(request){setTimeout(()=>{
        const body=window.testMode==='invalid'?'<html>Error</html>':window.testMode==='stale'?csv.replace(/14\/11\/2026/g,'03/11/2026'):csv;
        window.receiveNative({type:'roads',request,body,source:'Vialidad Provincial',error:window.testMode==='offline'?'Sin conexión':''});
      },30);},
      weather(request,key,lat,lon){setTimeout(()=>window.receiveNative({type:'weather',request,key,body:window.testMode==='offline'?'':JSON.stringify(weather),error:''}),20);},
      saveRoads(csv){window.savedRoads=csv;},openLink(url){window.openedLink=url;}
    };
  },{csv,weather});
  await page.goto('file:///'+path.join(root,'app/assets/index.html').replace(/\\/g,'/'));
  await page.screenshot({path:path.join(root,'build/pantalla-inicio.png'),fullPage:true});
  assert.equal(await page.locator('#search').isDisabled(),true);
  await page.click('#origin');assert.equal(await page.locator('#choices button').count(),15);
  await page.getByRole('button',{name:'Chos Malal',exact:true}).click();
  await page.click('#destination');assert.equal(await page.locator('#choices button').count(),14);
  await page.getByRole('button',{name:'Zapala',exact:true}).click();
  await page.click('#search');await page.waitForFunction(()=>document.getElementById('status').textContent.includes('finalizada'));
  assert.match(await page.locator('#results').innerText(),/Resumen meteorológico/);
  assert.match(await page.locator('#results').innerText(),/Parte de Vialidad Provincial/);
  assert.equal(await page.locator('#warnings').innerText(),'');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await page.screenshot({path:path.join(root,'build/pantalla-recorrido.png'),fullPage:true});
  await page.locator('summary').first().click();assert.equal(await page.locator('details[open]').count(),1);
  for(const mode of ['stale','invalid','offline']) {
    await page.evaluate(mode=>{window.testMode=mode;},mode);
    await page.click('#refresh');await page.waitForFunction(()=>document.getElementById('status').textContent.includes('finalizada'));
    if(mode!=='offline')assert.match(await page.locator('#warnings').innerText(),/No hay un parte vigente/);
    else assert.match(await page.locator('#results').innerText(),/No se pudo consultar el clima/);
  }
  await page.getByRole('button',{name:'Alertas meteorológicas · SMN'}).click();
  assert.equal(await page.evaluate(()=>window.openedLink),'https://www.smn.gob.ar/alertas');
  assert.deepEqual(errors,[]);
  await browser.close();
  console.log('Interfaz móvil: selectores, búsqueda, datos vigentes/vencidos/inválidos, fallos de clima, pronóstico y enlaces: OK');
})().catch(e=>{console.error(e);process.exit(1);});
