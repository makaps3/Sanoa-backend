"""
Adds the high-level `business_category` discriminator (retail vs restaurant)
to both vendor profile models so the frontend can toggle between the
"Shopping" and "Restaurants" experiences.

Also widens IndividualVendorProfile.vendor_type choices that were added in
the model but never reflected in a migration (food_vendor, market_trader,
local_brand, craftsperson).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0003_add_vendor_type_to_individual_vendor'),
    ]

    operations = [
        migrations.AddField(
            model_name='individualvendorprofile',
            name='business_category',
            field=models.CharField(
                choices=[
                    ('retail', 'Retail / Shopping'),
                    ('restaurant', 'Restaurant / Food'),
                ],
                default='retail',
                help_text=(
                    "High-level mode for the storefront. 'restaurant' enables "
                    "the fast-food / menu ordering UI on the frontend; "
                    "'retail' uses the standard shopping product grid."
                ),
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='businessvendorprofile',
            name='business_category',
            field=models.CharField(
                choices=[
                    ('retail', 'Retail / Shopping'),
                    ('restaurant', 'Restaurant / Food'),
                ],
                default='retail',
                help_text=(
                    "High-level mode for the storefront. 'restaurant' enables "
                    "the fast-food / menu ordering UI on the frontend; "
                    "'retail' uses the standard shopping product grid."
                ),
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='individualvendorprofile',
            name='vendor_type',
            field=models.CharField(
                choices=[
                    ('street_vendor', 'Street Vendor'),
                    ('freelancer', 'Freelancer'),
                    ('tuck_shop', 'Tuck Shop'),
                    ('home_business', 'Home Business'),
                    ('local_brand', 'Local Brand'),
                    ('craftsperson', 'Craftsperson'),
                    ('food_vendor', 'Food Vendor'),
                    ('market_trader', 'Market Trader'),
                    ('other', 'Other'),
                ],
                default='other',
                help_text='Type of vendor or business',
                max_length=20,
            ),
        ),
    ]
