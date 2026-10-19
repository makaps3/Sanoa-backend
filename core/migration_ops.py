"""Migration operations that SQLite tolerates but PostgreSQL needs help with."""
from django.db import migrations


class AlterPrimaryKeyToUUID(migrations.AlterField):
    """AlterField from an integer primary key to a UUIDField.

    SQLite rebuilds the table, so Django's default AlterField works there.
    PostgreSQL has no bigint -> uuid cast, so on PostgreSQL the table and
    every foreign-key column pointing at it are retyped directly. Integer ids
    can't be mapped to UUIDs, so on PostgreSQL the tables must be empty -
    the operation refuses rather than silently dropping data.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != 'postgresql':
            return super().database_forwards(app_label, schema_editor, from_state, to_state)

        model = to_state.apps.get_model(app_label, self.model_name)
        table = model._meta.db_table
        pk_col = model._meta.pk.column
        qn = schema_editor.quote_name

        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT con.conname, rel.relname, att.attname
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_attribute att
                  ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
                WHERE con.contype = 'f' AND con.confrelid = %s::regclass
                """,
                [table],
            )
            refs = cursor.fetchall()

            checks = [(table, pk_col)] + [(ref_table, ref_col) for _, ref_table, ref_col in refs]
            for check_table, check_col in checks:
                cursor.execute(
                    f'SELECT EXISTS (SELECT 1 FROM {qn(check_table)} WHERE {qn(check_col)} IS NOT NULL)'
                )
                if cursor.fetchone()[0]:
                    raise RuntimeError(
                        f'Cannot switch {table}.{pk_col} to UUID on PostgreSQL: '
                        f'{check_table}.{check_col} still has rows.'
                    )

        # Rows deleted earlier in this migration leave deferred FK checks
        # pending, which blocks ALTER TABLE - flush them first.
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')

        for conname, ref_table, _ in refs:
            schema_editor.execute(f'ALTER TABLE {qn(ref_table)} DROP CONSTRAINT {qn(conname)}')

        schema_editor.execute(f'ALTER TABLE {qn(table)} ALTER COLUMN {qn(pk_col)} DROP IDENTITY IF EXISTS')
        schema_editor.execute(f'ALTER TABLE {qn(table)} ALTER COLUMN {qn(pk_col)} DROP DEFAULT')
        schema_editor.execute(f'ALTER TABLE {qn(table)} ALTER COLUMN {qn(pk_col)} TYPE uuid USING NULL')

        for conname, ref_table, ref_col in refs:
            schema_editor.execute(f'ALTER TABLE {qn(ref_table)} ALTER COLUMN {qn(ref_col)} TYPE uuid USING NULL')
            schema_editor.execute(
                f'ALTER TABLE {qn(ref_table)} ADD CONSTRAINT {qn(conname)} '
                f'FOREIGN KEY ({qn(ref_col)}) REFERENCES {qn(table)} ({qn(pk_col)}) '
                'DEFERRABLE INITIALLY DEFERRED'
            )


class AlterForeignKeyToUUID(migrations.AlterField):
    """AlterField that re-points a foreign key from an integer-keyed model to
    a UUID-keyed one.

    On PostgreSQL the (empty) column is retyped to uuid first, then Django's
    normal AlterField swaps the constraint. Refuses if the column has values.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == 'postgresql':
            model = from_state.apps.get_model(app_label, self.model_name)
            table = model._meta.db_table
            column = model._meta.get_field(self.name).column
            qn = schema_editor.quote_name

            with schema_editor.connection.cursor() as cursor:
                cursor.execute(f'SELECT EXISTS (SELECT 1 FROM {qn(table)} WHERE {qn(column)} IS NOT NULL)')
                if cursor.fetchone()[0]:
                    raise RuntimeError(
                        f'Cannot re-point {table}.{column} to a UUID key on PostgreSQL: the column has values.'
                    )
                cursor.execute(
                    """
                    SELECT con.conname
                    FROM pg_constraint con
                    JOIN pg_attribute att
                      ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
                    WHERE con.contype = 'f' AND con.conrelid = %s::regclass AND att.attname = %s
                    """,
                    [table, column],
                )
                fk_names = [row[0] for row in cursor.fetchall()]

            schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')
            for name in fk_names:
                schema_editor.execute(f'ALTER TABLE {qn(table)} DROP CONSTRAINT {qn(name)}')
            schema_editor.execute(f'ALTER TABLE {qn(table)} ALTER COLUMN {qn(column)} TYPE uuid USING NULL')

        super().database_forwards(app_label, schema_editor, from_state, to_state)
