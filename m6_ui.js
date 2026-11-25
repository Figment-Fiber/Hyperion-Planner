"use strict";
let pendingInsertion=null,lastSavedRevision=null,recoveryTimer=null,recoveryDraft=null,comparisonSnapshot=null;
try{recoveryDraft=JSON.parse(localStorage.getItem('hyperion.recovery')||'null');}catch{}
const DEFAULT_REQUIREMENTS={rate_gbps:100,mode_id:'generic-100g',grid:'fixed',channels:1,center_thz:193.1,guard_band_ghz:0,launch_dbm:0,reserve_db:2};
const requirementBindings=[['req-rate','rate_gbps'],['req-mode','mode_id'],['req-grid','grid'],['req-channels','channels'],['req-center','center_thz'],['req-guard','guard_band_ghz'],['req-spacing','spacing_ghz'],['req-slot','slot_width_ghz'],['req-launch','launch_dbm'],['req-reserve','reserve_db'],['req-gsnr','required_gsnr_db'],['req-rx-min','rx_min_dbm'],['req-rx-max','rx_max_dbm'],['req-tx-osnr','tx_osnr'],['req-baud','baud_rate'],['req-roll','roll_off']];
function normalizeM6Project(){
  if(!project.m6)return;
  project.requirements||=clone(DEFAULT_REQUIREMENTS);
  for(const node of project.network.nodes){
    const settings=equipmentFor(node.id);settings.role||=[active().source,active().target].includes(node.id)?'terminal':'pass-through';
    settings.amplifiers||={};settings.amplifiers.by_neighbor||={};
    for(const link of project.network.links.filter(x=>[x.from,x.to].includes(node.id))){const neighbor=link.from===node.id?link.to:link.from;settings.amplifiers.by_neighbor[neighbor]||={};for(const direction of ['incoming','outgoing'])settings.amplifiers.by_neighbor[neighbor][direction]||=clone(settings.amplifiers[direction]||{enabled:false,control:'automatic',gain_db:15,target_dbm:0,model:'std_medium_gain'});}
  }
}
function syncM6Fields(){
  document.body.classList.toggle('m6-project',!!project.m6);
  const req=project.requirements||DEFAULT_REQUIREMENTS;
  for(const [id,key] of requirementBindings)$(id).value=key==='baud_rate'&&req[key]!==undefined?req[key]/1e9:req[key]??'';
  $('upgrade-project').hidden=!!project.m6;
  $('design-requirements').hidden=!project.m6;
  $('compare-rates').disabled=!project.m6;
  updateM6State();
}
function enableM6(){project.m6=true;project.requirements=clone(DEFAULT_REQUIREMENTS);delete project.reference_case;changed({editor:true});syncM6Fields();}
$('upgrade-project').onclick=enableM6;
for(const [id,key] of requirementBindings)$(id).onchange=()=>{
  if(!$(id).reportValidity())return;
  project.m6=true;project.requirements||=clone(DEFAULT_REQUIREMENTS);
  const value=$(id).value;
  if(value==='')delete project.requirements[key];else project.requirements[key]=$(id).type==='number'?$(id).valueAsNumber: (key==='rate_gbps'?Number(value):value);
  if(key==='baud_rate'&&value!=='')project.requirements[key]*=1e9;
  if(key==='rate_gbps') {project.requirements.mode_id='generic-'+value+'g';delete project.requirements.spacing_ghz;delete project.requirements.slot_width_ghz;project.equipment.service_gbps=Number(value);}
  if(key==='mode_id'){project.requirements.rate_gbps=Number(value.match(/\d+/)?.[0]||100);project.equipment.service_gbps=project.requirements.rate_gbps;}
  changed({editor:true});syncM6Fields();
};
$('requirements-defaults').onclick=()=>{project.m6=true;project.requirements=clone(DEFAULT_REQUIREMENTS);project.equipment.service_gbps=100;changed({editor:true});syncFields();syncM6Fields();};
$('service-rate').addEventListener('change',()=>{if(project.m6){project.requirements.rate_gbps=Number($('service-rate').value);project.requirements.mode_id='generic-'+project.requirements.rate_gbps+'g';delete project.requirements.spacing_ghz;delete project.requirements.slot_width_ghz;syncM6Fields();changed();}});
function updateM6State(){
  if(!$('project-state'))return;
  $('project-state').textContent=(lastSavedRevision===project.revision?'Project file downloaded':'Unsaved project changes')+' · Revision '+project.revision+(lastSnapshot===JSON.stringify(project)?' · Results current':' · Rerun after edits');
  const service=active();
  $('active-service-strip').textContent=(project.m6?'M07':'Legacy reference')+' · '+(site(service.source)?.name||service.source)+' → '+(site(service.target)?.name||service.target)+' · '+(project.requirements?.rate_gbps||project.equipment.service_gbps)+' GbE · '+(preview?.design?.lengths?.reduce((a,b)=>a+b,0).toFixed(3)||'—')+' km · '+(selection?selection.type+' '+selection.id:'Route overview');
  if(!$('comparison-pane').hidden&&comparisonSnapshot!==JSON.stringify(project))$('comparison-status').textContent='Design changed. Run comparison again for this revision.';
  clearTimeout(recoveryTimer);if(project.revision>1)recoveryTimer=setTimeout(()=>{try{localStorage.setItem('hyperion.recovery',JSON.stringify(project));}catch{}},700);
}
function markProjectSaved(){lastSavedRevision=project.revision;updateM6State();}
if(recoveryDraft)$('recover-draft').hidden=false;
$('recover-draft').onclick=async()=>{try{const value=recoveryDraft;await request('/api/preview',value);undoStack.push(JSON.stringify(project));restore(value);fitMap();$('recover-draft').hidden=true;}catch(error){status('Recovery unavailable: '+error.message);}};
window.addEventListener('beforeunload',event=>{if(project.revision>1&&lastSavedRevision!==project.revision){event.preventDefault();event.returnValue='';}});
function nearestSpan(point,excludeNode=null){
  // Include the marker's visible footprint, rather than requiring its center
  // to land almost exactly on a thin polyline. Confirmation remains mandatory.
  const pixel=map.latLngToLayerPoint(point);let match=null,best=28;
  for(const link of project.network.links){if(excludeNode&&[link.from,link.to].includes(excludeNode))continue;const points=spanPath(link).map(p=>map.latLngToLayerPoint(p));for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i],dx=b.x-a.x,dy=b.y-a.y,t=Math.max(0,Math.min(1,((pixel.x-a.x)*dx+(pixel.y-a.y)*dy)/(dx*dx+dy*dy||1))),distance=Math.hypot(pixel.x-a.x-t*dx,pixel.y-a.y-t*dy);if(distance<best){best=distance;match=link;}}}
  return match;
}
function offerInsertionAt(point,existingNodeId=null){const link=nearestSpan(point,existingNodeId);if(!link)return false;proposeInsertion(link.id,point,existingNodeId);return true;}
function proposeInsertion(linkId,point,existingNodeId=null){
  pendingInsertion={linkId,point,existingNodeId,base:existingNodeId?JSON.parse(committed):clone(project)};const link=project.network.links.find(x=>x.id===linkId);
  $('insert-description').textContent='Split '+site(link.from).name+' → '+site(link.to).name+' into two connected spans? Nothing will change until you select Yes.';
  $('insert-confirm').showModal();
}
$('insert-no').onclick=()=>{if(pendingInsertion?.existingNodeId){project=pendingInsertion.base;renderMap();}pendingInsertion=null;$('insert-confirm').close();status('Original span kept unchanged.');};
$('insert-confirm').addEventListener('cancel',()=>{if(pendingInsertion?.existingNodeId){project=pendingInsertion.base;renderMap();}pendingInsertion=null;status('Insertion cancelled; span unchanged.');});
$('insert-yes').onclick=()=>{
  if(!pendingInsertion)return;
  try{const edit=ProjectEditing.insertSite(pendingInsertion.base,pendingInsertion.linkId,pendingInsertion.point,$('insert-role').value,pendingInsertion.existingNodeId);project=edit.project;project.m6=true;project.requirements||=clone(DEFAULT_REQUIREMENTS);selection={type:'node',id:edit.insertedNodeId};pendingInsertion=null;$('insert-confirm').close();setTool(null);changed({editor:true});syncFields();syncM6Fields();status(edit.review?.length?'Site inserted. Review retained equipment assignments in results.':'Site inserted; spans split and lengths preserved.');}catch(error){$('insert-description').textContent=error.message;}
};
function checkField(parent,label,checked,change,id){const wrapper=document.createElement('label');wrapper.className='toggle';const input=document.createElement('input');input.type='checkbox';input.checked=checked;if(id)input.id=id;input.onchange=()=>{change(input.checked);changed({editor:true});};wrapper.append(input,document.createTextNode(label));parent.append(wrapper);return input;}
function stageControls(parent,settings,neighbor,direction){
  settings.amplifiers||={};settings.amplifiers.by_neighbor||={};settings.amplifiers.by_neighbor[neighbor]||={};
  const stages=settings.amplifiers.by_neighbor[neighbor];const stage=stages[direction]||=clone(settings.amplifiers[direction]||{enabled:false,control:'automatic',gain_db:15,target_dbm:0,model:'std_medium_gain'});
  const section=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=(direction==='incoming'?'Incoming preamp from ':'Outgoing booster toward ')+(site(neighbor)?.name||neighbor);section.append(legend);parent.append(section);
  checkField(section,'Use amplifier',stage.enabled,value=>stage.enabled=value,'amp-'+neighbor+'-'+direction);
  const controls=document.createElement('div');section.append(controls);
  selectField(controls,'Control',[['automatic','Automatic output target'],['manual','Manual gain']],stage.control,value=>stage.control=value);
  selectField(controls,'Generic model',[['std_low_gain','Low gain'],['std_medium_gain','Medium gain'],['std_high_gain','High gain']],stage.model,value=>stage.model=value);
  inputField(controls,stage.control==='manual'?'Requested gain (dB)':'Output target per channel (dBm)',stage.control==='manual'?stage.gain_db:stage.target_dbm,value=>{if(stage.control==='manual')stage.gain_db=value;else stage.target_dbm=value;},{min:stage.control==='manual'?0:-25,max:stage.control==='manual'?35:8});
  for(const field of controls.querySelectorAll('input,select,button'))field.disabled=!stage.enabled;
  controls.classList.toggle('disabled-stage',!stage.enabled);
}
function renderM6NodeControls(editor,node,settings){
  settings.role||=degrees(node.id)>1?'roadm':'terminal';
  selectField(editor,'Site role',[['terminal','Terminal'],['roadm','ROADM'],['amplifier','Amplifier site'],['splice','Splice site'],['pass-through','Passive pass-through'],['oeo','OEO regeneration']],settings.role,value=>settings.role=value,'node-role');
  if(settings.role==='splice')inputField(editor,'Additional site fusion-splice loss (dB)',settings.splice_loss_db??.1,value=>settings.splice_loss_db=value,{min:0,max:10,id:'site-splice-loss'});
  text(editor,'Selected service: '+(active().source===node.id?'Transmit terminal':active().target===node.id?'Receive terminal':settings.role==='roadm'?'ROADM express transit':settings.role==='oeo'?'Receive → electrical regeneration → transmit':'Optical pass-through'));
  const amps=document.createElement('details');amps.open=true;const title=document.createElement('summary');title.textContent='Amplifiers · optional';amps.append(title);editor.append(amps);
  for(const link of project.network.links.filter(x=>[x.from,x.to].includes(node.id))){const other=link.from===node.id?link.to:link.from;stageControls(amps,settings,other,'incoming');stageControls(amps,settings,other,'outgoing');}
  text(amps,'Unchecked stages are absent from the optical path. Automatic sets a target only for enabled hardware. Inspect effective gain and ASE after running.');
  for(const reading of lastResult?.component_readings||[]){if(!reading.uid.startsWith('Amp_'+node.id+'_'))continue;const pre=document.createElement('pre');pre.textContent='Last simulated revision '+lastResult.revision+' · '+reading.uid+'\n'+JSON.stringify(reading,null,2);amps.append(pre);}
  const bulk=document.createElement('details'),heading=document.createElement('summary');heading.textContent='Copy site setup';bulk.append(heading);editor.append(bulk);
  const destinations=inputField(bulk,'Target site IDs, comma separated','',()=>{}, {type:'text'});
  const copy=document.createElement('button');copy.textContent='Review copy';copy.onclick=()=>{const ids=destinations.value.split(',').map(x=>x.trim()).filter(Boolean);if(!ids.length)return;showDetail('Copy setup to '+ids.join(', '),'Panel, role and equipment settings will be copied. Existing manual amplifier settings are preserved.');const button=document.createElement('button');button.textContent='Apply copy';button.onclick=()=>{try{project=ProjectEditing.copySettings(project,node.id,ids,{preserveAmplifierOverrides:true});$('option-detail').close();changed({editor:true});}catch(error){$('option-reason').textContent=error.message;}};$('option-reason').append(button);};bulk.append(copy);
}
function renderM6SpanControls(editor,link){const button=document.createElement('button');button.textContent='Insert site into this span';button.id='insert-site';button.onclick=()=>{tool='insert';status('Click the chosen position on this span. You will confirm before it splits.');};editor.append(button);if(link.override!==null&&link.override!==undefined)text(editor,'ENGINEERED OVERRIDE · Moving sites or bends will not change the simulated length.');}
function showM6Results(result){
  const path=$('optical-path');path.replaceChildren();
  if(result.service_check){const p=document.createElement('p');p.textContent='Mode feasibility: '+result.service_check.status+' · '+(result.service_check.reason||result.service_check.detail||'');p.className=['Fail','Review'].includes(result.service_check.status)?'span-warning':'';path.append(p);}
  const sections=result.sections||[result];for(const [sectionIndex,section] of sections.entries()){
    if(sections.length>1)text(path,'Optical section '+(sectionIndex+1));
    for(const element of section.topology_input?.elements||[]){const chip=document.createElement('button');chip.textContent=element.uid+' · '+element.type;chip.onclick=()=>{const span=/^Span(\d+)/.exec(element.uid);const match=project.network.nodes.find(n=>element.uid==='Roadm_'+n.id||element.uid.startsWith('Amp_'+n.id+'_')||element.uid==='Splice_'+n.id);if(span&&result.selected_path?.links[Number(span[1])-1])choose('link',result.selected_path.links[Number(span[1])-1].id);else if(match)choose('node',match.id);else showDetail(element.uid,JSON.stringify(element,null,2));};path.append(chip);}
  }
  const spectrum=$('spectrum-view');spectrum.replaceChildren();const spec=result.service||result.service_spec;
  if(spec){text(spectrum,'Spectrum · '+(spec.mode_id||'')+' · '+(spec.assumption_status||'Generic assumptions'));for(const allocation of spec.allocations||[]){const block=document.createElement('div');block.className='spectrum-slot';block.textContent='Ch '+allocation.channel+' · '+allocation.frequency_thz.toFixed(5)+' THz · slot '+(allocation.slot_width/1e9)+' GHz · signal '+spec.occupied_width_ghz+' GHz';const band=document.createElement('span');band.className='occupied-spectrum';band.style.width=Math.min(100,spec.occupied_width_ghz/(allocation.slot_width/1e9)*100)+'%';block.append(band);spectrum.append(block);}}
  for(const review of project.edit_reviews||[]){if(review.acknowledged)continue;text(path,typeof review==='string'?review:review.message||JSON.stringify(review),'span-warning');if(typeof review==='object'){const ack=document.createElement('button');ack.textContent='Acknowledge reviewed assignment';ack.onclick=()=>{review.acknowledged=true;changed();};path.append(ack);}}
}
$('compare-rates').onclick=async()=>{
  if(!validFields())return;
  const source=JSON.stringify(project);$('comparison-pane').hidden=false;$('comparison-grid').replaceChildren();$('comparison-status').textContent='Calculating three alternative service modes on the same physical route…';$('compare-rates').disabled=true;
  $('comparison-pane').scrollIntoView({behavior:'smooth',block:'start'});
  try{const response=await request('/api/compare',clone(project));comparisonSnapshot=source;for(const scenario of response.scenarios){const card=document.createElement('article');card.className='comparison-card';const heading=document.createElement('h3');heading.textContent=scenario.rate_gbps+' Gb/s';card.append(heading);if(scenario.error){text(card,scenario.error,'span-warning');}else{const result=scenario.result;const mode=result.service||result.service_spec||{};text(card,mode.mode_id||'Generic mode');text(card,'Status: '+(result.service_check?.status||'Not evaluated'));text(card,result.service_check?.reason||'Generic planning assumptions; not vendor-certified');text(card,'GSNR, limiting channel: '+formatMetric(Math.min(...result.channels.map(c=>c.gsnr_db)))+' dB');text(card,'Slot: '+(mode.slot_width_ghz??mode.allocations?.[0]?.slot_width_ghz??'See allocation')+' GHz');text(card,'Baud rate: '+(mode.baud_rate/1e9)+' GBd · occupied '+mode.occupied_width_ghz+' GHz');text(card,'Receive power: '+formatMetric(Math.min(...result.channels.map(c=>c.power_dbm)))+' dBm/channel');text(card,'Worst section margin: '+formatMetric(Math.min(...(result.sections||[]).map(s=>s.service_check.margin_db??Infinity)))+' dB');text(card,'Channels: '+result.channels.length);text(card,'Distance: '+result.span_length_km.toFixed(3)+' km');const apply=document.createElement('button');apply.textContent='Use this mode';apply.onclick=()=>{project.requirements=clone(scenario.requirements);project.equipment.service_gbps=scenario.rate_gbps;changed({editor:true});syncFields();syncM6Fields();};card.append(apply);const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='Mode, spectrum and margin details';pre.textContent=JSON.stringify({mode,verdict:result.service_check,sections:result.sections?.map(s=>s.service_check)},null,2);details.append(summary,pre);card.append(details);} $('comparison-grid').append(card);} $('comparison-status').textContent=source===JSON.stringify(project)?'Three alternative single-handoff scenarios; same physical route, rate-specific mode/slot defaults. Results use labeled generic assumptions.':'Comparison completed for the previous revision. Rerun after edits.';if(response.workbook_url){const link=document.createElement('a');link.href=response.workbook_url;link.textContent='Download comparison Excel';$('comparison-status').append(document.createTextNode(' '),link);}}catch(error){$('comparison-status').textContent='Comparison failed: '+error.message;}finally{$('compare-rates').disabled=false;}
};
$('close-comparison').onclick=()=>$('comparison-pane').hidden=true;
function formatMetric(value,digits=2){return value===null||value===undefined?'∞ / no contribution':Number.isFinite(value)?value.toFixed(digits):'Not evaluated';}
function confirmTopologyChange(title,note,apply){showDetail(title,note);const button=document.createElement('button');button.textContent='Confirm change';button.onclick=()=>{$('option-detail').close();apply();};$('option-reason').append(button);}
normalizeM6Project();committed=JSON.stringify(project);syncM6Fields();
