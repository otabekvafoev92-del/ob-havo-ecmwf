import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require=createRequire(import.meta.resolve('maplibre-gl'));
const {VectorTile}=await import(pathToFileURL(require.resolve('@mapbox/vector-tile')).href);
const {PbfReader}=await import(pathToFileURL(require.resolve('pbf')).href);
function fields(bytes){
 let p=0;const out=[];
 const varint=()=>{let v=0,s=0,b;do{b=bytes[p++];v+=(b&127)*2**s;s+=7;}while(b>=128);return v;};
 while(p<bytes.length){const tag=varint(),field=Math.floor(tag/8),wire=tag%8;let value;
  if(wire===0)value=varint();else if(wire===2){const len=varint();value=bytes.subarray(p,p+len);p+=len;}else if(wire===1){p+=8;continue;}else if(wire===5){p+=4;continue;}else throw new Error('Invalid protobuf field');
  out.push({field,wire,value});
 }return out;
}
function glyphIDs(bytes){const ids=[];for(const stack of fields(bytes).filter(f=>f.field===1&&f.wire===2))for(const glyph of fields(stack.value).filter(f=>f.field===3&&f.wire===2)){const id=fields(glyph.value).find(f=>f.field===1&&f.wire===0)?.value;if(typeof id==='number')ids.push(id);}return new Set(ids);}
const latin=glyphIDs(await readFile('public/fonts/Open Sans Regular/0-255.pbf'));
const cyrillic=glyphIDs(await readFile('public/fonts/Open Sans Regular/1024-1279.pbf'));
for(const ch of 'Tashkent')assert.ok(latin.has(ch.codePointAt(0)));
for(const ch of 'ТашкентЧирчик')assert.ok(cyrillic.has(ch.codePointAt(0)));
console.log(`PASS: local fonts contain Latin and Cyrillic glyphs (${latin.size}, ${cyrillic.size})`);
const z=10,lat=41.3,lon=69.24,x=Math.floor((lon+180)/360*2**z),y=Math.floor((1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2*2**z);
const response=await fetch(`https://tiles-a.basemaps.cartocdn.com/vectortiles/carto.streets/v1/${z}/${x}/${y}.mvt`);
assert.equal(response.status,200);
const tile=new VectorTile(new PbfReader(new Uint8Array(await response.arrayBuffer())));
assert.ok(tile.layers.place?.length>0&&tile.layers.boundary?.length>0&&tile.layers.transportation?.length>0);
const names=Array.from({length:tile.layers.place.length},(_,i)=>tile.layers.place.feature(i).properties['name:ru']);
assert.ok(names.includes('Ташкент'));
console.log(`PASS: real map tile contains Ташкент, roads and ${tile.layers.boundary.length} administrative boundary features`);
