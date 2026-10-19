"""Add the auto-generated 4-digit drop-off PIN to DeliveryJob.

Used to verify hand-off at the customer's location — the driver must
ask the customer for their PIN before they can mark the job as
`delivered`. Existing rows get a freshly generated PIN via the
data-migration step below so historical jobs aren't left with a blank
column.
"""
import secrets

from django.db import migrations, models


def populate_pins(apps, schema_editor):
    DeliveryJob = apps.get_model('delivery', 'DeliveryJob')
    # Only touch rows that don't already have a PIN. Idempotent — safe
    # to re-run if the migration is rolled forward more than once.
    for job in DeliveryJob.objects.filter(delivery_pin=''):
        job.delivery_pin = f"{secrets.randbelow(10000):04d}"
        job.save(update_fields=['delivery_pin'])


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0008_deliveryjob_declined_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliveryjob',
            name='delivery_pin',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Auto-generated 4-digit PIN the customer reads to '
                    'the driver at drop-off.'
                ),
                max_length=4,
            ),
        ),
        migrations.RunPython(populate_pins, reverse_code=migrations.RunPython.noop),
    ]
