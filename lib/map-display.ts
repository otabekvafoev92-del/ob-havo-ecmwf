import type {StyleSpecification} from 'maplibre-gl';
import type {Place} from './weather';
export type ViewBounds=[number,number,number,number];
export const boundaryLayerIDs=['geography-outline','geography-country','geography-region','geography-local'];
export const labelsLayerID='geography-labels';
const nameField=['coalesce',['get','name:ru'],['get','name:en'],['get','name:latin'],['get','name']] as const;
export function geographicStyle():StyleSpecification{
 const textPaint={'text-color':'#eef5ff','text-halo-color':'#122136','text-halo-width':1.6};
 return {version:8,projection:{type:'mercator'},glyphs:'/fonts/{fontstack}/{range}.pbf',sources:{
  geography:{type:'vector',url:'https://tiles.basemaps.cartocdn.com/vector/carto.streets/v1/tiles.json',attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> © <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>'},
 },layers:[
  {id:'space',type:'background',paint:{'background-color':'#152638'}},
  {id:'base-map',type:'fill',source:'geography','source-layer':'landcover',paint:{'fill-color':['match',['get','class'],['wood','forest'],'#203e3a',['grass','farmland'],'#233b35','#223446'],'fill-opacity':0.65}},
  {id:'base-landuse',type:'fill',source:'geography','source-layer':'landuse',minzoom:7,paint:{'fill-color':'#293c50','fill-opacity':0.55}},
  {id:'base-water',type:'fill',source:'geography','source-layer':'water',paint:{'fill-color':'#234e6a','fill-opacity':1}},
  {id:'base-waterways',type:'line',source:'geography','source-layer':'waterway',minzoom:7,paint:{'line-color':'#427e9e','line-width':['interpolate',['linear'],['zoom'],7,0.5,14,2]}},
  {id:'base-roads',type:'line',source:'geography','source-layer':'transportation',minzoom:6,paint:{'line-color':['match',['get','class'],['motorway','trunk'],'#6884a5',['primary','secondary'],'#4a6685','#344e68'],'line-width':['interpolate',['linear'],['zoom'],6,0.4,11,1.3,15,3.2],'line-opacity':0.85}},
  {id:'geography-outline',type:'line',source:'geography','source-layer':'boundary',filter:['all',['==','maritime',0],['<=','admin_level',6]],paint:{'line-color':'#071324','line-width':['interpolate',['linear'],['zoom'],2,2.5,9,4],'line-opacity':0.7}},
  {id:'geography-country',type:'line',source:'geography','source-layer':'boundary',filter:['all',['==','admin_level',2],['==','maritime',0]],paint:{'line-color':'#eff4ff','line-width':['interpolate',['linear'],['zoom'],1,0.7,7,1.7],'line-opacity':0.85}},
  {id:'geography-region',type:'line',source:'geography','source-layer':'boundary',minzoom:3,filter:['all',['==','admin_level',4],['==','maritime',0]],paint:{'line-color':'#bacce9','line-width':1.25,'line-dasharray':[4,3],'line-opacity':0.85}},
  {id:'geography-local',type:'line',source:'geography','source-layer':'boundary',minzoom:5,filter:['all',['>','admin_level',4],['<=','admin_level',10],['==','maritime',0]],paint:{'line-color':'#7fd7ed','line-width':['interpolate',['linear'],['zoom'],5,0.7,11,1.6],'line-opacity':0.9,'line-dasharray':[3,2]}},
  {id:'geography-countries-labels',type:'symbol',source:'geography','source-layer':'place',minzoom:1,maxzoom:7,filter:['in','class','country','state'],layout:{'text-field':nameField as unknown as string,'text-font':['Open Sans Regular'],'text-size':['interpolate',['linear'],['zoom'],1,10,6,15],'text-transform':'uppercase','text-letter-spacing':0.1},paint:{...textPaint,'text-color':'#a7bbd3'}},
  {id:'geography-street-labels',type:'symbol',source:'geography','source-layer':'transportation_name',minzoom:12,layout:{'text-field':nameField as unknown as string,'text-font':['Open Sans Regular'],'text-size':10,'symbol-placement':'line','text-max-angle':35},paint:{...textPaint,'text-color':'#adc5df'}},
  {id:'geography-local-labels',type:'symbol',source:'geography','source-layer':'place',minzoom:8,filter:['in','class','village','suburb','neighbourhood','hamlet'],layout:{'text-field':nameField as unknown as string,'text-font':['Open Sans Regular'],'text-size':['interpolate',['linear'],['zoom'],8,10,13,13],'text-max-width':8,'text-padding':3},paint:textPaint},
  {id:labelsLayerID,type:'symbol',source:'geography','source-layer':'place',minzoom:2,filter:['in','class','city','town'],layout:{'text-field':nameField as unknown as string,'text-font':['Open Sans Regular'],'text-size':['interpolate',['linear'],['zoom'],2,10,7,14,11,19],'text-max-width':9,'text-padding':5,'text-variable-anchor':['center','top','bottom','left','right'],'text-radial-offset':0.4},paint:textPaint},
 ]};
}
export function cityCamera(place:Place){return {center:[place.longitude,place.latitude] as [number,number],zoom:8.8,pitch:0,bearing:0};}
export function normalizedViewBounds(raw:ViewBounds):ViewBounds{
 let [w,s,e,n]=raw;
 s=Math.max(-85,Math.min(85,s));n=Math.max(-85,Math.min(85,n));
 if(e-w>=359)return [-180,s,180,n];
 w=((w+180)%360+360)%360-180;e=((e+180)%360+360)%360-180;
 return [w,s,e,n];
}
export function boundsContain(outer:ViewBounds,inner:ViewBounds){
 if(inner[1]<outer[1]||inner[3]>outer[3])return false;
 if(outer[0]===-180&&outer[2]===180)return true;
 const containsLon=(lon:number)=>outer[0]<=outer[2]?lon>=outer[0]&&lon<=outer[2]:lon>=outer[0]||lon<=outer[2];
 if(longitudeSpan(inner)>longitudeSpan(outer))return false;
 if(inner[0]>inner[2]&&outer[0]<=outer[2])return false;
 return containsLon(inner[0])&&containsLon(inner[2]);
}

export function longitudeSpan(bounds:ViewBounds){return bounds[2]>=bounds[0]?bounds[2]-bounds[0]:bounds[2]+360-bounds[0];}
export function shouldUpdateWeatherBounds(loaded:ViewBounds|null,visible:ViewBounds){
 if(!loaded||!boundsContain(loaded,visible))return true;
 const area=(b:ViewBounds)=>longitudeSpan(b)*Math.max(0.001,b[3]-b[1]);
 return area(loaded)>area(visible)*9;
}
