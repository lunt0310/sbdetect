from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("seatbelt", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPlateBinding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plate_text", models.CharField(max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plate_bindings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "ser_plate_binding",
                "db_table_comment": "用户车牌绑定表",
                "verbose_name": "用户车牌绑定",
                "verbose_name_plural": "用户车牌绑定",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="userplatebinding",
            constraint=models.UniqueConstraint(
                fields=("user", "plate_text"),
                name="uk_user_plate_binding_user_plate",
            ),
        ),
        migrations.AddIndex(
            model_name="userplatebinding",
            index=models.Index(
                fields=["user", "is_active", "created_at"],
                name="idx_plate_binding_user_active",
            ),
        ),
        migrations.AddIndex(
            model_name="userplatebinding",
            index=models.Index(
                fields=["plate_text", "is_active"],
                name="idx_plate_binding_plate_active",
            ),
        ),
    ]
