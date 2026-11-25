"use strict";

const $ = id => document.getElementById(id);
const clone = value => structuredClone(value);
const uid = () => crypto.randomUUID();
const presets = {generic:"generic-gnpy-reference",ciena:"ciena-6500-s14-wl6e-motr",nokia:"nokia-1830-pss-hc-4cp4t8"};
function nextRouteNumber() {
  try { return Number(localStorage.getItem("hyperion.routeNumber") || 0) + 1; } catch { return 1; }
}
function initialProject() {
  return {
    version:2,m6:true,requirements:{rate_gbps:100,mode_id:"generic-100g",grid:"fixed",channels:1,center_thz:193.1,guard_band_ghz:0,launch_dbm:0,reserve_db:2}, project_id:uid(), revision:1, route_name:"DWDM Route " + nextRouteNumber(),
    network:{nodes:[{id:"A",name:"Kapolei",lat:21.335,lon:-158.058},{id:"B",name:"Honolulu",lat:21.307,lon:-157.858}],
      links:[{id:"A-B",from:"A",to:"B",bends:[],override:null,splices:[],inline_gain:null,fiber:{type_variety:"SSMF",loss_coef:0.2}}],
      services:[{id:"service-1",source:"A",target:"B",via:[]}]},
    active_service:"service-1",equipment:{vendor:"generic",service_gbps:100,mode:"automatic",nodes:{}},
    tx_power_dbm:null,booster_gain_db:null,preamp_gain_db:null,quality_limits:null,ase_threshold_db:null,ase_warning_db:1,
  };
}
let project = initialProject();
let undoStack = [], redoStack = [], committed = JSON.stringify(project);
let selection = null, tool = null, connectStart = null;
let draggingSite = false;
let draggingBend = false;
let insertionHighlight = null;
let preview = null, previewTimer, previewSequence = 0, lastSnapshot = null, lastResult = null, running = false;
let generation = 0, catalog = null;
const map = L.map("map", {maxZoom:18}).setView([21.47,-157.98],10);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);
const routeLayer = L.layerGroup().addTo(map);
const zoneLayer = L.layerGroup().addTo(map);
const active = () => project.network.services.find(service => service.id === project.active_service);
const degrees = id => project.network.links.filter(link => link.from === id || link.to === id).length;
const site = id => project.network.nodes.find(node => node.id === id);
const spanPath = link => [[site(link.from).lat,site(link.from).lon], ...(link.bends || []), [site(link.to).lat,site(link.to).lon]];
const status = message => { $("status").textContent = message; $("status").dataset.busy = String(/Checking|Running/.test(message)); };
function equipmentFor(id) { return project.equipment.nodes[id] ||= {}; }
function panelFor(id) {
  return equipmentFor(id).panel ||= {enabled:true,pairs_per_degree:1,connector_loss_db:.5,splices_per_degree:1,splice_loss_db:.1};
}
function changed({draw=true, editor=false}={}) {
  if(typeof normalizeM6Project==="function")normalizeM6Project();
  const serialized = JSON.stringify(project);
  if (serialized !== committed) {
    undoStack.push(committed);
    if (undoStack.length > 100) undoStack.shift();
    redoStack = [];
    project.revision++;
    committed = JSON.stringify(project);
    generation++;
  }
  $("undo").disabled = undoStack.length === 0;
  $("redo").disabled = redoStack.length === 0;
  $("stale-results").hidden = !lastSnapshot || lastSnapshot === JSON.stringify(project);
  if(typeof updateM6State==="function")updateM6State();
  if (draw) renderMap();
  renderNetworkList();
  if (editor) renderEditor();
  clearTimeout(previewTimer);
  status("Checking route and equipment…");
  previewTimer = setTimeout(updatePreview, 400);
}
async function request(path, body) {
  const response = await fetch(path, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed");
  return result;
}
async function updatePreview() {
  const sequence = ++previewSequence;
  const snapshot = clone(project);
  try {
    const result = await request("/api/preview", snapshot);
    if (sequence !== previewSequence || JSON.stringify(snapshot) !== JSON.stringify(project)) return;
    preview = result;
    if(typeof updateM6State==="function")updateM6State();
    renderScreening(result.zones);
    renderNetworkList();
    renderMap();
    renderSpanReadings();
    renderOptionChecks();
    status(lastSnapshot === JSON.stringify(project) ? "Simulation complete." : "Configuration checked. Run to calculate optical performance.");
    if ($("auto-run").checked && lastSnapshot !== JSON.stringify(project)) runSimulation();
  } catch (error) {
    if (sequence === previewSequence) {
      preview = null;
      status(error.message);
      $("zones-status").textContent = "Route screening unavailable until the route is connected.";
    }
  }
}
function setTool(value) {
  tool = tool === value ? null : value;
  connectStart = null;
  for (const [id,key] of [["place-site","site"],["draw-span","connect"],["draw-bend","bend"]])
    $(id).setAttribute("aria-pressed", String(tool === key));
  $("tool-hint").textContent = tool === "site" ? "Click to place a site (up to 20)." :
    tool === "connect" ? "Click the two sites to connect." :
    tool === "bend" ? "Click a span to add a bend or switch spans. Click away from the line to bend the selected span. Drag bends to move; click a bend to remove." : "Drag sites or click a span to edit.";
}
$("place-site").onclick = () => setTool("site");
$("draw-span").onclick = () => setTool("connect");
$("draw-bend").onclick = () => setTool("bend");
map.on("click", event => {
  const point = event.latlng.wrap();
  if (tool === "site") {
    if (project.network.nodes.length >= 20) { status("This build supports up to 20 sites."); return; }
    if(typeof offerInsertionAt==="function" && offerInsertionAt([point.lat,point.lng]))return;
    const id = "ABCDEFGHIJKLMNOPQRST".split("").find(id => !site(id));
    project.network.nodes.push({id,name:"Site " + id,lat:point.lat,lon:point.lng});
    selection = {type:"node",id};
    changed({editor:true});
    setTool("site");
  } else if(tool === "insert" && selection?.type === "link") {
    if(typeof proposeInsertion==="function")proposeInsertion(selection.id,[point.lat,point.lng]);
  } else if (tool === "bend") {
    // Clicking near another branch must not keep modifying the previous span.
    const target = typeof nearestSpan === "function" ? nearestSpan([point.lat,point.lng]) : null;
    const id = target?.id || (selection?.type === "link" ? selection.id : null);
    if (id) addSpanBend(id,[point.lat,point.lng]);
    else status("Click the span you want to bend first.");
  }
});
function addSpanBend(linkId, point) {
  const link = project.network.links.find(link => link.id === linkId);
  if (!link) return;
  if (link.bends.length >= 50) { status("A span can have up to 50 bends."); return; }
  const projected = spanPath(link).map(p => {const pixel=map.latLngToLayerPoint(p);return [pixel.x,pixel.y];});
  const pixel = map.latLngToLayerPoint(point);
  const index = ProjectEditing.bendSegmentIndex(projected,[pixel.x,pixel.y]);
  link.bends.splice(index,0,point);
  selection = {type:"link",id:linkId};
  $("route-settings").open = true;
  project.reference_case = false;
  changed({editor:true});
}
function choose(type,id) {
  selection = {type,id};
  $("route-settings").open = true;
  renderEditor();
  renderMap();
  $("route-settings").scrollTop=0;
  if(project.m6)$("design-requirements").open=false;
}
function addWarning(point, label, action, configured=false) {
  const icon = L.divIcon({className: configured ? "map-span-amplifier":"map-span-warning",
    html:configured ? "▲":"!",iconSize:[24,24]});
  L.marker(point,{icon,title:label}).addTo(routeLayer).on("click",action);
}
function renderMap() {
  // A preview response must not remove Leaflet's marker during an active drag.
  if (draggingSite || draggingBend) return;
  routeLayer.clearLayers();
  const selectedLinks = new Set(preview?.route?.links.map(link => link.id) || []);
  for (const link of project.network.links) {
    const line = L.polyline(spanPath(link),{color:selection?.id===link.id ? "#334761":selectedLinks.has(link.id) ? "#3d7772":"#827e76",weight:selection?.id===link.id?5:3}).addTo(routeLayer);
    line.on("click", event => {
      L.DomEvent.stopPropagation(event);
      const point=event.latlng.wrap();
      if((tool==="insert"||tool==="site")&&typeof proposeInsertion==="function"){proposeInsertion(link.id,[point.lat,point.lng]);return;}
      if(tool==="bend"){addSpanBend(link.id,[point.lat,point.lng]);return;}
      choose("link",link.id);
    });
    if (selection?.id===link.id) link.bends.forEach((point,index) => {
      const marker = L.marker(point,{draggable:true,icon:L.divIcon({className:"bend-point",html:"",iconSize:[14,14]}),title:"Bend " + (index+1) + " · Click to remove"}).addTo(routeLayer);
      marker.on("dragstart",()=>{draggingBend=true;});
      marker.on("drag",() => {
        const ll=marker.getLatLng().wrap(); link.bends[index]=[ll.lat,ll.lng]; line.setLatLngs(spanPath(link));
      });
      marker.on("dragend",()=>{
        draggingBend=false;
        const ll=marker.getLatLng().wrap();link.bends[index]=[ll.lat,ll.lng];
        project.reference_case=false;changed({editor:true});
      });
      marker.on("click",()=>{link.bends.splice(index,1);changed({editor:true});});
    });
    const index=preview?.route?.links.findIndex(item=>item.id===link.id) ?? -1;
    const length=link.override ?? (index>=0 ? preview.geometry.km[index]:null);
    if (length>80 || link.inline_gain!==null) {
      const points=spanPath(link), point=points[Math.floor((points.length-1)/2)];
      const midpoint=points.length===2 ? [(points[0][0]+points[1][0])/2,(points[0][1]+points[1][1])/2]:point;
      addWarning(midpoint,link.inline_gain!==null?"Midpoint EDFA":"Over 80 km · Review amplification",()=>choose("link",link.id),link.inline_gain!==null);
    }
  }
  for (const node of project.network.nodes) {
    const marker = L.marker([node.lat,node.lon], {draggable:true,title:node.name,
      icon:L.divIcon({className:"site-marker"+(selection?.id===node.id?" selected-marker":""),html:node.id,iconSize:[32,32]})}).addTo(routeLayer);
    marker.getElement().id="point-"+node.id.toLowerCase();
    marker.on("dragstart",()=>{draggingSite=true;});
    marker.on("drag",()=>{
      const ll=marker.getLatLng().wrap();node.lat=ll.lat;node.lon=ll.lng;
      if(typeof nearestSpan==="function"){
        const target=nearestSpan([node.lat,node.lon],node.id);
        if(insertionHighlight){map.removeLayer(insertionHighlight);insertionHighlight=null;}
        if(target){
          insertionHighlight=L.polyline(spanPath(target),{color:"#b14a30",weight:9,opacity:.75,interactive:false}).addTo(map);
          status("Release to insert "+node.id+" into this highlighted span. You will confirm before it changes.");
        }
      }
    });
    marker.on("dragend",()=>{
      draggingSite=false;
      if(insertionHighlight){map.removeLayer(insertionHighlight);insertionHighlight=null;}
      const ll=marker.getLatLng().wrap();node.lat=ll.lat;node.lon=ll.lng;
      if(typeof offerInsertionAt==="function" && offerInsertionAt([node.lat,node.lon],node.id))return;
      project.reference_case=false;changed({editor:true});
    });
    marker.on("click",()=> {
      if(tool==="connect") {
        if (!connectStart) {connectStart=node.id; status("Now click the other site."); return;}
        const from=connectStart; connectStart=null;
        if(from===node.id || project.network.links.some(link=>[link.from,link.to].includes(from)&&[link.from,link.to].includes(node.id))) {
          status("Choose a different unconnected pair.");return;
        }
        const link={id:uid(),from,to:node.id,bends:[],override:null,splices:[],inline_gain:null,fiber:{type_variety:"SSMF",loss_coef:.2}};
        project.network.links.push(link); selection={type:"link",id:link.id}; changed({editor:true});setTool("connect");
      } else {
        choose("node",node.id);
        const content=document.createElement("div");
        const title=document.createElement("strong");title.textContent=node.name;
        const text=document.createElement("p");text.textContent=degrees(node.id)+" line degrees · "+(panelFor(node.id).enabled?"Corning Centrix panel":"Direct termination");
        const button=document.createElement("button");button.textContent="Open site settings";
        button.onclick=()=>{map.closePopup();choose("node",node.id);};
        content.append(title,text,button);L.popup().setLatLng(marker.getLatLng()).setContent(content).openOn(map);
      }
    });
  }
}
function renderNetworkList() {
  const list=$("network-list");list.replaceChildren();
  for(const node of project.network.nodes) {
    const button=document.createElement("button");button.textContent=node.id+" · "+node.name+" · "+degrees(node.id)+"°";
    button.onclick=()=>choose("node",node.id);list.append(button);
  }
  for(const link of project.network.links) {
    const button=document.createElement("button");button.textContent=site(link.from).name+" → "+site(link.to).name;
    button.onclick=()=>choose("link",link.id);list.append(button);
  }
}
function inputField(parent,label,value,change,{type="number",min=0,max=100,step="any",id,placeholder=""}={}) {
  const wrapper=document.createElement("label");wrapper.textContent=label;
  const field=document.createElement("input");field.type=type;field.value=value??"";field.placeholder=placeholder;
  if(type==="number"){field.min=min;field.max=max;field.step=step;}else field.maxLength=100;
  if(id)field.id=id;
  field.addEventListener("change",()=>{if(!field.reportValidity())return;change(type==="number"?(field.value===""?null:field.valueAsNumber):field.value);changed();});
  wrapper.append(field);parent.append(wrapper);return field;
}
function selectField(parent,label,options,value,change,id) {
  const wrapper=document.createElement("label");wrapper.textContent=label;
  const field=document.createElement("select");if(id)field.id=id;
  field.replaceChildren(...options.map(([key,text])=>new Option(text,key)));field.value=value;
  field.onchange=()=>{change(field.value);changed({editor:true});};wrapper.append(field);parent.append(wrapper);return field;
}
function text(parent,value,css="quiet") {const p=document.createElement("p");p.textContent=value;p.className=css;parent.append(p);return p;}
function renderEditor() {
  const editor=$("selection-editor");editor.replaceChildren();
  if(!selection){text(editor,"Select a site or span to edit its configuration.");return;}
  const heading=document.createElement("h2");editor.append(heading);
  if(selection.type==="node") {
    const node=site(selection.id);if(!node){selection=null;return;}
    heading.textContent=node.id+" · Site settings";
    inputField(editor,"Site name",node.name,value=>{node.name=value.trim()||node.id;renderServiceSelects();},{type:"text",id:"site-name"});
    const settings=equipmentFor(node.id),panel=panelFor(node.id);
    if(project.m6 && typeof renderM6NodeControls==="function")renderM6NodeControls(editor,node,settings);
    selectField(editor,"Vendor override",[["","Use global preset"],["generic","Generic"],["ciena","Ciena"],["nokia","Nokia"]],settings.vendor||"",value=>{if(value)settings.vendor=value;else delete settings.vendor;delete settings.profile_id;},"node-vendor");
    const options=document.createElement("div");options.id="equipment-options";editor.append(options);
    selectField(editor,"Fiber termination",[["panel","Corning Centrix"],["direct","Direct termination / no panel"]],panel.enabled?"panel":"direct",value=>panel.enabled=value==="panel","panel-enabled");
    text(editor,"Centrix modular housing. 0.50 dB per mated pair and 0.10 dB per pigtail splice are editable planning assumptions.");
    inputField(editor,"Mated connector pairs per degree",panel.pairs_per_degree,value=>panel.pairs_per_degree=value,{step:"1",max:24,id:"panel-pairs"});
    inputField(editor,"Loss per mated pair (dB)",panel.connector_loss_db,value=>panel.connector_loss_db=value,{max:10,id:"panel-connector-loss"});
    inputField(editor,"Pigtail splices per degree",panel.splices_per_degree,value=>panel.splices_per_degree=value,{step:"1",max:24,id:"panel-splices"});
    inputField(editor,"Loss per pigtail splice (dB)",panel.splice_loss_db,value=>panel.splice_loss_db=value,{max:10,id:"panel-splice-loss"});
    if((settings.role|| (degrees(node.id)>=2?"roadm":"terminal"))==="roadm") {
      const roadm=settings.roadm ||= {target_pch_out_db:-20,path_loss_db:0,band_min_thz:191.3,band_max_thz:196.1};
      text(editor,"ROADM/WSS · "+degrees(node.id)+" connected degrees. The selected service determines the ingress and egress pair.");
      inputField(editor,"ROADM target (dBm/channel)",roadm.target_pch_out_db,value=>roadm.target_pch_out_db=value,{min:-30,max:5,id:"roadm-target"});
      inputField(editor,"Generic express path minimum loss (dB)",roadm.path_loss_db,value=>roadm.path_loss_db=value,{max:40,id:"roadm-path-loss"});
      inputField(editor,"WSS band lower edge (THz)",roadm.band_min_thz,value=>roadm.band_min_thz=value,{min:180,max:210,id:"wss-min"});
      inputField(editor,"WSS band upper edge (THz)",roadm.band_max_thz,value=>roadm.band_max_thz=value,{min:180,max:210,id:"wss-max"});
      text(editor,"Band constraints are checked for each channel. A vendor spectral transfer curve is required to model narrowing penalties.");
    }
    const remove=document.createElement("button");remove.textContent="Remove site";remove.className="danger";
    remove.disabled=project.network.nodes.length<=2;
    remove.onclick=()=>{const apply=()=>{project.network.nodes=project.network.nodes.filter(item=>item.id!==node.id);project.network.links=project.network.links.filter(link=>link.from!==node.id&&link.to!==node.id);delete project.equipment.nodes[node.id];selection=null;renderServiceSelects();changed({editor:true});};if(project.m6)confirmTopologyChange('Remove '+node.name+'?','This removes the site and its '+degrees(node.id)+' connected spans. Services using it will need reconnection. Undo is available.',apply);else apply();};editor.append(remove);
    renderOptionChecks();
  } else {
    const link=project.network.links.find(link=>link.id===selection.id);if(!link){selection=null;return;}
    heading.textContent=site(link.from).name+" → "+site(link.to).name;
    const readings=document.createElement("p");readings.id="span-readings";editor.append(readings);
    if(typeof renderM6SpanControls==="function")renderM6SpanControls(editor,link);
    inputField(editor,"Engineered length (km)",link.override,value=>{link.override=value;project.reference_case=false;},{min:.001,max:20000,id:"span-length",placeholder:"Follow drawn geometry"});
    const fiber=link.fiber ||= {type_variety:"SSMF",loss_coef:.2};
    selectField(editor,"Generic fiber model",[["SSMF","SSMF · Standard single mode"],["LOF","LOF · Large effective area"],["NZDF","NZDF · Non-zero dispersion shifted"]],fiber.type_variety,value=>fiber.type_variety=value,"fiber-type");
    inputField(editor,"Attenuation (dB/km)",fiber.loss_coef,value=>fiber.loss_coef=value,{min:.01,max:1,id:"fiber-loss"});
    inputField(editor,"From-end termination loss override (dB)",link.connector_in_db,value=>link.connector_in_db=value,{max:10,id:"connector-in",placeholder:"Use site panel"});
    inputField(editor,"To-end termination loss override (dB)",link.connector_out_db,value=>link.connector_out_db=value,{max:10,id:"connector-out",placeholder:"Use site panel"});
    text(editor,"Library dispersion, effective area and PMD follow the chosen GNPy model; attenuation is separately editable.");
    inputField(editor,"Midpoint EDFA gain target (dB)",link.inline_gain,value=>link.inline_gain=value,{min:8,max:35,id:"inline-gain",placeholder:"Automatic reference"});
    const suggestion=document.createElement("button");suggestion.id="suggest-amplifier";
    suggestion.onclick=()=>{
      const index=preview?.route?.links.findIndex(item=>item.id===link.id)??-1;
      if(index<0)return;
      link.inline_gain=Math.round(Math.min(35,Math.max(8,preview.design.lengths[index]*fiber.loss_coef/2+preview.design.connections[index].con_in_db))*10)/10;
      changed({editor:true});
    };editor.append(suggestion);
    const loss=document.createElement("div");editor.append(loss);
    link.splices.forEach((value,index)=>{
      inputField(loss,"Field splice "+(index+1)+" (dB)",value,next=>link.splices[index]=next,{max:10,id:"splice-"+index});
      const remove=document.createElement("button");remove.textContent="Remove splice "+(index+1);remove.onclick=()=>{link.splices.splice(index,1);changed({editor:true});};loss.append(remove);
    });
    const add=document.createElement("button");add.textContent="Add splice";add.disabled=link.splices.length>=100;
    add.onclick=()=>{link.splices.push(.1);changed({editor:true});};editor.append(add);
    text(editor,link.bends.length+" route bends · Click Draw bends and then the map to add. Drag a bend to move it or click it to remove.");
    const clear=document.createElement("button");clear.textContent="Clear bends";clear.onclick=()=>{link.bends=[];project.reference_case=false;changed({editor:true});};editor.append(clear);
    const remove=document.createElement("button");remove.textContent="Remove span";remove.className="danger";
    remove.onclick=()=>{const apply=()=>{project.network.links=project.network.links.filter(item=>item.id!==link.id);selection=null;changed({editor:true});};if(project.m6)confirmTopologyChange('Remove this span?','Its bends, splice entries and inline equipment will be removed. Connected services may need a new path. Undo is available.',apply);else apply();};editor.append(remove);
    renderSpanReadings();
  }
}
function renderSpanReadings() {
  if(selection?.type!=="link" || !$("span-readings"))return;
  const link=project.network.links.find(item=>item.id===selection.id);
  const index=preview?.route?.links.findIndex(item=>item.id===selection.id) ?? -1;
  if(index<0){$("span-readings").textContent="This span is outside the selected service. Select its endpoints to evaluate.";return;}
  const length=preview.design.lengths[index];
  const suggestion=$("suggest-amplifier");
  if(suggestion){
    const gain=Math.round(Math.min(35,Math.max(8,length*(link.fiber?.loss_coef??.2)/2+preview.design.connections[index].con_in_db))*10)/10;
    suggestion.textContent="Apply midpoint EDFA estimate · "+gain+" dB";
    suggestion.title="Initial target compensates the upstream half-span fiber and ingress loss, bounded to 8–35 dB. Review GNPy effective gain, output power and ASE before acceptance.";
  }
  $("span-readings").textContent="Drawn length "+preview.geometry.km[index].toFixed(3)+" km · Simulation "+length.toFixed(3)+" km"+(length>80&&link.inline_gain===null?" · ! Over 80 km: review amplification":"");
  $("span-readings").className=length>80&&link.inline_gain===null?"span-warning":"quiet";
}
function renderOptionChecks() {
  const container=$("equipment-options");if(!container||!catalog||selection?.type!=="node")return;
  container.replaceChildren();
  const node=site(selection.id),settings=equipmentFor(node.id);
  const current=settings.profile_id||presets[settings.vendor||project.equipment.vendor];
  const group=preview?.options?.find(group=>group.node_id===node.id);
  for(const option of group?.options || []) {
    const button=document.createElement("button");
    button.className="equipment-option"+(option.status==="Fail"?" incompatible":"");
    button.textContent=(option.id===current?"✓ ":"")+option.label;
    button.onclick=()=>{
      if(option.status==="Fail") {showDetail(option.label,option.reason);return;}
      settings.profile_id=option.id;settings.profile_override=true;changed({editor:true});
    };
    if(option.status==="Fail")button.setAttribute("aria-disabled","true");
    container.append(button);
    if(option.status!=="Pass")text(container,option.reason,"option-note");
  }
}
function showDetail(title,reason){$("option-title").textContent=title;$("option-reason").textContent=reason;$("option-detail").showModal();}
function renderScreening(zones) {
  $("zones-status").textContent=(zones.source?.status||"Unavailable")+" · "+(zones.coverage||"Confirm source coverage.");
  $("zones-findings").replaceChildren();
  for(const finding of zones.findings||[])text($("zones-findings"),finding.name+" · "+finding.reason,"span-warning");
}
function renderServiceSelects() {
  const service=active();
  for(const [id,key] of [["service-source","source"],["service-target","target"]]) {
    $(id).replaceChildren(...project.network.nodes.map(node=>new Option(node.id+" · "+node.name,node.id)));
    if(!site(service[key]))service[key]=project.network.nodes[key==="source"?0:project.network.nodes.length-1].id;
    $(id).value=service[key];
  }
  $("service-via").value=(service.via||[]).join(",");
}
function syncFields() {
  $("route-name").value=project.route_name;
  renderServiceSelects();
  $("design-mode").value=project.equipment.mode;
  $("service-rate").value=project.equipment.service_gbps;
  $("vendor").value=project.equipment.vendor;
  for(const [id,key] of [["tx-power","tx_power_dbm"],["booster-gain","booster_gain_db"],["preamp-gain","preamp_gain_db"],["ase-threshold","ase_threshold_db"]])$(id).value=project[key]??"";
  $("quality-threshold").value=project.quality_limits?.threshold??"";
  $("quality-reserve").value=project.quality_limits?.reserve??2;
  $("quality-warning").value=project.quality_limits?.warning??project.ase_warning_db??1;
}
for(const [id,key] of [["tx-power","tx_power_dbm"],["booster-gain","booster_gain_db"],["preamp-gain","preamp_gain_db"],["ase-threshold","ase_threshold_db"]]) {
  $(id).onchange=()=>{if(!$(id).reportValidity())return;project[key]=$(id).value===""?null:$(id).valueAsNumber;changed();};
}
for(const id of ["quality-threshold","quality-reserve","quality-warning"])$(id).onchange=()=>{
  if(!$(id).reportValidity())return;
  project.quality_limits=$("quality-threshold").value===""?null:{threshold:$("quality-threshold").valueAsNumber,reserve:$("quality-reserve").valueAsNumber,warning:$("quality-warning").valueAsNumber};
  project.ase_warning_db=$("quality-warning").valueAsNumber;changed();
};
$("route-name").onchange=()=>{project.route_name=$("route-name").value.trim()||"DWDM Route "+nextRouteNumber();changed({draw:false});};
for(const [id,key] of [["service-source","source"],["service-target","target"]])$(id).onchange=()=>{active()[key]=$(id).value;project.reference_case=false;changed({editor:true});};
$("service-via").onchange=()=>{active().via=$("service-via").value.split(",").map(id=>id.trim()).filter(Boolean);changed();};
$("design-mode").onchange=()=>{project.equipment.mode=$("design-mode").value;changed({editor:true});};
$("service-rate").onchange=()=>{project.equipment.service_gbps=Number($("service-rate").value);proposeProfiles();changed({editor:true});};
$("vendor").onchange=()=>{project.equipment.vendor=$("vendor").value;proposeProfiles(true);changed({editor:true});};
function proposeProfiles(vendorChanged=false) {
  if(project.m6 && !vendorChanged)return;
  if(project.equipment.mode!=="automatic")return;
  for(const node of project.network.nodes) {
    const settings=equipmentFor(node.id);
    const current=catalog?.profiles.find(item=>item.id===settings.profile_id);
    const incompatible=current?.client_rates_gbps && !current.client_rates_gbps.includes(project.equipment.service_gbps);
    if(!settings.vendor && (vendorChanged || !settings.profile_override || incompatible)) {
      settings.profile_id=presets[project.equipment.vendor];
      settings.profile_override=false;
    }
  }
}
function restore(value) {
  project=clone(value);selection=null;tool=null;
  if(typeof normalizeM6Project==="function")normalizeM6Project();
  for(const node of project.network.nodes)panelFor(node.id);
  committed=JSON.stringify(project);generation++;
  syncFields();renderEditor();renderMap();renderNetworkList();
  if(typeof syncM6Fields==="function")syncM6Fields();
  $("undo").disabled=!undoStack.length;$("redo").disabled=!redoStack.length;
  $("stale-results").hidden=!lastSnapshot||lastSnapshot===committed;
  clearTimeout(previewTimer);previewTimer=setTimeout(updatePreview,100);
}
$("undo").onclick=()=>{if(!undoStack.length)return;redoStack.push(JSON.stringify(project));restore(JSON.parse(undoStack.pop()));};
$("redo").onclick=()=>{if(!redoStack.length)return;undoStack.push(JSON.stringify(project));restore(JSON.parse(redoStack.pop()));};
$("back").onclick=()=>{selection=null;tool=null;map.closePopup();renderEditor();renderMap();};
$("new-route").onclick=()=>{const next=initialProject();undoStack.push(JSON.stringify(project));redoStack=[];restore(next);fitMap();};
$("reference").onclick=()=>{
  const next=initialProject();delete next.m6;delete next.requirements;next.reference_case=true;
  for(const node of next.network.nodes)next.equipment.nodes[node.id]={panel:{enabled:true,pairs_per_degree:1,connector_loss_db:.5,splices_per_degree:0,splice_loss_db:.1}};
  undoStack.push(JSON.stringify(project));redoStack=[];restore(next);fitMap();
};
function fitMap(){map.fitBounds(project.network.nodes.map(node=>[node.lat,node.lon]),{padding:[50,50],maxZoom:12});}
$("fit-map").onclick=fitMap;
$("map-region").onchange=()=>{
  map.setView($("map-region").value==="usa"?[39.5,-98.35]:[21.47,-157.98],$("map-region").value==="usa"?4:10);
};
$("save-route").onclick=async()=>{
  if(!validFields())return;
  try {
    const validation=await request("/api/preview",project);
    const summary=lastSnapshot===JSON.stringify(project)?lastResult?.equipment_summary:validation.equipment_summary;
    const saved={...clone(project),equipment_summary:summary||null};
    if(typeof markProjectSaved==="function")markProjectSaved();
    downloadJSON(saved,"hyperion-route.json");
    const number=/^DWDM Route (\d+)$/.exec(project.route_name);
    try{
      const savedIds=JSON.parse(localStorage.getItem("hyperion.savedIds")||"[]");
      if(!savedIds.includes(project.project_id)) {
        savedIds.push(project.project_id);
        const previous=Number(localStorage.getItem("hyperion.routeNumber")||0);
        localStorage.setItem("hyperion.routeNumber",String(Math.max(previous+1,Number(number?.[1]||0))));
        localStorage.setItem("hyperion.savedIds",JSON.stringify(savedIds));
      }
    }catch{}
    status("Project downloaded with route geometry and equipment quantities.");
  }catch(error){status("Could not save project. "+error.message);}
};
function downloadJSON(value,name) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:"application/json"}));
  const link=document.createElement("a");link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$("load-route").onclick=()=>$("route-file").click();
$("route-file").onchange=async event=>{
  const file=event.target.files[0];event.target.value="";if(!file)return;
  try {
    if(file.size>250000)throw new Error("Project exceeds 250 kB.");
    let value=JSON.parse(await file.text());
    if(value.version===1)value=migrate(value);
    if(value.version!==2||!value.network||!value.equipment)throw new Error("Choose a Hyperion project JSON file.");
    await request("/api/preview",value);
    undoStack.push(JSON.stringify(project));redoStack=[];restore(value);fitMap();
  }catch(error){status("Could not load project. "+error.message);}
};
function migrate(old) {
  const value=initialProject(),ids=old.coordinates.length===3?["A","C","B"]:["A","B"];
  value.route_name=old.route_name||value.route_name;
  value.network.nodes=ids.map((id,index)=>({id,name:old.site_names[index],lat:old.coordinates[index][0],lon:old.coordinates[index][1]}));
  value.network.links=ids.slice(1).map((id,index)=>({id:ids[index]+"-"+id,from:ids[index],to:id,bends:old.span_bends?.[index]||[],override:old.span_overrides[index],splices:old.span_splices?.[index]||[],inline_gain:old.inline_gains?.[index]??null,fiber:{type_variety:"SSMF",loss_coef:.2}}));
  for(const key of ["booster_gain_db","preamp_gain_db","tx_power_dbm","quality_limits","ase_threshold_db","ase_warning_db"])if(old[key]!==undefined)value[key]=old[key];
  value.reference_case=old.bundled;
  for(const id of ids)value.equipment.nodes[id]={panel:{enabled:true,pairs_per_degree:1,connector_loss_db:.5,splices_per_degree:0,splice_loss_db:.1}};
  if(ids.includes("C")) {
    const settings=value.equipment.nodes.C;
    settings.panel.connector_loss_db=old.roadm_connectors?.[0]??.5;
    value.network.links[0].connector_out_db=old.roadm_connectors?.[0]??.5;
    value.network.links[1].connector_in_db=old.roadm_connectors?.[1]??.5;
  }
  return value;
}
function validFields(){return [...document.querySelectorAll("input[type=number]")].every(field=>field.reportValidity());}
async function runSimulation() {
  if(running||!validFields())return;
  const snapshot=clone(project),serialized=JSON.stringify(snapshot);
  running=true;$("run").disabled=true;$("simulation-error").hidden=true;status("Running GNPy…");
  try {
    const result=await request("/api/run",snapshot);
    showResults(result);lastSnapshot=serialized;lastResult=result;
    if(typeof updateM6State==="function")updateM6State();
    $("stale-results").hidden=JSON.stringify(project)===serialized;
    status(JSON.stringify(project)===serialized?"Simulation complete.":"Simulation complete for the previous revision. Current edits require a rerun.");
  }catch(error){$("simulation-error").textContent="Calculation error · "+error.message;$("simulation-error").hidden=false;status("Simulation failed.");}
  finally{running=false;$("run").disabled=false;if($("auto-run").checked&&lastSnapshot!==JSON.stringify(project)&&lastSnapshot===serialized)updatePreview();}
}
$("run").onclick=runSimulation;
$("rail-settings").onclick=()=>{
  $("route-settings").open=true;
  $("route-settings").scrollIntoView({behavior:"smooth",block:"nearest"});
  $("route-settings").querySelector("summary").focus({preventScroll:true});
};
function showResults(result) {
  if(typeof showM6Results==="function")showM6Results(result);
  $("result-summary").textContent=result.route_name+" · Revision "+result.revision+" · "+result.site_names.join(" → ")+" · "+result.span_length_km.toFixed(3)+" km · "+result.channels.length+" channels";
  if(result.passive_budget)$("result-summary").textContent+=" · External passive loss "+result.passive_budget.total_external_passive_db.toFixed(2)+" dB (including local add/drop panels)";
  const checks=$("results-checks");checks.replaceChildren();
  const all=[];
  if(result.service_check)all.push({title:"Mode feasibility · stated planning assumptions",status:result.service_check.status,detail:result.service_check.reason});
  for(const [title,check] of [["GSNR planning",result.quality_check],["ASE OSNR planning",result.ase_check]]) {
    all.push({title,status:check.status,detail:check.reason||(Number.isFinite(check.remaining_db)?"Channel "+check.channel+" · Remaining margin "+check.remaining_db.toFixed(2)+" dB. "+(check.action||""):"Enter a planning threshold to evaluate this margin.")});
  }
  all.push({title:"FEC margin",status:"Not evaluated",detail:"A validated modem mode and supported FEC threshold are required."});
  for(const issue of result.engineering?.issues||[])all.push({title:issue.check||issue.title||issue.code||"Equipment",status:issue.status,detail:issue.detail||issue.reason||issue.message});
  for(const finding of result.zones?.findings||[])all.push({title:finding.name,status:"Review",detail:finding.reason});
  all.push({title:"Zones source",status:"Review",detail:(result.zones?.source?.status||"Unavailable")+" · "+(result.zones?.coverage||"")});
  for(const span of result.spans)if(span.amplifier_warning)all.push({title:span.from+" → "+span.to,status:"Review",detail:"Over 80 km. Review amplification and run optical margin checks."});
  for(const item of all) {
    const box=document.createElement("div");box.className="result-check"+(["Fail","Review"].includes(item.status)?" span-warning":"");
    const label=document.createElement("strong");label.textContent=item.title+" · "+item.status;
    box.append(label);text(box,item.detail||"", "");checks.append(box);
    if(["Fail","Review"].includes(item.status)&&selection){const fix=document.createElement("button");fix.textContent="Open selected settings";fix.onclick=()=>choose(selection.type,selection.id);box.append(fix);}
  }
  $("channels").replaceChildren(...result.channels.map(channel=>{
    const row=document.createElement("tr");
    const metric=(value,digits=2)=>value===null?"∞ / no contribution":Number.isFinite(value)?value.toFixed(digits):"Not evaluated";
    for(const value of [channel.channel,metric(channel.frequency_thz,5),metric(channel.power_dbm),metric(channel.osnr_ase_db),metric(channel.snr_nli_db),metric(channel.gsnr_db)])row.insertCell().textContent=value;
    return row;
  }));
  $("channel-table").hidden=false;
  $("report").textContent=result.report;$("transmission").hidden=false;
  const summary=$("equipment-summary-body");summary.replaceChildren();
  const inventory=result.equipment_summary?.bom||result.engineering?.bom||[];
  const table=document.createElement("table"),head=table.createTHead().insertRow();
  for(const label of ["Site","Equipment","Qty","Pricing"]) {const th=document.createElement("th");th.textContent=label;head.append(th);}
  const body=table.createTBody();
  for(const item of inventory) {
    const row=body.insertRow();
    for(const value of [item.site_id||item.segment_id||"Selected optical path",item.description,item.quantity,"Estimator"])
      row.insertCell().textContent=value;
  }
  const scroll=document.createElement("div");scroll.className="table-scroll";scroll.append(table);summary.append(scroll);
  text(summary,"Saved quantities cover the physical network. Unit prices and quotes are maintained in Hyperion Estimator.");
  text(summary,result.equipment_summary?.inventory_status||"Modeled amplifier inventory applies to the selected service.");
  for(const [id,key] of [["download","workbook_url"],["evidence-download","evidence_url"],["estimator-download","estimator_url"]]){$(id).href=result[key];$(id).hidden=false;}
}
function resizeControl(handle,orientation,read,write,min,max) {
  handle.addEventListener("pointerdown",event=>{
    handle.setPointerCapture(event.pointerId);
    const initial=orientation==="vertical"?event.clientX:event.clientY,start=read();
    const move=event=>{const delta=(orientation==="vertical"?event.clientX:event.clientY)-initial;write(Math.max(min,Math.min(max(),start+(orientation==="vertical"?-delta:delta))));map.invalidateSize();};
    const finish=()=>{handle.removeEventListener("pointermove",move);};
    handle.addEventListener("pointermove",move);handle.addEventListener("lostpointercapture",finish,{once:true});
  });
  handle.addEventListener("keydown",event=>{
    const forward=orientation==="vertical"?"ArrowLeft":"ArrowDown",backward=orientation==="vertical"?"ArrowRight":"ArrowUp";
    if(![forward,backward].includes(event.key))return;
    event.preventDefault();write(Math.max(min,Math.min(max(),read()+(event.key===forward?24:-24))));map.invalidateSize();
  });
}
resizeControl($("settings-resize"),"vertical",()=>$("route-settings").getBoundingClientRect().width,value=>$("workspace").style.setProperty("--settings-width",value+"px"),280,()=>Math.min(640,innerWidth*.55));
resizeControl($("map-resize"),"horizontal",()=>$("map").getBoundingClientRect().height,value=>$("map").style.height=value+"px",300,()=>Math.min(900,innerHeight*.85));
new ResizeObserver(()=>{
  map.invalidateSize();
  if(innerWidth>850)$("route-settings").style.maxHeight=document.querySelector(".map-pane").getBoundingClientRect().height+"px";
  else $("route-settings").style.maxHeight="65vh";
}).observe($("map"));
async function startApp(){
  try{catalog=await (await fetch("/equipment-catalog.json")).json();}catch{status("Equipment catalog unavailable.");}
  // Populate default equipment before the first history snapshot.
  for(const node of project.network.nodes)panelFor(node.id);
  committed=JSON.stringify(project);syncFields();renderMap();renderNetworkList();updatePreview();
  try {
    const zones=await (await fetch("/api/zones")).json();
    L.geoJSON(zones.geojson,{filter:feature=>["Polygon","MultiPolygon"].includes(feature.geometry?.type),style:{color:"#ec9169",weight:1,fillOpacity:.12}}).addTo(zoneLayer);
  }catch{}
}
startApp();
