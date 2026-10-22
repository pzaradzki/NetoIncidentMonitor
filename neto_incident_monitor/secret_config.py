"""Protect webhook credentials at rest with current-user Windows DPAPI."""
import base64
import ctypes
from ctypes import wintypes
import json
import os
import threading

KEYS = ('teams_webhook', 'google_chat_webhook')
LOCK = threading.RLock()
FORMAT = 'dpapi-user-v1'


class SecretStorageError(OSError):
    pass


class DataBlob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data, decrypt=False):
    if os.name != 'nt':
        raise SecretStorageError('Ochrona webhooków wymaga Windows DPAPI.')
    source = ctypes.create_string_buffer(data)
    incoming = DataBlob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = DataBlob()
    try:
        crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        operation = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
        operation.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.POINTER(DataBlob),
                              ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
        operation.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        # UI forbidden; deliberately omit CRYPTPROTECT_LOCAL_MACHINE.
        if not operation(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
            raise SecretStorageError('Nie udało się użyć ochrony webhooków Windows DPAPI.')
        try:
            return ctypes.string_at(outgoing.pbData, outgoing.cbData)
        finally:
            ctypes.memset(outgoing.pbData, 0, outgoing.cbData)
            kernel32.LocalFree(outgoing.pbData)
    finally:
        ctypes.memset(source, 0, ctypes.sizeof(source))


def protect(value):
    try:
        sealed = {'protection': FORMAT, 'blob': base64.b64encode(_crypt(value.encode('utf-8'))).decode('ascii')}
        if unprotect(sealed) != value:
            raise ValueError()
        return sealed
    except Exception:
        raise SecretStorageError('Nie udało się zabezpieczyć webhooka. Konfiguracja nie została zapisana.') from None


def unprotect(value):
    try:
        if not isinstance(value, dict) or value.get('protection') != FORMAT:
            raise ValueError()
        encrypted = base64.b64decode(value['blob'], validate=True)
        if not encrypted or len(encrypted) > 100000:
            raise ValueError()
        return _crypt(encrypted, decrypt=True).decode('utf-8')
    except Exception:
        raise SecretStorageError('Nie można odczytać webhooka dla bieżącego konta Windows. Wprowadź adres ponownie.') from None


class UnavailableSecret(str):
    """An empty runtime value preserving unreadable ciphertext on unrelated saves."""
    def __new__(cls, original):
        obj = str.__new__(cls, '')
        obj.original = original
        return obj


class Settings(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.protection_errors = []


def secret_containers(settings):
    yield settings, False
    entries = settings.get('filters')
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict):
            yield entry, True


def save_config(path, settings):
    with LOCK:
        encoded = dict(settings)
        if isinstance(encoded.get('filters'), list):
            encoded['filters'] = [dict(entry) if isinstance(entry, dict) else entry for entry in encoded['filters']]
        for container, _ in secret_containers(encoded):
            for key in KEYS:
                if key not in container:
                    continue
                value = container[key]
                if isinstance(value, UnavailableSecret):
                    container[key] = value.original
                elif isinstance(value, str):
                    container[key] = protect(value) if value else ''
                else:
                    raise SecretStorageError('Nieprawidłowa konfiguracja webhooka. Zapis został przerwany.')
        # Encryption must finish before creating or replacing any file.
        temporary = path.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(encoded, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()


def load_config(path, default):
    with LOCK:
        if not path.exists():
            return default
        raw = json.loads(path.read_text(encoding='utf-8'))
        settings = Settings(raw)
        migrate = False
        for container, per_filter in secret_containers(settings):
            for key in KEYS:
                value = container.get(key, '')
                if isinstance(value, str):
                    migrate |= bool(value)
                    continue
                try:
                    container[key] = unprotect(value)
                except SecretStorageError:
                    container[key] = UnavailableSecret(value)
                    enabled_key = 'notify_' + key.removesuffix('_webhook') if per_filter else key.replace('_webhook', '_enabled')
                    container[enabled_key] = False
                    settings.protection_errors.append('Nie można odczytać zapisanego webhooka. Wprowadź go ponownie w ustawieniach powiadomień.')
        if migrate:
            try:
                save_config(path, settings)
            except OSError:
                settings.protection_errors.append('Nie udało się zabezpieczyć dotychczasowych webhooków. Sprawdź możliwość zapisu konfiguracji.')
        return settings
