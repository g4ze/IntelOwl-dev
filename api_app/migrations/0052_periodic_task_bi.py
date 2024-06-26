# Generated by Django 4.1.10 on 2023-11-15 09:08

from django.conf import settings
from django.db import migrations

from intel_owl.celery import get_queue_name


def migrate(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    # notification

    c1 = CrontabSchedule.objects.get_or_create(minute=12)[0]
    PeriodicTask.objects.create(
        name="send_elastic_bi",
        task="intel_owl.tasks.send_bi_to_elastic",
        crontab=c1,
        enabled=settings.ELASTICSEARCH_BI_ENABLED,
        queue=get_queue_name("default"),
    )


def reverse_migrate(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="send_elastic_bi").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("django_celery_beat", "0018_improve_crontab_helptext"),
        ("api_app", "0051_pythonmodule_health_check_schedule_and_more"),
    ]

    operations = [migrations.RunPython(migrate, reverse_migrate)]
