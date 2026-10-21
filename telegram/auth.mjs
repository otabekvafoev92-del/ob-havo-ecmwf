import {createHmac,timingSafeEqual} from 'node:crypto';

const hmac=(key,value)=>createHmac('sha256',key).update(value).digest();
export function equalSecrets(a,b){
 const x=Buffer.from(a||''),y=Buffer.from(b||'');
 return x.length>0&&x.length===y.length&&timingSafeEqual(x,y);
}
export function allowedUsers(value=''){
 return new Set(value.split(',').map(s=>s.trim()).filter(s=>/^[1-9]\d{0,15}$/.test(s)));
}
export function validateInitData(raw,token,now=Date.now()){
 if(!token||typeof raw!=='string'||raw.length>16384)throw new Error('Не удалось проверить вход Telegram.');
 const params=new URLSearchParams(raw),keys=[...params.keys()];
 if(new Set(keys).size!==keys.length)throw new Error('Повторяющиеся параметры входа.');
 const hash=params.get('hash')||'';
 if(!/^[a-f0-9]{64}$/i.test(hash))throw new Error('Некорректная подпись Telegram.');
 params.delete('hash');
 const check=[...params].sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,v])=>`${k}=${v}`).join('\n');
 const expected=hmac(hmac('WebAppData',token),check).toString('hex');
 if(!equalSecrets(hash.toLowerCase(),expected))throw new Error('Подпись Telegram не совпадает.');
 const date=Number(params.get('auth_date'))*1000;
 if(!Number.isFinite(date)||date>now+30000||now-date>10*60*1000)throw new Error('Срок входа истёк. Откройте приложение заново через бота.');
 let user;try{user=JSON.parse(params.get('user')||'null');}catch{throw new Error('Некорректный профиль Telegram.');}
 if(!Number.isSafeInteger(user?.id)||user.id<=0||user.is_bot)throw new Error('Некорректный пользователь Telegram.');
 return user;
}
export function issueSession(userId,secret,now=Date.now()){
 const payload=Buffer.from(JSON.stringify({id:String(userId),exp:now+12*3600000})).toString('base64url');
 return `${payload}.${hmac(secret,payload).toString('base64url')}`;
}
export function readSession(value,secret,users,now=Date.now()){
 try{
  if(!value||value.length>1024||!secret)return null;
  const [payload,signature,...extra]=value.split('.');
  if(extra.length||!equalSecrets(signature,hmac(secret,payload).toString('base64url')))return null;
  const data=JSON.parse(Buffer.from(payload,'base64url').toString());
  return Number.isFinite(data.exp)&&data.exp>now&&data.exp<=now+12*3600000&&users.has(data.id)?data.id:null;
 }catch{return null;}
}
export function cookieValue(header,name){
 const part=(header||'').split(';').map(s=>s.trim()).find(s=>s.startsWith(`${name}=`));
 return part?.slice(name.length+1)||'';
}
