"""
Step 1 of 3: Drop the FK to the old NegotiatedPrice model before it is deleted.
This must run before negotiations.0004 so PostgreSQL can drop the table safely.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0010_remove_restaurant_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cartitem',
            name='negotiation',
        ),
    ]
