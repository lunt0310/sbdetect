from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("seatbelt", "0002_userplatebinding"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="real_name",
        ),
    ]
