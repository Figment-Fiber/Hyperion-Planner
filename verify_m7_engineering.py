"""Check map-edit fixtures against actual GNPy inputs and propagated metrics.

First run: node verify_m7_bends.cjs <fixtures.json>
Then run this file with that path and optionally an evidence output path.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
from m6_engine import network_simulation_m6, prepare_network_m6, section_inputs


def check(fixtures):
    cases = json.loads(Path(fixtures).read_text(encoding='utf-8'))
    checks, runs = [], {}

    def expect(condition, description):
        assert condition, description
        checks.append(description)

    def run(name, project, service='ac'):
        project = deepcopy(project)
        project['active_service'] = service
        result = network_simulation_m6(project)
        runs[name] = result
        return result

    original = run('before_bc_edit', cases['abOnly'])
    bent = run('after_bc_edit', cases['bcOnly'])
    old = prepare_network_m6(cases['abOnly'])
    new = prepare_network_m6(cases['bcOnly'])
    delta = new['design']['lengths'][1] - old['design']['lengths'][1]
    expect(delta > 1, 'A BC detour increases its WGS84 length by more than 1 km')
    expect(new['design']['lengths'][0] == old['design']['lengths'][0], 'AB length is unchanged by a BC edit')
    fibers = [e for e in section_inputs(new)[0]['topology']['elements'] if e['type'] == 'Fiber']
    expect([f['params']['length'] for f in fibers] == new['design']['lengths'], 'Actual GNPy fibers use edited effective lengths')
    power_delta = bent['channels'][0]['power_dbm'] - original['channels'][0]['power_dbm']
    expect(abs(power_delta + delta * .2) < .03, 'Downstream BC added length produces the expected 0.2 dB/km receiver loss')
    unaffected_before = run('ad_before_bc_edit', cases['abOnly'], 'ad')
    unaffected_after = run('ad_after_bc_edit', cases['bcOnly'], 'ad')
    expect(unaffected_before['channels'] == unaffected_after['channels'], 'Editing off-path BC leaves A-B-D channel results unchanged')
    reverse = deepcopy(cases['bcOnly'])
    reverse['network']['services'][0].update(source='C', target='A')
    reversed_route = prepare_network_m6(reverse)
    expect(reversed_route['geometry']['km'] == list(reversed(new['geometry']['km'])), 'Reverse service uses the same span lengths with reversed bends')

    fixed_before, fixed_after = deepcopy(cases['abOnly']), deepcopy(cases['bcOnly'])
    for project in (fixed_before, fixed_after):
        project['network']['links'][1]['override'] = 60
    fixed_a, fixed_b = run('override_before', fixed_before), run('override_after', fixed_after)
    expect(fixed_a['channels'] == fixed_b['channels'], 'Geometry edits preserve an explicit 60 km override and its optical results')
    expect(prepare_network_m6(fixed_after)['geometry']['km'][1] != 60, 'Drawn length stays separate from the engineered length')

    spliced = deepcopy(cases['bcOnly'])
    spliced['network']['links'][1]['splices'].append(.3)
    loss = run('extra_splice', spliced)
    expect(abs(loss['channels'][0]['power_dbm'] - bent['channels'][0]['power_dbm'] + .3) < .02, 'Added 0.3 dB splice reaches propagated receiver power')
    amplified = deepcopy(cases['bcOnly'])
    amplified['equipment']['nodes']['B']['amplifiers'] = {'by_neighbor': {'C': {'outgoing': {
        'enabled': True, 'control': 'manual', 'gain_db': 15, 'model': 'std_medium_gain'}}}}
    amp = run('bc_amplifier', amplified)
    stages = [r for r in amp['component_readings'] if r['type'] == 'Edfa']
    expect(len(stages) == 1 and stages[0]['noise_figure_db'] > 0, 'Enabled BC amplifier appears once and adds nonzero modeled noise figure')
    expect(amp['channels'][0]['osnr_ase_db'] < bent['channels'][0]['osnr_ase_db'], 'Enabled amplifier ASE reduces reported OSNR relative to the passive case')
    ad_amp = run('ad_with_bc_amplifier', amplified, 'ad')
    expect(ad_amp['channels'] == unaffected_after['channels'], 'An off-path BC amplifier does not enter A-B-D propagation')
    return {'status': 'Pass', 'checks': checks, 'runs': runs}


if __name__ == '__main__':
    evidence = check(sys.argv[1])
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(evidence, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'status': evidence['status'], 'checks': evidence['checks']}, indent=2))
