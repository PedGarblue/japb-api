# Generated by Django 4.1.7 on 2023-09-22 21:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='decimal_places',
            field=models.IntegerField(default=2),
        ),
    ]
