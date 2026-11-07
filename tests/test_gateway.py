import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fhir_gateway.generate import make_bundle, write_bundle
from fhir_gateway.pipeline import ingest
from fhir_gateway.quality import summarise
from fhir_gateway.report import render
from fhir_gateway.validate import partition_bundle, validate_shape


class GeneratorTests(unittest.TestCase):
    def test_generator_deterministic(self):
        self.assertEqual(make_bundle(3, 12), make_bundle(3, 12))

    def test_invalid_count(self):
        with self.assertRaises(ValueError):
            make_bundle(0)

    def test_four_resources_per_patient(self):
        bundle = make_bundle(7)
        self.assertEqual(len(bundle['entry']), 28)
        self.assertEqual(set(e['resource']['resourceType'] for e in bundle['entry']),
                         {'Patient', 'Encounter', 'Observation', 'Appointment'})

    def test_no_names_nhs_numbers(self):
        bundle = json.dumps(make_bundle(3)).lower()
        self.assertNotIn('nhsnumber', bundle)
        self.assertNotIn('"name"', bundle)
        self.assertNotIn('"address"', bundle)


class ShapeTests(unittest.TestCase):
    def setUp(self):
        self.entries = [r['resource'] for r in make_bundle(2)['entry']]

    def test_all_valid(self):
        self.assertTrue(all(validate_shape(e) is None for e in self.entries))

    def test_no_real_ids(self):
        p = {**self.entries[0], 'id': 'sensitive'}
        self.assertEqual(validate_shape(p), 'non_synthetic_id')

    def test_invalid_patient_birth(self):
        p = {**self.entries[0], 'birthDate': '2026-02-30'}
        self.assertEqual(validate_shape(p), 'invalid_birth_date')

    def test_wrong_encounter_status(self):
        self.assertEqual(validate_shape({**self.entries[1], 'status': 'ended'}), 'invalid_encounter_status')

    def test_naive_encounter_time(self):
        e = copy.deepcopy(self.entries[1])
        e['period']['start'] = '2025-01-01T09:00:00'
        self.assertEqual(validate_shape(e), 'invalid_encounter_period')

    def test_invalid_observation_code(self):
        o = copy.deepcopy(self.entries[2])
        o['code']['coding'][0]['code'] = '0000-0'
        self.assertEqual(validate_shape(o), 'unsupported_observation_code')

    def test_invalid_observation_unit(self):
        o = copy.deepcopy(self.entries[2])
        o['valueQuantity']['code'] = 'kg'
        self.assertEqual(validate_shape(o), 'invalid_observation_quantity')

    def test_boolean_not_numeric_quantity(self):
        o = copy.deepcopy(self.entries[2])
        o['valueQuantity']['value'] = True
        self.assertEqual(validate_shape(o), 'invalid_observation_quantity')

    def test_invalid_appointment_end(self):
        a = copy.deepcopy(self.entries[3])
        a['end'] = '2000-01-01T00:00:00+00:00'
        self.assertEqual(validate_shape(a), 'invalid_appointment_period')

    def test_unsupported_resource_type(self):
        self.assertEqual(validate_shape({'resourceType': 'Medication', 'id': 'med-SYN-0001'}), 'unsupported_resource_type')


class LinkageTests(unittest.TestCase):
    def test_all_accepted(self):
        good, bad = partition_bundle(make_bundle(5))
        self.assertEqual((len(good), len(bad)), (20, 0))

    def test_duplicate_resource_id(self):
        bundle = make_bundle(2)
        bundle['entry'].append(copy.deepcopy(bundle['entry'][0]))
        good, bad = partition_bundle(bundle)
        self.assertEqual(len(good), 8)
        self.assertEqual(bad[0]['reason'], 'duplicate_resource_id')

    def test_orphan_encounter(self):
        bundle = make_bundle(1)
        bundle['entry'][1]['resource']['subject']['reference'] = 'Patient/pt-SYN-9999'
        good, bad = partition_bundle(bundle)
        self.assertEqual(len(good), 2)  # Patient and Appointment, Observation cannot link to excluded Encounter
        self.assertEqual({b['reason'] for b in bad}, {'unresolved_patient_reference', 'unresolved_encounter_reference'})

    def test_observation_patient_encounter_disagreement(self):
        bundle = make_bundle(2)
        bundle['entry'][2]['resource']['subject']['reference'] = 'Patient/pt-SYN-0002'
        good, bad = partition_bundle(bundle)
        self.assertEqual(len(good), 7)
        self.assertEqual(bad[0]['reason'], 'encounter_patient_mismatch')

    def test_observation_outside_encounter(self):
        bundle = make_bundle(1)
        bundle['entry'][2]['resource']['effectiveDateTime'] = '2020-01-01T09:00:00+00:00'
        _, bad = partition_bundle(bundle)
        self.assertEqual(bad[0]['reason'], 'observation_outside_encounter_period')

    def test_unsupported_bundle_is_rejected(self):
        with self.assertRaises(ValueError):
            partition_bundle({'resourceType': 'Bundle', 'type': 'transaction', 'entry': []})

    def test_malformed_entry_does_not_crash(self):
        bundle = make_bundle(1)
        bundle['entry'].append(None)
        good, bad = partition_bundle(bundle)
        self.assertEqual((len(good), len(bad)), (4, 1))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / 'bundle.json'
        self.db = self.root / 'demo.sqlite'
        self.quarantine = self.root / 'quarantine.json'

    def test_end_to_end(self):
        write_bundle(make_bundle(10), self.input)
        result = ingest(self.input, self.db, self.quarantine)
        self.assertEqual((result['accepted'], result['quarantined']), (40, 0))
        data = summarise(self.db, self.quarantine)
        self.assertEqual(data['quality']['foreign_key_issues'], 0)
        self.assertEqual(data['counts']['observation'], 10)
        render(data, self.root / 'index.html')
        self.assertIn('FHIR Quality Gateway', (self.root / 'index.html').read_text())

    def test_mixed_input_generates_quarantine_report(self):
        bundle = make_bundle(4)
        bundle['entry'].append(copy.deepcopy(bundle['entry'][0]))
        invalid = copy.deepcopy(bundle['entry'][2])
        invalid['resource']['id'] = 'obs-SYN-9999'
        invalid['resource']['encounter']['reference'] = 'Encounter/enc-SYN-9999'
        bundle['entry'].append(invalid)
        write_bundle(bundle, self.input)
        audit = ingest(self.input, self.db, self.quarantine)
        self.assertEqual((audit['accepted'], audit['quarantined']), (16, 2))
        summary = summarise(self.db, self.quarantine)
        self.assertEqual(summary['quality']['quarantine_reasons']['duplicate_resource_id'], 1)
        self.assertEqual(summary['quality']['quarantine_reasons']['unresolved_encounter_reference'], 1)

    def test_repeat_import_replace_snapshot(self):
        write_bundle(make_bundle(4), self.input)
        ingest(self.input, self.db, self.quarantine)
        ingest(self.input, self.db, self.quarantine)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM patient').fetchone()[0], 4)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM audit').fetchone()[0], 2)

    def test_dependency_rejection_on_invalid_patient(self):
        bundle = make_bundle(1)
        bundle['entry'][0]['resource']['birthDate'] = 'not-a-date'
        write_bundle(bundle, self.input)
        outcome = ingest(self.input, self.db, self.quarantine)
        self.assertEqual((outcome['accepted'], outcome['quarantined']), (0, 4))


class PrivacyContractTests(unittest.TestCase):
    def test_patient_with_name_is_rejected(self):
        patient = make_bundle(1)['entry'][0]['resource']
        self.assertEqual(validate_shape({**patient, 'name': [{'family': 'Test'}]}), 'disallowed_personal_fields')

    def test_patient_with_real_identifier_system_is_rejected(self):
        patient = copy.deepcopy(make_bundle(1)['entry'][0]['resource'])
        patient['identifier'][0]['system'] = 'https://fhir.nhs.uk/Id/nhs-number'
        self.assertEqual(validate_shape(patient), 'invalid_synthetic_identifier_system')


class ConformanceRegressionTests(unittest.TestCase):
    """Rules that the HL7 validator showed the first version got wrong."""

    def test_fullurl_resolves_relative_references(self):
        for entry in make_bundle(3)['entry']:
            resource = entry['resource']
            self.assertTrue(entry['fullUrl'].endswith(f"/{resource['resourceType']}/{resource['id']}"))

    def test_identifier_system_is_not_an_example_domain(self):
        system = make_bundle(1)['entry'][0]['resource']['identifier'][0]['system']
        self.assertNotRegex(system, r'example\.(org|com|net)')

    def test_body_temperature_has_vital_signs_category(self):
        observation = make_bundle(1)['entry'][2]['resource']
        self.assertEqual(observation['category'][0]['coding'][0]['code'], 'vital-signs')

    def test_missing_category_is_quarantined(self):
        observation = copy.deepcopy(make_bundle(1)['entry'][2]['resource'])
        del observation['category']
        self.assertEqual(validate_shape(observation), 'missing_vital_signs_category')

    def test_every_resource_has_narrative(self):
        self.assertTrue(all('text' in e['resource'] for e in make_bundle(2)['entry']))


class InvalidFixtureTests(unittest.TestCase):
    def test_four_known_defects_are_caught(self):
        bundle = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/invalid_bundle.json').read_text())
        _, bad = partition_bundle(bundle)
        self.assertEqual([b['reason'] for b in bad], [
            'duplicate_resource_id', 'unresolved_encounter_reference',
            'encounter_patient_mismatch', 'observation_outside_encounter_period'])


if __name__ == '__main__':
    unittest.main()
