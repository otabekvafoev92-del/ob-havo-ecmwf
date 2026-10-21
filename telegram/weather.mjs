import {cities,coordinates,fetchJSON,localDate,loadForecast} from '../lib/weather.ts';
import {condition} from '../lib/weather-map.ts';
export {cities,coordinates,loadForecast};
export const escapeHTML=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const format=(v,digits=1)=>v==null||!Number.isFinite(v)?'—':new Intl.NumberFormat('ru-RU',{maximumFractionDigits:digits}).format(v);
const fields=['temperature_2m','precipitation','relative_humidity_2m','wind_speed_10m','wind_gusts_10m','cloud_cover','weather_code'];
export async function searchCities(name,fetcher=fetch){
 const q=String(name).trim();if(q.length<2||q.length>100)return [];
 const preset=cities.find(c=>c.name.toLowerCase()===q.toLowerCase());if(preset)return [preset];
 const p=new URLSearchParams({name:q,count:'8',language:'ru',format:'json'});
 const data=await fetchJSON(`https://geocoding-api.open-meteo.com/v1/search?${p}`,fetcher);
 return (data.results||[]).map(p=>({name:p.name,latitude:p.latitude,longitude:p.longitude,country:[p.admin1,p.country].filter(Boolean).join(', '),timezone:p.timezone}));
}
export async function fetchPoint(place,fetcher=fetch){
 const {lat,lon}=coordinates(new URLSearchParams({lat:String(place.latitude),lon:String(place.longitude)}));
 const q=new URLSearchParams({latitude:String(lat),longitude:String(lon),hourly:fields.join(','),forecast_days:'15',timezone:'auto',timeformat:'unixtime',wind_speed_unit:'ms',models:'ecmwf_ifs025'});
 const d=await fetchJSON(`https://api.open-meteo.com/v1/ecmwf?${q}`,fetcher);
 if(!d.hourly?.time?.length||!d.hourly.temperature_2m?.some(Number.isFinite))throw new Error('В источнике пока нет прогноза для этой точки.');
 return {timezone:d.timezone||'UTC',rows:d.hourly.time.map((t,i)=>Object.fromEntries([['time',t*1000],...fields.map(f=>[f,Number.isFinite(d.hourly[f]?.[i])?d.hourly[f][i]:null])]))};
}
export function forecastText(place,data,days=1,now=Date.now()){
 const tz=data.timezone,today=localDate(now,tz),groups=new Map();
 for(const r of data.rows){const day=localDate(r.time,tz);if(day<today)continue;if(!groups.has(day))groups.set(day,[]);groups.get(day).push(r);}
 const result=[`<b>${escapeHTML(place.name)}</b> · ${days===1?'Сегодня':'Прогноз на 7 дней'}`];
 const nearest=data.rows.find(r=>r.time>=now);
 if(days===1&&nearest){
  const time=new Intl.DateTimeFormat('ru-RU',{timeZone:tz,hour:'2-digit',minute:'2-digit'}).format(nearest.time);
  result.push(`Ближайший час · ${time}\n${escapeHTML(condition(nearest.weather_code).label)}, <b>${format(nearest.temperature_2m,0)} °C</b>\nОсадки: ${format(nearest.precipitation)} мм/ч\nВлажность: ${format(nearest.relative_humidity_2m,0)} %\nВетер: ${format(nearest.wind_speed_10m)} м/с · порывы ${format(nearest.wind_gusts_10m)} м/с`);
 }
 for(const [date,rows] of [...groups].slice(0,days)){
  const temps=rows.map(r=>r.temperature_2m).filter(Number.isFinite),rains=rows.map(r=>r.precipitation),winds=rows.map(r=>r.wind_speed_10m).filter(Number.isFinite);
  const rain=rains.every(Number.isFinite)?rains.reduce((a,b)=>a+b,0):null;
  const label=new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'short',weekday:'short',timeZone:'UTC'}).format(new Date(`${date}T12:00:00Z`));
  result.push(`${label}: <b>${temps.length?format(Math.min(...temps),0):'—'}…${temps.length?format(Math.max(...temps),0):'—'} °C</b> · осадки ${format(rain)} мм · ветер до ${winds.length?format(Math.max(...winds)):'—'} м/с${rain===null?' (осадки: неполные данные)':''}`);
 }
 if(groups.size===0)result.push('Для выбранного периода нет данных.');
 result.push(`Часовой пояс: ${escapeHTML(tz)}\nПрогноз ECMWF IFS 0.25° через Open-Meteo. Это расчёт модели, не наблюдения.`);
 return result.join('\n\n');
}
export async function meteogramURL(place,days=10,fetcher=fetch){
 const {lat,lon}=coordinates(new URLSearchParams({lat:String(place.latitude),lon:String(place.longitude)}));
 const q=new URLSearchParams({lat:String(lat),lon:String(lon),epsgram:days===15?'classical_15d':'classical_10d',station_name:place.name.slice(0,80)});
 const d=await fetchJSON(`https://charts.ecmwf.int/opencharts-api/v1/products/opencharts_meteogram/?${q}`,fetcher);
 const href=d.data?.link?.href;
 if(typeof href!=='string'||!href.startsWith('https://charts.ecmwf.int/content/'))throw new Error('ECMWF пока не вернул метеограмму. Повторите позже.');
 return href;
}
