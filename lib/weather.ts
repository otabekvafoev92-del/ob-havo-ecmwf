export type Place = { name: string; latitude: number; longitude: number; country?: string; timezone?: string };
export type Row = { time: number; temperature_2m: number | null; precipitation: number | null; cloud_cover: number | null; wind_speed_10m: number | null; wind_direction_10m: number | null; wind_gusts_10m: number | null };
export type Forecast = { rows: Row[]; timezone: string; fetchedAt: string; latitude: number; longitude: number; elevation: number; source: string; model: string };
export const fields = ['temperature_2m', 'precipitation', 'wind_speed_10m', 'wind_gusts_10m', 'cloud_cover', 'wind_direction_10m'] as const;
export type Field = typeof fields[number];
export const cities: Place[] = [
  {name:'Ташкент',latitude:41.26465,longitude:69.21627,country:'Узбекистан',timezone:'Asia/Tashkent'},
  {name:'Самарканд',latitude:39.6542,longitude:66.9597,country:'Узбекистан',timezone:'Asia/Samarkand'},
  {name:'Бухара',latitude:39.7747,longitude:64.4286,country:'Узбекистан',timezone:'Asia/Samarkand'},
  {name:'Андижан',latitude:40.7821,longitude:72.3442,country:'Узбекистан',timezone:'Asia/Tashkent'},
  {name:'Наманган',latitude:40.9983,longitude:71.6726,country:'Узбекистан',timezone:'Asia/Tashkent'},
  {name:'Фергана',latitude:40.3842,longitude:71.7843,country:'Узбекистан',timezone:'Asia/Tashkent'},
  {name:'Нукус',latitude:42.4531,longitude:59.6103,country:'Узбекистан',timezone:'Asia/Samarkand'},
  {name:'Стамбул',latitude:41.0138,longitude:28.9497,country:'Турция',timezone:'Europe/Istanbul'},
];
export function coordinates(search: URLSearchParams) {
  const a = search.get('lat'), b = search.get('lon');
  if (a === null || b === null || !a.trim() || !b.trim()) throw new Error('Укажите широту и долготу.');
  const lat = Number(a), lon = Number(b);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) throw new Error('Широта: от −90 до 90. Долгота: от −180 до 180.');
  return {lat,lon};
}
export async function fetchJSON<T>(url: string, fetcher: typeof fetch = fetch) {
  const res = await fetcher(url,{signal:AbortSignal.timeout(25000),headers:{Accept:'application/json'}});
  if (!res.ok) throw new Error(res.status === 429 ? 'Источник ограничил частоту запросов. Повторите через минуту.' : `Источник временно недоступен (${res.status}). Повторите запрос.`);
  const data = await res.json() as T & {error?: boolean;reason?: string};
  if (data.error) throw new Error(data.reason || 'Ошибка источника данных.');
  return data;
}
export async function loadForecast(lat: number, lon: number, fetcher: typeof fetch = fetch): Promise<Forecast> {
  const params = new URLSearchParams({latitude:String(lat),longitude:String(lon),hourly:fields.join(','),forecast_days:'15',timezone:'auto',timeformat:'unixtime',wind_speed_unit:'ms',models:'ecmwf_ifs025'});
  const data = await fetchJSON<{latitude:number;longitude:number;elevation:number;timezone:string;hourly:Record<string,(number|null)[]> & {time:number[]}}>(`https://api.open-meteo.com/v1/ecmwf?${params}`,fetcher);
  if (!Array.isArray(data.hourly?.time) || !data.hourly.time.length) throw new Error('Источник вернул пустой прогноз.');
  const rows: Row[] = data.hourly.time.map((t: number,i: number) => Object.fromEntries([['time',t*1000],...fields.map(f=>[f,Number.isFinite(data.hourly[f]?.[i]) ? data.hourly[f][i] : null])]) as Row);
  if (!rows.some(r=>r.temperature_2m !== null)) throw new Error('В прогнозе отсутствуют значения температуры.');
  return {rows,timezone:data.timezone||'UTC',fetchedAt:new Date().toISOString(),latitude:data.latitude,longitude:data.longitude,elevation:data.elevation,source:'ECMWF через Open-Meteo',model:'IFS 0.25°'};
}
export function localDate(time: number, timezone: string) {
  const p = new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(time);
  return ['year','month','day'].map(k=>p.find(v=>v.type===k)?.value).join('-');
}
export function selectRows(rows: Row[], from: string, to: string, timezone: string) {
  return rows.filter(r=>{const d=localDate(r.time,timezone);return d>=from&&d<=to;});
}
export function values(rows: Row[], field: Field): number[] { return rows.map(r=>r[field]).filter((v):v is number=>v!==null&&Number.isFinite(v)); }
export function stats(rows: Row[], field: Field) {
  const v=values(rows,field);
  return {min:v.length?Math.min(...v):null,max:v.length?Math.max(...v):null,mean:v.length?v.reduce((s,x)=>s+x,0)/v.length:null,sum:v.length?v.reduce((s,x)=>s+x,0):null,count:v.length,total:rows.length};
}
export function dailyRows(rows: Row[], timezone: string) {
  const groups = new Map<string,Row[]>();
  rows.forEach(r=>{const d=localDate(r.time,timezone);groups.set(d,[...(groups.get(d)||[]),r]);});
  return [...groups].map(([date,items])=>({date,temperature:stats(items,'temperature_2m'),rain:stats(items,'precipitation'),wind:stats(items,'wind_speed_10m'),cloud:stats(items,'cloud_cover')}));
}
export function comparison(rows: Row[], other: Row[], field: Field) {
  const byTime=new Map(other.map(r=>[r.time,r[field]]));
  return rows.map(r=>({time:r.time,primary:r[field],secondary:byTime.get(r.time)??null}));
}
export function makeCSV(rows: Row[], other: Row[], timezone: string) {
  const escape=(v: unknown)=>`"${String(v??'').replaceAll('"','""')}"`;
  const byTime=new Map(other.map(r=>[r.time,r]));
  return '\uFEFF'+[['Время UTC','Местное время',...fields.map(f=>`${f} (основная точка)`),...fields.map(f=>`${f} (сравнение)`)],...rows.map(r=>[new Date(r.time).toISOString(),new Intl.DateTimeFormat('sv-SE',{timeZone:timezone,dateStyle:'short',timeStyle:'short'}).format(r.time),...fields.map(f=>r[f]),...fields.map(f=>byTime.get(r.time)?.[f]??'')])].map(r=>r.map(escape).join(';')).join('\r\n');
}
