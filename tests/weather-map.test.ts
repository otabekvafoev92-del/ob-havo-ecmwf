import test from 'node:test';
import assert from 'node:assert/strict';
import {condition,fileURL,loadMapPoint,mapLayers,nightGeoJSON,normalizeLongitude,pointFields,precipitationPerHour,rowAtTime,solarAltitude,stepHours,sunPosition,timeIndex,validateMapMetadata,weatherLayerURL,type MapMetadata} from '../lib/weather-map.ts';
const meta:MapMetadata={completed:true,reference_time:'2026-10-19T00:00:00Z',last_modified_time:'2026-10-19T05:00:00Z',valid_times:['2026-10-19T00:00Z','2026-10-19T03:00Z','2026-10-19T06:00Z','2026-10-19T12:00Z','2026-10-20T00:00Z'],variables:mapLayers.flatMap(l=>[...l.required])};

test('Map refuses incomplete, invalid or out-of-order model metadata',()=>{
 assert.equal(validateMapMetadata(meta),meta);
 for(const m of [{...meta,completed:false},{...meta,valid_times:['invalid']},{...meta,valid_times:[meta.valid_times[2],meta.valid_times[1]]},{...meta,reference_time:'bad'}])assert.throws(()=>validateMapMetadata(m));
});
test('Frames are tied to an exact model run and retain the UTC date across midnight',()=>{
 assert.equal(fileURL(meta,'2026-10-20T00:00:00Z'),'https://openmeteo.s3.amazonaws.com/data_spatial/ecmwf_ifs025/2026/10/19/0000Z/2026-10-20T0000.om');
 assert.throws(()=>fileURL(meta,'2026-10-21T00:00Z'));
});
test('Rainfall normalization respects the actual 3-hour or 6-hour interval',()=>{
 assert.equal(stepHours(meta,meta.valid_times[1]),3);
 assert.equal(stepHours(meta,meta.valid_times[3]),6);
 assert.equal(precipitationPerHour(3,3),1);
 assert.equal(precipitationPerHour(6,6),1);
 assert.throws(()=>precipitationPerHour(2,0));
});
test('Categorical precipitation types use nearest sampling; continuous fields use linear sampling',()=>{
 assert.ok(weatherLayerURL(meta,meta.valid_times[2],'precipitation_type').includes('interpolation=nearest'));
 assert.ok(weatherLayerURL(meta,meta.valid_times[2],'precipitation').includes('interpolation=linear'));
 const wind=weatherLayerURL(meta,meta.valid_times[2],'wind_u_component_10m',true);
 assert.ok(wind.includes('arrows=true'));assert.ok(wind.includes('variable=wind_u_component_10m'));
});
test('The time slider chooses the closest available forecast instead of an unavailable hour',()=>{
 assert.equal(timeIndex(meta.valid_times,Date.parse('2026-10-19T05:30Z')),2);
 assert.equal(timeIndex([],Date.now()),0);
});
test('Solar geometry has the correct seasons and opposite hemispheres at noon',()=>{
 const june=sunPosition(Date.parse('2026-06-21T12:00:00Z'));
 const december=sunPosition(Date.parse('2026-12-21T12:00:00Z'));
 assert.ok(june.latitude>23&&june.latitude<24);assert.ok(december.latitude< -23&&december.latitude> -24);
 assert.ok(Math.abs(june.longitude)<3);
 assert.ok(solarAltitude(0,june.longitude,june)>60);
 assert.ok(solarAltitude(0,normalizeLongitude(june.longitude+180),june)< -60);
});
test('Night shading uses closed valid polygons and bounded opacity',()=>{
 const d=nightGeoJSON(Date.parse('2026-10-19T06:00Z'));
 assert.ok(d.features.length>1500&&d.features.length<3000);
 for(const f of d.features){const r=f.geometry.coordinates[0];assert.deepEqual(r[0],r.at(-1));assert.ok(f.properties.shade>=0&&f.properties.shade<=.26);for(const [lon,lat] of r){assert.ok(lon>=-180&&lon<=180);assert.ok(lat>=-90&&lat<=90);}}
});
test('Weather phenomena distinguish snow, rain, thunderstorms and missing data',()=>{
 assert.equal(condition(71).icon,'snow');assert.equal(condition(61).icon,'rain');assert.equal(condition(95).icon,'storm');assert.equal(condition(0).icon,'sun');assert.equal(condition(null).label,'Нет данных');
});
test('Point weather pins ECMWF and units, carries humidity and preserves nulls',async()=>{
 let requested='';
 const d=await loadMapPoint(41.26,69.21,undefined,(async(u:RequestInfo|URL)=>{requested=String(u);return Response.json({hourly:{time:[1792389600],temperature_2m:[12],relative_humidity_2m:[67],precipitation:[0.6],weather_code:[61]}});}) as typeof fetch);
 assert.ok(requested.includes('models=ecmwf_ifs025'));assert.ok(requested.includes('wind_speed_unit=ms'));assert.ok(requested.includes('relative_humidity_2m'));
 assert.equal(d.rows[0].relative_humidity_2m,67);assert.equal(d.rows[0].wind_speed_10m,null);assert.equal(d.rows[0].precipitation,.6);assert.equal(Object.keys(d.rows[0]).length,pointFields.length+1);
 assert.equal(rowAtTime(d.rows,1792389600000),d.rows[0]);assert.equal(rowAtTime(d.rows,1792393200000),null);
});
test('Point requests report upstream rate limits instead of inventing a weather value',async()=>{
 await assert.rejects(()=>loadMapPoint(0,0,undefined,(async()=>Response.json({error:true},{status:429})) as typeof fetch),/ограничил/);
});
