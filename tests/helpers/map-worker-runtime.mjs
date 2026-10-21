// Run the emitted worker's message protocol without a browser or WebGL.
import {parentPort,workerData} from 'node:worker_threads';
import {pathToFileURL} from 'node:url';
class Scope extends EventTarget {
 postMessage(data){parentPort.postMessage(data);}
}
globalThis.WorkerGlobalScope=Scope;
// These browser constructors are only used in instanceof checks for GeoJSON.
globalThis.ImageData=class ImageData {};
globalThis.ImageBitmap=class ImageBitmap {};
globalThis.self=new Scope();
globalThis.location={origin:'https://worker-test.invalid',href:'https://worker-test.invalid/'};
self.location=location;
parentPort.on('message',data=>self.dispatchEvent(new MessageEvent('message',{data})));
await import(pathToFileURL(workerData.path).href);
if(!self.worker)throw new Error('MapLibre worker did not initialize');
parentPort.postMessage({type:'ready'});
