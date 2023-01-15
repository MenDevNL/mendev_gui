from django.core.exceptions import ObjectDoesNotExist
from django.db import models, connection
from django.contrib.auth.models import Permission, User
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from crum import get_current_user
from django.utils.translation import gettext as _
from .functions import list_to_sql_string, random_string
import json


class SysOrganisation(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)
    contact = models.CharField(max_length=50, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address_1 = models.CharField(max_length=50, blank=True, null=True)
    address_2 = models.CharField(max_length=50, blank=True, null=True)
    zip = models.CharField(max_length=25, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)
    remarks = ArrayField(base_field=models.TextField(), blank=True, null=True)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if user and not self.pk:
            self.created_by = user.username
        if user and self.pk:
            self.modified_by = user.username
        super(SysOrganisation, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'sys_organisations'


class SysProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    language = models.CharField(max_length=10,
                                choices=settings.LANGUAGES,
                                default=settings.LANGUAGE_CODE
                                )
    organisation = models.ForeignKey(SysOrganisation, on_delete=models.CASCADE, blank=True, null=True)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if user and not self.pk:
            self.created_by = user.username
        if user and self.pk:
            self.modified_by = user.username
        super(SysProfile, self).save(*args, **kwargs)

    def __str__(self):
        return self.user.get_full_name()

    class Meta:
        managed = False
        db_table = 'sys_profiles'


class SysMenu(models.Model):
    name = models.CharField(max_length=30)
    url = models.CharField(max_length=30)
    sequence = models.IntegerField(default=0)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, null=True, blank=True)
    two_factor = models.BooleanField(blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    linkable = models.BooleanField(default=True)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def __init__(self, *args, **kwargs):
        super(SysMenu, self).__init__(*args, **kwargs)
        self.selected = False
        self.options = []
        self.num_options = 0
        self.level_shift = 0
        self.l1_menu = None
        self.l2_menu = None
        self.l3_menu = None
        self.l4_menu = None

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} - {self.sequence:02d}: {self.name}'
        else:
            return self.name

    @property
    def permission_name(self):
        if self.permission:
            return f'{self.permission.content_type.app_label}.{self.permission.codename}'
        else:
            return None

    def prepare(self, url, user, permitted_menu=None, level=0):
        self.selected = True
        if not permitted_menu:
            permitted_menu = SysMenu.objects.get(name='MAIN')
            permitted_menu.permittedMenu(user)
        self.options = permitted_menu.options
        self.num_options = len(self.options)
        self.level_shift = permitted_menu.level_shift
        for option in self.options:
            url_parts = option.url.split('/')
            url_needle = '@#$'
            part_counter = level + self.level_shift + 1
            if len(url_parts) > part_counter:
                url_needle = ''
                for i in range(part_counter):
                    url_needle += '/' + url_parts[i + 1]
            if url.find(url_needle) == 0: # URL found in option, thus selected
                option.selected = True
                self.l1_menu = SysMenu()
                self.l1_menu.name = option.name
                self.l1_menu.url = option.url
                self.l1_menu.prepare(
                    url=url,
                    user=user,
                    permitted_menu=option,
                    level=level + 1
                )
                self.l2_menu = self.l1_menu.l1_menu
                self.l3_menu = self.l1_menu.l2_menu
                self.l4_menu = self.l1_menu.l3_menu

    def permittedMenu(self, user):
        try:
            l0_available_options = self.sysmenu_set.all()
            for l0_available_option in l0_available_options:
                if not l0_available_option.permission or user and user.has_perm(l0_available_option.permission_name):
                    if l0_available_option.two_factor and not user.is_verified():
                        continue
                    l1_menu = l0_available_option
                    l1_available_options = l0_available_option.sysmenu_set.all()
                    for l1_available_option in l1_available_options:
                        if not l1_available_option.permission or user and user.has_perm(l1_available_option.permission_name):
                            if l1_available_option.two_factor and not user.is_verified():
                                continue
                            l2_menu = l1_available_option
                            l2_available_options = l2_menu.sysmenu_set.all()
                            for l2_available_option in l2_available_options:
                                if not l2_available_option.permission or user and user.has_perm(
                                        l2_available_option.permission_name):
                                    if l2_available_option.two_factor and not user.is_verified():
                                        continue
                                    l3_menu = l2_available_option
                                    l3_available_options = l3_menu.sysmenu_set.all()
                                    for l3_available_option in l3_available_options:
                                        if not l3_available_option.permission or user and user.has_perm(
                                                l3_available_option.permission_name):
                                            if l3_available_option.two_factor and not user.is_verified():
                                                continue
                                            l4_menu = l3_available_option
                                            l4_available_options = l4_menu.sysmenu_set.all()
                                            for l4_available_option in l4_available_options:
                                                if not l4_available_option.permission or user and user.has_perm(
                                                        l4_available_option.permission_name):
                                                    if l4_available_option.two_factor and not user.is_verified():
                                                        continue
                                                    l4_menu.options.append(l4_available_option)
                                            if not l4_menu.linkable:
                                                if len(l4_menu.options) == 0:
                                                    continue
                                                elif len(l4_menu.options) == 1:
                                                    l4_menu = l4_menu.options[0]
                                                    l4_menu.level_shift += 1
                                                else:
                                                    l4_menu.url = l4_menu.options[0].url
                                            l3_menu.options.append(l4_menu)
                                    if not l3_menu.linkable:
                                        if len(l3_menu.options) == 0:
                                            continue
                                        elif len(l3_menu.options) == 1:
                                            l3_menu = l3_menu.options[0]
                                            l3_menu.level_shift += 1
                                        else:
                                            l3_menu.url = l3_menu.options[0].url
                                    l2_menu.options.append(l3_menu)
                            if not l2_menu.linkable:
                                if len(l2_menu.options) == 0:
                                    continue
                                elif len(l2_menu.options) == 1:
                                    l2_menu = l2_menu.options[0]
                                    l2_menu.level_shift += 1
                                else:
                                    l2_menu.url = l2_menu.options[0].url
                            l1_menu.options.append(l2_menu)
                    if not l1_menu.linkable:
                        if len(l1_menu.options) == 0:
                            continue
                        elif len(l1_menu.options) == 1:
                            l1_menu = l1_menu.options[0]
                            l1_menu.level_shift += 1
                        else:
                            l1_menu.url = l1_menu.options[0].url
                    self.options.append(l1_menu)
        except Exception as error:
            print(f"{self.name}-{self.parent}-{self.linkable}")
            print(f"Unexpected error occurred: {error}")

    @classmethod
    def open_menu(cls, url='/'):
        menu = SysMenu.objects.get(name='mendev')
        menu.prepare(url=url, user=None)
        return menu

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if user and not self.pk:
            self.created_by = user.username
        if user and self.pk:
            self.modified_by = user.username
        super(SysMenu, self).save(*args, **kwargs)

    class Meta:
        ordering = ['sequence']
        permissions = [
            ("see_system_menu", "Can see System menu"),
        ]
        verbose_name = 'Menu'
        managed = False
        db_table = 'sys_menu'


class SysSetting(models.Model):
    key = models.CharField(max_length=255)
    value = models.TextField(null=True, blank=True)
    description = models.TextField(max_length=1000, blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    created_dt = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, default='cxx')
    modified_dt = models.DateTimeField(auto_now=True, null=True)
    modified_by = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        if self.parent:
            parent = self.parent.key + ': '
        else:
            parent = ''
        return f"{parent}{self.key}{': ' if self.value else ''}{self.value}"

    def settings(self):

        if self.value:
            return {self.key: self.value}
        else:
            values = {}
            for setting in self.objects.syssetting_set.all():
                values[setting.key] = setting.cfg()
            return {self.key: values}

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if user and not self.pk:
            self.created_by = user.username
        if user and self.pk:
            self.modified_by = user.username
        super(SysSetting, self).save(*args, **kwargs)

    class Meta:
        managed = False
        db_table = 'sys_settings'
        verbose_name = 'Setting'


class SysSubsystem(models.Model):
    name = models.CharField(max_length=25)
    processor = models.IntegerField()
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(editable=False, blank=True, null=True)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if user and not self.pk:
            self.created_by = user.username
        if user and self.pk:
            self.modified_by = user.username
        super(SysSubsystem, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

    def tasks_count(self, statuses=None):

        with connection.cursor() as cursor:
            query = """
                select count(*) as tasks_count
                from cxx.sys_tasks t
                join cxx.sys_task_types tt
                  on tt.id = t.task_type_id
                where tt.subsystem_id = %s
            """
            if statuses:
                query += f" and t.status in ({list_to_sql_string(statuses)})"
            cursor.execute(query, (self.id,))
            r = cursor.fetchone()
            if r:
                return r[0]

    class Meta:
        managed = False
        db_table = 'sys_subsystems'


class SysTaskType(models.Model):
    name = models.CharField(max_length=25)
    module = models.CharField(max_length=100)
    function = models.CharField(max_length=100)
    subsystem = models.ForeignKey(SysSubsystem, models.DO_NOTHING)
    allow_multiple = models.BooleanField()
    timeout_seconds = models.IntegerField(blank=True, null=True)
    notification_statuses = models.CharField(max_length=200, null=True, blank=True, help_text="Use commas to seperate the values")
    notify_requester = models.BooleanField(default=True)
    notify_by_mail = models.BooleanField(default=False)
    selectable = models.BooleanField(default=True)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if user and not self.pk:
            self.created_by = user.username
        if user and self.pk:
            self.modified_by = user.username
        super(SysTaskType, self).save(*args, **kwargs)

    def args(self):
        return SysTaskTypeArg.objects.filter(task_type=self).order_by('sequence')

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'sys_task_types'


class SysTaskTypeExclusion(models.Model):
    task_type = models.ForeignKey(SysTaskType, on_delete=models.CASCADE)
    excluded_task_type = models.ForeignKey(SysTaskType, related_name='excluded_task_type', on_delete=models.CASCADE)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'sys_task_types'


class SysTaskTypeArg(models.Model):
    task_type = models.ForeignKey('SysTaskType', models.CASCADE)
    sequence = models.IntegerField()
    name = models.CharField(max_length=50)
    label = models.CharField(max_length=50, null=True, blank=True)
    type = models.CharField(max_length=25)
    mandatory = models.BooleanField(default=False)
    default = models.CharField(max_length=100, null=True, blank=True)
    select_table = models.CharField(max_length=50, null=True, blank=True)
    select_column = models.CharField(max_length=50, null=True, blank=True)
    display_column = models.CharField(max_length=50, null=True, blank=True)
    select_filter = models.CharField(max_length=1000, null=True, blank=True)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if user and not self.pk:
            self.created_by = user.username
        if user and self.pk:
            self.modified_by = user.username
        super(SysTaskTypeArg, self).save(*args, **kwargs)

    class Meta:
        managed = False
        db_table = 'sys_task_type_args'
        unique_together = (('task_type', 'name'), ('task_type', 'sequence'),)


class SysTaskSchedule(models.Model):
    task_type = models.ForeignKey(SysTaskType, models.DO_NOTHING)
    name = models.CharField(max_length=25)
    kwargs = models.TextField(blank=True, null=True, default='\{\}')
    datetime_start = models.DateTimeField()
    datetime_expiration = models.DateTimeField(blank=True, null=True)
    datetime_next = models.DateTimeField(blank=True, null=True)
    frequency = models.CharField(max_length=25, blank=True, null=True)
    frequency_interval = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=25)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if user and not self.pk:
            self.created_by = user.username
        if user and self.pk:
            self.modified_by = user.username
        super(SysTaskSchedule, self).save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} {self.frequency} {self.frequency_interval}'

    def record_info(self):
        record_info = {
            'header': _('Record information'),
            'rows': {
                _('Table'): self._meta.db_table,
                _('Record ID'): self.pk,
            }
        }
        if self.created_dt:
            record_info['rows'][_('Created at')] = self.created_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Created by')] = self.created_by
        if self.modified_dt:
            record_info['rows'][_('Modified at')] = self.modified_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Modified by')] = self.modified_by
        return json.dumps(record_info)

    def kwargs_dict(self):
        try:
            return json.loads(self.kwargs)
        except:
            return {}

    def full_args(self):
        try:
            full_args = {}
            args = self.task_type.args()
            kwargs_dict = self.kwargs_dict()
            for arg in args:
                full_args[arg.name] = {
                    'label': arg.label if arg.label else arg.name,
                    'default': arg.default,
                    'type': arg.type,
                    'html_type': arg.html_type,
                    'mandatory': arg.mandatory,
                    'select_values': []
                }
                if arg.name in kwargs_dict:
                    full_args[arg.name]['value'] = kwargs_dict[arg.name]
                else:
                    full_args[arg.name]['value'] = None
                if arg.select_table and arg.select_column:
                    try:
                        with connection.cursor() as cursor:
                            if arg.select_values:
                                values = arg.select_values.split(',')
                                if arg.select_column not in values:
                                    select_values = [arg.select_column] + values
                                else:
                                    select_values = values
                                select_string = ','.join(select_values)
                            else:
                                values = [arg.select_column ]
                                select_string = arg.select_column
                            if arg.select_order:
                                select_order = arg.select_order
                            else:
                                select_order = arg.select_column
                            query = f"select distinct {select_string} from cxx.{arg.select_table}"
                            if arg.select_filter:
                                query += f" where {arg.select_filter}"
                            query += f" order by {select_order}"
                            cursor.execute(query)
                            for r in cursor.fetchall():
                                display_values = []
                                if arg.select_column not in values:
                                    start = 1
                                else:
                                    start = 0
                                for i in range(start, len(values)):
                                    display_values.append(str(r[i]))
                                value = ' '.join(display_values)
                                full_args[arg.name]['select_values'].append(
                                    {
                                        'code': str(r[0]),
                                        'value': value
                                    }
                                )
                    except:
                        pass
                elif arg.select_values:
                    try:
                        values = arg.select_values.split(',')
                        for value in values:
                            full_args[arg.name]['select_values'].append(
                                {
                                    'code': value,
                                    'value': value
                                }
                            )
                    except:
                        pass

            return full_args
        except:
            return None

    def active_tasks(self):
        return self.systask_set.filter(status='running')

    class Meta:
        managed = False
        db_table = 'sys_task_schedules'


class SysTask(models.Model):
    task_type = models.ForeignKey(SysTaskType, models.DO_NOTHING)
    task_schedule = models.ForeignKey(SysTaskSchedule, models.DO_NOTHING, blank=True, null=True)
    name = models.CharField(max_length=25)
    kwargs = models.TextField(blank=True, null=True)
    requesting_user = models.CharField(max_length=50)
    datetime_started = models.DateTimeField(blank=True, null=True)
    datetime_ended = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=25)
    result = models.TextField(blank=True, null=True)
    control = models.CharField(max_length=25, blank=True, null=True)
    pid = models.IntegerField(null=True, blank=True)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if user and not self.pk:
            self.created_by = user.username
        if user and self.pk:
            self.modified_by = user.username
        super(SysTask, self).save(*args, **kwargs)

    def validate_submit(self):
        error_messages = []
        if not self.name:
            error_messages.append(
                {
                    'item': 'name',
                    'message': _("Name is mandatory")
                }
            )
        if not self.task_type:
            error_messages.append(
                {
                    'item': 'task_type',
                    'message': _("Task type is mandatory")
                }
            )
        else:
            args = self.full_args()
            kwargs = self.kwargs_dict()
            for key, arg in args.items():
                if arg['mandatory'] and (key not in kwargs or not kwargs[key]):
                    error_messages.append(
                        {
                            'item': key,
                            'message': f"{arg['label']} {_('is mandatory')}"
                        }
                    )
        return error_messages

    def __str__(self):
        return self.name

    def record_info(self):
        record_info = {
            'header': _('Record information'),
            'rows': {
                _('Table'): self._meta.db_table,
                _('Record ID'): self.pk,
            }
        }
        if self.created_dt:
            record_info['rows'][_('Created at')] = self.created_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Created by')] = self.created_by
        if self.modified_dt:
            record_info['rows'][_('Modified at')] = self.modified_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Modified by')] = self.modified_by
        return json.dumps(record_info)

    def kwargs_dict(self):
        try:
            return json.loads(self.kwargs)
        except:
            return {}

    def full_args(self):
        try:
            full_args = {}
            args = self.task_type.args()
            kwargs_dict = self.kwargs_dict()
            for arg in args:
                full_args[arg.name] = {
                    'label': arg.label if arg.label else arg.name,
                    'default': arg.default,
                    'type': arg.type,
                    'html_type': arg.html_type,
                    'mandatory': arg.mandatory,
                    'select_values': []
                }
                if arg.name in kwargs_dict:
                    full_args[arg.name]['value'] = kwargs_dict[arg.name]
                else:
                    full_args[arg.name]['value'] = None
                if arg.select_table and arg.select_column:
                    try:
                        with connection.cursor() as cursor:
                            if arg.select_values:
                                values = arg.select_values.split(',')
                                if arg.select_column not in values:
                                    select_values = [arg.select_column] + values
                                else:
                                    select_values = values
                                select_string = ','.join(select_values)
                            else:
                                values = [arg.select_column ]
                                select_string = arg.select_column
                            if arg.select_order:
                                select_order = arg.select_order
                            else:
                                select_order = arg.select_column
                            query = f"select distinct {select_string} from cxx.{arg.select_table}"
                            if arg.select_filter:
                                query += f" where {arg.select_filter}"
                            query += f" order by {select_order}"
                            cursor.execute(query)
                            for r in cursor.fetchall():
                                display_values = []
                                if arg.select_column not in values:
                                    start = 1
                                else:
                                    start = 0
                                for i in range(start, len(values)):
                                    display_values.append(str(r[i]))
                                value = ' '.join(display_values)
                                full_args[arg.name]['select_values'].append(
                                    {
                                        'code': str(r[0]),
                                        'value': value
                                    }
                                )
                    except Exception as error:
                        print(error)
                elif arg.select_values:
                    try:
                        values = arg.select_values.split(',')
                        for value in values:
                            full_args[arg.name]['select_values'].append(
                                {
                                    'code': value,
                                    'value': value
                                }
                            )
                    except:
                        pass

            return full_args
        except:
            return None

    class Meta:
        managed = False
        db_table = 'sys_tasks'


class SysNotification(models.Model):
    subject = models.CharField(max_length=200)
    content = models.TextField(blank=True, null=True)
    task = models.ForeignKey(SysTask, on_delete=models.DO_NOTHING, blank=True, null=True)
    type = models.CharField(max_length=25, blank=True, null=True)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def record_info(self):
        record_info = {
            'header': _('Record information'),
            'rows': {
                _('Table'): self._meta.db_table,
                _('Record ID'): self.pk,
            }
        }
        if self.created_dt:
            record_info['rows'][_('Created at')] = self.created_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Created by')] = self.created_by
        if self.modified_dt:
            record_info['rows'][_('Modified at')] = self.modified_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Modified by')] = self.modified_by
        return json.dumps(record_info)

    class Meta:
        managed = False
        db_table = 'sys_notifications'


class SysUserNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notification = models.ForeignKey(SysNotification, on_delete=models.CASCADE)
    shown_datetime = models.DateTimeField(blank=True, null=True, editable=False)
    mailed_datetime = models.DateTimeField(blank=True, null=True, editable=False)
    archived = models.BooleanField(default=False)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def record_info(self):
        record_info = {
            'header': _('Record information'),
            'rows': {
                _('Table'): self._meta.db_table,
                _('Record ID'): self.pk,
            }
        }
        if self.created_dt:
            record_info['rows'][_('Created at')] = self.created_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Created by')] = self.created_by
        if self.modified_dt:
            record_info['rows'][_('Modified at')] = self.modified_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Modified by')] = self.modified_by
        return json.dumps(record_info)

    class Meta:
        managed = False
        db_table = 'sys_user_notifications'


class SysNotifiedUser(models.Model):
    task_type = models.ForeignKey(SysTaskType, on_delete=models.DO_NOTHING, blank=True, null=True)
    scope = models.CharField(max_length=50, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    notify_by_mail = models.BooleanField(default=False, blank=True, null=True)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    @property
    def username(self):
        try:
            return self.user.username
        except:
            return None

    def record_info(self):
        record_info = {
            'header': _('Record information'),
            'rows': {
                _('Table'): self._meta.db_table,
                _('Record ID'): self.pk,
            }
        }
        if self.created_dt:
            record_info['rows'][_('Created at')] = self.created_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Created by')] = self.created_by
        if self.modified_dt:
            record_info['rows'][_('Modified at')] = self.modified_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Modified by')] = self.modified_by
        return json.dumps(record_info)

    class Meta:
        managed = False
        db_table = 'sys_notified_users'


class SysLogging(models.Model):
    module = models.CharField(max_length=255)
    level = models.CharField(max_length=55)
    message = models.TextField()
    trace = models.TextField(blank=True, null=True)
    task = models.ForeignKey(SysTask, on_delete=models.DO_NOTHING, blank=True, null=True)
    category = models.CharField(max_length=25)
    scope = models.CharField(max_length=50)
    created_dt = models.DateTimeField(editable=False)
    created_by = models.CharField(max_length=50, default='cxx', editable=False)
    modified_dt = models.DateTimeField(blank=True, null=True, editable=False)
    modified_by = models.CharField(max_length=50, blank=True, null=True, editable=False)

    def record_info(self):
        record_info = {
            'header': _('Record information'),
            'rows': {
                _('Table'): self._meta.db_table,
                _('Record ID'): self.pk,
            }
        }
        if self.trace:
            record_info['rows'][_('Trace')] = self.trace
        if self.created_dt:
            record_info['rows'][_('Created at')] = self.created_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Created by')] = self.created_by
        if self.modified_dt:
            record_info['rows'][_('Modified at')] = self.modified_dt.strftime('%Y-%m-%d %H:%M:%S')
            record_info['rows'][_('Modified by')] = self.modified_by
        return json.dumps(record_info)

    class Meta:
        managed = False
        db_table = 'sys_logging'

