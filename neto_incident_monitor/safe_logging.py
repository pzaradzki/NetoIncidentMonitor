"""Keep exception locations without dumping browser URLs or form data."""
import logging
from logging.handlers import RotatingFileHandler
from time import monotonic
from pathlib import Path
import traceback
from copy import copy


class DiagnosticFileHandler(RotatingFileHandler):
    """Never dump a failed diagnostic record; bound retries of unavailable IO."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_at = 0
        self.failures = 0
        self.warned = False

    def emit(self, record):
        if monotonic() < self.retry_at:
            return
        failures = self.failures
        try:
            super().emit(record)
        except Exception:
            self.handleError(record)
        if self.failures == failures and self.retry_at:
            self.retry_at = 0
            self.warned = False
            try:
                logging.getLogger('servicenow').info('Przywrócono zapis diagnostyki logowania.')
            except Exception:
                pass

    def handleError(self, record):
        self.failures += 1
        self.retry_at = monotonic() + 30
        if not self.warned:
            self.warned = True
            try:
                logging.getLogger('servicenow').warning('Nie udało się zapisać diagnostyki logowania; zapis zostanie ponowiony.')
            except Exception:
                pass


class SafeExceptionFormatter(logging.Formatter):
    def format(self, record):
        record = copy(record)
        # Another handler may have cached the full, unsafe exception text.
        record.exc_text = None
        record.stack_info = None
        return super().format(record)

    def formatException(self, info):
        frames = traceback.extract_tb(info[2])
        locations = '\n'.join(f'  {Path(frame.filename).name}:{frame.lineno} ({frame.name})'
                              for frame in frames)
        # Exception messages and source lines can contain request/form values.
        return f'{info[0].__name__}\n{locations}'


def thread_exception(args):
    logging.getLogger('servicenow').error(
        'Nieobsłużony błąd wątku', exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
