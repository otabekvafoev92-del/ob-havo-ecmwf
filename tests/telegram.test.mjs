import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import {mkdtemp,writeFile,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {allowedUsers,issueSession,readSession,validateInitData} from '../telegram/auth.mjs';
import {createApp} from '../telegram/server.mjs';
import {configureBot,createBot,createTelegramClient} from '../telegram/bot.mjs';
import {cities,fetchPoint,forecastText} from '../telegram/weather.mjs';
const token='123456789:TEST_ONLY_NOT_A_REAL_TOKEN',now=Date.UTC(2026,9,21,5),uid=12345678,users=allowedUsers(String(uid));
function signed(id=uid,date=now){
 const p=new URLSearchParams({auth_date:String(Math.floor(date/1000)),query_id:'test-query',user:JSON.stringify({id,first_name:'Отабек'})});
 const key=createHmac('sha256','WebAppData').update(token).digest();
 const check=[...p].sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>`${k}=${v}`).join('\n');
 p.set('hash',createHmac('sha256',key).update(check).digest('hex'));return p.toString();
}
test('Mini App accepts signed Telegram identity, rejects tampering, stale/future data and duplicates',()=>{
 assert.equal(validateInitData(signed(),token,now).id,uid);
 assert.throws(()=>validateInitData(signed().replace('test-query','changed-query'),token,now));
 assert.throws(()=>validateInitData(signed(uid,now-601000),token,now));
 assert.throws(()=>validateInitData(signed(uid,now+31000),token,now));
 assert.throws(()=>validateInitData(signed()+'&user={}',token,now));
 assert.throws(()=>validateInitData('',token,now));
});
test('Session is signed, expires, and is rechecked against the current allowlist',()=>{
 const session=issueSession(uid,token,now);
 assert.equal(readSession(session,token,users,now+1000),String(uid));
 assert.equal(readSession(session+'x',token,users,now),null);
 assert.equal(readSession(session,token,new Set(),now),null);
 assert.equal(readSession(session,token,users,now+12*3600000),null);
 assert.equal(readSession(session,'other-secret',users,now),null);
});
test('Mini App gates the app, worker, fonts and APIs; valid login grants an HttpOnly cookie',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'ecmwf-telegram-'));
 try{
  await mkdir(join(dir,'assets'));await writeFile(join(dir,'index.html'),'<html>private weather app</html>');await writeFile(join(dir,'assets/worker.js'),'self.onmessage=()=>{};');
  let upstreamCalls=0;
  const app=createApp({token,users,appURL:'https://weather.example/',staticDir:dir,now:()=>now,fetcher:async()=>{upstreamCalls++;throw new Error('must not call');}});
  for(const path of ['/app','/assets/worker.js','/api/places?q=London','/fonts/Open%20Sans%20Regular/0-255.pbf'])assert.equal((await app(new Request('https://weather.example'+path))).status,401);
  assert.equal(upstreamCalls,0);
  const denied=await app(new Request('https://weather.example/auth/telegram',{method:'POST',body:JSON.stringify({initData:signed(uid+1)})}));
  assert.equal(denied.status,403);assert.equal((await denied.json()).telegram_id,String(uid+1));
  const login=await app(new Request('https://weather.example/auth/telegram',{method:'POST',headers:{Origin:'https://weather.example'},body:JSON.stringify({initData:signed()})}));
  assert.equal(login.status,200);const setCookie=login.headers.get('set-cookie');assert.match(setCookie,/HttpOnly; Secure; SameSite=Lax/);
  const headers={Cookie:setCookie.split(';')[0]};
  const page=await app(new Request('https://weather.example/app',{headers}));assert.equal(page.status,200);assert.match(await page.text(),/private weather app/);
  const worker=await app(new Request('https://weather.example/assets/worker.js',{headers}));assert.equal(worker.status,200);assert.match(worker.headers.get('content-type'),/javascript/);
  const missing=await app(new Request('https://weather.example/assets/missing-worker.js',{headers}));assert.equal(missing.status,404);assert.doesNotMatch(await missing.text(),/private weather app/);
  const badOrigin=await app(new Request('https://weather.example/auth/telegram',{method:'POST',headers:{Origin:'https://elsewhere.example'},body:JSON.stringify({initData:signed()})}));assert.equal(badOrigin.status,403);
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('Public entry contains only a Telegram login screen and no bot credentials',async()=>{
 const app=createApp({token,users,appURL:'https://weather.example/',now:()=>now});
 const page=await app(new Request('https://weather.example/'));
 const html=await page.text();assert.equal(page.status,200);assert.match(html,/Проверяем вход/);assert.ok(!html.includes(token));assert.ok(!html.includes('private weather app'));
});
test('Bot ignores unapproved accounts, groups, forged chat IDs and bot senders',async()=>{
 const calls=[],bot=createBot({api:async(...a)=>calls.push(a),users,appURL:'https://weather.example/'});
 const message={chat:{type:'private',id:uid},from:{id:uid},text:'/start'};
 await bot.handle({message:{...message,from:{id:uid+1}}});
 await bot.handle({message:{...message,chat:{id:uid,type:'group'}}});
 await bot.handle({message:{...message,chat:{id:uid+1,type:'private'}}});
 await bot.handle({message:{...message,from:{id:uid,is_bot:true}}});
 assert.equal(calls.length,0);
 await bot.handle({message});assert.equal(calls[0][0],'sendMessage');assert.match(calls[0][1].text,/Моя погода ECMWF/);
 const map=calls[0][1].reply_markup.inline_keyboard[1][0].web_app.url;assert.equal(new URL(map).searchParams.get('lat'),String(cities[0].latitude));
});
test('Point forecast pins ECMWF, includes humidity, and preserves gaps in daily rain totals',async()=>{
 let requested;
 const data=await fetchPoint(cities[0],async url=>{requested=new URL(url);return Response.json({timezone:'Asia/Tashkent',hourly:{time:[now/1000,now/1000+3600],temperature_2m:[20,21],precipitation:[0,null],relative_humidity_2m:[50,48],wind_speed_10m:[2,3],wind_gusts_10m:[4,5],cloud_cover:[0,10],weather_code:[0,1]}});});
 assert.equal(requested.searchParams.get('models'),'ecmwf_ifs025');assert.equal(requested.searchParams.get('wind_speed_unit'),'ms');assert.match(requested.searchParams.get('hourly'),/relative_humidity_2m/);
 const text=forecastText({...cities[0],name:'<b>unsafe</b>'},data,1,now);assert.match(text,/&lt;b&gt;unsafe&lt;\/b&gt;/);assert.match(text,/Влажность: 50/);assert.match(text,/осадки — мм/);assert.match(text,/неполные данные/);
});
test('An old city picker cannot silently select a result from a newer search',async()=>{
 const calls=[],bot=createBot({api:async(...a)=>calls.push(a),users,appURL:'https://weather.example/',fetcher:async()=>Response.json({results:[{name:'Первый',latitude:10,longitude:20},{name:'Второй',latitude:30,longitude:40}]})});
 const message={chat:{type:'private',id:uid},from:{id:uid},text:'Test City'};
 await bot.handle({message});const previous=calls.at(-1)[1].reply_markup.inline_keyboard[0][0].callback_data;
 await bot.handle({message:{...message,text:'Another City'}});
 await bot.handle({callback_query:{id:'callback',from:{id:uid},message,data:previous}});
 assert.match(calls.at(-1)[1].text,/список городов устарел/);
});
test('Telegram network failures never disclose the bot token or request URL',async()=>{
 const api=createTelegramClient(token,async url=>{throw new Error('Request failed: '+url);});
 await assert.rejects(()=>api('getMe'),e=>!e.message.includes(token)&&!e.message.includes('api.telegram.org'));
});
test('Setup refuses the wrong bot or an existing webhook before changing settings',async()=>{
 const calls=[];
 await assert.rejects(()=>configureBot(async method=>{calls.push(method);return {username:'another_bot'};},'https://weather.example/'));assert.deepEqual(calls,['getMe']);
 calls.length=0;
 await assert.rejects(()=>configureBot(async method=>{calls.push(method);return method==='getMe'?{username:'ObHavo_ECMWF_bot'}:{url:'https://existing.example/hook'};},'https://weather.example/'));assert.deepEqual(calls,['getMe','getWebhookInfo']);
});
