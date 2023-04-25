# Generated by Django 4.1.7 on 2023-04-22 00:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Receivable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=500)),
                ('amount_given', models.DecimalField(decimal_places=2, default=0, max_digits=19)),
                ('amount_to_receive', models.DecimalField(decimal_places=2, default=0, max_digits=19)),
                ('amount_paid', models.DecimalField(decimal_places=2, default=0, max_digits=19)),
                ('due_date', models.DateField()),
                ('contact', models.CharField(max_length=500)),
                ('status', models.CharField(choices=[('UNPAID', 'Unpaid'), ('PAID', 'Paid')], default='UNPAID', max_length=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='accounts.account')),
            ],
        ),
    ]