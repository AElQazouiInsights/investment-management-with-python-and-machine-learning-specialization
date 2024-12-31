var fe=Object.defineProperty,l=(e,t)=>fe(e,"name",{value:t,configurable:!0}),B=(e=>typeof require<"u"?require:typeof Proxy<"u"?new Proxy(e,{get:(t,i)=>(typeof require<"u"?require:t)[i]}):e)(function(e){if(typeof require<"u")return require.apply(this,arguments);throw new Error('Dynamic require of "'+e+'" is not supported')});function H(e){return!isNaN(parseFloat(e))&&isFinite(e)}l(H,"_isNumber");function h(e){return e.charAt(0).toUpperCase()+e.substring(1)}l(h,"_capitalize");function N(e){return function(){return this[e]}}l(N,"_getter");var F=["isConstructor","isEval","isNative","isToplevel"],O=["columnNumber","lineNumber"],k=["fileName","functionName","source"],pe=["args"],me=["evalOrigin"],_=F.concat(O,k,pe,me);function m(e){if(e)for(var t=0;t<_.length;t++)e[_[t]]!==void 0&&this["set"+h(_[t])](e[_[t]])}l(m,"StackFrame");m.prototype={getArgs:function(){return this.args},setArgs:function(e){if(Object.prototype.toString.call(e)!=="[object Array]")throw new TypeError("Args must be an Array");this.args=e},getEvalOrigin:function(){return this.evalOrigin},setEvalOrigin:function(e){if(e instanceof m)this.evalOrigin=e;else if(e instanceof Object)this.evalOrigin=new m(e);else throw new TypeError("Eval Origin must be an Object or StackFrame")},toString:function(){var e=this.getFileName()||"",t=this.getLineNumber()||"",i=this.getColumnNumber()||"",n=this.getFunctionName()||"";return this.getIsEval()?e?"[eval] ("+e+":"+t+":"+i+")":"[eval]:"+t+":"+i:n?n+" ("+e+":"+t+":"+i+")":e+":"+t+":"+i}};m.fromString=l(function(e){var t=e.indexOf("("),i=e.lastIndexOf(")"),n=e.substring(0,t),a=e.substring(t+1,i).split(","),r=e.substring(i+1);if(r.indexOf("@")===0)var o=/@(.+?)(?::(\d+))?(?::(\d+))?$/.exec(r,""),s=o[1],c=o[2],u=o[3];return new m({functionName:n,args:a||void 0,fileName:s,lineNumber:c||void 0,columnNumber:u||void 0})},"StackFrame$$fromString");for(g=0;g<F.length;g++)m.prototype["get"+h(F[g])]=N(F[g]),m.prototype["set"+h(F[g])]=function(e){return function(t){this[e]=!!t}}(F[g]);var g;for(v=0;v<O.length;v++)m.prototype["get"+h(O[v])]=N(O[v]),m.prototype["set"+h(O[v])]=function(e){return function(t){if(!H(t))throw new TypeError(e+" must be a Number");this[e]=Number(t)}}(O[v]);var v;for(b=0;b<k.length;b++)m.prototype["get"+h(k[b])]=N(k[b]),m.prototype["set"+h(k[b])]=function(e){return function(t){this[e]=String(t)}}(k[b]);var b,R=m;function W(){var e=/^\s*at .*(\S+:\d+|\(native\))/m,t=/^(eval@)?(\[native code])?$/;return{parse:l(function(i){if(i.stack&&i.stack.match(e))return this.parseV8OrIE(i);if(i.stack)return this.parseFFOrSafari(i);throw new Error("Cannot parse given Error object")},"ErrorStackParser$$parse"),extractLocation:l(function(i){if(i.indexOf(":")===-1)return[i];var n=/(.+?)(?::(\d+))?(?::(\d+))?$/,a=n.exec(i.replace(/[()]/g,""));return[a[1],a[2]||void 0,a[3]||void 0]},"ErrorStackParser$$extractLocation"),parseV8OrIE:l(function(i){var n=i.stack.split(`
`).filter(function(a){return!!a.match(e)},this);return n.map(function(a){a.indexOf("(eval ")>-1&&(a=a.replace(/eval code/g,"eval").replace(/(\(eval at [^()]*)|(,.*$)/g,""));var r=a.replace(/^\s+/,"").replace(/\(eval code/g,"(").replace(/^.*?\s+/,""),o=r.match(/ (\(.+\)$)/);r=o?r.replace(o[0],""):r;var s=this.extractLocation(o?o[1]:r),c=o&&r||void 0,u=["eval","<anonymous>"].indexOf(s[0])>-1?void 0:s[0];return new R({functionName:c,fileName:u,lineNumber:s[1],columnNumber:s[2],source:a})},this)},"ErrorStackParser$$parseV8OrIE"),parseFFOrSafari:l(function(i){var n=i.stack.split(`
`).filter(function(a){return!a.match(t)},this);return n.map(function(a){if(a.indexOf(" > eval")>-1&&(a=a.replace(/ line (\d+)(?: > eval line \d+)* > eval:\d+:\d+/g,":$1")),a.indexOf("@")===-1&&a.indexOf(":")===-1)return new R({functionName:a});var r=/((.*".+"[^@]*)?[^@]*)(?:@)/,o=a.match(r),s=o&&o[1]?o[1]:void 0,c=this.extractLocation(a.replace(r,""));return new R({functionName:s,fileName:c[0],lineNumber:c[1],columnNumber:c[2],source:a})},this)},"ErrorStackParser$$parseFFOrSafari")}}l(W,"ErrorStackParser");var ye=new W,he=ye,y=typeof process=="object"&&typeof process.versions=="object"&&typeof process.versions.node=="string"&&!process.browser,q=y&&typeof module<"u"&&typeof module.exports<"u"&&typeof B<"u"&&typeof __dirname<"u",we=y&&!q,ge=typeof Deno<"u",z=!y&&!ge,ve=z&&typeof window=="object"&&typeof document=="object"&&typeof document.createElement=="function"&&"sessionStorage"in window&&typeof importScripts!="function",be=z&&typeof importScripts=="function"&&typeof self=="object";typeof navigator=="object"&&typeof navigator.userAgent=="string"&&navigator.userAgent.indexOf("Chrome")==-1&&navigator.userAgent.indexOf("Safari")>-1;var V,A,Y,M,D;async function $(){if(!y||(V=(await import("./__vite-browser-external-9wXp6ZBx.js")).default,M=await import("./__vite-browser-external-9wXp6ZBx.js"),D=await import("./__vite-browser-external-9wXp6ZBx.js"),Y=(await import("./__vite-browser-external-9wXp6ZBx.js")).default,A=await import("./__vite-browser-external-9wXp6ZBx.js"),I=A.sep,typeof B<"u"))return;let e=M,t=await import("./__vite-browser-external-9wXp6ZBx.js"),i=await import("./__vite-browser-external-9wXp6ZBx.js"),n=await import("./__vite-browser-external-9wXp6ZBx.js"),a={fs:e,crypto:t,ws:i,child_process:n};globalThis.require=function(r){return a[r]}}l($,"initNodeModules");function K(e,t){return A.resolve(t||".",e)}l(K,"node_resolvePath");function J(e,t){return t===void 0&&(t=location),new URL(e,t).toString()}l(J,"browser_resolvePath");var T;y?T=K:T=J;var I;y||(I="/");function G(e,t){return e.startsWith("file://")&&(e=e.slice(7)),e.includes("://")?{response:fetch(e)}:{binary:D.readFile(e).then(i=>new Uint8Array(i.buffer,i.byteOffset,i.byteLength))}}l(G,"node_getBinaryResponse");function Q(e,t){let i=new URL(e,location);return{response:fetch(i,t?{integrity:t}:{})}}l(Q,"browser_getBinaryResponse");var L;y?L=G:L=Q;async function X(e,t){let{response:i,binary:n}=L(e,t);if(n)return n;let a=await i;if(!a.ok)throw new Error(`Failed to load '${e}': request failed.`);return new Uint8Array(await a.arrayBuffer())}l(X,"loadBinaryFile");var x;if(ve)x=l(async e=>await import(e),"loadScript");else if(be)x=l(async e=>{try{globalThis.importScripts(e)}catch(t){if(t instanceof TypeError)await import(e);else throw t}},"loadScript");else if(y)x=Z;else throw new Error("Cannot determine runtime environment");async function Z(e){e.startsWith("file://")&&(e=e.slice(7)),e.includes("://")?Y.runInThisContext(await(await fetch(e)).text()):await import(V.pathToFileURL(e).href)}l(Z,"nodeLoadScript");async function ee(e){if(y){await $();let t=await D.readFile(e,{encoding:"utf8"});return JSON.parse(t)}else return await(await fetch(e)).json()}l(ee,"loadLockFile");async function te(){if(q)return __dirname;let e;try{throw new Error}catch(n){e=n}let t=he.parse(e)[0].fileName;if(y&&!t.startsWith("file://")&&(t=`file://${t}`),we){let n=await import("./__vite-browser-external-9wXp6ZBx.js");return(await import("./__vite-browser-external-9wXp6ZBx.js")).fileURLToPath(n.dirname(t))}let i=t.lastIndexOf(I);if(i===-1)throw new Error("Could not extract indexURL path from pyodide module location");return t.slice(0,i)}l(te,"calculateDirname");function re(e){let t=e.FS,i=e.FS.filesystems.MEMFS,n=e.PATH,a={DIR_MODE:16895,FILE_MODE:33279,mount:function(r){if(!r.opts.fileSystemHandle)throw new Error("opts.fileSystemHandle is required");return i.mount.apply(null,arguments)},syncfs:async(r,o,s)=>{try{let c=a.getLocalSet(r),u=await a.getRemoteSet(r),d=o?u:c,p=o?c:u;await a.reconcile(r,d,p),s(null)}catch(c){s(c)}},getLocalSet:r=>{let o=Object.create(null);function s(d){return d!=="."&&d!==".."}l(s,"isRealDir");function c(d){return p=>n.join2(d,p)}l(c,"toAbsolute");let u=t.readdir(r.mountpoint).filter(s).map(c(r.mountpoint));for(;u.length;){let d=u.pop(),p=t.stat(d);t.isDir(p.mode)&&u.push.apply(u,t.readdir(d).filter(s).map(c(d))),o[d]={timestamp:p.mtime,mode:p.mode}}return{type:"local",entries:o}},getRemoteSet:async r=>{let o=Object.create(null),s=await Ee(r.opts.fileSystemHandle);for(let[c,u]of s)c!=="."&&(o[n.join2(r.mountpoint,c)]={timestamp:u.kind==="file"?(await u.getFile()).lastModifiedDate:new Date,mode:u.kind==="file"?a.FILE_MODE:a.DIR_MODE});return{type:"remote",entries:o,handles:s}},loadLocalEntry:r=>{let o=t.lookupPath(r).node,s=t.stat(r);if(t.isDir(s.mode))return{timestamp:s.mtime,mode:s.mode};if(t.isFile(s.mode))return o.contents=i.getFileDataAsTypedArray(o),{timestamp:s.mtime,mode:s.mode,contents:o.contents};throw new Error("node type not supported")},storeLocalEntry:(r,o)=>{if(t.isDir(o.mode))t.mkdirTree(r,o.mode);else if(t.isFile(o.mode))t.writeFile(r,o.contents,{canOwn:!0});else throw new Error("node type not supported");t.chmod(r,o.mode),t.utime(r,o.timestamp,o.timestamp)},removeLocalEntry:r=>{var o=t.stat(r);t.isDir(o.mode)?t.rmdir(r):t.isFile(o.mode)&&t.unlink(r)},loadRemoteEntry:async r=>{if(r.kind==="file"){let o=await r.getFile();return{contents:new Uint8Array(await o.arrayBuffer()),mode:a.FILE_MODE,timestamp:o.lastModifiedDate}}else{if(r.kind==="directory")return{mode:a.DIR_MODE,timestamp:new Date};throw new Error("unknown kind: "+r.kind)}},storeRemoteEntry:async(r,o,s)=>{let c=r.get(n.dirname(o)),u=t.isFile(s.mode)?await c.getFileHandle(n.basename(o),{create:!0}):await c.getDirectoryHandle(n.basename(o),{create:!0});if(u.kind==="file"){let d=await u.createWritable();await d.write(s.contents),await d.close()}r.set(o,u)},removeRemoteEntry:async(r,o)=>{await r.get(n.dirname(o)).removeEntry(n.basename(o)),r.delete(o)},reconcile:async(r,o,s)=>{let c=0,u=[];Object.keys(o.entries).forEach(function(f){let w=o.entries[f],S=s.entries[f];(!S||t.isFile(w.mode)&&w.timestamp.getTime()>S.timestamp.getTime())&&(u.push(f),c++)}),u.sort();let d=[];if(Object.keys(s.entries).forEach(function(f){o.entries[f]||(d.push(f),c++)}),d.sort().reverse(),!c)return;let p=o.type==="remote"?o.handles:s.handles;for(let f of u){let w=n.normalize(f.replace(r.mountpoint,"/")).substring(1);if(s.type==="local"){let S=p.get(w),de=await a.loadRemoteEntry(S);a.storeLocalEntry(f,de)}else{let S=a.loadLocalEntry(f);await a.storeRemoteEntry(p,w,S)}}for(let f of d)if(s.type==="local")a.removeLocalEntry(f);else{let w=n.normalize(f.replace(r.mountpoint,"/")).substring(1);await a.removeRemoteEntry(p,w)}}};e.FS.filesystems.NATIVEFS_ASYNC=a}l(re,"initializeNativeFS");var Ee=l(async e=>{let t=[];async function i(a){for await(let r of a.values())t.push(r),r.kind==="directory"&&await i(r)}l(i,"collect"),await i(e);let n=new Map;n.set(".",e);for(let a of t){let r=(await e.resolve(a)).join("/");n.set(r,a)}return n},"getFsHandles");function ie(e){let t={noImageDecoding:!0,noAudioDecoding:!0,noWasmDecoding:!1,preRun:le(e),quit(i,n){throw t.exited={status:i,toThrow:n},n},print:e.stdout,printErr:e.stderr,arguments:e.args,API:{config:e},locateFile:i=>e.indexURL+i,instantiateWasm:ce(e.indexURL)};return t}l(ie,"createSettings");function ne(e){return function(t){let i="/";try{t.FS.mkdirTree(e)}catch(n){console.error(`Error occurred while making a home directory '${e}':`),console.error(n),console.error(`Using '${i}' for a home directory instead`),e=i}t.FS.chdir(e)}}l(ne,"createHomeDirectory");function oe(e){return function(t){Object.assign(t.ENV,e)}}l(oe,"setEnvironment");function ae(e){return t=>{for(let i of e)t.FS.mkdirTree(i),t.FS.mount(t.FS.filesystems.NODEFS,{root:i},i)}}l(ae,"mountLocalDirectories");function se(e){let t=X(e);return i=>{let n=i._py_version_major(),a=i._py_version_minor();i.FS.mkdirTree("/lib"),i.FS.mkdirTree(`/lib/python${n}.${a}/site-packages`),i.addRunDependency("install-stdlib"),t.then(r=>{i.FS.writeFile(`/lib/python${n}${a}.zip`,r)}).catch(r=>{console.error("Error occurred while installing the standard library:"),console.error(r)}).finally(()=>{i.removeRunDependency("install-stdlib")})}}l(se,"installStdlib");function le(e){let t;return e.stdLibURL!=null?t=e.stdLibURL:t=e.indexURL+"python_stdlib.zip",[se(t),ne(e.env.HOME),oe(e.env),ae(e._node_mounts),re]}l(le,"getFileSystemInitializationFuncs");function ce(e){let{binary:t,response:i}=L(e+"pyodide.asm.wasm");return function(n,a){return async function(){try{let r;i?r=await WebAssembly.instantiateStreaming(i,n):r=await WebAssembly.instantiate(await t,n);let{instance:o,module:s}=r;typeof WasmOffsetConverter<"u"&&(wasmOffsetConverter=new WasmOffsetConverter(wasmBinary,s)),a(o,s)}catch(r){console.warn("wasm instantiation failed!"),console.warn(r)}}(),{}}}l(ce,"getInstantiateWasmFunc");var j="0.26.4";async function ue(e={}){var t,i;await $();let n=e.indexURL||await te();n=T(n),n.endsWith("/")||(n+="/"),e.indexURL=n;let a={fullStdLib:!1,jsglobals:globalThis,stdin:globalThis.prompt?globalThis.prompt:void 0,lockFileURL:n+"pyodide-lock.json",args:[],_node_mounts:[],env:{},packageCacheDir:n,packages:[],enableRunUntilComplete:!1,checkAPIVersion:!0},r=Object.assign(a,e);(t=r.env).HOME??(t.HOME="/home/pyodide"),(i=r.env).PYTHONINSPECT??(i.PYTHONINSPECT="1");let o=ie(r),s=o.API;if(s.lockFilePromise=ee(r.lockFileURL),typeof _createPyodideModule!="function"){let f=`${r.indexURL}pyodide.asm.js`;await x(f)}let c;if(e._loadSnapshot){let f=await e._loadSnapshot;ArrayBuffer.isView(f)?c=f:c=new Uint8Array(f),o.noInitialRun=!0,o.INITIAL_MEMORY=c.length}let u=await _createPyodideModule(o);if(o.exited)throw o.exited.toThrow;if(e.pyproxyToStringRepr&&s.setPyProxyToStringMethod(!0),s.version!==j&&r.checkAPIVersion)throw new Error(`Pyodide version does not match: '${j}' <==> '${s.version}'. If you updated the Pyodide version, make sure you also updated the 'indexURL' parameter passed to loadPyodide.`);u.locateFile=f=>{throw new Error("Didn't expect to load any more file_packager files!")};let d;c&&(d=s.restoreSnapshot(c));let p=s.finalizeBootstrap(d);return s.sys.path.insert(0,s.config.env.HOME),p.version.includes("dev")||s.setCdnUrl(`https://cdn.jsdelivr.net/pyodide/v${p.version}/full/`),s._pyodide.set_excepthook(),await s.packageIndexReady,s.initializeStreams(r.stdin,r.stdout,r.stderr),p}l(ue,"loadPyodide");const E=await ue({indexURL:"https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"}),U=new TextDecoder;let P=null,C=null;const Se=[{url:"/assets/PortfolioOptimizationKit.py",path:"/assets/PortfolioOptimizationKit.py",type:"text"},{url:"/assets/data/Portfolios_Formed_on_ME_monthly_EW.csv",path:"/assets/data/Portfolios_Formed_on_ME_monthly_EW.csv",type:"text"},{url:"/assets/data/edhec-hedgefundindices.csv",path:"/assets/data/edhec-hedgefundindices.csv",type:"text"}];try{await Promise.all(Se.map(async e=>{const t=await fetch(e.url);if(!t.ok)throw new Error(`Failed to fetch ${e.url}`);const i=await t.text(),n=e.path.split("/").slice(0,-1).join("/");n&&E.FS.mkdirTree(n),E.FS.writeFile(e.path,i)}))}catch(e){console.error("Error mounting files:",e)}onmessage=async e=>{if(e.data.inputBuffer&&e.data.waitBuffer&&e.data.interruptBuffer){P=new Uint8Array(e.data.inputBuffer),C=new Int32Array(e.data.waitBuffer),new Uint8Array(e.data.interruptBuffer);return}const{id:t,code:i}=e.data;E.setStdout({write:n=>(postMessage({id:t,output:U.decode(n)}),n.length)}),E.setStdin({stdin:()=>{postMessage({id:t,input:!0}),Atomics.wait(C,0,0);const n=new Uint8Array(Atomics.load(P,0));for(let r=0;r<n.length;r++)n[r]=Atomics.load(P,r+1);const a=U.decode(n);return postMessage({id:t,output:`${a}
`}),a}});try{await E.loadPackage(["pandas","numpy","scipy","statsmodels","matplotlib"]),E.runPython(`
      import sys
      sys.path.append('/assets')
    `),await E.runPythonAsync(i)}catch(n){postMessage({id:t,output:n.message})}finally{postMessage({id:t,done:!0})}};postMessage({ready:!0});
