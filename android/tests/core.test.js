const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const C=require('../app/web/core.js');
const points=JSON.parse(fs.readFileSync(path.join(__dirname,'../app/web/points.json'),'utf8'));
const expected=JSON.parse(fs.readFileSync(path.join(__dirname,'expected-routes.json'),'utf8'));
for(const row of expected) {
  const actual=C.routes(points,row.origin,row.destination).map(r=>r.map(p=>p.codigo));
  assert.deepEqual(actual,row.routes,`${row.origin} -> ${row.destination}`);
}
console.log(`${expected.length} pares de localidades: mismos recorridos y orden que Python`);
const csv=fs.readFileSync(path.join(__dirname,'roads.csv'),'utf8');
const roads=C.parseRoads(csv);
assert.equal(roads.length,106);
assert.equal(roads[0].ruta,'1');
const now=Date.parse('2026-11-14T22:00:00-03:00');
assert.equal(C.fresh(roads,now).length,106);
assert.equal(C.fresh(roads,now+72*3600000).length,0);
assert.equal(C.fresh(roads,now-24*3600000).length,0);
const cells=C.csvRows(csv);
const quoted=cell=>'"'+cell.replace(/"/g,'""')+'"';
for(const delimiter of [',',';','\t','|']) {
  const reverse=cells.map(row=>[...row].reverse().map(quoted).join(delimiter)).join('\n');
  assert.deepEqual(C.parseRoads(reverse),roads);
}
for(const invalid of ['', '<html>'+('error,'.repeat(1000))+'</html>',csv.replace('RutaNumero','OtraColumna'),csv.replace(/14\/11\/2026/g,'31/02/2026'),csv.slice(0,-4)])assert.throws(()=>C.parseRoads(invalid));
const raw=(tramo,estado_codigo='TCP')=>({tramo,estado_codigo,restriccion:'',observaciones:''});
const route=[{codigo:'A',nombre:'CHOS MALAL'},{codigo:'B',nombre:'LAS LAJAS'},{codigo:'C',nombre:'ZAPALA'}];
const states=C.states([raw('Chos Malal - Barrancas','I'),raw('Las Lajas - Zapala','T')],route);
assert.deepEqual(states.map(s=>s.level),[1,1,1]);assert.equal(states[0].inherited,true);
assert.deepEqual(C.states([raw('Chos Malal - Barrancas','I')],route).map(s=>s.level),[0,0,0]);
assert.equal(C.level({...raw('A - B'),observaciones:'Portación obligatoria de cadenas'}),3);
assert.equal(C.level(raw('A - B','I')),4);
assert.equal(C.level(raw('A - B','DESCONOCIDO')),0);
assert.deepEqual(C.routes(points,'NO EXISTE','ZAPALA'),[]);
console.log('CSV, delimitadores, columnas, vigencia, fechas inválidas y asociación de estados: OK');
