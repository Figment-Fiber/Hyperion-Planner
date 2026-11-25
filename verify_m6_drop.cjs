"use strict";
// Exercise the shipped map handlers, including a preview redraw during dragging.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function shippedFunction(file, name, next) {
  const source = fs.readFileSync(path.join(__dirname, file), 'utf8');
  return source.slice(source.indexOf('function '+name+'('), source.indexOf('function '+next+'('));
}
let clears=0, changed=0, proposal=null;
const markers=[];
const context={
  project:{network:{nodes:[{id:'A',lat:0,lon:0},{id:'B',lat:0,lon:200},{id:'C',lat:80,lon:100}],
    links:[{id:'ab',from:'A',to:'B',bends:[[0,100]],override:80,inline_gain:null}]}},
  selection:null,preview:null,draggingSite:false,draggingBend:false,insertionHighlight:null,
  map:{latLngToLayerPoint:p=>({x:p[1],y:p[0]}),removeLayer(){}},
  routeLayer:{clearLayers(){clears++;}},
  changed(){changed++;}, status(){},
  L:{divIcon:x=>x,polyline:()=>({addTo(){return this;},on(){return this;}}),
    marker(point){const marker={point,handlers:{},element:{},
      addTo(){markers.push(this);return this;},getElement(){return this.element;},
      on(name,handler){this.handlers[name]=handler;return this;},
      getLatLng(){return {wrap:()=>({lat:this.point[0],lng:this.point[1]})};}};return marker;}},
};
context.site=id=>context.project.network.nodes.find(n=>n.id===id);
context.spanPath=link=>[[context.site(link.from).lat,context.site(link.from).lon],...link.bends,[context.site(link.to).lat,context.site(link.to).lon]];
context.proposeInsertion=(...args)=>{proposal=args;};
vm.createContext(context);
vm.runInContext(shippedFunction('m6_ui.js','nearestSpan','proposeInsertion'),context);
vm.runInContext(shippedFunction('hyperion.js','renderMap','renderNetworkList'),context);
assert.equal(context.nearestSpan([24,100],'C').id,'ab','Visible marker overlap must offer insertion');
assert.equal(context.nearestSpan([40,100],'C'),null,'Distant drops must remain ordinary moves');
assert.equal(context.nearestSpan([0,100],'A'),null,'Never split a span at its own endpoint');
context.renderMap();
const c=markers.find(m=>m.element.id==='point-c');
c.handlers.dragstart();
context.renderMap();
assert.equal(clears,1,'A background preview redraw must not destroy an active marker');
c.point=[24,100];c.handlers.drag();
assert(context.insertionHighlight,'Eligible span should highlight while dragging');
c.handlers.dragend();
assert.equal(context.draggingSite,false);
assert.equal(context.insertionHighlight,null);
assert.equal(proposal[0],'ab');assert.equal(proposal[2],'C');
assert.equal(changed,0,'Dropping on a span must wait for confirmation');
assert.equal(context.project.network.links.length,1);
assert.equal(context.project.network.links[0].override,80);
context.renderMap();assert.equal(clears,2,'Redraw must resume after the drag');
// The final marker coordinates remain authoritative even without a last drag event.
const fresh=markers.findLast(m=>m.element.id==='point-c');
fresh.handlers.dragstart();fresh.point=[70,100];proposal=null;fresh.handlers.dragend();
assert.equal(proposal,null);assert.equal(changed,1);
assert.equal(context.site('C').lat,70);
console.log('Passed M06 drop tolerance, endpoint exclusion, highlight, preview redraw race, confirmation gate and final-coordinate checks.');
