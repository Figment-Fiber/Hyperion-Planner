"""Service allocation regression checks against pinned GNPy spectrum parsing."""
import unittest
from service_model import resolve_service, compare_requirements

class Services(unittest.TestCase):
    def test_rate_defaults_and_comparison(self):
        variants = compare_requirements({'requirements': {'channels': 3, 'launch_dbm': -2, 'spacing_ghz': 50}})
        self.assertEqual([v['spacing_ghz'] for v in variants], [50,75,150])
        for result in variants:
            self.assertEqual(result['status'], 'Pass')
            self.assertEqual(result['channel_count'], 3)
            self.assertEqual(result['launch_dbm'], -2)
            self.assertFalse(result['vendor_certified'])
            self.assertEqual(result['verdict_scope'], 'Generic planning')
    def test_occupied_slot_and_guard_checks(self):
        self.assertEqual(resolve_service({'requirements': {'rate_gbps':400,'slot_width_ghz':50}})['status'], 'Fail')
        self.assertEqual(resolve_service({'requirements': {'channels':2,'slot_width_ghz':75}})['status'], 'Fail')
        self.assertEqual(resolve_service({'requirements': {'channels':2,'guard_band_ghz':14}})['status'], 'Fail')
        self.assertEqual(resolve_service({'requirements': {'channels':2,'guard_band_ghz':13}})['status'], 'Pass')
    def test_flex_grid_and_band(self):
        self.assertEqual(resolve_service({'requirements': {'grid':'flex','center_thz':193.10625}})['status'], 'Pass')
        self.assertEqual(resolve_service({'requirements': {'grid':'flex','center_thz':193.101}})['status'], 'Fail')
        self.assertEqual(resolve_service({'requirements': {'grid':'flex','slot_width_ghz':51}})['status'], 'Fail')
        self.assertEqual(resolve_service({'requirements': {'center_thz':196.1}})['status'], 'Fail')
    def test_unknown_is_not_vendor_pass(self):
        result = resolve_service({'requirements': {'mode_id':'vendor-unknown'}})
        self.assertEqual(result['status'], 'Not evaluated')
        self.assertIsNone(result['required_gsnr_db'])
        self.assertIsNone(result['rx_min_dbm'])
        self.assertEqual(resolve_service({'requirements': {'fec':'vendor-fec'}})['status'], 'Not evaluated')
    def test_bad_numbers(self):
        for req in ({'channels':1.5},{'launch_dbm':float('nan')},{'rx_min_dbm':2,'rx_max_dbm':0},{'grid':'other'}):
            with self.assertRaises(ValueError):
                resolve_service({'requirements':req})
    def test_actual_gnpy_carriers(self):
        from gnpy.tools.json_io import _spectrum_from_json
        result = resolve_service({'requirements': {'rate_gbps':800,'channels':3,'launch_dbm':-2}})
        carriers = _spectrum_from_json(result['gnpy_spectrum']['spectrum'])
        self.assertEqual(list(carriers), [a['frequency_hz'] for a in result['allocations']])
        for carrier in carriers.values():
            self.assertEqual(carrier.baud_rate, 128e9)
            self.assertEqual(carrier.slot_width, 150e9)
            self.assertAlmostEqual(carrier.tx_power, 10**(-2/10)*1e-3)

if __name__ == '__main__':
    unittest.main()
