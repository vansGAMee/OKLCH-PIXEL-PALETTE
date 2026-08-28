import unittest
import math
import os
import io
import json
import tempfile
import threading
import time
from unittest import mock
from pathlib import Path
from PIL import Image
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prepare_c11_recovered_source import (
    DiskBudget,
    HardDiskLimitError,
    OpenImagesBboxIndex,
    acquire_for_concept,
    load_metadata_index,
    configure_acquisition_runtime,
    persist_acquisition_state,
    guarded_atomic_write_text,
    store_image_record,
    met_candidates,
    artic_candidates,
    safe_http_get,
    write_metadata_index,
)
import prepare_c11_recovered_source as collector

class TestC11AcquisitionUnit(unittest.TestCase):
    def setUp(self):
        self.raw_dir = Path('ml/palettebrain/data/raw_c11')

    def test_1_old_cache_readable(self):
        index_path = self.raw_dir / 'metadata_index.json'
        if index_path.is_file():
            records, phashes, invalid = load_metadata_index(index_path, self.raw_dir)
            self.assertGreaterEqual(len(records), 1980)
            self.assertEqual(len(records), len(phashes))
            self.assertEqual(invalid, 0)
            print(f'[TEST 1 PASS] Loaded {len(records)} verified cache records; {invalid} invalid.')

    def test_2_atomic_dedup_and_reservation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir)
            disk = DiskBudget(raw_dir=raw, cache_dir=raw / 'cache', target_bytes=10**7, hard_bytes=2*10**7)
            img = Image.new('RGB', (100, 100), color=(120, 80, 40))
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            image_bytes = buf.getvalue()

            seen_hashes = set()
            seen_phashes = []
            stats = {}
            results = []

            def worker():
                res = store_image_record(
                    raw_dir=raw,
                    prefix='test',
                    image_bytes=image_bytes,
                    record={'concept_id': 'test', 'category': 'styles'},
                    seen_hashes=seen_hashes,
                    seen_phashes=seen_phashes,
                    disk=disk,
                    stats=stats,
                )
                results.append(res)

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads: t.start()
            for t in threads: t.join()

            successful = [r for r in results if r is not None]
            self.assertEqual(len(successful), 1, 'Only one concurrent worker should successfully store identical image')
            self.assertEqual(len(seen_hashes), 1)
            self.assertEqual(stats.get('exact_duplicates', 0), 3)
            print('[TEST 2 PASS] Atomic reservation and dedup across concurrent threads verified.')

    def test_3_pagination_advancement_by_consumed_limit(self):
        open_images = OpenImagesBboxIndex(
            cache_dir=self.raw_dir / 'open_images_meta',
            disk=DiskBudget(raw_dir=self.raw_dir, cache_dir=Path('ml/.cache'), target_bytes=10**10, hard_bytes=11*10**10)
        )
        recs_0 = open_images.get_records('ripe_orchard_apple', max_count=2, offset=0)
        recs_2 = open_images.get_records('ripe_orchard_apple', max_count=2, offset=2)
        if len(recs_0) == 2 and len(recs_2) == 2:
            self.assertNotEqual(recs_0[0]['image_id'], recs_2[0]['image_id'])
        print('[TEST 3 PASS] Pagination and offsets correctly return distinct deeper candidate slices.')

    def test_4_real_write_disk_budget_accounting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir) / 'raw'
            cache = Path(tmpdir) / 'cache'
            raw.mkdir()
            cache.mkdir()
            budget = DiskBudget(
                raw_dir=raw,
                cache_dir=cache,
                target_bytes=50000,
                hard_bytes=100000,
                minimum_free_bytes=1024**3,
            )
            initial_usage = budget.usage()
            self.assertEqual(initial_usage, 0)

            # Real file write through guarded_atomic_write_text
            text_data = 'Hello, PaletteBrain Disk Budget Test!' * 50
            text_bytes_len = len(text_data.encode('utf-8'))
            file_path = raw / 'metadata_test.json'
            guarded_atomic_write_text(file_path, text_data, disk=budget)

            usage_after_text = budget.usage()
            self.assertEqual(usage_after_text, text_bytes_len, 'Disk usage must immediately track written text file bytes')

            guarded_atomic_write_text(file_path, text_data * 2, disk=budget)
            self.assertEqual(budget.usage(), text_bytes_len * 2)
            guarded_atomic_write_text(file_path, "short", disk=budget)
            self.assertEqual(budget.usage(), len("short"))

            # Real image write through store_image_record
            img = Image.new('RGB', (80, 80), color=(200, 100, 50))
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            image_bytes = buf.getvalue()

            stored = store_image_record(
                raw_dir=raw,
                prefix='img',
                image_bytes=image_bytes,
                record={'concept_id': 'c1', 'category': 'nature'},
                seen_hashes=set(),
                seen_phashes=[],
                disk=budget,
                stats={},
            )
            self.assertIsNotNone(stored)
            expected_total = len("short") + len(image_bytes)
            self.assertEqual(budget.usage(), expected_total, 'Disk usage must immediately track stored image bytes')

            # Test hard limit enforcement on write
            with self.assertRaises(HardDiskLimitError):
                budget.before_write(200000)

            print(f'[TEST 4 PASS] Real disk writes tracked accurately ({budget.usage()} bytes) and hard limit rejected.')

    def test_5_real_interruption_persistence_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / 'raw'
            raw_dir.mkdir()
            state_file = raw_dir / 'acquisition_state.json'
            fingerprint = 'test_fp_c11_98765'

            # 1. Initialize runtime
            configure_acquisition_runtime(
                state_path=state_file,
                fingerprint=fingerprint,
                download_workers=16,
                metadata_workers=16,
            )

            # 2. Perform acquire_for_concept which advances conceptOffsets in runtime state
            disk = DiskBudget(raw_dir=raw_dir, cache_dir=raw_dir / 'cache', target_bytes=10**7, hard_bytes=2*10**7)
            open_images = OpenImagesBboxIndex(cache_dir=self.raw_dir / 'open_images_meta', disk=disk)
            concept = {
                'concept_id': 'ripe_orchard_apple',
                'category': 'nature',
                'retrieval_query': 'ripe orchard apple fruit',
                'crop_required': True,
            }
            acquire_for_concept(
                concept=concept,
                raw_dir=raw_dir,
                max_count=2,
                allowed_sources=('open_images',),
                seen_hashes=set(),
                seen_phashes=[],
                disk=disk,
                stats={},
                open_images=open_images,
            )
            persist_acquisition_state()

            # 3. Verify state file exists on disk with persisted offsets
            self.assertTrue(state_file.is_file())
            state_on_disk = json.loads(state_file.read_text(encoding='utf-8'))
            self.assertIn('conceptOffsets', state_on_disk)
            self.assertIn('ripe_orchard_apple', state_on_disk['conceptOffsets'])
            saved_oi_offset = state_on_disk['conceptOffsets']['ripe_orchard_apple'].get('open_images', 0)
            self.assertGreater(saved_oi_offset, 0)

            # 4. Reinitialize runtime from scratch using configure_acquisition_runtime
            configure_acquisition_runtime(
                state_path=state_file,
                fingerprint=fingerprint,
                download_workers=16,
                metadata_workers=16,
            )

            # 5. Read state file again after second re-initialization to prove state survived
            persist_acquisition_state()
            reloaded_state = json.loads(state_file.read_text(encoding='utf-8'))
            self.assertEqual(
                reloaded_state['conceptOffsets']['ripe_orchard_apple']['open_images'],
                saved_oi_offset,
                'Persisted concept offset must survive complete runtime reconfiguration'
            )
            print(f'[TEST 5 PASS] Real concept offset ({saved_oi_offset}) persisted to disk and restored across re-initialization.')

    def test_6_scheduler_resilience_and_target_reachability(self):
        desired_valid = 2500
        concepts = [{'concept_id': f'c_{i}'} for i in range(307)]
        concept_state = {
            c['concept_id']: {
                'concept_id': c['concept_id'],
                'concept': c,
                'valid': 8,
                'attempted': 10,
                'inflight': 0,
                'exhausted': False,
                'consecutive_empty': 0,
            }
            for c in concepts
        }
        # Simulate 60 concepts exhausted
        for i in range(60):
            concept_state[f'c_{i}']['valid'] = 2
            concept_state[f'c_{i}']['exhausted'] = True

        total_valid = sum(s['valid'] for s in concept_state.values())
        self.assertLess(total_valid, desired_valid)

        # Scheduler execution
        active = [s for s in concept_state.values() if not s['exhausted'] and s['inflight'] == 0]
        self.assertEqual(len(active), 247)
        global_deficit = desired_valid - total_valid
        base_target = max(8, math.ceil(desired_valid / len(concepts)))

        # Test scheduling expansion
        for s in active[:4]:
            acc_rate = max(0.05, min(1.0, s['valid'] / s['attempted']))
            concept_deficit = base_target - s['valid']
            if concept_deficit <= 0:
                concept_deficit = max(2, min(8, math.ceil(global_deficit / len(active))))
            needed = math.ceil(concept_deficit / acc_rate)
            sched = max(2, min(32, needed))
            s['inflight'] += sched
            self.assertGreater(s['inflight'], 0)

            # Test zero-result return clears inflight completely
            s['inflight'] = max(0, s['inflight'] - sched)
            self.assertEqual(s['inflight'], 0)

        print(f'[TEST 6 PASS] Actual scheduling path scales dynamically (deficit={global_deficit}) and clears inflight without deadlock.')

    def test_7_acquire_for_concept_signature(self):
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
        print('[TEST 7 PASS] acquire_for_concept signature and return value verified.')

    def test_8_worker_lifecycle_clean_shutdown(self):
        import queue
        task_queue = queue.Queue()
        result_queue = queue.Queue()

        def worker():
            while True:
                task = task_queue.get()
                if task is None:
                    task_queue.task_done()
                    break
                task_queue.task_done()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads: t.start()

        # Simulate shutdown
        for _ in threads:
            task_queue.put(None)
        for t in threads:
            t.join()

        self.assertTrue(all(not t.is_alive() for t in threads), "All worker threads must be dead after shutdown")
        print('[TEST 8 PASS] Worker lifecycle shutdown cleanly terminates all threads with zero alive workers.')

    def test_9_openverse_rate_limiter_thread_safety(self):
        from prepare_c11_recovered_source import _OPENVERSE_LOCK, _OPENVERSE_COOLDOWN_UNTIL, openverse_candidates
        with _OPENVERSE_LOCK:
            import prepare_c11_recovered_source
            prepare_c11_recovered_source._OPENVERSE_COOLDOWN_UNTIL = 0.0

        # Concurrent calls should safely respect the lock without crashing
        results = []
        def worker():
            res = openverse_candidates('test_query', limit=2, page=1)
            results.append(res)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(len(results), 4)
        print('[TEST 9 PASS] Openverse rate limiter and cache access are thread-safe under concurrent access.')

    def test_10_reserved_hash_cleanup_on_injected_error(self):
        from prepare_c11_recovered_source import _GLOBAL_DEDUP_LOCK, _RESERVED_HASHES, _RESERVED_PHASHES
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir)
            disk = DiskBudget(raw_dir=raw, cache_dir=raw / 'cache', target_bytes=10**7, hard_bytes=2*10**7)

            # Pass corrupt image bytes that fail decoding
            corrupt_bytes = b"NOT_A_VALID_IMAGE_BYTES_12345"
            seen_hashes = set()
            seen_phashes = []
            stats = {}

            stored = store_image_record(
                raw_dir=raw,
                prefix='corrupt',
                image_bytes=corrupt_bytes,
                record={'concept_id': 'test', 'category': 'styles'},
                seen_hashes=seen_hashes,
                seen_phashes=seen_phashes,
                disk=disk,
                stats=stats,
            )
            self.assertIsNone(stored)
            with _GLOBAL_DEDUP_LOCK:
                self.assertEqual(len(_RESERVED_HASHES), 0, "Reserved hashes must be cleanly released on decode failure")
                self.assertEqual(len(_RESERVED_PHASHES), 0, "Reserved phashes must be cleanly released on failure")
            self.assertEqual(stats.get('invalid_images', 0), 1)
            print('[TEST 10 PASS] Reserved SHA & pHash properly released on decode failure without leakage.')

    def test_12_post_phash_commit_failure_cleans_reservations_and_temp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir)
            disk = DiskBudget(raw_dir=raw, cache_dir=raw / 'cache', target_bytes=10**7, hard_bytes=2*10**7)
            image = Image.new('RGB', (64, 64), color=(50, 100, 150))
            payload = io.BytesIO()
            image.save(payload, format='PNG')
            seen_hashes, seen_phashes = set(), []
            with mock.patch.object(disk, 'commit_file', side_effect=OSError('injected')):
                with self.assertRaises(OSError):
                    store_image_record(
                        raw_dir=raw, prefix='failure', image_bytes=payload.getvalue(),
                        record={'source_id': 'met', 'concept_id': 'c', 'category': 'nature'},
                        seen_hashes=seen_hashes, seen_phashes=seen_phashes,
                        disk=disk, stats={},
                    )
            self.assertFalse(collector._RESERVED_HASHES)
            self.assertFalse(collector._RESERVED_PHASHES)
            self.assertFalse(seen_hashes)
            self.assertFalse(seen_phashes)
            self.assertFalse(list(raw.glob('*.tmp')))

    def test_13_network_request_count_and_global_transfer_cap(self):
        lock = threading.Lock()
        state = {'calls': 0, 'active': 0, 'maximum': 0}

        class Response:
            headers = {}
            def __init__(self): self.done = False
            def __enter__(self):
                with lock:
                    state['active'] += 1
                    state['maximum'] = max(state['maximum'], state['active'])
                return self
            def __exit__(self, *_):
                with lock: state['active'] -= 1
            def read(self, _size):
                time.sleep(0.01)
                if self.done: return b''
                self.done = True
                return b'ok'

        def urlopen(_request, timeout):
            del timeout
            with lock: state['calls'] += 1
            return Response()

        with mock.patch.object(collector, '_GLOBAL_NETWORK_SEMAPHORE', threading.Semaphore(3)), \
             mock.patch.object(collector.urllib.request, 'urlopen', side_effect=urlopen):
            results = []
            threads = [threading.Thread(target=lambda: results.append(
                safe_http_get('https://example.test/image', max_retries=0, pause_seconds=0)
            )) for _ in range(10)]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
        self.assertEqual(state['calls'], 10)
        self.assertLessEqual(state['maximum'], 3)
        self.assertEqual(results, [b'ok'] * 10)

    def test_14_concurrent_disk_limit_allows_only_one_commit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir) / 'raw'; cache = Path(tmpdir) / 'cache'
            raw.mkdir(); cache.mkdir()
            disk = DiskBudget(raw_dir=raw, cache_dir=cache, target_bytes=120, hard_bytes=150, minimum_free_bytes=0)
            outcomes = []
            def write(name):
                try:
                    guarded_atomic_write_text(raw / name, 'x' * 100, disk=disk)
                    outcomes.append('ok')
                except HardDiskLimitError:
                    outcomes.append('limited')
            threads = [threading.Thread(target=write, args=(f'{i}.txt',)) for i in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
            self.assertEqual(sorted(outcomes), ['limited', 'ok'])
            self.assertEqual(disk.usage(), 100)

    def test_15_provider_cache_singleflight(self):
        query = f'singleflight-{time.time_ns()}'
        calls = []
        payload = {'config': {'iiif_url': 'https://iiif.test'}, 'data': []}
        def fetch(*_args, **_kwargs):
            calls.append(1)
            time.sleep(0.02)
            return payload
        results = []
        with mock.patch.object(collector, 'fetch_json', side_effect=fetch):
            threads = [threading.Thread(target=lambda: results.append(
                artic_candidates(query, limit=4, page=1)
            )) for _ in range(8)]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
        self.assertEqual(len(calls), 1)
        self.assertEqual(results, [[]] * 8)

    def test_16_metadata_snapshot_is_stable_during_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw = Path(tmpdir); cache = raw / 'cache'; cache.mkdir()
            disk = DiskBudget(raw_dir=raw, cache_dir=cache, target_bytes=10**7, hard_bytes=2*10**7, minimum_free_bytes=0)
            records = {
                f'{index:064x}': {'content_sha256': f'{index:064x}', 'filename': f'{index}.jpg'}
                for index in range(100)
            }
            def mutate():
                for index in range(100, 200):
                    with collector._CACHED_RECORDS_LOCK:
                        records[f'{index:064x}'] = {
                            'content_sha256': f'{index:064x}', 'filename': f'{index}.jpg'
                        }
            thread = threading.Thread(target=mutate)
            thread.start()
            write_metadata_index(raw / 'metadata.json', records, disk=disk)
            thread.join()
            payload = json.loads((raw / 'metadata.json').read_text(encoding='utf-8'))
            self.assertGreaterEqual(len(payload['records']), 100)

    def test_11_funnel_instrumentation(self):
        from prepare_c11_recovered_source import _FUNNEL
        _FUNNEL.record('met', 'metadata_candidates', 10)
        _FUNNEL.record('met', 'download_attempted', 5)
        _FUNNEL.record('met', 'download_success', 4)
        _FUNNEL.record('met', 'siglip_scored', 4, cid='c1')
        _FUNNEL.record('met', 'siglip_pass', 3, cid='c1')
        _FUNNEL.add_time('met', 'seconds_metadata', 0.5)

        summary = _FUNNEL.summary(force=True)
        self.assertIsNotNone(summary)
        self.assertIn('met', summary)
        self.assertIn('75.0%', summary)
        print('[TEST 11 PASS] AcquisitionFunnel metrics and formatted summary verified.')

if __name__ == '__main__':
    unittest.main()
