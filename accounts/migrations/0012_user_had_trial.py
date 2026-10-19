"""Add the `had_trial` flag to User.

Once the customer consumes their one-time 14-day subscription trial,
this flips to True for life — future re-subscribes skip the trial and
fall through to the normal paid Paystack flow.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_alter_user_user_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='had_trial',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'True after the customer has consumed their one-time '
                    '14-day subscription trial. Future re-subscribes skip '
                    'the trial.'
                ),
            ),
        ),
    ]
