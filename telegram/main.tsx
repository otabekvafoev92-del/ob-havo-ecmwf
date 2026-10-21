import {createRoot} from 'react-dom/client';
import Home from '../app/page';
import '../app/globals.css';
import './telegram.css';

type WebApp={ready:()=>void;expand:()=>void;setHeaderColor?:(color:string)=>void;setBackgroundColor?:(color:string)=>void};
const telegram=(window as unknown as {Telegram?:{WebApp?:WebApp}}).Telegram?.WebApp;
telegram?.ready();telegram?.expand();telegram?.setHeaderColor?.('#102039');telegram?.setBackgroundColor?.('#f7f8fb');
createRoot(document.getElementById('root')!).render(<><div className="telegram-title"><b>Моя погода ECMWF</b><span>Личное приложение</span></div><Home/></>);
