"""Isolated Windows regression runner; never opens the user's runtime data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import weakref
from concurrent.futures import ThreadPoolExecutor


def child(module, result_path, data):
    import unittest
    import tkinter as tk
    import neto_incident_monitor.runtime_paths as paths
    paths.DATA = Path(data)
    paths.DATA.mkdir(parents=True, exist_ok=True)
    callback_errors = []
    roots = weakref.WeakSet()
    original_init, original_destroy = tk.Tk.__init__, tk.Tk.destroy

    def init(root, *args, **kwargs):
        original_init(root, *args, **kwargs)
        roots.add(root)
        root.report_callback_exception = lambda kind, error, trace: callback_errors.append(kind.__name__)
        root.tk.createcommand('bgerror', lambda *args: callback_errors.append('TclError'))

    def destroy(root):
        try:
            root.update_idletasks()
            owners = {}
            def collect(widget):
                for command in widget._tclCommands or ():
                    owners[command] = widget
                for widget_child in widget.children.values():
                    collect(widget_child)
            collect(root)
            for timer in root.tk.call('after', 'info'):
                script, _ = root.tk.call('after', 'info', timer)
                command = root.tk.splitlist(script)[0]
                owner = owners.get(command)
                if owner is not None:
                    owner.after_cancel(timer)
                else:
                    root.tk.call('after', 'cancel', timer)
        except tk.TclError:
            pass
        original_destroy(root)
        roots.discard(root)

    tk.Tk.__init__, tk.Tk.destroy = init, destroy
    # App may replace root.report_callback_exception; failures still fail the run.
    def report_exception(widget):
        callback_errors.append(sys.exc_info()[0].__name__)
    tk.Misc._report_exception = report_exception
    started = time.monotonic()
    result = None
    try:
        result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromName(module))
    finally:
        for root in list(roots):
            try:
                if root.winfo_exists():
                    root.destroy()
            except tk.TclError:
                pass
        from neto_incident_monitor.login_diagnostics import close_diagnostics
        close_diagnostics()
        import logging
        logging.shutdown()
        summary = dict(module=module, seconds=round(time.monotonic()-started, 2),
                       tests=result.testsRun if result else 0,
                       failures=[test.id() for test, _ in result.failures] if result else ['runner'],
                       errors=[test.id() for test, _ in result.errors] if result else ['runner'],
                       skipped=[dict(test=test.id(), reason=reason) for test, reason in result.skipped] if result else [],
                       callback_errors=callback_errors)
        Path(result_path).write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return int(not result.wasSuccessful() or bool(callback_errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('modules', nargs='*')
    parser.add_argument('--output', default='build/audit-regression.json')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--jobs', type=int, default=3)
    parser.add_argument('--child', nargs=3)
    args = parser.parse_args()
    if args.child:
        return child(*args.child)
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    modules = args.modules or ['tests.'+p.stem for p in sorted((root/'tests').glob('test_*.py'))]
    def run_module(module):
        with tempfile.TemporaryDirectory(prefix='neto-regression-') as directory:
            folder = Path(directory)
            with (folder/'console.txt').open('w', encoding='utf-8') as stream:
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(root))
                process = subprocess.Popen([sys.executable, '-B', '-m', 'tools.run_regression',
                    '--child', module, str(folder/'result.json'), str(folder/'data')],
                    stdout=stream, stderr=stream, env=env)
                try:
                    code = process.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                    else:
                        process.kill()
                    process.wait()
                    code = -1
            if (folder/'result.json').exists():
                summary = json.loads((folder/'result.json').read_text(encoding='utf-8'))
            else:
                summary = dict(module=module, tests=0, failures=[], errors=['timeout' if code == -1 else 'runner'], skipped=[], callback_errors=[])
            summary['exit_code'] = code
            print(module, 'OK' if code == 0 else 'FAILED', summary['tests'], flush=True)
            if code:
                # Print only test identifiers, never arbitrary exception contents.
                print(json.dumps(summary), flush=True)
            return summary
    # Native focus/visibility tests must never compete with another test window.
    native = {'tests.test_browser_window', 'tests.test_hidden_runtime_native', 'tests.test_login_runtime_native'}
    summaries = [run_module(module) for module in modules if module in native]
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        summaries.extend(executor.map(run_module, [module for module in modules if module not in native]))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summaries, indent=2), encoding='utf-8')
    print('TOTAL', sum(s['tests'] for s in summaries), 'SKIPPED', sum(len(s['skipped']) for s in summaries),
          'FAILED_MODULES', sum(s['exit_code'] != 0 for s in summaries), flush=True)
    return int(any(s['exit_code'] for s in summaries))


if __name__ == '__main__':
    raise SystemExit(main())
