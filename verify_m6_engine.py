"""Focused real-GNPy M06 checks; runs locally without paid services."""
from copy import deepcopy
import json
from m6_engine import network_simulation_m6, prepare_network_m6, section_inputs, run_section, _parse, CHANNEL_HEADING


def fixture(count=2, length=40):
    ids = [f'N{i}' for i in range(count)]
    return {'version':2,'m6':True,'project_id':'m6-engine-test', 'network':{
        'nodes':[{'id':uid,'name':uid,'lat':21.3+i*.01,'lon':-157.9+i*.01} for i,uid in enumerate(ids)],
        'links':[{'id':f'L{i}','from':a,'to':b,'override':length,'bends':[], 'splices':[]} for i,(a,b) in enumerate(zip(ids,ids[1:]))],
        'services':[{'id':'S','source':ids[0],'target':ids[-1]}]},
        'equipment':{'nodes':{uid:{'role':'pass-through' if 0<i<count-1 else 'terminal'} for i,uid in enumerate(ids)}},
        'requirements':{'rate_gbps':100,'channels':3}}


def check():
    payload=fixture()
    base=network_simulation_m6(payload)
    assert len(base['channels'])==3
    assert not any(e['type']=='Edfa' for e in base['effective_topology']['elements'])
    # CLI includes transmitter noise in its OSNR ASE column even without EDFA.
    assert all(row['osnr_ase_db'] is not None for row in base['channels'])
    assert all(row['gsnr_db'] is not None for row in base['channels'])
    json.dumps(base,allow_nan=False)
    noiseless = _parse(CHANNEL_HEADING+'\n1 193.1 -1 inf inf inf',1)
    assert noiseless[0]['no_ase'] and noiseless[0]['osnr_ase_db'] is None
    json.dumps(noiseless,allow_nan=False)
    changed=deepcopy(payload)
    changed['network']['links'][0]['splices']=[1]
    loss=network_simulation_m6(changed)
    assert abs(loss['channels'][0]['power_dbm']-base['channels'][0]['power_dbm']+1)<.011
    changed['equipment']['nodes']['N1']['amplifiers']={'incoming':{'enabled':True,'control':'manual','gain_db':15}}
    amplified=network_simulation_m6(changed)
    assert sum(e['type']=='Edfa' for e in amplified['effective_topology']['elements'])==1
    assert amplified['channels'][0]['osnr_ase_db'] is not None
    assert amplified['channels'][0]['power_dbm']>loss['channels'][0]['power_dbm']+10
    stage=next(r for r in amplified['component_readings'] if r['type']=='Edfa')
    assert stage['uid']=='Amp_N1_incoming' and stage['node_id']=='N1' and stage['section_id']==1
    assert stage['effective_gain_db']==15 and stage['noise_figure_db']>0
    assert 'input_power_dbm' in stage and 'output_power_dbm' in stage
    assert len(stage['channel_output_power_dbm'])==3
    # Per-neighbor direction override can explicitly turn a globally enabled stage off.
    changed['equipment']['nodes']['N1']['amplifiers']['by_neighbor']={'N0':{'incoming':{'enabled':False}}}
    prepared=prepare_network_m6(changed)
    assert not any(e['type']=='Edfa' for e in section_inputs(prepared)[0]['topology']['elements'])
    # OEO retains first-section failures instead of reporting only a clean final section.
    regenerated=fixture(3,40)
    regenerated['network']['links'][0]['override']=140
    regenerated['equipment']['nodes']['N1']['role']='oeo'
    oeo=network_simulation_m6(regenerated)
    assert len(oeo['sections'])==2
    assert oeo['sections'][0]['service_check']['status']=='Fail'
    assert oeo['service_check']['status']=='Fail'
    assert oeo['sections'][1]['channels'][0]['power_dbm']>oeo['sections'][0]['channels'][0]['power_dbm']+15
    assert {r['section_id'] for r in oeo['component_readings']}=={1,2}
    twenty=fixture(20,1)
    many=network_simulation_m6(twenty)
    assert len(many['spans'])==19
    assert len(many['selected_path']['nodes'])==20
    # CLI replay of saved exact inputs is independently repeatable, including override.
    original=section_inputs(prepare_network_m6(payload))[0]
    replay=run_section(original,3)
    assert replay['channels']==base['channels']
    limited=fixture(length=200)
    limited['equipment']['nodes']['N1']['amplifiers']={'incoming':{'enabled':True,'control':'automatic','target_dbm':8}}
    capped=network_simulation_m6(limited)
    assert any(i['check']=='Amplifier channel target' for i in capped['engineering']['issues'])
    print(json.dumps({'status':'PASS','checks':['three exact channels','zero hidden amplifiers','JSON-safe no-ASE infinity','splice changes receiver power','enabled amplifier adds ASE and gain','per-degree OFF override','OEO all-section failure aggregation','twenty-site real GNPy path','saved-input CLI replay'], 'baseline_channels':base['channels'], 'runtime_seconds':sum(r['runtime_seconds'] for r in (base,loss,amplified,oeo,many))},indent=2))


if __name__=='__main__':
    check()
