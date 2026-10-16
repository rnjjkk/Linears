import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from longtripletun.report_store import begin_report, publish_report, remove_generated, stage_loose_outputs, remove_loose_outputs


class ReportStoreTests(unittest.TestCase):
    def test_new_portfolio_replaces_report_and_removes_stale_details(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            first = begin_report(root)
            (first/'report.md').write_text('portfolio A')
            (first/'details').mkdir()
            (first/'details'/'recommended_weights.csv').write_text('old weights')
            (first/'details'/'approved_test').mkdir()
            (first/'details'/'approved_test'/'risk_levels.csv').write_text('old approved levels')
            publish_report(first)
            second = begin_report(root)
            (second/'report.md').write_text('portfolio B: keep original')
            (second/'details').mkdir()
            (second/'details'/'recommended_weights.csv').write_text('level,ticker,weight_percent')
            latest, warnings = publish_report(second)
            self.assertFalse(warnings)
            self.assertEqual((latest/'report.md').read_text(), 'portfolio B: keep original')
            self.assertEqual((latest/'details'/'recommended_weights.csv').read_text(), 'level,ticker,weight_percent')
            self.assertFalse((latest/'details'/'approved_test').exists())
            self.assertEqual({p.name for p in root.iterdir()}, {'report.md', 'details', '.report_files.json'})

    def test_retry_after_interruption_keeps_completed_report(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            first = begin_report(root)
            (first/'report.md').write_text('completed')
            publish_report(first)
            interrupted = begin_report(root)
            (interrupted/'metrics.csv').write_text('incomplete calculation')
            retry = begin_report(root)
            self.assertEqual((root/'report.md').read_text(), 'completed')
            self.assertFalse((retry/'metrics.csv').exists())
            (retry/'report.md').write_text('new completed report')
            publish_report(retry)
            self.assertEqual({p.name for p in root.iterdir()}, {'report.md', '.report_files.json'})

    def test_unknown_file_in_pending_report_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            draft = begin_report(root)
            (draft/'personal_notes.txt').write_text('keep')
            with self.assertRaises(ValueError):
                begin_report(root)
            self.assertEqual((draft/'personal_notes.txt').read_text(), 'keep')

    def test_main_report_preserves_comparison_report(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            comparison = root/'comparisons'
            comparison.mkdir()
            (comparison/'comparison.md').write_text('keep comparison')
            draft = begin_report(root)
            (draft/'report.md').write_text('main result')
            result, warnings = publish_report(draft)
            self.assertEqual(result, root)
            self.assertFalse(warnings)
            self.assertEqual((comparison/'comparison.md').read_text(), 'keep comparison')
            self.assertFalse((root/'latest').exists())

    def test_locked_directory_updates_files(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            first = begin_report(root)
            (first/'report.md').write_text('old')
            latest, _ = publish_report(first)
            second = begin_report(root)
            (second/'report.md').write_text('new')
            rename = Path.rename
            def locked(path, target):
                if path == latest:
                    raise PermissionError('directory locked')
                return rename(path, target)
            with patch.object(Path, 'rename', locked):
                result, warnings = publish_report(second)
            self.assertEqual(result, latest)
            self.assertEqual((latest/'report.md').read_text(), 'new')
            self.assertFalse(warnings)

    def test_loose_outputs_protect_inputs_and_changed_files(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            base = Path(temp)
            draft = begin_report(base/'reports')
            protected = base/'proposed_weights.csv'
            protected.write_text('user input')
            output = base/'cost_comparison.csv'
            output.write_text('result')
            saved = stage_loose_outputs(base, draft, [protected])
            self.assertTrue(output.exists())
            self.assertNotIn(protected.name, saved)
            self.assertEqual((draft/'details'/output.name).read_text(), 'result')
            output.write_text('newer concurrent output')
            remove_loose_outputs(base, saved)
            self.assertTrue(output.exists())
            output.write_text('result')
            remove_loose_outputs(base, saved)
            self.assertFalse(output.exists())
            self.assertEqual(protected.read_text(), 'user input')

    def test_replaces_only_completed_reports(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            old = root/'20260101_000000_000000'
            old.mkdir()
            (old/'report.md').write_text('old')
            draft = begin_report(root)
            with self.assertRaises(ValueError):
                publish_report(draft)
            self.assertTrue(old.exists())
            (draft/'report.md').write_text('first')
            latest, warnings = publish_report(draft)
            self.assertFalse(old.exists())
            self.assertFalse(warnings)
            second = begin_report(root)
            (second/'report.md').write_text('second')
            publish_report(second)
            self.assertEqual((latest/'report.md').read_text(), 'second')
            self.assertEqual({p.name for p in root.iterdir()}, {'report.md', '.report_files.json'})

    def test_unknown_files_and_inputs_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            (root/'portfolio.csv').write_text('input')
            old = root/'20260101_000000_000000'
            old.mkdir()
            (old/'my_notes.txt').write_text('keep')
            draft = begin_report(root)
            (draft/'report.md').write_text('new')
            _, warnings = publish_report(draft)
            self.assertTrue(warnings)
            self.assertEqual((old/'my_notes.txt').read_text(), 'keep')
            self.assertEqual((root/'portfolio.csv').read_text(), 'input')
            with self.assertRaises(ValueError):
                remove_generated(root, root)

    def test_failed_switch_restores_latest(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            first = begin_report(root)
            (first/'report.md').write_text('old')
            publish_report(first)
            draft = begin_report(root)
            (draft/'report.md').write_text('new')
            import longtripletun.report_store as store
            original = store._replace_file
            failed = False
            def fail_stage(source, target):
                nonlocal failed
                if source.parent == draft and source.name == 'report.md' and not failed:
                    failed = True
                    raise OSError('simulated publish failure')
                return original(source, target)
            with patch('longtripletun.report_store._replace_file', fail_stage), self.assertRaises(OSError):
                publish_report(draft)
            self.assertEqual((root/'report.md').read_text(), 'old')


if __name__ == '__main__':
    unittest.main()
