import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_collapse_subaccount_vendor'),
        ('debit', '0005_collapse_credit_vendor'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='credit_purchase',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transactions',
                to='debit.creditpurchase',
                help_text='Linked credit purchase when payment_intent is credit_payment',
            ),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='payment_intent',
            field=models.CharField(
                choices=[
                    ('order_payment', 'Order Payment'),
                    ('subscription_payment', 'Subscription Payment'),
                    ('tier_payment', 'Tier Payment'),
                    ('credit_payment', 'Credit Repayment'),
                    ('deposit', 'Deposit'),
                ],
                default='order_payment',
                max_length=20,
            ),
        ),
    ]
