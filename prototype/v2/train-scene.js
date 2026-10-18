/* Procedural illustration; Three r170 bindings are supplied immediately above by build_v2.py. */
window.TrainScene = (() => {
  function mount(container, options) {
    let counts = options.counts || {}, selected = options.selected, hovered = null, disposed = false;
    const regions = options.regions || [], byId = new Map(regions.map(r => [r.id,r]));
    const root = document.createElement('div'); root.className = 'ts-scene';
    root.innerHTML = `<style>
.ts-scene{position:relative;width:100%;height:100%;min-height:240px;overflow:hidden;background:radial-gradient(ellipse at 50% 65%,#edf2f3 0%,#f8fafb 65%,#fff 100%);isolation:isolate}.ts-scene canvas{display:block;width:100%;height:100%;touch-action:none;cursor:grab}.ts-scene canvas:active{cursor:grabbing}.ts-scene .ts-tip{position:absolute;z-index:3;pointer-events:none;max-width:270px;padding:9px 12px;border:1px solid #dce2e6;border-radius:6px;background:#fff;color:#1e2a33;box-shadow:0 3px 14px #142d3620;font:12px/1.5 'Segoe UI',sans-serif}.ts-scene .ts-hint{position:absolute;bottom:12px;left:16px;color:#687983;font:12px 'Segoe UI',sans-serif;pointer-events:none}.ts-scene .ts-fallback{width:100%;height:100%;display:none}.ts-scene.ts-failed .ts-fallback{display:block}.ts-scene.ts-failed canvas{display:none}.ts-scene .ts-fallback [data-region]{cursor:pointer;stroke:#60727b;stroke-width:1.2;transition:fill .12s}.ts-scene .ts-fallback [data-region].ts-active{fill:#0f6e74!important;stroke:#08494e}.ts-scene .ts-fallback [data-region].ts-hover{stroke:#0f6e74;stroke-width:3}.ts-scene .ts-fallback [data-region]:focus{outline:none;stroke:#2563eb;stroke-width:3}@media(prefers-reduced-motion:reduce){.ts-scene .ts-fallback [data-region]{transition:none}}@media print{.ts-scene canvas,.ts-scene .ts-hint,.ts-scene .ts-tip{display:none!important}.ts-scene .ts-fallback{display:block!important}}
</style><div class="ts-tip" hidden></div><span class="ts-hint">Drag to rotate · select a system to explore</span>`;
    container.append(root);
    const tip = root.querySelector('.ts-tip'), hint = root.querySelector('.ts-hint');
    const svgNS='http://www.w3.org/2000/svg';
    const svg=document.createElementNS(svgNS,'svg'); svg.classList.add('ts-fallback');svg.setAttribute('viewBox','0 0 900 340');svg.setAttribute('role','img');svg.setAttribute('aria-label','Train systems, illustrative side elevation');
    const title=document.createElementNS(svgNS,'title');title.textContent='Train systems — illustrative side elevation';svg.append(title);
    function svgShape(id,d,fill){const p=document.createElementNS(svgNS,'path');p.setAttribute('d',d);p.setAttribute('fill',fill);p.dataset.region=id;p.setAttribute('tabindex','0');p.setAttribute('role','button');p.setAttribute('aria-label',byId.get(id)?.label||id);p.addEventListener('pointerenter',e=>showTip(id,e));p.addEventListener('pointermove',e=>positionTip(e));p.addEventListener('pointerleave',()=>setHover(null));p.addEventListener('focus',()=>{setHover(id);tip.hidden=true;});p.addEventListener('blur',()=>setHover(null));p.addEventListener('click',()=>options.onSelect?.(id));p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();options.onSelect?.(id);}});svg.append(p);}
    svgShape('carbody','M60 192 L76 135 Q80 124 98 124 H425 V226 H55 Z M448 124 H803 Q828 124 844 153 L856 226 H448 Z','#e6e9eb');
    svgShape('interiors','M103 143 H177 V177 H103 Z M225 143 H285 V177 H225 Z M333 143 H409 V177 H333 Z M463 143 H526 V177 H463 Z M574 143 H639 V177 H574 Z M689 143 H796 V177 H689 Z','#a9bcc6');
    svgShape('doors','M184 139 H216 V218 H184 Z M292 139 H324 V218 H292 Z M534 139 H566 V218 H534 Z M647 139 H679 V218 H647 Z','#c2cbd0');
    svgShape('hvac','M263 109 H356 V122 H263 Z M656 109 H749 V122 H656 Z','#64717b');
    svgShape('electrical_auxiliary','M127 111 H207 V123 H127 Z M148 110 L173 78 L200 110 M152 78 H196','#8d9da5');
    svgShape('control_cab','M76 140 L64 180 H94 V140 Z M60 185 H95 V213 H55 Z','#8099a6');
    svgShape('traction','M190 231 H318 V252 H190 Z','#56656f');
    svgShape('braking','M552 231 H677 V252 H552 Z','#7a8992');
    svgShape('bogie_structure','M101 232 H160 V246 H101 Z M336 232 H397 V246 H336 Z M474 232 H530 V246 H474 Z M745 232 H807 V246 H745 Z M107 249 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0 M137 249 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0 M339 249 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0 M369 249 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0 M475 249 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0 M505 249 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0 M746 249 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0 M776 249 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0','#3b4651');root.prepend(svg);
    let renderer, scene, camera, assembly, resizeObserver, frame=0, yaw=-.36,pitch=.27,distance=22,drag=null;
    const meshes=[],proxies=[], disposables=[];
    function positionTip(e){const r=root.getBoundingClientRect();tip.style.left=Math.max(8,Math.min(e.clientX-r.left+14,r.width-285))+'px';tip.style.top=Math.max(8,Math.min(e.clientY-r.top+14,r.height-80))+'px';}
    function showTip(id,e){setHover(id);const c=counts[id]||{};tip.textContent=`${byId.get(id)?.label||id} · ${Number(c.total||0).toLocaleString()} suppliers assigned · ${c.scored||0} scored · ${c.researchOnly||0} research-only · demo assignment`;tip.hidden=false;if(e)positionTip(e);}
    function paint(){for(const m of meshes){m.material.color.set(m.userData.regionId===selected?'#0f6e74':m.userData.base);m.material.emissive.set(m.userData.regionId===hovered?'#0f6e74':'#000000');m.material.emissiveIntensity=.35;}svg.querySelectorAll('[data-region]').forEach(p=>{p.classList.toggle('ts-active',p.dataset.region===selected);p.classList.toggle('ts-hover',p.dataset.region===hovered);p.setAttribute('aria-pressed',String(p.dataset.region===selected));});requestRender();}
    function setHover(id){hovered=id;if(!id)tip.hidden=true;if(renderer)renderer.domElement.style.cursor=drag?'grabbing':id?'pointer':'grab';paint();}
    function requestRender(){if(renderer&&!disposed&&!frame)frame=requestAnimationFrame(()=>{frame=0;renderer.render(scene,camera);});}
    function fallback(){root.classList.add('ts-failed');tip.hidden=true;hint.textContent='Illustrative side elevation · select a system';if(frame)cancelAnimationFrame(frame);frame=0;}
    function cameraView(){camera.position.set(Math.sin(yaw)*distance,1.15+Math.sin(pitch)*distance,Math.cos(yaw)*distance);camera.lookAt(0,1.15,0);camera.updateMatrixWorld();requestRender();}
    try {
      renderer=new WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));renderer.setClearColor(0xffffff,0);renderer.domElement.setAttribute('aria-hidden','true');root.prepend(renderer.domElement);
      scene=new Scene();camera=new PerspectiveCamera(28,1,.1,100);assembly=new Group();scene.add(assembly);scene.add(new HemisphereLight(0xffffff,0x83939c,2.5));const light=new DirectionalLight(0xffffff,3);light.position.set(-6,12,9);scene.add(light);
      function detail(id,geo,x,y,z,color='#e6e9eb',opacity=1){const mat=new MeshStandardMaterial({color,roughness:.57,metalness:.16,transparent:opacity<1,opacity});const mesh=new Mesh(geo,mat);mesh.position.set(x,y,z);mesh.userData={regionId:id,base:color};assembly.add(mesh);meshes.push(mesh);disposables.push(geo,mat);return mesh;}
      function box(id,x,y,z,w,h,d,color,opacity){return detail(id,new BoxGeometry(w,h,d),x,y,z,color,opacity);}
      function proxy(id,x,y,z,w,h,d){const geo=new BoxGeometry(w,h,d),mat=new MeshBasicMaterial({visible:false});const m=new Mesh(geo,mat);m.position.set(x,y,z);m.userData.regionId=id;assembly.add(m);proxies.push(m);disposables.push(geo,mat);}
      const roof='#3b4651',body='#e6e9eb',glass='#a9bcc6';
      for(const center of [-4.4,4.4]){
        // Rounded shoulders, long lower sill, and a deliberately open near side on the trailer.
        const profile=new Shape();profile.moveTo(-.98,0);profile.lineTo(.98,0);profile.lineTo(.98,1.55);profile.quadraticCurveTo(.98,1.94,.58,1.94);profile.lineTo(-.58,1.94);profile.quadraticCurveTo(-.98,1.94,-.98,1.55);profile.closePath();
        const shell=new ExtrudeGeometry(profile,{depth:7.9,bevelEnabled:false,curveSegments:3});shell.rotateY(Math.PI/2);shell.translate(-3.95,0,0);detail('carbody',shell,center,.84,0,body);
        box('carbody',center,.97,1.005,7.9,.25,.1,body);box('carbody',center,2.7,0,7.92,.16,1.88,body);
        // Windows sit proud of the shell; the trailer's near-side cutaway is recessed below.
        for(const z of [-1.006,1.006]){
          for(const offset of [-2.65,-.25,2.55])box('interiors',center+offset,2.12,z,1.36,.59,.045,glass,.7);
          for(const offset of [-1.55,1.35]){for(const leaf of [-.22,.22])box('doors',center+offset+leaf,1.72,z*1.012,.42,1.53,.06,'#bdc8ce');proxy('doors',center+offset,1.73,z*1.07,1,1.7,.2);}
        }
        box('hvac',center+1.5,2.96,0,1.9,.34,1.25,roof);proxy('hvac',center+1.5,3,0,2.1,.5,1.45);
        for(const offset of [-2.8,2.8]){
          box('bogie_structure',center+offset,.68,0,1.55,.28,1.52,roof);
          for(const dx of [-.48,.48])for(const z of [-.91,.91]){const wheel=detail('bogie_structure',new CylinderGeometry(.38,.38,.19,12),center+offset+dx,.43,z,roof);wheel.rotation.x=Math.PI/2;const disc=detail('braking',new TorusGeometry(.2,.045,4,12),center+offset+dx,.43,z+(z>0?.11:-.11),'#87949c');}
          proxy('bogie_structure',center+offset,.48,0,1.9,.9,2.2);
        }
        proxy('carbody',center,1.45,0,7.8,.55,1.85);
        for(const z of [-1.09,1.09])for(const offset of [-2.65,-.25,2.55])proxy('interiors',center+offset,2.13,z,1.4,.65,.13);
      }
      // A framed cutaway reveals seating on the trailer, with a pale interior floor.
      box('interiors',5.3,1.86,1.06,1.55,1.12,.1,'#cbd9dc');box('interiors',5.3,1.35,1.19,1.55,.12,.48,'#879ea7');
      for(const x of [4.85,5.45]){box('interiors',x,1.61,1.2,.35,.48,.25,'#597b87');box('interiors',x,1.43,1.36,.35,.13,.36,'#7596a1');}
      proxy('interiors',5.3,1.9,1.17,1.6,1.2,.3);
      box('carbody',0,1.15,0,.8,.3,.5,roof);
      box('traction',-4.6,.72,0,2.5,.48,1.58,'#56656f');proxy('traction',-4.6,.7,0,2.8,.65,1.9);
      box('braking',4.1,.72,0,2.25,.48,1.58,'#7b8b94');proxy('braking',4.1,.7,0,2.5,.65,1.9);
      // Cab face and dark windscreen at the leftmost end.
      box('control_cab',-8.38,1.78,0,.16,1.34,1.76,'#879ea7');box('control_cab',-8.48,2.1,0,.05,.62,1.52,'#3c5968');proxy('control_cab',-8.45,1.85,0,.4,1.75,2.05);
      for(const z of [-.7,.7])box('control_cab',-8.5,1.35,z,.06,.12,.21,'#fff4d6');
      box('electrical_auxiliary',-6,2.96,0,1.7,.26,1.2,roof);
      function strut(x1,y1,x2,y2,z){const dx=x2-x1,dy=y2-y1,m=box('electrical_auxiliary',(x1+x2)/2,(y1+y2)/2,z,Math.hypot(dx,dy),.06,.06,'#56656f');m.rotation.z=Math.atan2(dy,dx);}
      strut(-6.3,3.1,-5.5,3.8,0);strut(-5.5,3.8,-4.7,3.15,0);box('electrical_auxiliary',-5.5,3.83,0,.14,.06,1.5,roof);proxy('electrical_auxiliary',-5.6,3.4,0,2.1,1.05,1.55);
      // Two quiet reference rails ground the assembly without expensive shadows.
      for(const z of [-.87,.87]){const rail=box(null,0,.02,z,18,.035,.045,'#b7c6cc');rail.userData.regionId=null;}
      const raycaster=new Raycaster(),pointer=new Vector2();
      function hit(e){const r=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);scene.updateMatrixWorld();camera.updateMatrixWorld();raycaster.setFromCamera(pointer,camera);return raycaster.intersectObjects(proxies,false)[0]?.object.userData.regionId||null;}
      const canvas=renderer.domElement;
      canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();fallback();});
      canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;drag={x:e.clientX,y:e.clientY,yaw,pitch,moved:0};canvas.setPointerCapture(e.pointerId);tip.hidden=true;});
      canvas.addEventListener('pointermove',e=>{if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.moved=Math.max(drag.moved,Math.hypot(dx,dy));if(drag.moved>=4){yaw=Math.max(-.61,Math.min(.61,drag.yaw+dx*.004));pitch=Math.max(.14,Math.min(.524,drag.pitch+dy*.003));cameraView();setHover(null);}}else{const id=hit(e);if(id)showTip(id,e);else setHover(null);}});
      canvas.addEventListener('pointerup',e=>{if(!drag)return;const click=drag.moved<4&&Math.hypot(e.clientX-drag.x,e.clientY-drag.y)<4;drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);if(click){const id=hit(e);if(id)options.onSelect?.(id);}});
      canvas.addEventListener('pointercancel',()=>{drag=null;setHover(null);});canvas.addEventListener('pointerleave',()=>{if(!drag)setHover(null);});
      function resize(){const w=Math.max(1,root.clientWidth),h=Math.max(1,root.clientHeight);renderer.setSize(w,h,false);camera.aspect=w/h;camera.fov=28;camera.updateProjectionMatrix();
        // Fit the assembly on resize, preserving its useful size when the app changes card height.
        // The bounds include roof equipment and wheel/rail edges; no orbit-time zoom.
        distance=22;
        for(let pass=0;pass<3;pass++){cameraView();let extentX=0,extentY=0;for(const x of [-8.6,8.5])for(const y of [0,3.9])for(const z of [-1.5,1.5]){const point=new Vector3(x,y,z).project(camera);extentX=Math.max(extentX,Math.abs(point.x));extentY=Math.max(extentY,Math.abs(point.y));}distance*=Math.max(extentX/.93,extentY/.78);}
        cameraView();}
      resizeObserver=new ResizeObserver(resize);resizeObserver.observe(root);resize();
    }catch(error){console.warn('Train WebGL unavailable; using interactive SVG.',error);fallback();}
    paint();
    return {update(next={}){if(Object.hasOwn(next,'counts'))counts=next.counts||{};if(Object.hasOwn(next,'selected'))selected=next.selected;paint();},highlight(id){setHover(id);},resetView(){yaw=-.36;pitch=.27;if(camera)cameraView();setHover(null);},destroy(){disposed=true;if(frame)cancelAnimationFrame(frame);resizeObserver?.disconnect();disposables.forEach(d=>d.dispose());renderer?.dispose();root.remove();}};
  }
  return {mount};
})();

