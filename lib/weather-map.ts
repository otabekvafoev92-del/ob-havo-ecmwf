export type NightData={type:'FeatureCollection';features:{type:'Feature';properties:{shade:number};geometry:{type:'Polygon';coordinates:number[][][]}}[]};
export const SPATIAL_ROOT='https://openmeteo.s3.amazonaws.com/data_spatial/ecmwf_ifs025';
export type MapMetadata={completed:boolean;reference_time:string;last_modified_time:string;valid_times:string[];variables:string[]};
export const mapLayers=[
 {key:'precipitation',label:'Осадки',unit:'мм/ч',required:['precipitation']},
 {key:'precipitation_type',label:'Тип осадков',unit:'',required:['precipitation_type']},
 {key:'cloud_cover',label:'Облака',unit:'%',required:['cloud_cover']},
 {key:'wind_u_component_10m',label:'Ветер',unit:'м/с',required:['wind_u_component_10m','wind_v_component_10m']},
 {key:'relative_humidity_2m',label:'Влажность',unit:'%',required:['relative_humidity_2m']},
 {key:'temperature_2m',label:'Температура',unit:'°C',required:['temperature_2m']},
] as const;
export type MapLayer=typeof mapLayers[number]['key'];
export const precipitationTypes=[
 {code:1,label:'Дождь',color:'#4dd791'},
 {code:3,label:'Ледяной дождь',color:'#f77695'},
 {code:5,label:'Снег',color:'#91beff'},
 {code:6,label:'Мокрый снег',color:'#b9a0ed'},
 {code:7,label:'Дождь со снегом',color:'#4de2e6'},
 {code:8,label:'Ледяная крупа',color:'#ffc06e'},
 {code:12,label:'Ледяная морось',color:'#ed9ad2'},
];
export function validateMapMetadata(value:unknown):MapMetadata{
 const d=value as MapMetadata;
 if(!d||d.completed!==true||!Number.isFinite(Date.parse(d.reference_time))||!Array.isArray(d.valid_times)||d.valid_times.length<2||d.valid_times.some(t=>!Number.isFinite(Date.parse(t)))||!Array.isArray(d.variables))throw new Error('Источник вернул неполный расчёт карты. Попробуйте обновить.');
 const times=d.valid_times.map(t=>Date.parse(t));
 if(times.some((t,i)=>i>0&&t<=times[i-1]))throw new Error('Некорректная шкала времени модели.');
 return d;
}
export function timeIndex(times:string[],now=Date.now()){
 if(!times.length)return 0;
 let result=0;for(let i=1;i<times.length;i++)if(Math.abs(Date.parse(times[i])-now)<Math.abs(Date.parse(times[result])-now))result=i;
 return result;
}
export function stepHours(metadata:MapMetadata,time:string){
 const i=metadata.valid_times.findIndex(t=>Date.parse(t)===Date.parse(time));
 if(i<0)throw new Error('Срок отсутствует в расчёте модели.');
 const current=Date.parse(metadata.valid_times[i]);
 const previous=i>0?Date.parse(metadata.valid_times[i-1]):Date.parse(metadata.reference_time);
 const hours=(current-previous)/3600000;
 return hours>0?hours:(Date.parse(metadata.valid_times[1])-current)/3600000;
}
export function fileURL(metadata:MapMetadata,time:string){
 if(!metadata.valid_times.some(t=>Date.parse(t)===Date.parse(time)))throw new Error('Срок отсутствует в расчёте модели.');
 const r=new Date(metadata.reference_time).toISOString(),t=new Date(time).toISOString();
 return `${SPATIAL_ROOT}/${r.slice(0,4)}/${r.slice(5,7)}/${r.slice(8,10)}/${r.slice(11,13)}${r.slice(14,16)}Z/${t.slice(0,10)}T${t.slice(11,13)}${t.slice(14,16)}.om`;
}
export function weatherLayerURL(metadata:MapMetadata,time:string,variable:MapLayer,arrows=false){
 const q=new URLSearchParams({variable,dark:'true',interpolation:variable==='precipitation_type'?'nearest':'linear',color_blend:variable==='precipitation_type'?'false':'true',tile_size:'512',...(arrows?{arrows:'true'}:{})});
 return `om://${fileURL(metadata,time)}?${q}`;
}
export function precipitationPerHour(value:number,hours:number){
 if(!Number.isFinite(hours)||hours<=0)throw new Error('Некорректный шаг осадков.');
 return value/hours;
}
export const formatMapTime=(time:string|number,timezone='UTC')=>new Intl.DateTimeFormat('ru-RU',{timeZone:timezone,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(time));
const rad=(d:number)=>d*Math.PI/180,deg=(r:number)=>r*180/Math.PI;
export const normalizeLongitude=(lon:number)=>((lon+180)%360+360)%360-180;
// Approximate apparent solar position, from mean solar coordinates and sidereal time.
export function sunPosition(time:number){
 const d=time/86400000+2440587.5-2451545;
 const g=rad(357.529+0.98560028*d),q=280.459+0.98564736*d;
 const L=rad(q+1.915*Math.sin(g)+0.020*Math.sin(2*g)),e=rad(23.439-0.00000036*d);
 const ra=deg(Math.atan2(Math.cos(e)*Math.sin(L),Math.cos(L)));
 return {longitude:normalizeLongitude(ra-(280.1600+360.9856235*d)),latitude:deg(Math.asin(Math.sin(e)*Math.sin(L)))};
}
export function solarAltitude(latitude:number,longitude:number,sun:{latitude:number;longitude:number}){
 const cosine=Math.sin(rad(latitude))*Math.sin(rad(sun.latitude))+Math.cos(rad(latitude))*Math.cos(rad(sun.latitude))*Math.cos(rad(longitude-sun.longitude));
 return deg(Math.asin(Math.max(-1,Math.min(1,cosine))));
}
export function nightGeoJSON(time:number):NightData{
 const sun=sunPosition(time),features:NightData['features']=[];
 for(let lat=-88;lat<88;lat+=4)for(let lon=-180;lon<180;lon+=4){
  const altitude=solarAltitude(lat+2,lon+2,sun);
  if(altitude>=2)continue;
  features.push({type:'Feature',properties:{shade:Math.min(0.26,Math.max(0,(2-altitude)/60))},geometry:{type:'Polygon',coordinates:[[[lon,lat],[lon+4,lat],[lon+4,lat+4],[lon,lat+4],[lon,lat]]]}});
 }
 return {type:'FeatureCollection',features};
}
export const pointFields=['temperature_2m','relative_humidity_2m','precipitation','cloud_cover','wind_speed_10m','wind_direction_10m','wind_gusts_10m','weather_code','precipitation_type','pressure_msl'] as const;
export type PointField=typeof pointFields[number];
export type MapPointRow={time:number}&Record<PointField,number|null>;
export type MapPointData={rows:MapPointRow[];fetchedAt:string};
export async function loadMapPoint(lat:number,lon:number,signal?:AbortSignal,fetcher:typeof fetch=fetch):Promise<MapPointData>{
 const q=new URLSearchParams({latitude:String(lat),longitude:String(lon),hourly:pointFields.join(','),models:'ecmwf_ifs025',forecast_days:'15',timezone:'GMT',timeformat:'unixtime',wind_speed_unit:'ms'});
 const res=await fetcher(`https://api.open-meteo.com/v1/ecmwf?${q}`,{signal:signal?AbortSignal.any([signal,AbortSignal.timeout(25000)]):AbortSignal.timeout(25000)});
 const d=await res.json() as {error?:boolean;reason?:string;hourly?:Record<string,(number|null)[]> &{time:number[]}};
 if(!res.ok||d.error)throw new Error(res.status===429?'Источник ограничил запросы. Повторите через минуту.':d.reason||'Не удалось получить погоду в точке.');
 if(!d.hourly?.time?.length)throw new Error('Точечный прогноз пока недоступен.');
 const h=d.hourly;
 return {rows:h.time.map((t,i)=>Object.fromEntries([['time',t*1000],...pointFields.map(f=>[f,Number.isFinite(h[f]?.[i])?h[f][i]:null])]) as MapPointRow),fetchedAt:new Date().toISOString()};
}
export function rowAtTime(rows:MapPointRow[],time:string|number){
 const t=typeof time==='number'?time:Date.parse(time);
 return rows.find(r=>r.time===t)||null;
}
export function condition(code:number|null|undefined){
 if(code==null)return {label:'Нет данных',icon:'cloud'};
 if(code===0)return {label:'Ясно',icon:'sun'};
 if(code===1||code===2)return {label:code===1?'Малооблачно':'Переменная облачность',icon:'partly'};
 if(code===3)return {label:'Пасмурно',icon:'cloud'};
 if(code===45||code===48)return {label:'Туман',icon:'fog'};
 if([51,53,55].includes(code))return {label:'Морось',icon:'rain'};
 if([56,57,66,67].includes(code))return {label:'Ледяные осадки',icon:'snow'};
 if([71,73,75,77,85,86].includes(code))return {label:'Снег',icon:'snow'};
 if([61,63,65,80,81,82].includes(code))return {label:'Дождь',icon:'rain'};
 if([95,96,99].includes(code))return {label:'Гроза',icon:'storm'};
 return {label:'Погодные явления',icon:'cloud'};
}
