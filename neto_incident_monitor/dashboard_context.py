"""Safe error categories for analytics reads."""


class DashboardReadError(ValueError):
    def __init__(self, reason, retryable=True):
        self.reason, self.retryable = reason, retryable
        super().__init__('Nie potwierdzono poprawnego odczytu dashboardu (' + reason + ').')
