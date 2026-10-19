"""
Step 3 of 3: Add negotiation FK to NegotiationRoom (now that the new model exists).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_cartitem_negotiation_room'),
        ('negotiations', '0004_rebuild_negotiations'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartitem',
            name='negotiation',
            field=models.ForeignKey(
                to='negotiations.NegotiationRoom',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
            ),
        ),
    ]
