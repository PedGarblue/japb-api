from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0003_reportaccount_user_reportcurrency_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reportaccount",
            name="initial_balance",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="reportaccount",
            name="end_balance",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="reportaccount",
            name="total_income",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="reportaccount",
            name="total_expenses",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="reportcurrency",
            name="initial_balance",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="reportcurrency",
            name="end_balance",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="reportcurrency",
            name="total_income",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="reportcurrency",
            name="total_expenses",
            field=models.BigIntegerField(default=0),
        ),
    ]
