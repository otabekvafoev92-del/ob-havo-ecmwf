'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import type {Map as MapLibreMap,Marker,GeoJSONSource} from 'maplibre-gl';
// MapLibre 6 needs an explicit, bundled worker URL when used through Vite.
import mapWorkerURL from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import type {OmProtocolSettings} from '@openmeteo/weather-map-layer';
type ColorScale=OmProtocolSettings['colorScales'][string];
import {ArrowDown,ArrowUpRight,ChevronLeft,ChevronRight,Cloud,CloudFog,CloudLightning,CloudRain,CloudSnow,CloudSun,Droplets,Globe2,Layers,LocateFixed,MapPin,MoonStar,Mountain,Navigation,Pause,Play,RefreshCw,Sun,Thermometer,Wind,X} from 'lucide-react';
import type {Place} from '@/lib/weather';
import {boundaryLayerIDs,cityCamera,geographicStyle,normalizedViewBounds,shouldUpdateWeatherBounds,type ViewBounds} from '@/lib/map-display';
import {condition,fileURL,formatMapTime,loadMapPoint,mapLayers,nightGeoJSON,normalizeLongitude,precipitationPerHour,precipitationTypes,rowAtTime,SPATIAL_ROOT,stepHours,sunPosition,solarAltitude,timeIndex,validateMapMetadata,weatherLayerURL,type MapLayer,type MapMetadata,type MapPointData} from '@/lib/weather-map';

type OMModule=typeof import('@openmeteo/weather-map-layer');
type Engine=typeof import('maplibre-gl');
const emptyGeoJSON={type:'FeatureCollection' as const,features:[]};
const fmt=(v:number|null|undefined,decimals=1)=>v==null||!Number.isFinite(v)?'—':new Intl.NumberFormat('ru-RU',{maximumFractionDigits:decimals}).format(v);
const icons={sun:Sun,partly:CloudSun,cloud:Cloud,fog:CloudFog,rain:CloudRain,snow:CloudSnow,storm:CloudLightning};
const mapIcons=[CloudRain,CloudSnow,Cloud,Wind,Droplets,Thermometer];
const terrainAttribution='Terrain Tiles © <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noreferrer">Mapzen / AWS</a>';
let protocolInstalled=false;

export default function WeatherGlobe({place,timezone,onSelect,revision=0}:{place:Place;timezone:string;onSelect:(p:Place)=>void;revision?:number}){
 const container=useRef<HTMLDivElement>(null),panel=useRef<HTMLDivElement>(null);
 const map=useRef<MapLibreMap|null>(null),engine=useRef<Engine|null>(null),om=useRef<OMModule|null>(null);
 const marker=useRef<Marker|null>(null),sunMarker=useRef<Marker|null>(null),settings=useRef<OmProtocolSettings|null>(null);
 const metadataRef=useRef<MapMetadata|null>(null),pointRef=useRef<Place>(place);
 const durationByFile=useRef(new Map<string,number>()),slowFrame=useRef(false);
 const loadedBounds=useRef<ViewBounds|null>(null),viewportKey=useRef('');
 const [viewRevision,setViewRevision]=useState(0),[borders,setBorders]=useState(true);
 const [metadata,setMetadata]=useState<MapMetadata|null>(null),[metadataError,setMetadataError]=useState('');
 const [layer,setLayer]=useState<MapLayer>('precipitation'),[index,setIndex]=useState(0),[renderIndex,setRenderIndex]=useState(0);
 const [clouds,setClouds]=useState(false),[arrows,setArrows]=useState(false),[daylight,setDaylight]=useState(false);
 const [opacity,setOpacity]=useState(0.60),[mode,setMode]=useState<'globe'|'terrain'|'flat'>('flat');
 const [playing,setPlaying]=useState(false),[frameLoading,setFrameLoading]=useState(true),[frameError,setFrameError]=useState(''),[mapError,setMapError]=useState(''),[mapReady,setMapReady]=useState(false);
 const [refresh,setRefresh]=useState(0),[utc,setUtc]=useState(false),[details,setDetails]=useState(true);
 const [point,setPoint]=useState<Place>(place),[pointData,setPointData]=useState<MapPointData|null>(null),[pointLoading,setPointLoading]=useState(false),[pointError,setPointError]=useState('');
 const [sample,setSample]=useState<{value:number;direction?:number}|null>(null),[legend,setLegend]=useState<{gradient:string;min:number;max:number}|null>(null);
 const frames=useMemo(()=>metadata?.valid_times.filter(t=>Date.parse(t)>Date.parse(metadata.reference_time))||[],[metadata]);
 const frame=frames[renderIndex],chosen=frames[index];
 const tz=utc?'UTC':timezone;
 const selectedLayer=mapLayers.find(x=>x.key===layer)!;
 const isStale=metadata&&Date.now()-Date.parse(metadata.reference_time)>36*3600000;
 const pointRow=useMemo(()=>pointData&&frame?rowAtTime(pointData.rows,frame):null,[pointData,frame]);
 const weather=condition(pointRow?.weather_code),WeatherIcon=icons[weather.icon as keyof typeof icons];
 const loadingFrame=frameLoading||renderIndex!==index;
 const sourceIDs=['weather-main','weather-clouds','weather-wind'];
 const sourceURLs=useRef<Record<string,string>>({});
 const pendingFrame=useRef(0);

 useEffect(()=>{const timer=setInterval(()=>setRefresh(v=>v+1),15*60*1000);return()=>clearInterval(timer);},[]);
 useEffect(()=>{const c=new AbortController();setMetadataError('');setPlaying(false);fetch(`${SPATIAL_ROOT}/latest.json`,{signal:AbortSignal.any([c.signal,AbortSignal.timeout(25000)]),cache:'no-store'}).then(async res=>{if(!res.ok)throw new Error('Не удалось загрузить расчёт ECMWF.');const d=validateMapMetadata(await res.json());metadataRef.current=d;for(const t of d.valid_times)durationByFile.current.set(fileURL(d,t),stepHours(d,t));setMetadata(d);const f=d.valid_times.filter(t=>Date.parse(t)>Date.parse(d.reference_time));const i=timeIndex(f);setIndex(i);setRenderIndex(i);}).catch(e=>{if(e.name!=='AbortError')setMetadataError(e.message);});return()=>c.abort();},[refresh,revision]);
 useEffect(()=>{const timer=setTimeout(()=>setRenderIndex(index),250);return()=>clearTimeout(timer);},[index]);
 useEffect(()=>{pointRef.current=point;},[point]);
 useEffect(()=>{setPoint(place);if(map.current&&mapReady)map.current.flyTo({center:[place.longitude,place.latitude],zoom:mode==='terrain'?6:mode==='flat'?8.8:2.2,pitch:mode==='terrain'?55:0,duration:1100});},[place.latitude,place.longitude,mapReady]);
 useEffect(()=>{const c=new AbortController();setPointData(null);setPointError('');setPointLoading(true);loadMapPoint(point.latitude,point.longitude,c.signal).then(setPointData).catch(e=>{if(e.name!=='AbortError')setPointError(e.message);}).finally(()=>{if(!c.signal.aborted)setPointLoading(false);});return()=>c.abort();},[point.latitude,point.longitude,refresh,revision]);

 useEffect(()=>{
  let stopped=false,resize:ResizeObserver|undefined,loadTimer:ReturnType<typeof setTimeout>|undefined;
  loadTimer=setTimeout(()=>{if(!stopped){setMapError('Карта не завершила загрузку за 30 секунд. Проверьте соединение и нажмите «Повторить».');setFrameLoading(false);setPlaying(false);}},30000);
  Promise.all([import('maplibre-gl'),import('@openmeteo/weather-map-layer')]).then(([ml,weatherModule])=>{
   if(stopped||!container.current)return;
   engine.current=ml;om.current=weatherModule;
   const ptypeColors:Array<[number,number,number,number]>=Array.from({length:256},()=>[0,0,0,0]);
   for(const p of precipitationTypes){const h=p.color.replace('#','');ptypeColors[p.code]=[parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16),0.95];}
   const ptypeScale:ColorScale={type:'breakpoint',unit:'',breakpoints:Array.from({length:256},(_,i)=>i),colors:ptypeColors};
   const config:OmProtocolSettings={...weatherModule.defaultOmProtocolSettings,maxStatesWithData:4,colorScales:{...weatherModule.defaultOmProtocolSettings.colorScales,precipitation_type:ptypeScale},postReadCallback:(_reader,data,state)=>{
    if(state.dataOptions.variable==='precipitation'&&data.values){
     const hours=durationByFile.current.get(state.omFileUrl.split('?')[0]);
     if(!hours)throw new Error('Не удалось определить шаг осадков.');
     for(let i=0;i<data.values.length;i++)data.values[i]=precipitationPerHour(data.values[i],hours);
     if(data.scaleFactor)data.scaleFactor*=hours;
    }
   }};
   settings.current=config;
   if(protocolInstalled)ml.removeProtocol('om');
   ml.addProtocol('om',(params,controller)=>weatherModule.omProtocol(params,controller,config));protocolInstalled=true;
   ml.setWorkerUrl(mapWorkerURL);
   ml.setWorkerCount(2);
   const m=new ml.Map({container:container.current,style:geographicStyle(),...cityCamera(pointRef.current),pixelRatio:Math.min(window.devicePixelRatio||1,1.5),attributionControl:{compact:true},maxZoom:15,maxPitch:75,canvasContextAttributes:{antialias:false}});
   map.current=m;
   const updateViewport=()=>{
    const b=m.getBounds();if(!b)return;
    const visible=normalizedViewBounds([b.getWest(),b.getSouth(),b.getEast(),b.getNorth()]);
    if(!shouldUpdateWeatherBounds(loadedBounds.current,visible))return;
    weatherModule.getProtocolInstance(config).stateByKey.clear();
    weatherModule.updateCurrentBounds(visible);
    const clipped=weatherModule.currentBounds;
    if(clipped){loadedBounds.current=[...clipped];viewportKey.current=clipped.map(v=>v.toFixed(4)).join(',');setViewRevision(v=>v+1);}
   };
   updateViewport();
   m.on('movestart',()=>setPlaying(false));m.on('moveend',updateViewport);
   m.addControl(new ml.NavigationControl({visualizePitch:true}),'bottom-right');
   if(panel.current)m.addControl(new ml.FullscreenControl({container:panel.current}),'bottom-right');
   m.on('load',()=>{
    if(stopped)return;
    clearTimeout(loadTimer);
    m.setSky({'sky-color':'#101d34','horizon-color':'#294c77','fog-color':'#0b1423','sky-horizon-blend':0.5,'horizon-fog-blend':0.5,'atmosphere-blend':['interpolate',['linear'],['zoom'],0,1,3,0]});
    m.addSource('elevation',{type:'raster-dem',tiles:['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],tileSize:256,encoding:'terrarium',maxzoom:12,attribution:terrainAttribution});
    m.addSource('night',{type:'geojson',data:emptyGeoJSON});m.addLayer({id:'night-shade',type:'fill',source:'night',paint:{'fill-color':'#020714','fill-opacity':['get','shade'],'fill-antialias':false}},'geography-outline');
    const el=document.createElement('div');el.className='map-pin-marker';el.innerHTML='<span></span>';const cityName=document.createElement('strong');cityName.textContent=pointRef.current.name;el.appendChild(cityName);
    marker.current=new ml.Marker({element:el}).setLngLat([pointRef.current.longitude,pointRef.current.latitude]).addTo(m);
    const sun=document.createElement('div');sun.className='map-sun-marker';sun.title='Точка, над которой солнце в зените';sun.setAttribute('aria-label',sun.title);sun.innerHTML='<span>☀</span>';
    sunMarker.current=new ml.Marker({element:sun}).setLngLat([0,0]).addTo(m);
    setMapReady(true);setMapError('');
   });
   m.on('click',e=>{setPlaying(false);setDetails(true);setPoint({name:'Выбранная точка',latitude:Math.max(-90,Math.min(90,e.lngLat.lat)),longitude:normalizeLongitude(e.lngLat.lng)});});
   let readyTimer:ReturnType<typeof setTimeout>|undefined;
   const checkWeatherReady=()=>{clearTimeout(readyTimer);readyTimer=setTimeout(()=>{if(stopped)return;if(m.getSource('weather-main')&&sourceIDs.filter(id=>m.getSource(id)).every(id=>m.isSourceLoaded(id))){setFrameLoading(false);if(slowFrame.current){slowFrame.current=false;setFrameError('');}}},50);};
   m.on('idle',checkWeatherReady);m.on('sourcedata',e=>{if(e.sourceId?.startsWith('weather-'))checkWeatherReady();});
   m.on('error',e=>{if(stopped)return;const id=(e as {sourceId?:string}).sourceId;if(id?.startsWith('weather-')){setFrameError('Не удалось загрузить погодный слой. Обновите карту или выберите другой срок.');setFrameLoading(false);setPlaying(false);}else if(id==='elevation'){setFrameError('Рельеф временно недоступен. Погодные слои можно смотреть на глобусе или в 2D.');}else{clearTimeout(loadTimer);setMapError(`Не удалось загрузить основу карты. ${e.error?.message||'Проверьте соединение и повторите.'}`);setFrameLoading(false);setPlaying(false);}});
   m.on('webglcontextlost',()=>{setMapError('Графический контекст потерян. Перезагрузите страницу, чтобы восстановить 3D-карту.');setPlaying(false);});
   resize=new ResizeObserver(()=>m.resize());resize.observe(container.current);
  }).catch(e=>{clearTimeout(loadTimer);if(!stopped){setMapError(`Не удалось запустить карту. ${e.message||''}`);setFrameLoading(false);}});
  return()=>{stopped=true;clearTimeout(loadTimer);resize?.disconnect();marker.current?.remove();sunMarker.current?.remove();map.current?.remove();map.current=null;setMapReady(false);};
 },[]);

 useEffect(()=>{
  const m=map.current,mod=om.current,config=settings.current;
  if(!mapReady||!m||!mod||!config||!metadata||!frame)return;
  const id=++pendingFrame.current;slowFrame.current=false;setFrameLoading(true);setFrameError('');setSample(null);
  const scopedURL=(varName:MapLayer,vector=false)=>weatherLayerURL(metadata,frame,varName,vector)+`&viewport=${encodeURIComponent(viewportKey.current)}`;
  const removeSource=(source:string)=>{if(m.getLayer(`${source}-layer`))m.removeLayer(`${source}-layer`);if(m.getSource(source))m.removeSource(source);delete sourceURLs.current[source];};
  const addRaster=(source:string,varName:MapLayer,alpha:number)=>{
   const url=scopedURL(varName);const previous=sourceURLs.current[source];
   if(m.getSource(source)){
    if(previous!==url)(m.getSource(source) as unknown as {setUrl:(url:string)=>void}).setUrl(url);
    m.setPaintProperty(`${source}-layer`,'raster-opacity',alpha);
    m.setPaintProperty(`${source}-layer`,'raster-resampling',varName==='precipitation_type'?'nearest':'linear');
   }else{
    m.addSource(source,{type:'raster',url,tileSize:512,maxzoom:6,attribution:'Weather © ECMWF / Open-Meteo · CC BY 4.0'});
    m.addLayer({id:`${source}-layer`,type:'raster',source,paint:{'raster-opacity':alpha,'raster-fade-duration':150,'raster-resampling':varName==='precipitation_type'?'nearest':'linear'}},'night-shade');
   }
   sourceURLs.current[source]=url;
  };
  try{
   addRaster('weather-main',layer,opacity);
   if(clouds&&layer!=='cloud_cover')addRaster('weather-clouds','cloud_cover',0.32);else removeSource('weather-clouds');
   if(arrows){
    const url=scopedURL('wind_u_component_10m',true);
    if(m.getSource('weather-wind')){if(sourceURLs.current['weather-wind']!==url)(m.getSource('weather-wind') as unknown as {setUrl:(url:string)=>void}).setUrl(url);}
    else{m.addSource('weather-wind',{type:'vector',url,maxzoom:6});m.addLayer({id:'weather-wind-layer',type:'line',source:'weather-wind','source-layer':'wind-arrows',paint:{'line-color':'#ecf6ff','line-width':1.25,'line-opacity':0.82}},'night-shade');}
    sourceURLs.current['weather-wind']=url;
   }else removeSource('weather-wind');
   const scale=mod.getColorScale(layer,true,config.colorScales);
   const min=scale.type==='breakpoint'?scale.breakpoints[0]:scale.min,max=scale.type==='breakpoint'?scale.breakpoints.at(-1)!:scale.max;
   const gradient=Array.from({length:16},(_,i)=>{const [r,g,b]=mod.getColor(scale,min+(max-min)*i/15);return `rgb(${r},${g},${b}) ${i/15*100}%`;}).join(',');
   setLegend({gradient:`linear-gradient(90deg,${gradient})`,min,max});
   if(sourceIDs.filter(source=>m.getSource(source)).every(source=>m.isSourceLoaded(source)))setFrameLoading(false);
  }catch(e){setFrameError((e as Error).message);setFrameLoading(false);setPlaying(false);}
  const timer=setTimeout(()=>{if(id===pendingFrame.current&&sourceIDs.filter(source=>m.getSource(source)).some(source=>!m.isSourceLoaded(source))){slowFrame.current=true;setFrameError('Загрузка слоя занимает больше времени. Повторите запрос, если карта осталась пустой.');setPlaying(false);}},45000);
  return()=>clearTimeout(timer);
 },[mapReady,metadata,frame,layer,clouds,arrows,refresh,viewRevision]);
 useEffect(()=>{if(mapReady&&map.current?.getLayer('weather-main-layer'))map.current.setPaintProperty('weather-main-layer','raster-opacity',opacity);},[opacity,mapReady]);
 useEffect(()=>{const m=map.current;if(!m||!mapReady||!frame)return;const solar=sunPosition(Date.parse(frame));if(sunMarker.current){sunMarker.current.setLngLat([solar.longitude,solar.latitude]);sunMarker.current.getElement().style.display=daylight?'':'none';}const source=m.getSource('night') as GeoJSONSource|undefined;source?.setData(daylight?nightGeoJSON(Date.parse(frame)):emptyGeoJSON);},[frame,daylight,mapReady]);
 useEffect(()=>{marker.current?.setLngLat([point.longitude,point.latitude]);const label=marker.current?.getElement().querySelector('strong');if(label)label.textContent=point.name==='Выбранная точка'?'':point.name;},[point.latitude,point.longitude,point.name,mapReady]);
 useEffect(()=>{if(!mapReady||!map.current)return;for(const id of boundaryLayerIDs)if(map.current.getLayer(id))map.current.setLayoutProperty(id,'visibility',borders?'visible':'none');},[borders,mapReady]);
 useEffect(()=>{let cancelled=false;setSample(null);if(!mapReady||frameLoading||frameError||!om.current||!sourceURLs.current['weather-main'])return;om.current.getValueFromLatLong(point.latitude,point.longitude,sourceURLs.current['weather-main'],map.current?.getZoom()).then(v=>{if(!cancelled&&Number.isFinite(v.value))setSample(v);}).catch(()=>{});return()=>{cancelled=true;};},[point.latitude,point.longitude,frameLoading,frameError,frame,layer,mapReady]);
 useEffect(()=>{if(!playing||frameLoading||renderIndex!==index||frameError||!mapReady)return;if(index>=frames.length-1){setPlaying(false);return;}const timer=setTimeout(()=>setIndex(v=>Math.min(frames.length-1,v+1)),2600);return()=>clearTimeout(timer);},[playing,frameLoading,renderIndex,index,frameError,mapReady,frames.length]);
 function changeMode(next:'globe'|'terrain'|'flat'){
  const m=map.current;if(!m||!mapReady)return;setMode(next);
  m.setProjection({type:next==='flat'?'mercator':'globe'});m.setTerrain(next==='terrain'?{source:'elevation',exaggeration:1.5}:null);
  m.flyTo({center:[point.longitude,next==='globe'?Math.max(-50,Math.min(50,point.latitude)):point.latitude],zoom:next==='globe'?1.55:next==='terrain'?9:8.8,pitch:next==='terrain'?56:0,bearing:0,duration:1400});
 }
 function step(delta:number){setPlaying(false);setIndex(v=>Math.max(0,Math.min(frames.length-1,v+delta)));}
 const ptypeLabel=sample&&layer==='precipitation_type'?(sample.value===0?'Без осадков':precipitationTypes.find(t=>t.code===Math.round(sample.value))?.label||'Нет данных'):null;
 const sun=frame?sunPosition(Date.parse(frame)):null;
 const DetailIcon=pointRow?.weather_code===0&&sun&&solarAltitude(point.latitude,point.longitude,sun)<0?MoonStar:WeatherIcon;
 return <section className="weather-world" ref={panel}>
  <div className="world-toolbar"><div><span className="number-label">КАРТА ПОГОДЫ</span><h2>Города и погода<span className="world-live">ECMWF IFS · 0.25°</span></h2></div><button className="world-refresh" onClick={()=>{setPlaying(false);setRefresh(v=>v+1);}} title="Обновить расчёт" aria-label="Обновить расчёт"><RefreshCw size={16}/></button></div>
  <div className="world-layers" aria-label="Слои погоды">{mapLayers.map((item,i)=>{const Icon=mapIcons[i];const available=!metadata||item.required.every(v=>metadata.variables.includes(v));return <button key={item.key} disabled={!available} title={available?item.label:'Нет в доступном расчёте'} className={item.key===layer?'selected':''} aria-pressed={item.key===layer} onClick={()=>{setPlaying(false);setLayer(item.key);}}><Icon size={15}/>{item.label}</button>;})}</div>
  <div className="globe-stage" aria-busy={loadingFrame}>
   <div className="globe-canvas" ref={container} aria-label="Карта погоды с названиями городов и административными границами"/>
   <div className="world-status"><span className={loadingFrame?'world-status-dot loading':'world-status-dot'}/>{metadataError?'Ошибка данных':loadingFrame?'Загружаем погодный слой…':frameError?'Проверьте загрузку слоя':'Прогноз ECMWF'}<span className="world-status-time">{chosen?formatMapTime(chosen,tz):'Загрузка…'}</span></div>
   <div className="world-mode"><button title="Показать выбранный город" aria-label="Приблизить город" onClick={()=>{const m=map.current;if(!m)return;setMode('flat');m.setTerrain(null);m.setProjection({type:'mercator'});m.flyTo({...cityCamera(point),zoom:10.4,duration:800});}}><LocateFixed size={15}/><span>К городу</span></button><button title="Вращаемый глобус" aria-label="Глобус" className={mode==='globe'?'selected':''} onClick={()=>changeMode('globe')}><Globe2 size={16}/><span>Глобус</span></button><button title="Приблизить рельеф выбранной точки" className={mode==='terrain'?'selected':''} onClick={()=>changeMode('terrain')}><Mountain size={16}/><span>3D рельеф</span></button><button title="Плоская карта" className={mode==='flat'?'selected':''} onClick={()=>changeMode('flat')}><Layers size={15}/><span>Карта</span></button></div>
   <div className="world-options"><label><input type="checkbox" checked={borders} onChange={e=>setBorders(e.target.checked)}/><MapPin size={14}/> Адм. границы</label><label><input type="checkbox" checked={clouds} onChange={e=>{setPlaying(false);setClouds(e.target.checked);}}/><Cloud size={14}/> Облака</label><label><input type="checkbox" checked={arrows} onChange={e=>{setPlaying(false);setArrows(e.target.checked);}}/><Wind size={14}/> Направление ветра</label><label><input type="checkbox" checked={daylight} onChange={e=>setDaylight(e.target.checked)}/><Sun size={14}/> Солнце и ночь</label><label className="world-opacity">Слой<input aria-label="Прозрачность погодного слоя" type="range" min="0.2" max="1" step="0.05" value={opacity} onChange={e=>setOpacity(Number(e.target.value))}/></label></div>
   {!mapReady&&!mapError&&<div className="world-map-loading"><Globe2 size={48}/><span>Открываем карту города…</span></div>}
   {(metadataError||mapError)&&<div className="world-map-error" role="alert"><Cloud size={30}/><h3>Карта пока недоступна</h3><p>{metadataError||mapError}</p><button onClick={()=>mapError?window.location.reload():setRefresh(v=>v+1)}>Повторить</button></div>}
   {frameError&&!mapError&&<div className="world-frame-error" role="alert">{frameError}<button onClick={()=>setRefresh(v=>v+1)}>Повторить <RefreshCw size={12}/></button></div>}
   {isStale&&<div className="world-stale">Расчёт старше 36 часов. Время расчёта указано под картой.</div>}
   <button className="world-details-toggle" aria-expanded={details} onClick={()=>setDetails(v=>!v)}><MapPin size={14}/>{details?'Скрыть карточку':'Погода в точке'}</button>
   {details&&<aside className="world-point-card"><div className="world-point-heading"><span><MapPin size={12}/> ПОГОДА В ТОЧКЕ</span><button aria-label="Скрыть карточку погоды" onClick={()=>setDetails(false)}><X size={14}/></button></div><h3>{point.name}</h3><p className="world-point-coordinates">{fmt(point.latitude,3)}°, {fmt(point.longitude,3)}° <button title="Приблизить эту точку" aria-label="Приблизить выбранную точку" onClick={()=>changeMode('terrain')}><LocateFixed size={13}/></button></p>
    {pointLoading?<div className="world-point-loading"><RefreshCw size={17} className="spinning"/> Получаем прогноз…</div>:pointError?<div className="world-point-error" role="alert">{pointError}<button onClick={()=>setRefresh(v=>v+1)}>Повторить</button></div>:pointRow?<><div className={'world-condition '+weather.icon}><div><strong>{fmt(pointRow.temperature_2m,0)}°</strong><span>{weather.label}</span></div><div className="weather-illustration"><DetailIcon size={55} strokeWidth={1.3}/>{weather.icon==='rain'&&Array.from({length:5},(_,i)=><i key={i} className="rain-streak" style={{left:8+i*10,animationDelay:`${i*.23}s`}}/>)}{weather.icon==='snow'&&Array.from({length:4},(_,i)=><i key={i} className="snow-speck" style={{left:10+i*11,animationDelay:`${i*.4}s`}}/>)}</div></div><div className="world-point-stats"><div><CloudRain size={14}/><span>Осадки</span><b>{fmt(pointRow.precipitation)} <small>мм/ч</small></b></div><div><Droplets size={14}/><span>Влажность</span><b>{fmt(pointRow.relative_humidity_2m,0)} <small>%</small></b></div><div><Wind size={14}/><span>Ветер</span><b>{fmt(pointRow.wind_speed_10m)} <small>м/с</small>{pointRow.wind_direction_10m!==null&&<Navigation size={11} style={{transform:`rotate(${pointRow.wind_direction_10m+135}deg)`}}/>}</b></div><div><Wind size={14}/><span>Порывы</span><b>{fmt(pointRow.wind_gusts_10m)} <small>м/с</small></b></div><div><Cloud size={14}/><span>Облачность</span><b>{fmt(pointRow.cloud_cover,0)} <small>%</small></b></div><div><ArrowDown size={14}/><span>Давление</span><b>{fmt(pointRow.pressure_msl,0)} <small>гПа</small></b></div></div></>:<p className="world-point-error">Для выбранного срока нет точечного прогноза.</p>}
    {sample&&!frameLoading&&<div className="world-exact-value"><span>Значение слоя в точке</span><b>{ptypeLabel||`${fmt(sample.value)} ${selectedLayer.unit}`}</b></div>}
    <button className="world-detail-link" onClick={()=>onSelect(point)}>Подробный прогноз <ArrowUpRight size={13}/></button><p className="world-point-note">Белые линии — страны и регионы. Голубые — доступные местные границы OSM. Контуры муниципалитетов есть не везде. Карточка — последний точечный прогноз.</p>
   </aside>}
   <div className="world-legend"><b>{selectedLayer.label} {selectedLayer.unit&&<span>· {selectedLayer.unit}</span>}</b>{layer==='precipitation_type'?<div className="world-type-legend">{precipitationTypes.map(t=><span key={t.code}><i style={{background:t.color}}/>{t.label}</span>)}</div>:legend?<><div className="world-color-bar" style={{background:legend.gradient}}/><div className="world-color-labels"><span>{fmt(legend.min,2)}</span><span>{fmt((legend.min+legend.max)/2)}</span><span>{fmt(legend.max)}+</span></div></>:<p>Загружаем шкалу…</p>}</div>
   <div className="world-map-hint">Перетаскивайте карту · Колесо: масштаб · Клик: погода</div>
  </div>
  <div className="world-timeline"><div className="world-timeline-top"><div className="world-playback"><button aria-label="Предыдущий срок" disabled={!frames.length||index===0} onClick={()=>step(-1)}><ChevronLeft size={17}/></button><button className="world-play" aria-label={playing?'Остановить анимацию':'Запустить анимацию прогноза'} onClick={()=>{if(index===frames.length-1)setIndex(0);setPlaying(v=>!v);}} disabled={!frames.length||!!metadataError||!!mapError}>{playing?<Pause size={17}/>:<Play size={17} fill="currentColor"/>}</button><button aria-label="Следующий срок" disabled={!frames.length||index===frames.length-1} onClick={()=>step(1)}><ChevronRight size={17}/></button><span>{playing?'Анимация прогноза':'Шкала прогноза'}</span></div><div className="world-time-label">{chosen?formatMapTime(chosen,tz):'—'} <span>{tz}</span></div><div className="world-time-actions"><button onClick={()=>{setPlaying(false);setIndex(timeIndex(frames));}}>Сейчас</button><button className={utc?'selected':''} onClick={()=>setUtc(v=>!v)}>{utc?'UTC':'Местное время'}</button></div></div><input className="world-time-range" aria-label="Время прогноза на карте" type="range" min="0" max={Math.max(0,frames.length-1)} step="1" value={Math.min(index,Math.max(0,frames.length-1))} disabled={!frames.length} onChange={e=>{setPlaying(false);setIndex(Number(e.target.value));}}/><div className="world-day-ticks">{frames.length>0&&[...new Set([0,Math.floor((frames.length-1)/4),Math.floor((frames.length-1)/2),Math.floor((frames.length-1)*3/4),frames.length-1])].map(i=><button key={i} onClick={()=>{setPlaying(false);setIndex(i);}}>{formatMapTime(frames[i],tz)}</button>)}</div></div>
  <div className="world-source-note"><span><span className="live-dot"/> {metadata?`Расчёт ${formatMapTime(metadata.reference_time,'UTC')} UTC`:'Получаем расчёт ECMWF…'}</span><span>ECMWF через Open-Meteo · Автообновление 15 мин · Шаг {metadata&&frame?stepHours(metadata,frame):'3–6'} ч</span><p>Анимация показывает прогноз, а не спутниковую трансляцию. Осадки — средняя интенсивность за предыдущий шаг модели. Положение солнца рассчитано для выбранного времени.</p></div>
 </section>;
}
