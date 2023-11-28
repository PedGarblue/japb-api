# Generated by Django 4.1.7 on 2023-11-22 15:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0004_transaction_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='type',
            field=models.CharField(choices=[('expense', 'expense'), ('income', 'income')], default='expense', max_length=50),
        ),
    ]