import assert from 'node:assert/strict';
import {readdir,readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {Worker} from 'node:worker_threads';
async function files(dir){
 const entries=await readdir(dir,{withFileTypes:true});
 return (await Promise.all(entries.map(e=>e.isDirectory()?files(`${dir}/${e.name}`):`${dir}/${e.name}`))).flat();
}
// A successful framework build used to omit this asset entirely (production 404).
const directory=(process.argv[2]||'dist/client').replace(/\/$/,'');
const builtFiles=await files(directory);
const workerPath=builtFiles.find(f=>/\/maplibre-gl-worker[-.][\w-]+\.(mjs|js)$/.test(f));
assert.ok(workerPath,'The production build must emit the MapLibre worker');
const workerURL=workerPath.slice(directory.length);
const chunks=await Promise.all(builtFiles.filter(f=>f.endsWith('.js')&&f!==workerPath).map(f=>readFile(f,'utf8')));
assert.ok(chunks.some(code=>code.includes(workerURL)&&code.includes('.setWorkerUrl(')),'The map must configure the emitted worker URL');
const worker=new Worker(new URL('./helpers/map-worker-runtime.mjs',import.meta.url),{workerData:{path:resolve(workerPath)}});
function waitFor(predicate){
 return new Promise((ok,fail)=>{
  const timer=setTimeout(()=>{cleanup();fail(new Error('Map worker response timed out'));},10000);
  const cleanup=()=>{clearTimeout(timer);worker.off('message',message);worker.off('error',error);};
  const message=value=>{if(predicate(value)){cleanup();ok(value);}};
  const error=e=>{cleanup();fail(e);};
  worker.on('message',message);worker.on('error',error);
 });
}
try{
 await waitFor(m=>m.type==='ready');
 const response=waitFor(m=>m.id==='city-data'&&m.type==='<response>');
 worker.postMessage({id:'city-data',type:'LD',origin:'https://worker-test.invalid',sourceMapId:'test-map',data:{type:'geojson',source:'cities',data:{type:'FeatureCollection',features:[{type:'Feature',properties:{name:'Ташкент'},geometry:{type:'Point',coordinates:[69.24,41.3]}}]},geojsonVtOptions:{maxZoom:14}}});
 const result=await response;
 assert.equal(result.error,null,JSON.stringify(result.error));
 assert.deepEqual(result.data,{});
 console.log(`PASS: ${workerURL} is emitted, configured, starts and processes city data`);
}finally{await worker.terminate();}
