import {createServer} from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import {resolve,sep,extname,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {Readable} from 'node:stream';
import {createHmac} from 'node:crypto';
import {allowedUsers,cookieValue,issueSession,readSession,validateInitData} from './auth.mjs';
import {configureBot,createBot,createTelegramClient,pollBot} from './bot.mjs';
import {coordinates,loadForecast,meteogramURL,searchCities} from './weather.mjs';

const cookieName='__Host-ecmwf_session';
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.wasm':'application/wasm','.pbf':'application/x-protobuf','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.txt':'text/plain; charset=utf-8','.woff2':'font/woff2','.json':'application/json'};
const baseHeaders={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Robots-Tag':'noindex, nofollow'};
const authPage=`<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Моя погода ECMWF</title><meta name="robots" content="noindex,nofollow"><style>body{margin:0;min-height:100dvh;display:grid;place-items:center;background:#102039;color:#e5efff;font:16px/1.65 system-ui,sans-serif}main{max-width:420px;padding:28px}h1{font-size:28px;line-height:1.2}p{color:#a7bad5}a{color:#a9c8ff}button{border:0;border-radius:10px;padding:12px 18px;background:#376ce4;color:white;font:inherit}#identity{color:#e5efff;user-select:all}</style><main><p>ECMWF · ПРИВАТНЫЙ ПРОГНОЗ</p><h1>Моя погода</h1><p id="status">Проверяем вход через Telegram…</p><p id="identity"></p><button id="retry" hidden>Повторить</button><p><a href="https://t.me/ObHavo_ECMWF_bot">Открыть бота</a></p></main><script src="https://telegram.org/js/telegram-web-app.js"></script><script>
async function login(){const status=document.getElementById('status'),retry=document.getElementById('retry');retry.hidden=true;const tg=window.Telegram&&window.Telegram.WebApp;if(!tg||!tg.initData){status.textContent='Откройте карту кнопкой «Карта погоды» в боте.';return;}tg.ready();tg.expand();try{const response=await fetch('/auth/telegram',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({initData:tg.initData}),signal:AbortSignal.timeout(15000)});const data=await response.json();if(!response.ok){status.textContent=data.error||'Вход не выполнен.';if(data.telegram_id)document.getElementById('identity').textContent='Ваш Telegram ID: '+data.telegram_id;retry.hidden=false;return;}location.replace('/app'+location.search+location.hash);}catch{status.textContent='Не удалось связаться с сервером. Проверьте соединение и повторите.';retry.hidden=false;}}document.getElementById('retry').onclick=login;login();</script></html>`;

export function createApp({token,users,appURL,staticDir=resolve('telegram-dist'),fetcher=fetch,now=Date.now,isReady=()=>true}){
 const origin=new URL(appURL).origin;
 const sessionKey=createHmac('sha256',token).update('ECMWF Telegram session v1').digest();
 const json=(data,status=200,headers={})=>Response.json(data,{status,headers:{...baseHeaders,...headers}});
 const limits=new Map();
 return async request=>{
  const url=new URL(request.url),method=request.method;
  if(url.pathname==='/healthz')return json({service:'ecmwf-telegram',status:isReady()?'ready':'starting'},isReady()?200:503);
  if(url.pathname==='/robots.txt')return new Response('User-agent: *\nDisallow: /\n',{headers:{...baseHeaders,'Content-Type':'text/plain'}});
  if(url.pathname==='/auth/telegram'){
   const clearCookie=`${cookieName}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;
   if(method!=='POST')return json({error:'Метод не поддерживается.'},405,{Allow:'POST'});
   if(request.headers.get('origin')&&request.headers.get('origin')!==origin)return json({error:'Недопустимый адрес входа.'},403);
   try{
    const body=await request.text();if(body.length>18000)return json({error:'Слишком большой запрос.'},413);
    const {initData}=JSON.parse(body),user=validateInitData(initData,token,now());
    if(!users.has(String(user.id)))return json({error:'Доступ к приложению закрыт. Передайте ваш Telegram ID владельцу для настройки доступа.',telegram_id:String(user.id)},403,{'Set-Cookie':clearCookie});
    return json({ok:true},200,{'Set-Cookie':`${cookieName}=${issueSession(user.id,sessionKey,now())}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=43200`});
   }catch{return json({error:'Вход не подтверждён. Закройте приложение и откройте его заново через бота.'},401,{'Set-Cookie':clearCookie});}
  }
  if(url.pathname==='/'&&method==='GET')return new Response(authPage,{headers:{...baseHeaders,'Content-Type':types['.html']}});
  const uid=readSession(cookieValue(request.headers.get('cookie'),cookieName),sessionKey,users,now());
  if(!uid)return json({error:'Откройте приложение через Telegram-бота.'},401);
  if(!['GET','HEAD'].includes(method))return json({error:'Метод не поддерживается.'},405,{Allow:'GET, HEAD'});
  if(url.pathname.startsWith('/api/')){
   const bucket=limits.get(uid)||{start:now(),count:0};if(now()-bucket.start>60000){bucket.start=now();bucket.count=0;}bucket.count++;limits.set(uid,bucket);
   if(bucket.count>60)return json({error:'Слишком много запросов. Повторите через минуту.'},429,{'Retry-After':'60'});
   try{
    if(url.pathname==='/api/places')return json({results:await searchCities(url.searchParams.get('q')||'',fetcher)});
    if(url.pathname==='/api/forecast'){
     let coords;try{coords=coordinates(url.searchParams);}catch(e){return json({error:e.message},400);}
     return json(await loadForecast(coords.lat,coords.lon,fetcher));
    }
    if(url.pathname==='/api/meteogram'){
     let coords;try{coords=coordinates(url.searchParams);}catch(e){return json({error:e.message},400);}
     const place={name:(url.searchParams.get('name')||'Выбранная точка').slice(0,80),latitude:coords.lat,longitude:coords.lon};
     return json({url:await meteogramURL(place,Number(url.searchParams.get('days')),fetcher),source:'ECMWF Open Charts',license:'CC BY 4.0',fetchedAt:new Date(now()).toISOString()});
    }
    return json({error:'Адрес не найден.'},404);
   }catch(e){return json({error:e.message||'Источник временно недоступен.'},502);}
  }
  let path;try{path=decodeURIComponent(url.pathname);}catch{return json({error:'Некорректный адрес.'},400);}
  const filename=path==='/app'||path==='/app/'?'index.html':path.replace(/^\//,'');
  const file=resolve(staticDir,filename),root=resolve(staticDir)+sep;
  if(!file.startsWith(root)||!types[extname(file)])return json({error:'Адрес не найден.'},404);
  try{
   if(!(await stat(file)).isFile())return json({error:'Адрес не найден.'},404);
   return new Response(method==='HEAD'?null:await readFile(file),{headers:{...baseHeaders,'Content-Type':types[extname(file)]}});
  }catch{return json({error:'Файл не найден.'},404);}
 };
}

async function start(){
 const token=process.env.TELEGRAM_BOT_TOKEN;
 const domain=process.env.RAILWAY_PUBLIC_DOMAIN;
 const appURL=process.env.PUBLIC_APP_URL||(domain?`https://${domain}/`:'');
 if(!token||!appURL||!appURL.startsWith('https://'))throw new Error('Настройте TELEGRAM_BOT_TOKEN и PUBLIC_APP_URL (HTTPS).');
 const users=allowedUsers(process.env.ALLOWED_TELEGRAM_USER_IDS);
 let healthy=false;
 const app=createApp({token,users,appURL,isReady:()=>healthy}),stop=new AbortController();
 const server=createServer(async(req,res)=>{
  try{
   let body;const chunks=[];let size=0;
   if(req.method==='POST'){for await(const chunk of req){size+=chunk.length;if(size>20000){res.writeHead(413);res.end();return;}chunks.push(chunk);}body=Buffer.concat(chunks);}
   const request=new Request(new URL(req.url,new URL(appURL).origin),{method:req.method,headers:req.headers,body});
   const response=await app(request);res.writeHead(response.status,Object.fromEntries(response.headers));
   if(!response.body){res.end();return;}Readable.fromWeb(response.body).pipe(res);
  }catch{res.writeHead(500,{'Content-Type':'text/plain'});res.end('Не удалось выполнить запрос.');}
 });
 server.requestTimeout=30000;
 server.listen(Number(process.env.PORT)||3000,'0.0.0.0',()=>console.log('Моя погода ECMWF: HTTP-сервер запущен.'));
 const shutdown=()=>{stop.abort();server.close();setTimeout(()=>process.exit(0),5000).unref();};
 process.on('SIGTERM',shutdown);process.on('SIGINT',shutdown);
 const api=createTelegramClient(token);
 await configureBot(api,appURL);
 healthy=true;
 if(!users.size){console.warn('Список доступа пуст. Ответы бота выключены; откройте Mini App, получите свой ID и добавьте его в ALLOWED_TELEGRAM_USER_IDS.');return;}
 console.log('Бот настроен; доступ ограничен разрешёнными Telegram ID.');
 await pollBot(api,createBot({api,users,appURL}),stop.signal);
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))start().catch(()=>{console.error('Запуск остановлен. Проверьте настройки доступа, токен, имя бота и отсутствие другой копии polling/webhook.');process.exit(1);});
