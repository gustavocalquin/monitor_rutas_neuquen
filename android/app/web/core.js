(function(root) {
  'use strict';
  const norm = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().trim().replace(/\s+/g, ' ');
  function routes(points, origin, destination) {
    const byCode = Object.fromEntries(points.map(p => [p.codigo,p]));
    const graph = {};
    for (const point of points) for (const raw of point.corredores) {
      const codes = raw.split('-').map(norm).filter(Boolean);
      if (codes.some(code => !byCode[code])) throw Error('La base contiene un corredor inválido.');
      for (let i=1;i<codes.length;i++) {
        (graph[codes[i-1]] ||= new Set()).add(codes[i]);
        (graph[codes[i]] ||= new Set()).add(codes[i-1]);
      }
    }
    const start = points.find(p=>p.nombre===origin)?.codigo;
    const end = points.find(p=>p.nombre===destination)?.codigo;
    if (!start || !end || start === end) return [];
    const paths=[];
    function walk(code,path) {
      if (paths.length>=80 || path.length>points.length+1) return;
      if(code===end) { paths.push(path); return; }
      for(const next of [...(graph[code]||[])].sort()) if(!path.includes(next)) walk(next,[...path,next]);
    }
    walk(start,[start]);
    if(!paths.length) return [];
    const min=Math.min(...paths.map(p=>p.length));
    return paths.filter(p=>p.length<=min+4).sort((a,b)=>a.length-b.length || a.join('|').localeCompare(b.join('|'))).slice(0,6).map(path=>path.map(c=>byCode[c]));
  }

  function csvRows(text) {
    text=text.replace(/^\uFEFF/,'').trim();
    const first=text.split(/\r?\n/)[0] || '';
    const separator=[',',';','\t','|'].sort((a,b)=>first.split(b).length-first.split(a).length)[0];
    const rows=[]; let row=[], field='', quoted=false, ended=false;
    for(let i=0;i<text.length;i++) {
      const ch=text[i];
      if(quoted) {
        if(ch==='"') { if(text[i+1]==='"') {field+='"';i++;} else {quoted=false;ended=true;} }
        else field+=ch;
      } else if(ch==='"') {
        if(field || ended) throw Error('El CSV contiene comillas inválidas.');
        quoted=true;
      } else if(ch===separator) {row.push(field);field='';ended=false;}
      else if(ch==='\n' || ch==='\r') {
        if(ch==='\r' && text[i+1]==='\n') i++;
        row.push(field);if(row.some(v=>v.trim())) rows.push(row);
        row=[];field='';ended=false;
      } else {
        if(ended && ch.trim()) throw Error('El CSV contiene una fila inválida.');
        field+=ch;
      }
    }
    if(quoted) throw Error('El CSV está incompleto.');
    row.push(field);if(row.some(v=>v.trim())) rows.push(row);
    return rows;
  }
  function dateOf(row) {
    const match=/^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})$/.exec(row.fecha+' '+row.hora);
    if(!match) throw Error('El parte contiene una fecha inválida.');
    const [,d,m,y,h,min]=match.map(Number);
    const local=new Date(Date.UTC(y,m-1,d,h,min));
    if(local.getUTCFullYear()!==y || local.getUTCMonth()!==m-1 || local.getUTCDate()!==d || h>23 || min>59) throw Error('Fecha fuera de rango.');
    return local.getTime()+3*3600000;
  }
  function parseRoads(text) {
    const rows=csvRows(text);
    const fields={CodigoTramo:'codigo_tramo',RutaNumero:'ruta',RutaProvincial:'ruta_provincial',RutaTramo:'tramo',RutaTipo:'superficie',RutaLongitud:'longitud',RutaEstado:'estado_codigo',RutaSeccion:'restriccion',RutaObservacion:'observaciones',Fecha:'fecha',Hora:'hora'};
    const header=(rows.shift()||[]).map(s=>s.trim());
    if(new Set(header).size!==header.length || Object.keys(fields).some(k=>!header.includes(k))) throw Error('La fuente no devolvió el formato esperado del parte.');
    if(!rows.length) throw Error('El parte no contiene tramos.');
    return rows.map(values=>{
      if(values.length!==header.length) throw Error('El parte contiene filas incompletas.');
      const row={};for(const [k,v] of Object.entries(fields)) row[v]=values[header.indexOf(k)].trim();
      if(!/^\d+$/.test(row.codigo_tramo) || !/^\d+$/.test(row.ruta) || !['0','1'].includes(row.ruta_provincial) || !row.tramo || !row.estado_codigo) throw Error('El parte contiene un tramo inválido.');
      row.timestamp=dateOf(row);return row;
    });
  }
  function fresh(rows,now=Date.now()) {return rows.filter(row=>now-row.timestamp>=0 && now-row.timestamp<=48*3600000);}
  function level(row) {
    const code=norm(row.estado_codigo);
    if(['I','INT'].includes(code)) return 4;
    if(code==='TCP') return /CADENA|HIELO|NIEVE|HORARIO|NOCTURNO|RESTRICCION|PORTACION|OBLIGATORI[OA]|CALZADA RESBALADIZA/.test(norm(row.restriccion+' '+row.observaciones))?3:2;
    return code==='T'?1:0;
  }
  const labels=['Sin asociación segura','Transitable','Transitable con precaución','Precaución / restricción importante','Intransitable'];
  function mentions(row,route) {const text=norm(row.tramo);return route.map((p,i)=>text.includes(p.nombre)?i:-1).filter(i=>i>=0);}
  function states(rows,route) {
    const result=route.map(()=>({level:0,rows:[],inherited:false}));
    for(const row of rows) {
      const indices=mentions(row,route);if(indices.length<2) continue;
      for(let i=Math.min(...indices);i<=Math.max(...indices);i++) {result[i].rows.push(row);result[i].level=Math.max(result[i].level,level(row));}
    }
    const valid=result.map((r,i)=>r.level?i:-1).filter(i=>i>=0);
    for(let i=0;i<result.length;i++) if(!result[i].level && valid.length) {
      const nearest=[...valid].sort((a,b)=>Math.abs(i-a)-Math.abs(i-b) || result[b].level-result[a].level)[0];
      result[i]={...result[nearest],inherited:true,from:route[nearest].nombre};
    }
    return result;
  }
  function weatherText(code) {
    return ({0:'Despejado',1:'Mayormente despejado',2:'Parcialmente nublado',3:'Cubierto',45:'Niebla',48:'Niebla con escarcha',51:'Llovizna leve',53:'Llovizna',55:'Llovizna intensa',56:'Llovizna helada',57:'Llovizna helada intensa',61:'Lluvia leve',63:'Lluvia',65:'Lluvia intensa',66:'Lluvia helada',67:'Lluvia helada intensa',71:'Nevada leve',73:'Nevada',75:'Nevada intensa',77:'Granos de nieve',80:'Chaparrones leves',81:'Chaparrones',82:'Chaparrones intensos',85:'Chaparrones de nieve',86:'Nieve intensa',95:'Tormenta',96:'Tormenta con granizo',99:'Tormenta con granizo intenso'})[code]||'Sin dato';
  }
  function weatherIcon(code) {return code===0?'☀️':[1,2].includes(code)?'🌤️':code===3?'☁️':[45,48].includes(code)?'🌫️':[71,73,75,77,85,86].includes(code)?'🌨️':code>=95?'⛈️':[56,57,66,67].includes(code)?'🧊':'🌧️';}
  const api={norm,routes,csvRows,parseRoads,dateOf,fresh,level,states,mentions,labels,weatherText,weatherIcon};
  if(typeof module!=='undefined') module.exports=api; else root.RouteCore=api;
})(typeof window==='undefined'?globalThis:window);
