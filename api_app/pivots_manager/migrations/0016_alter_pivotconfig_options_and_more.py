# Generated by Django 4.1.10 on 2023-09-28 13:57

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analyzers_manager", "0043_modify_yaraify_url"),
        ("connectors_manager", "0022_alter_connectorconfig_python_module"),
        ("pivots_manager", "0015_alter_pivotmap_pivot_config"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="pivotconfig",
            options={"ordering": ["name", "disabled"]},
        ),
        migrations.RemoveConstraint(
            model_name="pivotconfig",
            name="pivot_config_all_null_configs",
        ),
        migrations.RemoveConstraint(
            model_name="pivotconfig",
            name="pivot_config_no_null_configs",
        ),
        migrations.RemoveField(
            model_name="pivotconfig",
            name="related_analyzer_config",
        ),
        migrations.RemoveField(
            model_name="pivotconfig",
            name="related_connector_config",
        ),
        migrations.AddField(
            model_name="pivotconfig",
            name="related_analyzer_configs",
            field=models.ManyToManyField(
                blank=True,
                related_name="pivots",
                to="analyzers_manager.analyzerconfig",
            ),
        ),
        migrations.AddField(
            model_name="pivotconfig",
            name="related_connector_configs",
            field=models.ManyToManyField(
                blank=True,
                related_name="pivots",
                to="connectors_manager.connectorconfig",
            ),
        ),
        migrations.AddIndex(
            model_name="pivotconfig",
            index=models.Index(
                fields=["python_module", "disabled"],
                name="pivots_mana_python__75b643_idx",
            ),
        ),
    ]
