"""Standalone updater, launched from user data so installation files are unlocked."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

EXE = 'Neto Incident Monitor.exe'


def wait_for_parent(pid, ready, cancelled):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    process = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE only; never terminate it.
    if not process:
        raise RuntimeError('Nie można potwierdzić procesu aplikacji.')
    try:
        ready.write_text('ready', encoding='ascii')
        for _ in range(120):
            if cancelled.exists():
                raise RuntimeError('Aktualizacja anulowana.')
            result = kernel.WaitForSingleObject(process, 1000)
            if result == 0:
                if cancelled.exists():
                    raise RuntimeError('Aktualizacja anulowana.')
                return
            if result != 258:
                raise RuntimeError('Błąd oczekiwania na zamknięcie aplikacji.')
        raise RuntimeError('Aplikacja nie została zamknięta w ciągu 120 sekund.')
    finally:
        kernel.CloseHandle(process)


def validate_job(job):
    target, stage, payload = (Path(job[k]).resolve() for k in ('target', 'stage', 'payload'))
    if (not target.parent.is_dir() or target == target.parent or target == Path.home().resolve()
            or stage.parent != target.parent or not stage.name.startswith('.neto-update-')
            or payload.parent != stage or payload.name != 'Neto Incident Monitor'
            or not (target / EXE).is_file() or not (payload / EXE).is_file()
            or not (payload / '_internal').is_dir() or (target / 'data').exists()):
        raise ValueError('Nieprawidłowe foldery aktualizacji.')
    return target, stage, payload


def launch(target, resume_monitoring=False):
    return subprocess.Popen([str(target / EXE)] + (['--resume-monitoring'] if resume_monitoring else []), cwd=target)


def check_health(target, work, expected):
    report = work / 'health.json'
    report.unlink(missing_ok=True)
    process = subprocess.Popen([str(target / EXE), '--smoke-test', str(report)], cwd=work)
    try:
        code = process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise RuntimeError('Test nowej wersji przekroczył limit czasu.')
    result = json.loads(report.read_text(encoding='utf-8'))
    if code or not result.get('ok') or result.get('version') != expected:
        raise RuntimeError('Test nowej wersji nie powiódł się.')


def install(job, work, health=check_health, restart=launch):
    target, stage, payload = validate_job(job)
    backup = target.parent / ('.neto-backup-' + uuid4().hex)
    failed = stage / 'failed'
    # All renamed paths are validated siblings; never delete user directories.
    try:
        target.rename(backup)
    except Exception:
        restart(target)
        raise
    try:
        payload.rename(target)
        health(target, work, job['version'])
        restart(target)
    except Exception:
        if target.exists():
            target.rename(failed)
        backup.rename(target)
        restart(target)
        raise
    # Keep the previous installation as an additional recovery copy.
    return backup


def main(job_path):
    work = Path(job_path).resolve().parent
    try:
        job = json.loads(Path(job_path).read_text(encoding='utf-8'))
        validate_job(job)
        wait_for_parent(int(job['pid']), work / 'ready', work / 'cancelled')
        backup = install(job, work, restart=lambda target: launch(target, job.get('resume_monitoring', False)))
        (work / 'result.json').write_text(json.dumps({'ok': True, 'backup': str(backup)}), encoding='utf-8')
    except Exception as error:
        (work / 'result.json').write_text(json.dumps({'ok': False, 'error_type': type(error).__name__}), encoding='utf-8')
        ctypes.windll.user32.MessageBoxW(None,
            f'Aktualizacja nie została ukończona. Poprzednia wersja została zachowana.\nSzczegóły: {work / "result.json"}',
            'Neto Incident Monitor', 0x10)
        sys.exit(1)
