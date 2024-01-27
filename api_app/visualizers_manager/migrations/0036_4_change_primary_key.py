# Generated by Django 4.2.8 on 2024-01-09 14:31
import django
from django.db import migrations, models


def migrate(apps, schema_editor):
    VisualizerReport = apps.get_model("visualizers_manager", "VisualizerReport")
    VisualizerConfig = apps.get_model("visualizers_manager", "VisualizerConfig")
    PlaybookConfig = apps.get_model("playbooks_manager", "PlaybookConfig")
    name = VisualizerConfig.objects.filter(
        name=models.OuterRef("old_config")
    ).values_list("pk")[:1]
    VisualizerReport.objects.update(config=models.Subquery(name))
    for config in VisualizerConfig.objects.all():
        config.playbooks.set(PlaybookConfig.objects.filter(name__in=config.playbooks2))
        if config.disabled2:
            ContentType = apps.get_model("contenttypes", "ContentType")
            ct = ContentType.objects.get_for_model(config)
            OrganizationPluginConfiguration = apps.get_model(
                "api_app", "OrganizationPluginConfiguration"
            )
            for org in config.disabled2:
                if org:
                    OrganizationPluginConfiguration.objects.create(
                        organization=org,
                        object_id=config.pk,
                        content_type=ct,
                        disabled=True,
                    )


class Migration(migrations.Migration):
    dependencies = [
        ("api_app", "0056_alter_organizationpluginconfiguration_content_type"),
        ("visualizers_manager", "0036_3_change_primary_key"),
        ("playbooks_manager", "0022_add_dns0_to_free_playbook"),
    ]

    operations = [
        migrations.RenameField(
            model_name="visualizerreport", old_name="config", new_name="old_config"
        ),
        migrations.AddField(
            model_name="visualizerreport",
            name="config",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reports",
                to="visualizers_manager.visualizerconfig",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="visualizerconfig",
            name="playbooks",
            field=models.ManyToManyField(
                related_name="visualizers",
                to="playbooks_manager.PlaybookConfig",
            ),
        ),
        migrations.RunPython(migrate),
        migrations.AlterField(
            model_name="visualizerreport",
            name="config",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reports",
                to="visualizers_manager.visualizerconfig",
            ),
        ),
        migrations.RemoveField(model_name="visualizerreport", name="old_config"),
        migrations.RemoveField(model_name="visualizerconfig", name="playbooks2"),
        migrations.RemoveField(model_name="visualizerconfig", name="disabled2"),
    ]
