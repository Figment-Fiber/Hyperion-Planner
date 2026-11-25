"""M06 full network and OEO amplifier inventory reconciliation regressions."""
from copy import deepcopy
from engineering_model import summarize_network
from verify_m5_equipment import fixture

def main():
    project = fixture()
    project['equipment']['nodes']['b'] = {'role':'oeo', 'amplifiers': {
        'incoming': {'enabled': True},
        'by_neighbor': {'d': {'incoming': {'enabled': False}, 'outgoing': {'enabled': True}}}}}
    planned = summarize_network(project)
    items = {i['id']:i for i in planned['bom']}
    assert items['b.transponder']['quantity'] == 2
    assert 'b.amp.incoming.a' in items and 'b.amp.incoming.c' in items
    assert 'b.amp.incoming.d' not in items and 'b.amp.outgoing.d' in items
    route = {'nodes':[{'id':'a'},{'id':'b'},{'id':'c'}], 'links':[{'id':'ab'},{'id':'bc'}]}
    result = {'selected_path':route, 'sections':[
        {'topology_input': {'elements':[{'uid':'Amp_b_incoming','type':'Edfa'}]}},
        {'topology_input': {'elements':[{'uid':'Amp_b_outgoing','type':'Edfa'}, {'uid':'ILA_2','type':'Edfa'}]}}]}
    # Explicit midpoint configured for the selected second link.
    project['network']['links'][1]['inline_gain'] = 12
    result['service_id'] = 'ac'
    summary = summarize_network(project, result)
    ids = [i['id'] for i in summary['bom']]
    assert len(ids) == len(set(ids))
    assert ids.count('b.amp.incoming.a') == 1
    assert ids.count('bc.inline-edfa') == 1
    assert len(summary['actual_service_amplifiers']) == 3
    assert any(i['engine_element_id']=='Amp_b_incoming' for i in summary['actual_service_amplifiers'])
    assert 'b.amp.outgoing.d' in ids
    express = deepcopy(project)
    express['equipment']['nodes']['b'] = {'role':'pass-through','profile_id':'ciena-2x100g-motr'}
    summary = summarize_network(express)
    assert not any(i['id']=='b.transponder' for i in summary['bom'])
    assert not any(i.get('node_id')=='b' and i['check']=='Client equipment' for i in summary['issues'])
    assert summary['estimator_equipment']['items'] == summary['bom']
    print('M06 full-network amplifier OFF/ON, OEO quantities, section reconciliation and stable export passed.')

if __name__ == '__main__':
    main()
