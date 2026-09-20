import {pipeline,env} from './vendor/transformers.min.js';
import './discovery.js';
const D=globalThis.GoldDiscovery;
env.allowRemoteModels=false;
env.useBrowserCache=false; // Assets already ship with the extension; no duplicate CacheStorage copy.
env.localModelPath=new URL('./models/',import.meta.url).href;
env.backends.onnx.wasm.wasmPaths=new URL('./vendor/',import.meta.url).href;
env.backends.onnx.wasm.numThreads=1;
env.backends.onnx.wasm.proxy=false;
let modelPromise,prototypes,prototypesPromise,run=0;
async function embed(texts){
  const model=await (modelPromise ||= pipeline('feature-extraction','Xenova/all-MiniLM-L6-v2',{quantized:true}));
  const output=await model(texts,{pooling:'mean',normalize:true});return output.tolist();
}
async function init(){
  if(prototypes)return;
  await (prototypesPromise ||= (async()=>{const result={};for(const [label,texts] of Object.entries(D.descriptions))result[label]=await embed(texts);prototypes=result;})());
}
self.onmessage=async({data})=>{
  const {type,id}=data;
  if(type==='cancel'){run++;return;}
  try{
    if(type==='query'){const [vector]=await embed([data.query]);postMessage({type:'query',id,vector});return;}
    if(type==='index'){
      const token=++run;await init();let batch=[];
      for(let i=0;i<data.posts.length;i++){
        if(token!==run)return;
        const p=data.posts[i],parts=D.chunks(D.text(p));let vectors=[];
        for(let j=0;j<parts.length;j+=8){if(token!==run)return;vectors.push(...await embed(parts.slice(j,j+8)));}
        batch.push({key:p.key,fingerprint:D.fingerprint(p),vectors,suggestions:D.suggestions(p,vectors,prototypes)});
        if(batch.length===16||i===data.posts.length-1){postMessage({type:'batch',id,records:batch,done:i+1,total:data.posts.length});batch=[];}
      }
      postMessage({type:'complete',id});
    }
  }catch(error){modelPromise=null;prototypesPromise=null;postMessage({type:'error',id,requestType:type,error:error.message});}
};
