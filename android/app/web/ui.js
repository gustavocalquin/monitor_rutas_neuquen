'use strict';
const C=window.RouteCore, points=window.POINTS;
const $=id=>document.getElementById(id);
const title=text=>String(text).toLocaleLowerCase('es').replace(/(^|\s|-)(\p{L})/gu,(_,a,b)=>a+b.toLocaleUpperCase('es'));
const esc=text=>String(text??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const num=(value,dec=0)=>value!==null && value!==undefined && Number.isFinite(Number(value))?Number(value).toFixed(dec):'s/d';
const state={origin:null,destination:null,request:0,routes:[],roads:[],weather:{},errors:[],pending:0,roadPending:false,busy:false,source:'',date:'',selected:null};
const towns=points.filter(p=>p.tipo==='LOCALIDAD').sort((a,b)=>a.nombre.localeCompare(b.nombre,'es'));
function enable() { $('search').disabled=state.busy || !state.origin || !state.destination; $('refresh').disabled=state.busy; $('origin').disabled=state.busy;$('destination').disabled=state.busy; }
function select(which) {
  if(state.busy) return;
  state.selected=which;
  $('picker-title').textContent=which==='origin'?'¿Desde dónde salís?':'¿Hasta dónde viajás?';
  $('choices').replaceChildren();
  for(const point of towns) {
    if(point.nombre===state[which==='origin'?'destination':'origin']) continue;
    const button=document.createElement('button');button.className='choice'+(state[which]===point.nombre?' selected':'');button.textContent=title(point.nombre);
    button.onclick=()=>{state[which]=point.nombre;$(which).querySelector('b').textContent=title(point.nombre);closePicker();enable();};
    $('choices').append(button);
  }
  $('picker').hidden=false;document.body.style.overflow='hidden';$('close-picker').focus();
}
window.closePicker=function(){if($('picker').hidden)return false;$('picker').hidden=true;document.body.style.overflow='';if(state.selected)$(state.selected).focus();return true;};
$('origin').onclick=()=>select('origin');$('destination').onclick=()=>select('destination');$('close-picker').onclick=closePicker;
$('picker').onclick=event=>{if(event.target===$('picker'))closePicker();};
document.addEventListener('keydown',event=>{
  if($('picker').hidden)return;
  if(event.key==='Escape')closePicker();
  if(event.key==='Tab'){
    const buttons=[...$('picker').querySelectorAll('button')];const first=buttons[0],last=buttons.at(-1);
    if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
  }
});
const links=[['Parte diario · Vialidad Provincial','https://w2.dpvneuquen.gov.ar/ParteDiario.pdf'],['Vialidad Provincial del Neuquén','https://www.dpvneuquen.gov.ar/'],['Estado de rutas · Vialidad Nacional','https://www.argentina.gob.ar/transporte/vialidad-nacional/estado-de-rutas'],['Alertas meteorológicas · SMN','https://www.smn.gob.ar/alertas'],['Información de rutas · WhatsApp','https://whatsapp.com/channel/0029Vakr9GiIyPtaTYFeIe2J']];
for(const [label,url] of links){const b=document.createElement('button');b.className='link';b.innerHTML=esc(label)+' <span aria-hidden="true">↗</span>';b.onclick=()=>window.AndroidApp?.openLink(url);$('links').append(b);}
function progress() {
  state.busy=state.pending>0 || state.roadPending;
  $('status').innerHTML=state.busy?'<span class="spinner"></span>'+esc(state.roadPending?'Consultando clima y estado de rutas…':`Consultando clima: faltan ${state.pending} puntos…`):'Consulta finalizada · '+new Date().toLocaleString('es-AR',{timeZone:'America/Argentina/Buenos_Aires',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  enable();
}
function search() {
  if(state.busy || !state.origin || !state.destination)return;
  state.request++;state.roads=[];state.weather={};state.errors=[];state.source='';state.date='';
  try{state.routes=C.routes(points,state.origin,state.destination);}catch(error){state.errors.push(error.message);state.routes=[];}
  if(!state.routes.length){$('results').textContent='No se encontró un recorrido entre esas localidades.';return;}
  const unique=[...new Map(state.routes.flat().map(p=>[p.codigo,p])).values()];
  state.pending=unique.length;state.roadPending=true;state.busy=true;enable();$('refresh').hidden=false;
  render();progress();
  if(!window.AndroidApp){state.errors.push('Esta vista necesita la aplicación Android para consultar datos.');state.pending=0;state.roadPending=false;progress();render();return;}
  window.AndroidApp.roads(state.request);
  for(const p of unique)window.AndroidApp.weather(state.request,p.codigo,p.lat,p.lon);
}
$('search').onclick=search;$('refresh').onclick=search;
window.receiveNative=function(message) {
  if(message.request!==state.request)return;
  if(message.type==='roads') {
    state.roadPending=false;state.source=message.source;
    if(message.error)state.errors.push(message.error);
    try {
      const all=C.parseRoads(message.body);state.roads=C.fresh(all);
      const last=all.reduce((a,b)=>a.timestamp>b.timestamp?a:b);state.date=last.fecha+' '+last.hora;
      if(all.length!==state.roads.length)state.errors.push(`Se omitieron ${all.length-state.roads.length} tramos con fecha fuera de vigencia. Última fecha del archivo: ${state.date}. Sólo se usan registros de las últimas 48 horas, sin fechas futuras.`);
      if(state.roads.length)window.AndroidApp.saveRoads(message.body);
    } catch(error){state.errors.push('No se pudo leer un parte válido de Vialidad.');}
    if(!state.roads.length)state.errors.push('No hay un parte vigente disponible. El clima se consulta por separado.');
  } else if(message.type==='weather') {
    state.pending=Math.max(0,state.pending-1);
    try {
      const data=JSON.parse(message.body);
      if(!data.current || data.error)throw Error();
      state.weather[message.key]=data;
    }catch(error){state.weather[message.key]=null;}
  }
  progress();render();
};
function forecast(data) {
  const hourly=data.hourly;if(!hourly?.time)return '';
  const first=hourly.time.findIndex(t=>Date.parse(t+'-03:00')>Date.now());if(first<0)return '';
  return [1,2,3,6].map(offset=>{
    const i=first+offset-1;if(i>=hourly.time.length)return '';
    const vis=hourly.visibility?.[i];
    return `<div class="forecast"><b>+${offset} h · ${esc(hourly.time[i].slice(11,16))}</b><br>${num(hourly.temperature_2m?.[i],1)} °C · ${esc(C.weatherText(hourly.weather_code?.[i]))}<br><span class="muted">Precip. ${num(hourly.precipitation?.[i],1)} mm · Nieve ${num(hourly.snowfall?.[i],1)} cm<br>Ráfagas ${num(hourly.wind_gusts_10m?.[i])} km/h · Visibilidad ${vis==null?'s/d':num(vis/1000,1)+' km'}</span></div>`;
  }).join('');
}
function render() {
  $('warnings').innerHTML=state.errors.map(error=>'<div class="notice">'+esc(error)+'</div>').join('');
  let html='';
  for(let n=0;n<state.routes.length;n++) {
    const route=state.routes[n], states=C.states(state.roads,route);
    if(state.routes.length>1)html+=`<h2>Alternativa ${n+1}</h2>`;
    const roadnames=[...new Set(route.map(p=>p.ruta).filter(Boolean))].join(' · ');
    html+=`<div class="route-head"><b>${esc(title(route[0].nombre))} → ${esc(title(route.at(-1).nombre))}</b><p>${route.length} puntos monitoreados · ${esc(roadnames)}</p></div><h3>Tu recorrido</h3><p class="legend">🟢 Transitable · 🟡 Precaución · 🟠 Restricción<br>🔴 Intransitable · ⚪ Sin asociación segura</p><ul class="timeline">`;
    for(let i=0;i<route.length;i++) {
      const s=states[i],p=route[i];
      html+=`<li><span class="dot l${s.level}"></span><strong>${esc(title(p.nombre))}</strong><small>${esc(p.ruta)} · ${esc(C.labels[s.level])}</small>${s.inherited?`<small>Estimado por cercanía a ${esc(title(s.from))}</small>`:''}</li>`;
    }
    html+='</ul>';
    const valid=route.filter(p=>state.weather[p.codigo]?.current?.temperature_2m!=null);
    if(valid.length) {
      const cold=valid.reduce((a,b)=>state.weather[a.codigo].current.temperature_2m<state.weather[b.codigo].current.temperature_2m?a:b);
      const windy=route.filter(p=>state.weather[p.codigo]?.current?.wind_gusts_10m!=null).sort((a,b)=>state.weather[b.codigo].current.wind_gusts_10m-state.weather[a.codigo].current.wind_gusts_10m)[0];
      html+=`<h3>Resumen meteorológico</h3><div class="card"><div class="temperature">${num(state.weather[cold.codigo].current.temperature_2m)}°</div><p>Mínimo actual en <b>${esc(title(cold.nombre))}</b></p>${windy?`<p class="muted">Ráfagas máximas: ${num(state.weather[windy.codigo].current.wind_gusts_10m)} km/h en ${esc(title(windy.nombre))}</p>`:''}</div>`;
    }
    html+='<h3>Clima en cada punto</h3>';
    for(const p of route) {
      const data=state.weather[p.codigo];
      if(!data){html+=`<div class="card"><b>${esc(title(p.nombre))}</b><p class="muted">${Object.prototype.hasOwnProperty.call(state.weather,p.codigo)?'No se pudo consultar el clima. Podés reintentar con Actualizar datos.':'Consultando…'}</p></div>`;continue;}
      const c=data.current,short=forecast(data);
      html+=`<div class="card"><div class="weather-top"><div><strong>${esc(title(p.nombre))}</strong><p class="muted">${esc(p.ruta)}${p.tipo==='PUNTO DE INTERES'?' · Punto de interés':''}</p></div><div class="temperature">${num(c.temperature_2m,1)}°</div></div><p>${C.weatherIcon(c.weather_code)} ${esc(C.weatherText(c.weather_code))}</p><p class="muted">Viento ${num(c.wind_speed_10m)} km/h · Ráfagas ${num(c.wind_gusts_10m)} km/h</p>${c.time?`<p class="muted">Dato: ${esc(c.time.replace('T',' '))} · hora argentina</p>`:''}${short?`<details data-point="${esc(n+'-'+p.codigo)}"><summary>Próximas horas</summary>${short}</details>`:''}</div>`;
    }
    html+='<h3>Parte de Vialidad Provincial</h3>';
    const relevant=state.roads.filter(row=>C.mentions(row,route).length>=2).sort((a,b)=>C.level(b)-C.level(a));
    if(!relevant.length)html+='<p class="muted">No hay registros vigentes que puedan asociarse con seguridad a este recorrido.</p>';
    for(const row of relevant)html+=`<div class="card official"><strong>${esc(row.tramo)}</strong><p>${esc(C.labels[C.level(row)])}</p>${row.restriccion?'<p>Restricción: '+esc(row.restriccion)+'</p>':''}${row.observaciones?'<p>'+esc(row.observaciones)+'</p>':''}<small>${row.ruta_provincial==='1'?'RP':'RN'} ${esc(row.ruta)} · ${esc(row.fecha)} ${esc(row.hora)}</small></div>`;
    if(relevant.length)html+='<p class="legend">Fuente de descarga: '+esc(state.source)+'</p>';
  }
  const opened=new Set([...$('results').querySelectorAll('details[open]')].map(el=>el.dataset.point));
  $('results').innerHTML=html;
  for(const el of $('results').querySelectorAll('details'))if(opened.has(el.dataset.point))el.open=true;
}
