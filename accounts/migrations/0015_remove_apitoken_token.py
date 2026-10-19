from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('accounts', '0014_alter_user_user_type')]

    operations = [
        # Authentication already uses token_hash. Removing stored plaintext does
        # not revoke existing credentials or change their hashes.
        migrations.RemoveField(model_name='apitoken', name='token'),
    ]
