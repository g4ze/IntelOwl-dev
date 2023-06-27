# This file is a part of IntelOwl https://github.com/intelowlproject/IntelOwl
# See the file 'LICENSE' for copying permission.
import logging
import uuid
from typing import Any, Dict, Type

from celery.canvas import Signature
from django.conf import settings
from django.contrib.postgres import fields as pg_fields
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Manager, QuerySet
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.module_loading import import_string

from api_app.core.choices import ParamTypes, ReportStatus
from api_app.validators import plugin_name_validator, validate_config
from certego_saas.apps.organization.organization import Organization
from certego_saas.apps.user.models import User
from intel_owl.celery import DEFAULT_QUEUE, get_queue_name

logger = logging.getLogger(__name__)


class AbstractReport(models.Model):
    # constants
    Status = ReportStatus

    # fields
    status = models.CharField(max_length=50, choices=Status.choices)
    report = models.JSONField(default=dict)
    errors = pg_fields.ArrayField(
        models.CharField(max_length=512), default=list, blank=True
    )
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(default=timezone.now)
    task_id = models.UUIDField()  # tracks celery task id

    job = models.ForeignKey(
        "api_app.Job", related_name="%(class)ss", on_delete=models.CASCADE
    )
    # meta

    class Meta:
        abstract = True

    @classmethod
    @property
    def config(cls) -> "AbstractConfig":
        raise NotImplementedError()

    @property
    def runtime_configuration(self):
        return self.job.get_config_runtime_configuration(self.config)

    def __str__(self):
        return f"{self.__class__.__name__}(job:#{self.job_id}, {self.config.name})"

    # properties
    @property
    def user(self) -> models.Model:
        return self.job.user

    @property
    def process_time(self) -> float:
        secs = (self.end_time - self.start_time).total_seconds()
        return round(secs, 2)

    def append_error(self, err_msg: str, save=True):
        self.errors.append(err_msg)
        if save:
            self.save(update_fields=["errors"])


# This is required as a function (and not even a lambda)
# because the default must be a callable
def config_default():
    return dict(queue=DEFAULT_QUEUE, soft_time_limit=60)


def valid_value_for_test(func):
    def wrapper(self, user=None):
        try:
            return func(self, user)
        except RuntimeError:
            from api_app.models import PluginConfig

            if not settings.STAGE_CI:
                raise
            if "url" in self.name:

                return PluginConfig.objects.get_or_create(
                    value="https://intelowl.com",
                    parameter=self,
                    owner=None,
                    for_organization=False,
                )[0]
            elif "pdns_credentials" == self.name:
                return PluginConfig.objects.get_or_create(
                    value="user|pwd",
                    parameter=self,
                    owner=None,
                    for_organization=False,
                )[0]
            elif "test" in self.name:
                raise
            else:
                return PluginConfig.objects.get_or_create(
                    value="test",
                    parameter=self,
                    owner=None,
                    for_organization=False,
                )[0]

    return wrapper


class Parameter(models.Model):
    name = models.CharField(null=False, blank=False, max_length=50)
    type = models.CharField(
        choices=ParamTypes.choices, max_length=10, null=False, blank=False
    )
    description = models.TextField(blank=True, default="")
    is_secret = models.BooleanField(null=False)
    required = models.BooleanField(null=False)
    analyzer_config = models.ForeignKey(
        "analyzers_manager.AnalyzerConfig",
        related_name="parameters",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    connector_config = models.ForeignKey(
        "connectors_manager.ConnectorConfig",
        related_name="parameters",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    visualizer_config = models.ForeignKey(
        "visualizers_manager.VisualizerConfig",
        related_name="parameters",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = [
            ("name", "analyzer_config"),
            ("name", "connector_config"),
            ("name", "visualizer_config"),
        ]
        indexes = [
            models.Index(fields=["analyzer_config", "is_secret"]),
            models.Index(fields=["connector_config", "is_secret"]),
            models.Index(fields=["visualizer_config", "is_secret"]),
        ]

    def clean_config(self):
        count_configs = (
            bool(self.analyzer_config)
            + bool(self.connector_config)
            + bool(self.visualizer_config)
        )

        if count_configs > 1:
            msg = (
                "You can't have the same parameter on more than one"
                " configuration at the time"
            )
            logger.error(msg)
            raise ValidationError(msg)
        elif count_configs == 0:
            msg = "The parameter must be set to at least a configuration"
            logger.error(msg)
            raise ValidationError(msg)

    def clean(self) -> None:
        super().clean()
        self.clean_config()

    @cached_property
    def config(self):
        return self.analyzer_config or self.connector_config or self.visualizer_config

    def values_for_user(self, user: User = None) -> QuerySet:
        from api_app.models import PluginConfig

        return PluginConfig.visible_for_user(user).filter(parameter=self)

    @valid_value_for_test
    def get_first_value(self, user: User):
        from api_app.models import PluginConfig

        # priority for value retrieved
        # 1 - Owner
        # 2 - Organization
        # 3 - Default
        qs = self.values_for_user(user)
        try:
            result = qs.get(owner=user)
            logger.info(f"Retrieved {result.value=} owned by the user")
            return result
        except PluginConfig.DoesNotExist:
            if user.has_membership():
                try:
                    result = qs.get(
                        for_organization=True,
                        owner=user.membership.organization.owner,
                    )
                    logger.info(f"Retrieved {result.value=} owned by the organization")
                    return result
                except PluginConfig.DoesNotExist:
                    ...
            try:
                result = qs.get(owner__isnull=True)
                logger.info(f"Retrieved {result.value=}, default value")
                return result
            except PluginConfig.DoesNotExist:
                raise RuntimeError(
                    "Unable to find a valid value for parameter"
                    f" {self.name} for configuration {self.config.name}"
                )


class AbstractConfig(models.Model):
    name = models.CharField(
        max_length=100,
        null=False,
        unique=True,
        primary_key=True,
        validators=[plugin_name_validator],
    )
    description = models.TextField(null=False)

    disabled = models.BooleanField(null=False, default=False)
    disabled_in_organizations = models.ManyToManyField(
        Organization, related_name="%(app_label)s_%(class)s_disabled", blank=True
    )

    class Meta:
        indexes = [models.Index(fields=["name"]), models.Index(fields=["disabled"])]
        abstract = True

    @classmethod
    @property
    def runtime_configuration_key(cls) -> str:
        return f"{cls.__name__.split('Config')[0].lower()}s"

    @classmethod
    @property
    def snake_case_name(cls) -> str:
        import re

        return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()

    def _is_disabled_in_org(self, user: User = None):
        if user and user.has_membership():
            return self.disabled_in_organizations.filter(
                pk=user.membership.organization.pk
            ).exists()
        return False

    @classmethod
    def runnable(cls, user: User = None) -> QuerySet:
        objs = cls.objects.filter(disabled=False)
        if user and user.has_membership():
            objs = objs.exclude(disabled_in_organization=user.membership.organization)
        return objs

    def is_runnable(self, user: User = None):
        disabled_in_org = self._is_disabled_in_org(user)
        logger.debug(f"{disabled_in_org=}, {self.disabled=}")
        return not disabled_in_org and not self.disabled


class PythonConfig(AbstractConfig):

    parameters: Manager

    python_module = models.CharField(null=False, max_length=120, db_index=True)

    config = models.JSONField(
        blank=False,
        default=config_default,
        validators=[validate_config],
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=("python_module", "disabled")),
        ]
        ordering = ["name", "disabled"]

    @classmethod
    @property
    def plugin_type(cls) -> str:
        # retro compatibility

        raise NotImplementedError()

    @classmethod
    @property
    def stage_status_complete(cls) -> str:
        from api_app.choices import Status

        name_plugin = cls.__name__.split("Config")[0]
        return getattr(Status, f"{name_plugin.upper()}S_COMPLETED").value

    @classmethod
    @property
    def stage_status_running(cls) -> str:
        from api_app.choices import Status

        name_plugin = cls.__name__.split("Config")[0]
        return getattr(Status, f"{name_plugin.upper()}S_RUNNING").value

    @classmethod
    def signature_pipeline_running(cls, job) -> Signature:
        return cls._signature_pipeline_status(job, cls.stage_status_running)

    @classmethod
    def signature_pipeline_completed(cls, job) -> Signature:
        return cls._signature_pipeline_status(job, cls.stage_status_complete)

    @classmethod
    def _signature_pipeline_status(cls, job, status: str) -> Signature:
        from intel_owl import tasks

        return tasks.job_set_pipeline_status.signature(
            args=[job.pk, status],
            kwargs={},
            queue=get_queue_name(DEFAULT_QUEUE),
            soft_time_limit=10,
            immutable=True,
            MessageGroupId=str(uuid.uuid4()),
        )

    @property
    def python_base_path(self) -> str:
        raise NotImplementedError()

    def clean_python_module(self):
        try:
            _ = self.python_class
        except ImportError as exc:
            raise ValidationError(
                "`python_module` incorrect, "
                f"{self.python_complete_path} couldn't be imported"
            ) from exc

    def clean_config_queue(self):
        queue = self.config["queue"]
        if queue not in settings.CELERY_QUEUES:
            logger.warning(
                f"Analyzer {self.name} has a wrong queue."
                f" Setting to `{DEFAULT_QUEUE}`"
            )
            self.config["queue"] = DEFAULT_QUEUE

    def clean(self):
        super().clean()
        self.clean_python_module()
        self.clean_config_queue()

    @property
    def options(self):
        return self.parameters.filter(is_secret=False)

    @property
    def secrets(self):
        return self.parameters.filter(is_secret=True)

    @property
    def required_parameters(self) -> QuerySet:
        return self.parameters.filter(required=True)

    def _is_configured(self, user: User = None) -> bool:
        for param in self.required_parameters:
            param: Parameter
            if not param.values_for_user(user).exists():
                return False
        return True

    @classmethod
    def runnable(cls, user: User = None) -> QuerySet:
        raise NotImplementedError()

    def is_runnable(self, user: User = None):
        return super().is_runnable(user) and self._is_configured(user)

    @cached_property
    def queue(self):
        queue = self.config["queue"]
        if queue not in settings.CELERY_QUEUES:
            queue = DEFAULT_QUEUE
        return get_queue_name(queue)

    @cached_property
    def routing_key(self):
        return self.config["queue"]

    @cached_property
    def soft_time_limit(self):
        return self.config["soft_time_limit"]

    @cached_property
    def python_complete_path(self) -> str:
        return f"{self.python_base_path}.{self.python_module}"

    @cached_property
    def python_class(self) -> Type:
        return import_string(self.python_complete_path)

    @classmethod
    @property
    def config_exception(cls):
        raise NotImplementedError()

    def read_params(self, job) -> Dict[Parameter, Any]:
        # priority
        # 1 - Runtime config
        # 2 - Value inside the db
        result = {}
        for param in self.parameters.all():
            param: Parameter
            if param.name in job.get_config_runtime_configuration(self):
                result[param] = job.get_config_runtime_configuration(self)[param.name]
            else:
                try:
                    result[param] = param.get_first_value(job.user).value
                except RuntimeError as e:
                    if param.required:
                        raise e
        return result

    def get_signature(self, job):
        from api_app.models import Job
        from intel_owl import tasks

        job: Job
        if self.is_runnable(job.user):
            # gen new task_id
            task_id = str(uuid.uuid4())
            args = [
                job.pk,
                self.python_complete_path,
                self.pk,
                job.get_config_runtime_configuration(self),
                task_id,
            ]

            return tasks.run_plugin.signature(
                args,
                {},
                queue=self.queue,
                soft_time_limit=self.soft_time_limit,
                task_id=task_id,
                immutable=True,
                MessageGroupId=str(task_id),
            )
        raise RuntimeError(
            f"Unable to create signature, config {self.name} is not runnable"
        )
