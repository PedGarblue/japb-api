# Generated by Django 4.1.7 on 2023-04-21 18:38

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("currencies", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="currency",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
