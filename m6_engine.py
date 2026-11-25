"""Explicit M06 optical sections, replayed through the pinned GNPy CLI.

No element is implicitly amplified: --no-insert-edfas disables GNPy's element
insertion and Span.padding=0 disables automatic minimum-span attenuation.
OEO sites terminate one independent optical section and start the next.
"""
from copy import deepcopy
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import math
import re
import subprocess
import sys
import time

from gnpy_reference import ANSI, CHANNEL_HEADING, GNPY_VERSION, configured_edfa
from route_geometry import resolve_network, segmented_route


def number(value, low, high, label):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be a finite number from {low} to {high}.")
    return value


def prepare_network_m6(payload):
    from engineering_model import panel_connections, summarize_network, equipment_settings
    from service_model import resolve_service
    from zones_screening import screen_routes
    from hyperion import marine_screening
    route = resolve_network(payload)
    geometry = segmented_route(route['coordinates'], route['span_bends'], marine_screening)
    projected = deepcopy(payload)
    entries = payload.get('equipment', {}).get('nodes', {})
    nodes = []
    for index, node in enumerate(route['nodes']):
        entry = deepcopy(entries.get(node['id'], {}))
        entry.update(id=node['id'], degrees=route['degrees'][node['id']],
                     local_add_drop=index in (0, len(route['nodes']) - 1))
        entry.setdefault('role', 'roadm' if entry['degrees'] > 1 else 'terminal')
        if entry['role'] not in ('terminal', 'roadm', 'amplifier', 'splice', 'pass-through', 'oeo'):
            raise ValueError('Unsupported optical site role.')
        nodes.append(entry)
    projected.update(coordinates=route['coordinates'], site_names=route['site_names'],
                     site_ids=[node['id'] for node in route['nodes']])
    projected.setdefault('equipment', {})['nodes'] = nodes
    connections = panel_connections(projected)
    lengths, fibers, splices, gains = [], [], [], []
    for index, link in enumerate(route['links']):
        length = link.get('override') or geometry['km'][index]
        number(length, .000001, 20000, 'Span length in km')
        fiber = link.get('fiber', {'type_variety': 'SSMF', 'loss_coef': .2})
        if fiber.get('type_variety', 'SSMF') not in ('SSMF', 'NZDF', 'LOF'):
            raise ValueError('Choose a supported fiber profile.')
        number(fiber.get('loss_coef', .2), .01, 1, 'Fiber attenuation')
        losses = link.get('splices', [])
        if not isinstance(losses, list) or len(losses) > 100:
            raise ValueError('Up to 100 splice losses are supported per span.')
        for loss in losses:
            number(loss, 0, 10, 'Splice loss')
        gain = link.get('inline_gain')
        if gain is not None:
            number(gain, 8, 35, 'Inline amplifier gain')
        for field, target in (('connector_in_db', 'con_in_db'), ('connector_out_db', 'con_out_db')):
            if link.get(field) is not None:
                connections[index][target] = number(link[field], 0, 10, 'Connector loss')
        lengths.append(length)
        fibers.append(fiber)
        splices.append(losses)
        gains.append(gain)
    service = resolve_service(payload)
    projected['equipment']['service_gbps'] = service['rate_gbps']
    panels = equipment_settings(projected)['nodes']
    local_panels = []
    for node in panels:
        panel = node['panel']
        local_panels.append((panel['pairs_per_degree']*panel['connector_loss_db']+
                             panel['splices_per_degree']*panel['splice_loss_db']) if panel['enabled'] else 0)
    summary_payload = deepcopy(payload)
    summary_payload.setdefault('equipment', {})['service_gbps'] = service['rate_gbps']
    design = dict(lengths=lengths, connections=connections, splices=splices,
                  inline_gains=gains, fibers=fibers, nodes=nodes, site_ids=projected['site_ids'], local_panel_losses=local_panels)
    return dict(route=route, geometry=geometry, projected=projected, design=design,
                service=service, zones=screen_routes(geometry['paths']),
                equipment_summary=summarize_network(summary_payload), summary_payload=summary_payload)


def _amplifier(entry, side, neighbor, uid, estimated_input_dbm):
    setting = deepcopy(entry.get('amplifiers', {}).get(side, {}))
    setting.update(entry.get('amplifiers', {}).get('by_neighbor', {}).get(neighbor, {}).get(side, {}))
    if not setting.get('enabled', False):
        return None
    control = setting.get('control', 'automatic')
    if control not in ('automatic', 'manual'):
        raise ValueError('Amplifier control must be automatic or manual.')
    if control == 'automatic':
        target = number(setting.get('target_dbm', 0), -30, 10, 'Amplifier channel target')
        # Explicit planning estimate, not an unlimited ideal-gain component.
        gain = min(35, max(8, target - estimated_input_dbm))
    else:
        gain = number(setting.get('gain_db', 15), 8, 35, 'Amplifier gain')
    amp = configured_edfa(uid, gain)
    model = setting.get('model')
    if model:
        if model not in ('std_low_gain', 'std_medium_gain', 'std_high_gain'):
            raise ValueError('Unsupported generic EDFA model.')
        amp['type_variety'] = model
    return amp


def section_inputs(prepared):
    """Exact serialized inputs for each transparent section, before CLI design."""
    package = distribution('gnpy')
    if package.version != GNPY_VERSION:
        raise RuntimeError(f'GNPy {GNPY_VERSION} is required; found {package.version}.')
    examples = Path(package.locate_file('gnpy/example-data'))
    equipment = json.loads((examples / 'eqpt_config.json').read_bytes())
    equipment['Roadm'] = [{'type_variety':p.get('type_variety','default'),
                            **{k:v for k,v in p.items() if k!='type_variety'}} for p in equipment['Roadm']]
    service, design, route = prepared['service'], prepared['design'], prepared['route']
    equipment['SI'][0].update(service['spectrum'])
    # SI is the propagation-band envelope when there are no EDFAs. A tight
    # center-to-center SI range would silently trim the outer allocated slots.
    equipment['SI'][0].update(f_min=191.3e12, f_max=196.1e12)
    equipment['Span'][0].update(power_mode=False, padding=0, con_in=0, con_out=0)
    reference = json.loads((examples / 'edfa_example_network.json').read_bytes())
    template = next(e for e in reference['elements'] if e['type'] == 'Fiber')
    nodes = design['nodes']
    cuts = [0, *[i for i in range(1, len(nodes)-1) if nodes[i]['role'] == 'oeo'], len(nodes)-1]
    output = []
    for section_index, (start, end) in enumerate(zip(cuts, cuts[1:]), 1):
        eq = deepcopy(equipment)
        elements = [{'uid': 'Site_A', 'type': 'Transceiver'}]
        estimate = service['launch_dbm']
        def add(element):
            elements.append(element)
        def amp_at(index, side, neighbor):
            nonlocal estimate
            amp = _amplifier(nodes[index], side, neighbor,
                             f"Amp_{nodes[index]['id']}_{side}", estimate)
            if amp:
                add(amp)
                estimate += amp['operational']['gain_target']
        def roadm_at(index):
            nonlocal estimate
            if nodes[index]['role'] != 'roadm':
                return
            cfg = nodes[index].get('roadm', {})
            target = number(cfg.get('target_pch_out_db', -20), -30, 5, 'ROADM target power')
            loss = number(cfg.get('path_loss_db', 0), 0, 40, 'ROADM path loss')
            profile = deepcopy(eq['Roadm'][0])
            variety = 'm6_' + str(index)
            profile.pop('type_variety',None)
            profile = {'type_variety':variety, **profile}
            profile.update(target_pch_out_db=target)
            impairments = []
            for path_id, kind in enumerate(('express', 'add', 'drop')):
                imp = {'frequency-range': {'lower-frequency': 191.3e12, 'upper-frequency': 196.1e12},
                       'roadm-maxloss': loss, 'roadm-pmd': 0, 'roadm-pdl': 0}
                if kind != 'express':
                    imp['roadm-osnr'] = profile.get('add_drop_osnr', 38) + 10 * math.log10(2)
                impairments.append({'roadm-path-impairments-id': path_id, f'roadm-{kind}-path': [imp]})
            profile['roadm-path-impairments'] = impairments
            eq['Roadm'].append(profile)
            add({'uid': 'Roadm_' + nodes[index]['id'], 'type': 'Roadm', 'type_variety': variety,
                 'params':{'per_degree_pch_out_db':{'Roadm_Interface_'+nodes[index]['id']:target}}})
            # GNPy 3.0.1 visualization bookkeeping references an uninitialized
            # previous_node for a direct ROADM->Fiber edge. An explicit zero-loss
            # interface preserves the physics and avoids changing installed GNPy.
            add({'uid':'Roadm_Interface_'+nodes[index]['id'],'type':'Fused','params':{'loss':0}})
            estimate = min(estimate - loss, target)
        def splice_at(index):
            nonlocal estimate
            if nodes[index]['role'] == 'splice':
                loss = number(nodes[index].get('splice_loss_db',.1),0,10,'Site splice loss')
                add({'uid':'Site_Splice_'+nodes[index]['id'],'type':'Fused','params':{'loss':loss}})
                estimate -= loss
        if nodes[start]['role'] in ('roadm','oeo'):
            loss = design['local_panel_losses'][start]
            add({'uid':'Local_Add_Panel','type':'Fused','params':{'loss':loss}})
            estimate -= loss
        roadm_at(start)
        splice_at(start)
        for i in range(start, end):
            amp_at(i, 'outgoing', nodes[i+1]['id'])
            fiber = deepcopy(template)
            fiber.update(uid=f'Span{i+1}', type_variety=design['fibers'][i].get('type_variety', 'SSMF'))
            fiber['params'].pop('pmd_coef', None)
            attenuation = design['fibers'][i].get('loss_coef', .2)
            con = design['connections'][i]
            fiber['params'].update(length=design['lengths'][i], loss_coef=attenuation,
                                   con_in=con['con_in_db'], con_out=con['con_out_db'] + sum(design['splices'][i]))
            gain = design['inline_gains'][i]
            if gain is None:
                add(fiber)
            else:
                fraction = number(route['links'][i].get('inline_position_fraction', .5), .000001, .999999, 'Inline position')
                second = deepcopy(fiber)
                second['uid'] += '_After_ILA'
                fiber['params']['length'] *= fraction
                second['params']['length'] *= 1 - fraction
                fiber['params']['con_out'] = 0
                second['params']['con_in'] = 0
                add(fiber)
                add(configured_edfa(f'ILA_{i+1}', gain))
                add(second)
                estimate += gain
            estimate -= design['lengths'][i] * attenuation + con['con_in_db'] + con['con_out_db'] + sum(design['splices'][i])
            amp_at(i+1, 'incoming', nodes[i]['id'])
            roadm_at(i+1)
            splice_at(i+1)
        if nodes[end]['role'] in ('roadm','oeo'):
            loss = design['local_panel_losses'][end]
            add({'uid':'Local_Drop_Panel','type':'Fused','params':{'loss':loss}})
        add({'uid': 'Site_B', 'type': 'Transceiver'})
        if any(e['type']=='Edfa' for e in elements):
            # With EDFAs the filter envelope comes from their bands. Design
            # loading must use the actual allocated count, not the entire band.
            eq['SI'][0].update(f_min=service['spectrum']['f_min'], f_max=service['spectrum']['f_max'],
                               use_si_channel_count_for_design=True)
        topology = {'network_name': f'Hyperion M06 optical section {section_index}', 'elements': elements,
                    'connections': [{'from_node': a['uid'], 'to_node': b['uid']} for a,b in zip(elements,elements[1:])]}
        output.append(dict(index=section_index, start=start, end=end, topology=topology,
                           equipment=eq, spectrum=service['gnpy_spectrum']))
    return output


def _parse(output, expected):
    table = output.partition(CHANNEL_HEADING)[2]
    pattern = re.compile(r'\s*(\d+)\s+' + r'\s+'.join([r'(-?(?:\d+(?:\.\d+)?|inf|nan))'] * 5) + r'\s*', re.I)
    rows = []
    for line in table.splitlines():
        match = pattern.fullmatch(line)
        if not match:
            continue
        channel, *values = match.groups()
        row = dict(zip(('frequency_thz','power_dbm','osnr_ase_db','snr_nli_db','gsnr_db'), map(float, values)))
        row['channel'] = int(channel)
        row['no_ase'] = math.isinf(row['osnr_ase_db']) and row['osnr_ase_db'] > 0
        for key, value in list(row.items()):
            if isinstance(value, float) and not math.isfinite(value):
                row[key] = None
        rows.append(row)
    if len(rows) != expected:
        raise RuntimeError(f'GNPy returned {len(rows)} channels; expected {expected}.\n{table[-4000:]}')
    return rows


def parse_component_readings(report, section_id, revision=None):
    """Only parse numeric measurements printed by GNPy, without inferred values."""
    headings = list(re.finditer(r'(?m)^(Edfa|Fiber|Roadm|Fused|Transceiver)\s+(\S+)\s*$',report))
    readings = []
    fields = {
        'effective_gain_db':r'effective gain\(dB\)',
        'noise_figure_db':r'noise figure \(dB\)',
        'input_power_dbm':r'Power In \(dBm\)',
        'output_power_dbm':r'Power Out \(dBm\)',
        'input_attenuation_db':r'pad att_in \(dB\)',
        'output_voa_db':r'output VOA \(dB\)',
        'loss_db':r'total loss \(dB\)',
        'length_km':r'length \(km\)',
        'reference_pch_out_dbm':r'reference pch out \(dBm\)',
    }
    for index,match in enumerate(headings):
        block = report[match.end():headings[index+1].start() if index+1<len(headings) else len(report)]
        kind,uid = match.groups()
        reading = dict(uid=uid,type=kind,section_id=section_id,revision=revision,
                       source='GNPy CLI component report',units='dB, dBm and km as indicated by field names')
        variety = re.search(r'(?m)^\s*type_variety:\s+(\S+)',block)
        if variety:
            reading['type_variety']=variety.group(1)
        for name,label in fields.items():
            value = re.search(r'(?mi)^\s*'+label+r':\s*(-?\d+(?:\.\d+)?)\s*$',block)
            if value:
                reading[name]=float(value.group(1))
        line = re.search(r'(?mi)^\s*actual pch out \(dBm\):\s*(.+)$',block)
        if line:
            reading['channel_output_power_dbm']=[dict(label=label.strip(),value_dbm=float(value))
                for label,value in re.findall(r'([^,:]+):\s*(-?\d+(?:\.\d+)?)',line.group(1))]
        readings.append(reading)
    return readings


def run_section(section, expected):
    with TemporaryDirectory(prefix='hyperion-m6-') as directory:
        folder = Path(directory)
        for name, data in (('topology',section['topology']),('equipment',section['equipment']),('spectrum',section['spectrum'])):
            (folder / f'{name}.json').write_text(json.dumps(data), encoding='utf-8')
        command = [sys.executable, '-c', 'from gnpy.tools.cli_examples import transmission_main_example; transmission_main_example()',
                   str(folder/'topology.json'), 'Site_A', 'Site_B', '-e', str(folder/'equipment.json'),
                   '--spectrum', str(folder/'spectrum.json'), '--no-insert-edfas', '--show-channels',
                   '--save-network', str(folder/'effective.json')]
        started = time.perf_counter()
        completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=180)
        runtime = time.perf_counter() - started
        if completed.returncode:
            raise RuntimeError('GNPy M06 section failed: ' + (completed.stderr+'\n'+completed.stdout)[-8000:])
        output = ANSI.sub('', completed.stdout)
        effective = json.loads((folder/'effective.json').read_bytes())
        expected_amps = sum(e['type'] == 'Edfa' for e in section['topology']['elements'])
        if sum(e['type'] == 'Edfa' for e in effective['elements']) != expected_amps:
            raise RuntimeError('GNPy changed the explicitly configured amplifier count.')
        hashes = {name + '_sha256': hashlib.sha256((folder/f'{name}.json').read_bytes()).hexdigest()
                  for name in ('topology','equipment','spectrum')}
    return dict(channels=_parse(output, expected), raw_stdout=output, raw_stderr=completed.stderr,
                report=output.partition(CHANNEL_HEADING)[0].strip(), runtime_seconds=runtime,
                effective_topology=effective, command=command, **hashes)


def network_simulation_m6(payload):
    from engineering_model import evaluate_design, summarize_network
    prepared = prepare_network_m6(payload)
    route, geometry, design, service = (prepared[k] for k in ('route','geometry','design','service'))
    sections = []
    inputs = section_inputs(prepared)
    for section in inputs:
        result = run_section(section, len(service['allocations']))
        channels = result['channels']
        required = service.get('required_gsnr_db')
        reserve = service.get('reserve_db', 0)
        reasons = []
        margins = []
        for row in channels:
            if row['gsnr_db'] is None:
                reasons.append('Non-finite GSNR')
            elif required is not None:
                margins.append(row['gsnr_db'] - required - reserve)
            if service.get('rx_min_dbm') is not None and row['power_dbm'] < service['rx_min_dbm']:
                reasons.append('Receiver power below minimum')
            if service.get('rx_max_dbm') is not None and row['power_dbm'] > service['rx_max_dbm']:
                reasons.append('Receiver power above maximum')
        if margins and min(margins) < 0:
            reasons.append('GSNR below requirement plus reserve')
        check = dict(status='Fail' if reasons else 'Pass' if required is not None else 'Not evaluated',
                     reason='; '.join(sorted(set(reasons))) or 'All channels meet illustrative section limits.',
                     margin_db=min(margins) if margins else None)
        sections.append({**result, 'section': section['index'], 'from':route['site_names'][section['start']],
                         'to':route['site_names'][section['end']], 'topology_input': section['topology'],
                         'equipment_input': section['equipment'], 'spectrum_input':section['spectrum'], 'service_check':check})
    result = deepcopy(sections[-1])
    spans = []
    for i, link in enumerate(route['links']):
        con = design['connections'][i]
        passive = design['lengths'][i]*design['fibers'][i].get('loss_coef',.2)+con['con_in_db']+con['con_out_db']+sum(design['splices'][i])
        terminal_stage = (_amplifier(design['nodes'][i], 'outgoing', design['nodes'][i+1]['id'], 'preview', 0) is not None
                          or _amplifier(design['nodes'][i+1], 'incoming', design['nodes'][i]['id'], 'preview', 0) is not None)
        spans.append(dict(id=link['id'], **{'from':route['site_names'][i], 'to':route['site_names'][i+1]},
                          geodesic_km=geometry['km'][i],simulation_km=design['lengths'][i],
                          source='Engineered override' if link.get('override') is not None else 'Segmented WGS84',
                          splice_losses_db=design['splices'][i],splice_total_db=sum(design['splices'][i]),
                          connector_loss_db=con['con_in_db']+con['con_out_db'],inline_gain_db=design['inline_gains'][i],
                          amplifier_warning=design['lengths'][i]>80 and design['inline_gains'][i] is None and not terminal_stage,
                          marine_screening=geometry['marine'][i],route_vertices=geometry['paths'][i], passive_loss_db=passive))
    failed = any(s['service_check']['status']=='Fail' for s in sections) or service['status']=='Fail'
    result.update(engine_version=GNPY_VERSION, python_version=sys.version.split()[0],
                  topology='Explicit M06 transparent sections',equipment='Bundled GNPy 3.0.1 generic equipment',
                  reference_bandwidth='signal',spectrum=service['spectrum'],service=service,sections=sections,
                  service_check=dict(status='Fail' if failed else 'Pass' if all(s['service_check']['status']=='Pass' for s in sections) and service['status']=='Pass' else 'Not evaluated',
                      reason='Every OEO-delimited section must pass; all mode limits are illustrative.', section_checks=[s['service_check'] for s in sections]),
                  runtime_seconds=sum(s['runtime_seconds'] for s in sections),
                  report='\n\n'.join(f"OPTICAL SECTION {s['section']} ({s['from']} to {s['to']})\n{s['report']}" for s in sections),
                  raw_stdout='\n\n'.join(s['raw_stdout'] for s in sections),
                  route_name=payload.get('route_name','DWDM Route'),project_id=payload.get('project_id'),revision=payload.get('revision',1),
                  span_length_km=sum(design['lengths']),span_lengths_km=design['lengths'],length_source='Per-span configuration',
                  points=route['coordinates'],site_names=route['site_names'],map_estimate_km=sum(geometry['km']),
                  spans=spans,baseline=None,selected_path=route,snapshot=deepcopy(payload),zones=prepared['zones'],service_id=route['service_id'])
    result['component_readings'] = []
    for section in sections:
        readings = parse_component_readings(section['report'],section['section'],payload.get('revision',1))
        for reading in readings:
            for node in design['nodes']:
                if reading['uid'] in (f"Amp_{node['id']}_incoming",f"Amp_{node['id']}_outgoing",f"Roadm_{node['id']}",f"Site_Splice_{node['id']}",f"Roadm_Interface_{node['id']}"):
                    reading['node_id']=node['id']
                    if reading['type']=='Edfa':
                        side='incoming' if reading['uid'].endswith('_incoming') else 'outgoing'
                        node_index=design['site_ids'].index(node['id'])
                        neighbor_index=node_index-1 if side=='incoming' else node_index+1
                        stage=deepcopy(node.get('amplifiers',{}).get(side,{}))
                        if 0<=neighbor_index<len(design['nodes']):
                            neighbor=design['site_ids'][neighbor_index]
                            stage.update(node.get('amplifiers',{}).get('by_neighbor',{}).get(neighbor,{}).get(side,{}))
                            reading['neighbor_id']=neighbor
                        reading['side']=side
                        reading['control']=stage.get('control','automatic')
                        reading['requested_gain_db']=stage.get('gain_db',15) if reading['control']=='manual' else None
                        reading['requested_target_dbm']=stage.get('target_dbm',0) if reading['control']=='automatic' else None
            if reading['uid']=='Site_A':
                reading['node_id']=design['site_ids'][inputs[section['section']-1]['start']]
            if reading['uid']=='Site_B':
                reading['node_id']=design['site_ids'][inputs[section['section']-1]['end']]
        section['component_readings']=readings
        result['component_readings'].extend(readings)
    total = sum(s['passive_loss_db'] for s in spans)
    site_splices = sum(number(n.get('splice_loss_db',.1),0,10,'Site splice loss') for n in design['nodes'] if n['role']=='splice')
    local_panels = sum(design['local_panel_losses'][s['start']] if design['nodes'][s['start']]['role'] in ('roadm','oeo') else 0 for s in inputs)
    local_panels += sum(design['local_panel_losses'][s['end']] if design['nodes'][s['end']]['role'] in ('roadm','oeo') else 0 for s in inputs)
    result['passive_budget'] = dict(line_spans_db=total,site_splice_loss_db=site_splices,local_add_drop_panel_db=local_panels,total_external_passive_db=total+site_splices+local_panels,
                                    scope='Configured external fiber, panel connections and splices. ROADM loss is propagated separately.')
    result['engineering'] = evaluate_design(prepared['projected'],result)
    issues = result['engineering']['issues']
    for review in payload.get('edit_reviews', []):
        if isinstance(review, dict) and not review.get('acknowledged'):
            issues.append(dict(node_id=review.get('node_id'), check='Inserted equipment assignment', status='Review', reason=review.get('message', 'Review inserted-site assignments.'), action='Inspect and acknowledge the assignment, then rerun.'))
    for section in sections:
        for line in section['raw_stderr'].splitlines():
            if 'WARNING:' in line and ('can not be met' in line or 'maximum' in line or 'gain' in line.lower()):
                issues.append(dict(check='GNPy design warning',status='Review',
                                   reason=f"Section {section['section']}: {line}",
                                   action='Inspect the target power and amplifier configuration and rerun.'))
    for reading in result['component_readings']:
        target=reading.get('requested_target_dbm')
        actual=reading.get('channel_output_power_dbm',[])
        if target is not None and actual and any(abs(p['value_dbm']-target)>.1 for p in actual):
            issues.append(dict(node_id=reading.get('node_id'),check='Amplifier channel target',status='Review',
                reason=f"Section {reading['section_id']} {reading['uid']} requested {target} dBm/channel; reported output is "+
                    ', '.join(f"{p['value_dbm']} dBm" for p in actual)+'.',
                action='The finite amplifier range or saturation can prevent the requested target; inspect its model and launch power.'))
    for issue in service['issues']:
        issues.append({**issue, 'action':'Review the operating-mode assumptions and rerun.'})
    for index,node in enumerate(design['nodes']):
        if node['role'] != 'roadm':
            continue
        cfg = node.get('roadm',{})
        low = number(cfg.get('band_min_thz',191.3),180,210,'WSS lower band edge')
        high = number(cfg.get('band_max_thz',196.1),180,210,'WSS upper band edge')
        if low >= high:
            raise ValueError('WSS lower band edge must be below its upper edge.')
        clipped = [a['channel'] for a in service['allocations']
                   if a['frequency_thz'] - a['baud_rate']*(1+a['roll_off'])/2e12 < low
                   or a['frequency_thz'] + a['baud_rate']*(1+a['roll_off'])/2e12 > high]
        if clipped:
            issues.append(dict(node_id=node['id'],check='WSS passband',status='Fail',
                               reason=f'Channels {clipped} extend outside configured {low}–{high} THz WSS passband.',
                               action='Change the WSS passband or reallocate the service spectrum.'))
        passband = number(cfg.get('passband_ghz',4800),1,10000,'WSS per-channel passband')
        if service['baud_rate']*(1+service['roll_off'])/1e9 > passband:
            issues.append(dict(node_id=node['id'],check='WSS channel filter width',status='Fail',
                               reason=f'Occupied channel width exceeds configured {passband} GHz WSS filter.',
                               action='Use a wider filter or a narrower supported channel mode.'))
    profiles = {p['type_variety']:p for p in result['equipment_input']['Edfa']}
    for block in re.split(r'(?m)^Edfa ',result['report'])[1:]:
        uid = block.splitlines()[0]
        variety = re.search(r'type_variety:\s+(\S+)',block)
        gain = re.search(r'effective gain\(dB\):\s+(-?[\d.]+)',block)
        power = re.search(r'Power Out \(dBm\):\s+(-?[\d.]+)',block)
        if not variety or not gain:
            continue
        profile = profiles.get(variety.group(1),{})
        value = float(gain.group(1))
        reasons = []
        if value < profile.get('gain_min',-100) - .01:
            reasons.append(f'Effective gain {value} dB is below model minimum; GNPy may add input attenuation.')
        if value > profile.get('gain_flatmax',100) + .01:
            reasons.append(f'Effective gain {value} dB exceeds model flat-gain limit.')
        if power and float(power.group(1)) >= profile.get('p_max',100)-.1:
            reasons.append('Aggregate output is at or near model saturation limit.')
        if reasons:
            issues.append(dict(node_id=uid,check='Amplifier operating range',status='Review',reason=' '.join(reasons),
                               action='Select a suitable amplifier model, adjust gain/launch power and rerun.'))
    if any(i['status']=='Fail' for i in issues):
        result['service_check']['status']='Fail'
    elif result['service_check']['status'] != 'Fail' and any(i['status'] in ('Not evaluated','Review') for i in issues):
        result['service_check']['status']='Not evaluated'
    result['service_check']['engineering_issue_count']=len(issues)
    result['equipment_summary'] = summarize_network(prepared['summary_payload'],result)
    return result
