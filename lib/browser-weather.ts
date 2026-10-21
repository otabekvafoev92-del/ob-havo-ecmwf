import {loadForecast,type Forecast,type Place} from './weather.ts';

// Browser requests use the visitor's connection; the same-origin route is a
// fallback for networks that cannot reach the data provider directly.
export async function browserForecast(point: Place, signal?: AbortSignal, fresh=false, fetcher: typeof fetch=fetch): Promise<Forecast> {
  try {
    return await loadForecast(point.latitude,point.longitude,((url,init)=>fetcher(url,{
      ...init,
      signal:signal?AbortSignal.any([signal,...(init?.signal?[init.signal]:[])]):init?.signal,
    })) as typeof fetch);
  } catch(e) {
    if(signal?.aborted)throw e;
    const query=new URLSearchParams({lat:String(point.latitude),lon:String(point.longitude),...(fresh?{fresh:'1'}:{})});
    const res=await fetcher(`/api/forecast?${query}`,{signal,cache:'no-store'});
    const data=await res.json() as Forecast & {error?:string};
    if(!res.ok)throw new Error(data.error||'Не удалось загрузить прогноз. Повторите запрос.');
    return data;
  }
}
