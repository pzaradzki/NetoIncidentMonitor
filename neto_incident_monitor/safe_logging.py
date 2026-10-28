"""Keep exception locations without dumping browser URLs or form data."""
import logging
from pathlib import Path
import traceback
from copy import copy


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
