from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from . import schema  # noqa: F401 - register authentication extensions

        # Enable WAL + a busy timeout on every SQLite connection so
        # concurrent requests on the ASGI server don't hit
        # "database is locked". No-op for non-sqlite backends.
        from django.db.backends.signals import connection_created
        from django.dispatch import receiver

        @receiver(connection_created, dispatch_uid='core.sqlite_pragmas')
        def _set_sqlite_pragmas(sender, connection, **kwargs):
            if connection.vendor != 'sqlite':
                return
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA synchronous=NORMAL;')
            cursor.execute('PRAGMA busy_timeout=30000;')
            cursor.execute('PRAGMA foreign_keys=ON;')
