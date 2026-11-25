"""Independent M06 cross-module regressions with real GNPy propagation."""
from copy import deepcopy
import json
from pathlib import Path
from m6_engine import network_simulation_m6, prepare_network_m6, section_inputs
from verify_m6_engine import fixture


def check():
    findings = []
    evidence = {}

    def expect(condition, name):
        findings.append({'check': name, 'status': 'Pass' if condition else 'Fail'})

    base = fixture(2, 10)
    base['requirements'].update(channels=1, required_gsnr_db=-10, reserve_db=0)
    generic = network_simulation_m6(base)
    expect(generic['service_check']['status'] == 'Pass', 'Generic short path can pass')
    vendor = deepcopy(base)
    vendor['equipment']['vendor'] = 'ciena'
    vendor_result = network_simulation_m6(vendor)
    expect(vendor_result['service_check']['status'] == 'Not evaluated',
           'Unqualified vendor optical mode blocks overall Pass')
    mismatch = deepcopy(base)
    mismatch['equipment']['vendor'] = 'ciena'
    mismatch['equipment']['nodes']['N0']['profile_id'] = 'nokia-1830-pss-hc-4cp4t8'
    mismatch_result = network_simulation_m6(mismatch)
    expect(mismatch_result['service_check']['status'] == 'Fail',
           'Vendor hardware incompatibility reaches overall verdict')
    capacity = deepcopy(base)
    capacity['requirements'].update(rate_gbps=400, mode_id='generic-400g')
    capacity['equipment']['vendor'] = 'ciena'
    for node in capacity['equipment']['nodes'].values():
        node['profile_id'] = 'ciena-2x100g-motr'
    capacity_result = network_simulation_m6(capacity)
    expect(capacity_result['service_check']['status'] == 'Fail',
           '400G requirement checked against 100G-only hardware despite missing equipment rate')
    unknown = deepcopy(base)
    unknown['requirements']['mode_id'] = 'unqualified-mode'
    unknown_result = network_simulation_m6(unknown)
    expect(unknown_result['service_check']['status'] == 'Not evaluated',
           'Unknown operating mode cannot pass with supplied numeric limits')

    roadm = fixture(3, 1)
    roadm['requirements'].update(channels=1, required_gsnr_db=-10, reserve_db=0)
    roadm['equipment']['nodes']['N1'].update(role='roadm', roadm={'target_pch_out_db': -1, 'path_loss_db': 2, 'passband_ghz': 50})
    normal = network_simulation_m6(roadm)
    changed = deepcopy(roadm)
    changed['equipment']['nodes']['N1']['roadm']['path_loss_db'] = 12
    lossy = network_simulation_m6(changed)
    expect(abs(lossy['channels'][0]['power_dbm'] - normal['channels'][0]['power_dbm'] + 10) < .02,
           'ROADM path loss changes actual propagated power by 10 dB')
    narrow = deepcopy(roadm)
    narrow['equipment']['nodes']['N1']['roadm'].update(band_min_thz=193.09, band_max_thz=193.11)
    narrow_result = network_simulation_m6(narrow)
    expect(narrow_result['service_check']['status'] == 'Fail',
           'WSS passband narrower than occupied spectrum fails')
    width = deepcopy(roadm)
    width['equipment']['nodes']['N1']['roadm']['passband_ghz'] = 12.5
    width_result = network_simulation_m6(width)
    expect(width_result['service_check']['status'] == 'Fail', 'Per-channel WSS width check fails below occupied width')
    zero = deepcopy(roadm)
    zero['equipment']['nodes']['N1']['roadm']['target_pch_out_db'] = 0
    zero_result = network_simulation_m6(zero)
    expect(len(zero_result['channels']) == 1, 'Exact zero dBm ROADM target runs successfully')

    disabled = deepcopy(base)
    disabled['equipment']['nodes']['N0']['amplifiers'] = {
        'outgoing': {'enabled': True, 'control': 'manual', 'gain_db': 15},
        'by_neighbor': {'N1': {'outgoing': {'enabled': False}}}}
    off = network_simulation_m6(disabled)
    expect(not any(e['type'] == 'Edfa' for e in off['effective_topology']['elements']),
           'Per-neighbor disabled stage absent from effective topology')
    expect(off['channels'] == generic['channels'], 'Disabled stage leaves propagated channel metrics unchanged')
    oeo = fixture(4, 1)
    oeo['equipment']['nodes']['N1']['role'] = 'oeo'
    oeo['equipment']['nodes']['N2']['role'] = 'oeo'
    oeo['network']['links'][1]['override'] = 200
    oeo_result = network_simulation_m6(oeo)
    expect(len(oeo_result['sections']) == 3 and oeo_result['sections'][1]['service_check']['status'] == 'Fail'
           and oeo_result['service_check']['status'] == 'Fail', 'Middle OEO section failure survives clean final section')
    twenty = fixture(20, 1)
    expect(len(prepare_network_m6(twenty)['route']['nodes']) == 20, 'Twenty-site path accepted')
    too_many = fixture(21, 1)
    try:
        prepare_network_m6(too_many)
        rejected = False
    except ValueError:
        rejected = True
    expect(rejected, 'Twenty-first site rejected')
    for name, value in [('generic', generic), ('vendor', vendor_result), ('mismatch', mismatch_result), ('capacity', capacity_result),
                        ('unknown', unknown_result), ('roadm', normal), ('lossy', lossy),
                        ('narrow', narrow_result), ('width', width_result), ('zero_target', zero_result), ('off', off), ('oeo', oeo_result)]:
        evidence[name] = value
    destination = Path('evidence/m06/integration')
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'results.json').write_text(json.dumps({'checks': findings, 'runs': evidence}, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(findings, indent=2))
    assert all(check['status'] == 'Pass' for check in findings), 'Integration regressions remain; see evidence/m06/integration/results.json'


if __name__ == '__main__':
    check()
