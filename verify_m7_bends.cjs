"use strict";
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const ProjectEditing=require('./project_editing.js');
const app=fs.readFileSync(path.join(__dirname,'hyperion.js'),'utf8');
const m6=fs.readFileSync(path.join(__dirname,'m6_ui.js'),'utf8');
const copy=x=>JSON.parse(JSON.stringify(x));
const before={version:2,m6:true,project_id:'m7-bend-check',active_service:'ac',
  requirements:{rate_gbps:100,channels:1},
  network:{nodes:[{id:'A',name:'A',lat:21.335,lon:-158.058},{id:'B',name:'B',lat:21.307,lon:-157.858},
    {id:'C',name:'C',lat:21.50,lon:-157.70},{id:'D',name:'D',lat:21.15,lon:-157.72}],
    links:[['ab','A','B'],['bc','B','C'],['bd','B','D']].map(([id,from,to])=>({id,from,to,bends:[],override:null,splices:[.1],inline_gain:null,fiber:{type_variety:'SSMF',loss_coef:.2}})),
    services:[{id:'ac',source:'A',target:'C'},{id:'ad',source:'A',target:'D'}]},
  equipment:{vendor:'generic',nodes:{A:{role:'terminal'},B:{role:'roadm'},C:{role:'terminal'},D:{role:'terminal'}}}};
const elements={};const lines=[],markers=[];let handler, edits=0,clears=0;
const context={project:copy(before),ProjectEditing,tool:'bend',selection:{type:'link',id:'ab'},preview:null,draggingSite:false,draggingBend:false,
  map:{latLngToLayerPoint:p=>({x:p[1]*10000,y:-p[0]*10000}),on:(name,fn)=>{handler=fn;}},
  $:id=>elements[id]||=( {} ),status(){},changed(){edits++;},routeLayer:{clearLayers(){clears++;}},
  L:{DomEvent:{stopPropagation(){}},divIcon:x=>x,
    polyline:()=>({handlers:{},addTo(){lines.push(this);return this;},on(name,fn){this.handlers[name]=fn;return this;}}),
    marker:(point,options)=>({point,options,handlers:{},addTo(){markers.push(this);return this;},getElement(){return {};},on(name,fn){this.handlers[name]=fn;return this;},getLatLng(){return {wrap:()=>({lat:this.point[0],lng:this.point[1]})};}})}};
context.site=id=>context.project.network.nodes.find(n=>n.id===id);
context.spanPath=link=>[[context.site(link.from).lat,context.site(link.from).lon],...link.bends,[context.site(link.to).lat,context.site(link.to).lon]];
vm.createContext(context);
vm.runInContext(m6.slice(m6.indexOf('function nearestSpan('),m6.indexOf('function proposeInsertion(')),context);
vm.runInContext(app.slice(app.indexOf('map.on("click"'),app.indexOf('function choose(')),context);
vm.runInContext(app.slice(app.indexOf('function renderMap('),app.indexOf('function renderNetworkList(')),context);
const click=(lat,lon)=>handler({latlng:{wrap:()=>({lat,lng:lon})}});
const link=id=>context.project.network.links.find(l=>l.id===id);
click(21.32,-157.96);assert.equal(link('ab').bends.length,1);
const ab=copy(link('ab'));
const abOnly=copy(context.project);
// Starting on AB must not trap subsequent map clicks on the BC or BD branch.
click(21.4035,-157.779);assert.equal(context.selection.id,'bc');
assert.deepEqual(copy(link('ab')),ab);
const first=copy(link('bc').bends[0]);
click(21.35525,-157.8185);
assert.deepEqual(copy(link('bc').bends),[[21.35525,-157.8185],first], 'Earlier-segment bend must precede the later bend');
// A deliberate detour away from all lines stays on the selected BC span.
click(21.43,-157.9);assert.equal(context.selection.id,'bc');
const bcOnly=copy(context.project),bc=copy(link('bc'));
click(21.2285,-157.789);assert.equal(context.selection.id,'bd');
assert.deepEqual(copy(link('bc')),bc);assert.deepEqual(copy(link('ab')),ab);
// Test the actual polyline click handler as well as the map fallback.
context.renderMap();
lines[1].handlers.click({latlng:{wrap:()=>({lat:21.45175,lng:-157.7395})}});
assert.equal(context.selection.id,'bc');assert.equal(link('bc').bends.length,4);
assert.equal(link('bd').bends.length,1);assert.equal(edits,6);
// A delayed preview must not destroy a bend marker while it is being dragged.
context.renderMap();
const bend=markers.findLast(m=>m.options.icon.className==='bend-point');
const redraws=clears;
bend.handlers.dragstart();context.renderMap();assert.equal(clears,redraws);
bend.handlers.dragend();assert.equal(context.draggingBend,false);
for(const original of before.network.links){
  const edited=link(original.id);const {bends,...rest}=edited;const {bends:old,...originalRest}=original;
  assert.deepEqual(copy(rest),originalRest,'Bend edits must not alter losses, overrides, equipment or endpoints');
}
assert.deepEqual(copy(context.project.equipment),before.equipment);
assert.deepEqual(JSON.parse(JSON.stringify(context.project)),copy(context.project));
assert.equal(ProjectEditing.bendSegmentIndex([[0,0],[10,0],[10,10]],[5,2]),0);
assert.equal(ProjectEditing.bendSegmentIndex([[0,0],[10,0],[10,10]],[12,5]),1);
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify({before,abOnly,bcOnly,after:context.project},null,2));
console.log('Passed M07 multi-degree AB→BC→BD switching, polyline clicks, ordered segment insertion, save serialization and unchanged engineering settings.');
