from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0007_expand_driver_profile_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliveryjob',
            name='declined_by',
            field=models.ManyToManyField(
                blank=True,
                help_text='Drivers who declined this job offer.',
                related_name='declined_jobs',
                to='delivery.DeliveryDriver',
            ),
        ),
    ]
