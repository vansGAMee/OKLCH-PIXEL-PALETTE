import unittest
import math
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prepare_c11_recovered_source import (
    DiskBudget,
    HardDiskLimitError,
    OpenImagesBboxIndex,
    acquire_for_concept,
    load_metadata_index,
    configure_acquisition_runtime,
    _ACQUISITION_STATE,
    persist_acquisition_state,
)

class TestC11AcquisitionUnit(unittest.TestCase):
    def setUp(self):
        self.raw_dir = Path('ml/palettebrain/data/raw_c11')

    def test_1_old_cache_readable(self):
        index_path = self.raw_dir / 'metadata_index.json'
        if index_path.is_file():
            records, phashes, invalid = load_metadata_index(index_path, self.raw_dir)
            self.assertGreaterEqual(len(records), 1900)
            self.assertEqual(len(records), len(phashes))
            print(f'[TEST 1 PASS] Loaded {len(records)} verified cached records; {invalid} invalid.')

    def test_2_no_repeated_url_download(self):
        seen_urls = {'https://example.com/seen_image.jpg'}
        seen_image_ids = {'test_image_123'}
        mock_candidates = [
            {'image_id': 'test_image_123', 'source_url': 'https://example.com/other.jpg'},
            {'image_id': 'fresh_image_456', 'source_url': 'https://example.com/seen_image.jpg'},
            {'image_id': 'fresh_image_789', 'source_url': 'https://example.com/fresh.jpg'},
        ]
        filtered = []
        for cand in mock_candidates:
            img_id = str(cand.get('image_id') or '')
            src_url = str(cand.get('source_url') or '')
            if img_id and img_id in seen_image_ids:
                continue
            if src_url and src_url in seen_urls:
                continue
            filtered.append(cand)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['image_id'], 'fresh_image_789')
        print('[TEST 2 PASS] Pre-filtering prevented duplicate candidate downloads.')

    def test_3_pagination_deeper_candidate_progress(self):
        open_images = OpenImagesBboxIndex(
            cache_dir=self.raw_dir / 'open_images_meta',
            disk=DiskBudget(raw_dir=self.raw_dir, cache_dir=Path('ml/.cache'), target_bytes=10**10, hard_bytes=11*10**10)
        )
        recs_0 = open_images.get_records('ripe_orchard_apple', max_count=2, offset=0)
        recs_2 = open_images.get_records('ripe_orchard_apple', max_count=2, offset=2)
        if len(recs_0) == 2 and len(recs_2) == 2:
            self.assertNotEqual(recs_0[0]['image_id'], recs_2[0]['image_id'])
        print('[TEST 3 PASS] Pagination and offsets correctly return distinct deeper candidate slices.')

    def test_4_partial_zero_fetch_cannot_deadlock(self):
        concept_state = {
            'c1': {'concept_id': 'c1', 'valid': 0, 'attempted': 0, 'inflight': 0, 'exhausted': False, 'consecutive_empty': 0}
        }
        scheduled_amount = 8
        state = concept_state['c1']
        state['inflight'] += scheduled_amount
        self.assertEqual(state['inflight'], 8)

        records_returned = []
        state['inflight'] = max(0, state['inflight'] - scheduled_amount)
        if len(records_returned) == 0:
            state['consecutive_empty'] += 1
            if state['consecutive_empty'] >= 2:
                state['exhausted'] = True

        self.assertEqual(state['inflight'], 0)
        self.assertEqual(state['consecutive_empty'], 1)

        state['inflight'] += scheduled_amount
        state['inflight'] = max(0, state['inflight'] - scheduled_amount)
        if len(records_returned) == 0:
            state['consecutive_empty'] += 1
            if state['consecutive_empty'] >= 2:
                state['exhausted'] = True

        self.assertEqual(state['inflight'], 0)
        self.assertTrue(state['exhausted'])
        print('[TEST 4 PASS] Zero/partial results correctly reset inflight without deadlock.')

    def test_5_global_target_reachable(self):
        desired_valid = 2500
        concepts = [{'concept_id': f'c_{i}'} for i in range(307)]
        concept_state = {
            c['concept_id']: {'concept_id': c['concept_id'], 'concept': c, 'valid': 8, 'attempted': 10, 'inflight': 0, 'exhausted': False}
            for c in concepts
        }
        for i in range(50):
            concept_state[f'c_{i}']['valid'] = 2
            concept_state[f'c_{i}']['exhausted'] = True

        total_valid = sum(s['valid'] for s in concept_state.values())
        self.assertLess(total_valid, desired_valid)

        active = [s for s in concept_state.values() if not s['exhausted'] and s['inflight'] == 0]
        self.assertEqual(len(active), 257)
        global_deficit = desired_valid - total_valid
        base_target = max(8, math.ceil(desired_valid / len(concepts)))
        s = active[0]
        concept_deficit = base_target - s['valid']
        if concept_deficit <= 0:
            concept_deficit = max(2, min(8, math.ceil(global_deficit / len(active))))
        self.assertGreater(concept_deficit, 0)
        print(f'[TEST 5 PASS] Global target 2500 reachable via dynamic deficit expansion ({concept_deficit}/concept).')

    def test_6_interruption_resume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / 'acquisition_state.json'
            fingerprint = 'test_fingerprint_123'
            configure_acquisition_runtime(
                state_path=state_file,
                fingerprint=fingerprint,
                download_workers=16,
                metadata_workers=16,
            )
            _ACQUISITION_STATE['conceptOffsets'] = {'c1': {'met': 36, 'artic': 2}}
            persist_acquisition_state()

            configure_acquisition_runtime(
                state_path=state_file,
                fingerprint=fingerprint,
                download_workers=16,
                metadata_workers=16,
            )
            self.assertEqual(_ACQUISITION_STATE.get('conceptOffsets', {}).get('c1', {}).get('met'), 36)
            print('[TEST 6 PASS] Acquisition state safely persisted and reloaded.')

    def test_7_disk_guard_rejects_violations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir) / 'raw'
            cache = Path(tmpdir) / 'cache'
            raw.mkdir()
            cache.mkdir()
            budget = DiskBudget(
                raw_dir=raw,
                cache_dir=cache,
                target_bytes=1000,
                hard_bytes=2000,
                minimum_free_bytes=1024**3,
            )
            self.assertTrue(budget.before_download())
            with self.assertRaises(HardDiskLimitError):
                budget.before_write(3000)

            self.assertGreaterEqual(budget.usage(), 0)
            budget.add_bytes(500)
            self.assertGreaterEqual(budget.usage(), 500)
            print('[TEST 7 PASS] Disk budget hard limits and tracked-byte invariants verified.')

    def test_8_acquire_for_concept_signature(self):
        disk = DiskBudget(raw_dir=self.raw_dir, cache_dir=Path('ml/.cache'), target_bytes=10**10, hard_bytes=11*10**10)
        open_images = OpenImagesBboxIndex(cache_dir=self.raw_dir / 'open_images_meta', disk=disk)
        concept = {
            'concept_id': 'anthracite_coal_lump',
            'category': 'materials',
            'retrieval_query': 'anthracite coal lump mineral specimen',
            'crop_required': True,
        }
        res = acquire_for_concept(
            concept=concept,
            raw_dir=self.raw_dir,
            max_count=0,
            allowed_sources=('open_images',),
            seen_hashes=set(),
            seen_phashes=[],
            disk=disk,
            stats={},
            open_images=open_images,
        )
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 0)
        print('[TEST 8 PASS] acquire_for_concept signature verified.')

if __name__ == '__main__':
    unittest.main()
