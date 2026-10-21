import test from 'node:test';
import assert from 'node:assert/strict';
import {coordinates,loadForecast,localDate,selectRows,stats,dailyRows,comparison,makeCSV,type Row} from '../lib/weather.ts';
const row=(iso:string,temp:number|null=10,rain:number|null=0):Row=>({time:Date.parse(iso),temperature_2m:temp,precipitation:rain,cloud_cover:50,wind_speed_10m:3,wind_gusts_10m:5,wind_direction_10m:90});

test('Coordinates accept the equator and reject missing, empty, out of range or nonfinite inputs',()=>{
 assert.deepEqual(coordinates(new URLSearchParams('lat=0&lon=0')),{lat:0,lon:0});
 for(const q of ['lat=&lon=1','lat=91&lon=2','lat=41&lon=-181','lat=NaN&lon=1','lat=Infinity&lon=0','lon=1'])assert.throws(()=>coordinates(new URLSearchParams(q)));
});
test('Local-day filters include both boundary days in Tashkent',()=>{
 const r=[row('2026-10-18T18:00:00Z'),row('2026-10-18T19:00:00Z'),row('2026-10-19T18:00:00Z'),row('2026-10-19T19:00:00Z')];
 assert.equal(localDate(r[1].time,'Asia/Tashkent'),'2026-10-19');
 assert.deepEqual(selectRows(r,'2026-10-19','2026-10-19','Asia/Tashkent'),r.slice(1,3));
});
test('Daylight saving boundaries use IANA zones rather than a fixed offset',()=>{
 assert.equal(localDate(Date.parse('2026-10-25T22:30:00Z'),'Europe/Berlin'),'2026-10-25');
 assert.equal(localDate(Date.parse('2026-10-24T22:30:00Z'),'Europe/Berlin'),'2026-10-25');
});
test('Precipitation is summed, temperature is averaged and nulls are not converted to zero',()=>{
 const r=[row('2026-10-19T00:00Z',-2,.7),row('2026-10-19T01:00Z',4,1.3),row('2026-10-19T02:00Z',null,null)];
 assert.equal(stats(r,'temperature_2m').mean,1);
 assert.equal(stats(r,'precipitation').sum,2);
 assert.equal(stats(r,'precipitation').count,2);
 assert.equal(stats([r[2]],'temperature_2m').mean,null);
 assert.equal(stats([],'precipitation').sum,null);
});
test('Daily extremes and rainfall respect the main point timezone',()=>{
 const r=[row('2026-10-18T19:00Z',3,.5),row('2026-10-19T18:00Z',12,2),row('2026-10-19T19:00Z',5,1)];
 const days=dailyRows(r,'Asia/Tashkent');
 assert.equal(days.length,2);assert.equal(days[0].temperature.min,3);assert.equal(days[0].temperature.max,12);assert.equal(days[0].rain.sum,2.5);
});
test('Different cities compare at the exact UTC timestamp, with gaps preserved',()=>{
 const a=[row('2026-10-19T00:00Z',10),row('2026-10-19T01:00Z',20)];
 const b=[row('2026-10-19T01:00Z',8),row('2026-10-19T02:00Z',9)];
 const c=comparison(a,b,'temperature_2m');assert.equal(c[0].secondary,null);assert.equal(c[1].secondary,8);
});
test('CSV carries UTC timestamps, all fields and aligned comparison columns',()=>{
 const csv=makeCSV([row('2026-10-19T01:00Z',12,0.5)],[row('2026-10-19T01:00Z',8,0)],'Asia/Tashkent');
 assert.ok(csv.startsWith('\uFEFF'));assert.ok(csv.includes('2026-10-19T01:00:00.000Z'));assert.ok(csv.includes('2026-10-19 06:00'));assert.ok(csv.includes('"0.5"'));assert.equal(csv.split('\r\n')[0].split(';').length,14);
});
test('Forecast loader pins the ECMWF model and m/s units and preserves missing values',async()=>{
 let url='';
 const fetcher=(async(u:RequestInfo|URL)=>{url=String(u);return Response.json({latitude:41.25,longitude:69.25,timezone:'Asia/Tashkent',elevation:430,hourly:{time:[1792371600,1792375200],temperature_2m:[10,null],precipitation:[0,1],wind_speed_10m:[3,4]}});}) as typeof fetch;
 const d=await loadForecast(41.3,69.2,fetcher);
 assert.ok(url.includes('models=ecmwf_ifs025'));assert.ok(url.includes('wind_speed_unit=ms'));assert.equal(d.rows[0].time,1792371600000);assert.equal(d.rows[1].temperature_2m,null);assert.equal(d.rows[1].cloud_cover,null);
});
test('Upstream rate limits, empty forecasts and invalid data produce actionable errors',async()=>{
 await assert.rejects(()=>loadForecast(1,1,(async()=>new Response('',{status:429})) as typeof fetch),/частоту/);
 await assert.rejects(()=>loadForecast(1,1,(async()=>Response.json({hourly:{time:[]}})) as typeof fetch),/пустой/);
 await assert.rejects(()=>loadForecast(1,1,(async()=>Response.json({hourly:{time:[1],temperature_2m:[null]}})) as typeof fetch),/отсутствуют/);
});

test('Browser loads the provider directly before trying the hosting fallback',async()=>{
 const {browserForecast}=await import('../lib/browser-weather.ts');
 const urls:string[]=[];
 const d=await browserForecast({name:'Ташкент',latitude:41.26,longitude:69.21},undefined,false,(async(u:RequestInfo|URL)=>{urls.push(String(u));return Response.json({latitude:41.25,longitude:69.25,timezone:'Asia/Tashkent',elevation:430,hourly:{time:[1792371600],temperature_2m:[12]}});}) as typeof fetch);
 assert.equal(urls.length,1);assert.ok(urls[0].startsWith('https://api.open-meteo.com/'));assert.equal(d.rows[0].temperature_2m,12);
});
test('Browser falls back to the same-origin route if a local network blocks the provider',async()=>{
 const {browserForecast}=await import('../lib/browser-weather.ts');
 const urls:string[]=[];
 const d=await browserForecast({name:'Ташкент',latitude:41.26,longitude:69.21},undefined,true,(async(u:RequestInfo|URL)=>{urls.push(String(u));if(urls.length===1)throw new TypeError('Failed to fetch');return Response.json({rows:[],model:'IFS 0.25°'});}) as typeof fetch);
 assert.equal(urls.length,2);assert.ok(urls[1].startsWith('/api/forecast?'));assert.ok(urls[1].includes('fresh=1'));assert.equal(d.model,'IFS 0.25°');
});
test('Changing the selected point cancels its request without starting an obsolete fallback',async()=>{
 const {browserForecast}=await import('../lib/browser-weather.ts');
 const controller=new AbortController();controller.abort();let calls=0;
 await assert.rejects(()=>browserForecast({name:'Точка',latitude:1,longitude:1},controller.signal,false,(async()=>{calls++;throw new DOMException('Aborted','AbortError');}) as typeof fetch),{name:'AbortError'});
 assert.equal(calls,1);
});
