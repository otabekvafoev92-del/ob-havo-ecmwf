import {setTimeout as delay} from 'node:timers/promises';
import {cities,coordinates,escapeHTML,fetchPoint,forecastText,meteogramURL,searchCities} from './weather.mjs';

export function createTelegramClient(token,fetcher=fetch){
 return async(method,payload={},signal)=>{
  if(!/^[A-Za-z]+$/.test(method))throw new Error('Некорректный метод Telegram.');
  let res;try{res=await fetcher(`https://api.telegram.org/bot${token}/${method}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:signal?AbortSignal.any([signal,AbortSignal.timeout(35000)]):AbortSignal.timeout(35000)});}catch{throw new Error('Telegram временно недоступен.');}
  let body;try{body=await res.json();}catch{throw new Error('Telegram вернул некорректный ответ.');}
  if(!res.ok||!body.ok){const error=new Error(`Ошибка Telegram API (${res.status}).`);error.status=res.status;error.retryAfter=Math.min(60,Math.max(1,body.parameters?.retry_after||5));throw error;}
  return body.result;
 };
}
export function createBot({api,users,appURL,fetcher=fetch}){
 const sessions=new Map();
 const state=id=>{if(!sessions.has(id))sessions.set(id,{place:cities[0],matches:[],searchRevision:0});return sessions.get(id);};
 const appLink=place=>{const u=new URL(appURL);u.searchParams.set('lat',String(place.latitude));u.searchParams.set('lon',String(place.longitude));u.searchParams.set('name',place.name);return u.href;};
 const keyboard=place=>({inline_keyboard:[[{text:'Сегодня',callback_data:'today'},{text:'7 дней',callback_data:'week'}],[{text:'Карта и сравнение',web_app:{url:appLink(place)}}],[{text:'Выбрать город',callback_data:'cities'},{text:'Метеограмма ECMWF',callback_data:'meteogram'}]]});
 const send=(chatId,text,markup)=>api('sendMessage',{chat_id:chatId,text,parse_mode:'HTML',...(markup?{reply_markup:markup}:{})});
 async function showForecast(chatId,s,days){const data=await fetchPoint(s.place,fetcher);await send(chatId,forecastText(s.place,data,days),keyboard(s.place));}
 async function chooseCity(chatId){
  await send(chatId,'Напишите название города или отправьте свою геолокацию.',{keyboard:[[{text:'Отправить геолокацию',request_location:true}],[{text:'Ташкент'},{text:'Самарканд'},{text:'Бухара'}],[{text:'Андижан'},{text:'Наманган'},{text:'Фергана'}]],resize_keyboard:true});
 }
 async function handle(update){
  const callback=update.callback_query,message=callback?.message||update.message,from=callback?.from||message?.from;
  // Fail closed: private chat, allowlisted sender, and matching private chat ID.
  if(!from||from.is_bot||!users.has(String(from.id))||message?.chat?.type!=='private'||String(message.chat.id)!==String(from.id))return;
  const chatId=message.chat.id,s=state(String(from.id));
  if(callback)await api('answerCallbackQuery',{callback_query_id:callback.id});
  const text=message.text?.trim()||'',command=text.split(/\s/,1)[0].split('@')[0].toLowerCase(),action=callback?.data;
  try{
   if(action==='today'||command==='/today')return await showForecast(chatId,s,1);
   if(action==='week'||command==='/week')return await showForecast(chatId,s,7);
   if(action==='cities'||command==='/city')return await chooseCity(chatId);
   if(action==='meteogram'||command==='/meteogram'){
    const url=await meteogramURL(s.place,10,fetcher);
    return await api('sendPhoto',{chat_id:chatId,photo:url,caption:`Официальная метеограмма ECMWF ENS · ${s.place.name}\nВремя на диаграмме — UTC. © ECMWF · CC BY 4.0`,reply_markup:keyboard(s.place)});
   }
   if(command==='/map')return await send(chatId,`Карта, слои погоды и сравнение для <b>${escapeHTML(s.place.name)}</b>.`,keyboard(s.place));
   if(command==='/start')return await send(chatId,'<b>Моя погода ECMWF</b>\n\nВыберите город или отправьте геолокацию. Прогноз можно смотреть сообщениями и на интерактивной карте.\n\nДоступ ограничен вашим Telegram-аккаунтом.',keyboard(s.place));
   if(command==='/help'||command==='/settings')return await send(chatId,'/city — выбор города или геолокация\n/today — прогноз на сегодня\n/week — прогноз на 7 дней\n/map — карта и сравнение\n/meteogram — официальная диаграмма ECMWF\n\nМожно просто написать название города.',keyboard(s.place));
   if(action?.startsWith('pick:')){
    const [revision,value]=action.slice(5).split(':'),i=Number(value);
    if(Number(revision)!==s.searchRevision||!Number.isInteger(i)||!s.matches[i])return await send(chatId,'Этот список городов устарел. Напишите название города ещё раз.');
    s.place=s.matches[i];s.matches=[];return await showForecast(chatId,s,1);
   }
   if(message.location){
    const {lat,lon}=coordinates(new URLSearchParams({lat:String(message.location.latitude),lon:String(message.location.longitude)}));
    s.place={name:'Выбранная точка',latitude:lat,longitude:lon};return await showForecast(chatId,s,1);
   }
   if(text.length>=2&&!text.startsWith('/')){
    s.matches=await searchCities(text,fetcher);s.searchRevision++;
    if(!s.matches.length)return await send(chatId,'Город не найден. Попробуйте другое название или отправьте геолокацию.');
    if(s.matches.length===1){s.place=s.matches[0];s.matches=[];return await showForecast(chatId,s,1);}
    return await send(chatId,'Уточните город:',{inline_keyboard:s.matches.map((p,i)=>[{text:`${p.name} · ${p.country||''}`.slice(0,100),callback_data:`pick:${s.searchRevision}:${i}`}])});
   }
   await send(chatId,'Выберите действие или напишите название города.',keyboard(s.place));
  }catch(e){
   // Only weather helpers' messages reach the chat; transport errors never include tokens.
   await send(chatId,escapeHTML(e.message||'Не удалось получить прогноз. Повторите позже.'),keyboard(s.place));
  }
 }
 return {handle};
}
export async function configureBot(api,appURL){
 const me=await api('getMe');
 if(me.username?.toLowerCase()!=='obhavo_ecmwf_bot')throw new Error('Токен относится к другому боту.');
 const webhook=await api('getWebhookInfo');
 if(webhook.url)throw new Error('У бота уже включён webhook. Удалите его перед запуском polling, чтобы не прервать другую службу.');
 await api('setMyName',{name:'Моя погода ECMWF',language_code:'ru'});
 await api('setMyDescription',{description:'Приватный прогноз ECMWF: города, геолокация, температура, осадки, влажность, ветер и интерактивная карта.',language_code:'ru'});
 await api('setMyCommands',{commands:[{command:'start',description:'Моя погода ECMWF'},{command:'city',description:'Город или геолокация'},{command:'today',description:'Прогноз на сегодня'},{command:'week',description:'Прогноз на 7 дней'},{command:'map',description:'Карта и сравнение'},{command:'meteogram',description:'Метеограмма ECMWF'},{command:'help',description:'Справка'}],language_code:'ru'});
 await api('setChatMenuButton',{menu_button:{type:'web_app',text:'Карта погоды',web_app:{url:appURL}}});
}
export async function pollBot(api,bot,signal){
 let offset=0;
 while(!signal.aborted){
  try{
   const updates=await api('getUpdates',{offset,timeout:25,allowed_updates:['message','callback_query']},signal);
   for(const update of updates){if(signal.aborted)break;await bot.handle(update);offset=update.update_id+1;}
  }catch(e){
   if(signal.aborted)return;
   if(e.status===401||e.status===409)throw new Error('Polling остановлен: проверьте токен и отсутствие второй копии бота.');
   console.warn('Запрос бота не завершён; повторяем без вывода секретов.');
   await delay((e.retryAfter||5)*1000,undefined,{signal}).catch(()=>{});
  }
 }
}
