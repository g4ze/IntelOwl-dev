from django.db import migrations
from django.db.models.fields.related_descriptors import (
    ForwardManyToOneDescriptor,
    ForwardOneToOneDescriptor,
    ManyToManyDescriptor,
)

plugin = {
    "python_module": {
        "module": "validin.Validin",
        "base_path": "api_app.analyzers_manager.observable_analyzers",
    },
    "name": "Validin",
    "description": "(Validin's)[https://app.validin.com/docs] API for threat researchers, teams, and companies to investigate historic and current data describing the structure and composition of the internet.",
    "disabled": False,
    "soft_time_limit": 60,
    "routing_key": "default",
    "health_check_status": True,
    "type": "observable",
    "docker_based": False,
    "maximum_tlp": "CLEAR",
    "observable_supported": ["ip", "domain"],
    "supported_filetypes": [],
    "run_hash": False,
    "run_hash_type": "",
    "not_supported_filetypes": [],
    "health_check_task": None,
    "model": "analyzers_manager.AnalyzerConfig",
}

params = [
    {
        "python_module": {
            "module": "validin.Validin",
            "base_path": "api_app.analyzers_manager.observable_analyzers",
        },
        "name": "scan_choice",
        "type": "str",
        "description": "all_records,a_records,aaaa_records,ns_records,ns_for,ptr_records,live_dns_query,dns_history_reverse_ip,ptr_records,cidr_dns_history,ptr_records_for_cidr\r\ndefault runs all of them",
        "is_secret": False,
        "required": False,
    },
    {
        "python_module": {
            "module": "validin.Validin",
            "base_path": "api_app.analyzers_manager.observable_analyzers",
        },
        "name": "api_key_name",
        "type": "str",
        "description": "",
        "is_secret": True,
        "required": True,
    },
]

values = [
    {
        "parameter": {
            "python_module": {
                "module": "validin.Validin",
                "base_path": "api_app.analyzers_manager.observable_analyzers",
            },
            "name": "scan_choice",
            "type": "str",
            "description": "all_records,a_records,aaaa_records,ns_records,ns_for,ptr_records,live_dns_query,dns_history_reverse_ip,ptr_records,cidr_dns_history,ptr_records_for_cidr\r\ndefault runs all of them",
            "is_secret": False,
            "required": False,
        },
        "analyzer_config": "Validin",
        "connector_config": None,
        "visualizer_config": None,
        "ingestor_config": None,
        "pivot_config": None,
        "for_organization": False,
        "value": "default",
        "updated_at": "2024-02-05T23:09:25.617798Z",
        "owner": None,
    }
]


def _get_real_obj(Model, field, value):
    if (
        type(getattr(Model, field))
        in [ForwardManyToOneDescriptor, ForwardOneToOneDescriptor]
        and value
    ):
        other_model = getattr(Model, field).get_queryset().model
        # in case is a dictionary, we have to retrieve the object with every key
        if isinstance(value, dict):
            real_vals = {}
            for key, real_val in value.items():
                real_vals[key] = _get_real_obj(other_model, key, real_val)
            value = other_model.objects.get_or_create(**real_vals)[0]
        # it is just the primary key serialized
        else:
            if isinstance(value, int):
                value = other_model.objects.get(pk=value)
            else:
                value = other_model.objects.get(name=value)
    return value


def _create_object(Model, data):
    mtm, no_mtm = {}, {}
    for field, value in data.items():
        if type(getattr(Model, field)) is ManyToManyDescriptor:
            mtm[field] = value
        else:
            value = _get_real_obj(Model, field, value)
            no_mtm[field] = value
    try:
        o = Model.objects.get(**no_mtm)
    except Model.DoesNotExist:
        o = Model(**no_mtm)
        o.full_clean()
        o.save()
        for field, value in mtm.items():
            attribute = getattr(o, field)
            attribute.set(value)


def migrate(apps, schema_editor):
    Parameter = apps.get_model("api_app", "Parameter")
    PluginConfig = apps.get_model("api_app", "PluginConfig")
    python_path = plugin.pop("model")
    Model = apps.get_model(*python_path.split("."))
    _create_object(Model, plugin)
    for param in params:
        _create_object(Parameter, param)
    for value in values:
        _create_object(PluginConfig, value)


def reverse_migrate(apps, schema_editor):
    python_path = plugin.pop("model")
    Model = apps.get_model(*python_path.split("."))
    Model.objects.get(name=plugin["name"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("api_app", "0059_alter_organizationpluginconfiguration_unique_together"),
        ("analyzers_manager", "0064_analyzer_config_zippy_scan"),
    ]

    operations = [migrations.RunPython(migrate, reverse_migrate)]
