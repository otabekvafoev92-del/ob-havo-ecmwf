import test from 'node:test';
import assert from 'node:assert/strict';
import {cityCamera,geographicStyle,boundsContain,normalizedViewBounds,shouldUpdateWeatherBounds} from '../lib/map-display.ts';
import {getRanges,domainOptions,updateCurrentBounds,currentBounds} from '@openmeteo/weather-map-layer';

test('The initial map opens on the chosen city at a useful local zoom',()=>{
 const camera=cityCamera({name:'Ташкент',latitude:41.26,longitude:69.21});
 assert.deepEqual(camera.center,[69.21,41.26]);assert.ok(camera.zoom>=8);assert.equal(camera.pitch,0);
});
test('Labels and administrative boundaries remain above the weather insertion point',()=>{
 const style=geographicStyle(),ids=style.layers.map(l=>l.id);
 assert.equal(style.projection?.type,'mercator');
 assert.ok(ids.indexOf('geography-labels')>ids.indexOf('geography-local'));
 assert.ok(ids.indexOf('geography-country')>ids.indexOf('base-map'));
 const labels=style.layers.find(l=>l.id==='geography-labels')!;assert.equal(labels.type,'symbol');
 assert.ok(JSON.stringify(labels).includes('name:ru'));assert.equal(style.glyphs,'/fonts/{fontstack}/{range}.pbf');
 assert.equal(Object.values(style.sources).filter(s=>s.type==='raster').length,0,'Raster placeholders must not be used as geography');
});
test('A normal city viewport reads less than 1% of the global ECMWF field',()=>{
 const grid=domainOptions.find(d=>d.value==='ecmwf_ifs025')!.grid;
 const count=(ranges:{start:number;end:number}[])=>ranges.reduce((n,r)=>n*(r.end-r.start),1);
 const global=count(getRanges(grid,undefined));
 updateCurrentBounds([67.5,39.8,71.2,42.8]);
 const regional=count(getRanges(grid,currentBounds));
 assert.ok(global>1000000);assert.ok(regional>0&&regional<global/100,`regional=${regional}, global=${global}`);
});
test('Panning inside the loaded area reuses it, while leaving it fetches a new window',()=>{
 const loaded:[number,number,number,number]=[65,38,72,44];
 assert.equal(shouldUpdateWeatherBounds(loaded,[66,39,71,43]),false);
 assert.equal(shouldUpdateWeatherBounds(loaded,[71,39,75,43]),true);
});
test('Zooming from a world view into a city releases the oversized data window',()=>{
 assert.equal(shouldUpdateWeatherBounds([-180,-85,180,85],[68,40,70,42]),true);
});
test('Dateline bounds are normalized without mistaking a 350-degree viewport for a small wrapped window',()=>{
 assert.deepEqual(normalizedViewBounds([170,-20,190,20]),[170,-20,-170,20]);
 assert.equal(boundsContain([170,-20,-170,20],[175,-10,-175,10]),true);
 assert.equal(boundsContain([170,-20,-170,20],[-175,-10,175,10]),false);
 assert.equal(boundsContain([-180,-85,180,85],[170,-20,-170,20]),true);
});
