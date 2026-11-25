"""Explicit hypothetical service assumptions and exact GNPy channel allocations."""
from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path

@lru_cache(maxsize=1)
def mode_catalog():
    return json.loads(Path(__file__).with_name('service_modes.json').read_text(encoding='utf-8'))

def number(value, low, high, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be numeric')
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}')
    return value

def on_step(value, step):
    return abs(value / step - round(value / step)) < 1e-6

def resolve_service(payload, rate=None):
    req = payload.get('requirements', {})
    if not isinstance(req, dict):
        raise ValueError('requirements must be an object')
    rate = number(rate if rate is not None else req.get('rate_gbps', 100), 1, 1600, 'rate_gbps')
    modes = {m['id']: m for m in mode_catalog()['modes']}
    mode_id = req.get('mode_id', f'generic-{rate:g}g')
    known = mode_id in modes
    mode = modes.get(mode_id, modes.get(f'generic-{rate:g}g', modes['generic-100g']))
    issues = []
    def issue(check, status, reason):
        issues.append(dict(check=check, status=status, reason=reason))
    if not known:
        issue('Operating mode', 'Not evaluated', 'No qualified data for this mode; diagnostic spectrum uses explicitly generic assumptions.')
    if known and mode['rate_gbps'] != rate:
        issue('Client-to-line capacity', 'Fail', 'Selected mode does not match requested service rate.')
    grid = req.get('grid', 'fixed')
    if grid not in ('fixed', 'flex'):
        raise ValueError('grid must be fixed or flex')
    spacing = number(req.get('spacing_ghz', mode['default_spacing_ghz']), 6.25, 400, 'spacing_ghz')
    slot = number(req.get('slot_width_ghz', mode['default_slot_width_ghz']), 12.5, 400, 'slot_width_ghz')
    baud = number(req.get('baud_rate', mode['baud_rate']), 1e9, 300e9, 'baud_rate')
    roll = number(req.get('roll_off', mode['roll_off']), 0, 1, 'roll_off')
    occupied = baud / 1e9 * (1 + roll)
    count = number(req.get('channels', 1), 1, 96, 'channels')
    if int(count) != count:
        raise ValueError('channels must be an integer')
    count = int(count)
    center = number(req.get('center_thz', 193.1), 180, 210, 'center_thz')
    guard = number(req.get('guard_band_ghz', 0), 0, 100, 'guard_band_ghz')
    launch = number(req.get('launch_dbm', payload.get('tx_power_dbm', 0)), -20, 8, 'launch_dbm')
    tx_osnr = number(req.get('tx_osnr', 40), 0, 80, 'tx_osnr')
    reserve = number(req.get('reserve_db', 2), 0, 20, 'reserve_db')
    lower = number(req.get('band_min_thz', 191.3), 180, 210, 'band_min_thz')
    upper = number(req.get('band_max_thz', 196.1), 180, 210, 'band_max_thz')
    if lower >= upper:
        raise ValueError('band_min_thz must be below band_max_thz')
    thresholds = {}
    for key, default, low, high in [('required_gsnr_db', mode['required_gsnr_db'], -20, 60), ('rx_min_dbm', -20, -60, 20), ('rx_max_dbm', 0, -60, 20)]:
        value = req.get(key, default if known else None)
        thresholds[key] = None if value is None else number(value, low, high, key)
    if thresholds['rx_min_dbm'] is not None and thresholds['rx_max_dbm'] is not None and thresholds['rx_min_dbm'] > thresholds['rx_max_dbm']:
        raise ValueError('rx_min_dbm exceeds rx_max_dbm')
    if any(v is None for v in thresholds.values()):
        issue('Quality thresholds', 'Not evaluated', 'Missing receiver or signal-bandwidth GSNR threshold.')
    modulation = req.get('modulation', mode['modulation'])
    fec = req.get('fec', 'Unspecified generic coded mode')
    if modulation != mode['modulation'] or fec != 'Unspecified generic coded mode':
        issue('Modulation/FEC characterization', 'Not evaluated', 'Custom modulation/FEC has no characterized performance curve.')
    if slot + 1e-6 < occupied:
        issue('Occupied bandwidth', 'Fail', 'Slot is narrower than baud rate multiplied by (1 + roll-off).')
    if count > 1 and spacing + 1e-6 < slot:
        issue('Slot collision', 'Fail', 'Adjacent allocated slots overlap.')
    if count > 1 and spacing - occupied + 1e-6 < guard:
        issue('Guard band', 'Fail', 'Adjacent occupied spectra leave less than the requested total guard band.')
    if grid == 'flex' and (not on_step(slot, 12.5) or not on_step(spacing, 6.25)):
        issue('Flex grid', 'Fail', 'Slot width must be a multiple of 12.5 GHz; center spacing a multiple of 6.25 GHz.')
    if grid == 'fixed' and not on_step(spacing, 12.5):
        issue('Fixed grid', 'Fail', 'This generic uniform grid requires spacing in 12.5 GHz increments.')
    allocations = []
    for i in range(count):
        freq = round(center + i * spacing / 1000, 9)
        if not on_step(freq - 193.1, .00625 if grid == 'flex' else spacing / 1000):
            issue('Channel center', 'Fail', f'Channel {i+1} is off the selected grid anchored at 193.1 THz.')
        if freq - slot / 2000 < lower - 1e-9 or freq + slot / 2000 > upper + 1e-9:
            issue('Optical band', 'Fail', f'Channel {i+1} slot extends outside the configured optical band.')
        allocations.append(dict(channel=i+1, frequency_hz=freq*1e12, frequency_thz=freq, baud_rate=baud, slot_width=slot*1e9, roll_off=roll, launch_dbm=launch, tx_osnr=tx_osnr, slot_low_thz=freq-slot/2000, slot_high_thz=freq+slot/2000, signal_low_thz=freq-occupied/2000, signal_high_thz=freq+occupied/2000))
    spectrum = dict(f_min=allocations[0]['frequency_hz']-spacing*1e9, f_max=allocations[-1]['frequency_hz'], baud_rate=baud, spacing=spacing*1e9, roll_off=roll, power_dbm=launch, tx_power_dbm=launch, tx_osnr=tx_osnr, power_range_db=[0,0,1], sys_margins=reserve, use_si_channel_count_for_design=True)
    blocks = [dict(f_min=a['frequency_hz'], f_max=a['frequency_hz'], baud_rate=baud, slot_width=slot*1e9, roll_off=roll, tx_osnr=tx_osnr, tx_power_dbm=launch, label=f'{mode_id}-ch{a["channel"]}') for a in allocations]
    status = 'Fail' if any(x['status']=='Fail' for x in issues) else 'Not evaluated' if any(x['status']=='Not evaluated' for x in issues) else 'Pass'
    return dict(mode_id=mode_id, propagation_mode_id=mode['id'], mode_label=mode['label'], rate_gbps=rate, mode_payload_gbps=mode['rate_gbps'], baud_rate=baud, roll_off=roll, modulation=modulation, fec=fec, slot_width=slot*1e9, spacing=spacing*1e9, slot_width_ghz=slot, spacing_ghz=spacing, min_slot_width_ghz=occupied, occupied_width_ghz=occupied, guard_band_ghz=guard, actual_gap_ghz=spacing-occupied if count>1 else None, launch_dbm=launch, tx_osnr=tx_osnr, tx_osnr_reference_bandwidth='0.1 nm', reserve_db=reserve, reference_bandwidth='signal', channel_count=count, carrier_count=1, allocations=allocations, gnpy_spectrum={'spectrum':blocks}, spectrum=spectrum, status=status, issues=issues, assumption_status='Illustrative generic planning assumptions', vendor_certified=False, verdict_scope='Generic planning', provenance=dict(mode=mode_catalog()['description'], threshold_source='Editable hypothetical signal-bandwidth GSNR and receiver thresholds; no measured BER/FEC curve.', grid_source=mode_catalog()['grid_source'], spectrum_source=mode_catalog()['spectrum_source'], minimum_slot_source='Occupied width is baud rate times (1 + roll-off); implementation rejects narrower slots. This is not a rate-to-FEC certification rule.', guard_definition='Total free bandwidth between adjacent occupied signal edges; allocated slot non-overlap is checked separately.'), **thresholds)

def compare_requirements(payload):
    shared = {k:v for k,v in payload.get('requirements', {}).items() if k in ('grid','channels','center_thz','guard_band_ghz','launch_dbm','reserve_db','tx_osnr','band_min_thz','band_max_thz')}
    results = []
    for rate in (100,400,800):
        variant = deepcopy(payload)
        variant['requirements'] = dict(shared, rate_gbps=rate, mode_id=f'generic-{rate}g')
        results.append(resolve_service(variant))
    return results
