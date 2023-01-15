import json
from datetime import datetime, timedelta

from _socket import gethostname
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

from .forms import UserUpdateForm, ProfileUpdateForm
from .models import SysMenu, SysProfile, SysSetting, SysSubsystem, SysTaskType, SysTask
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.utils.translation import gettext as _
from django.shortcuts import render, redirect, get_object_or_404
from django.views import generic
from django.conf import settings as system_settings
import requests


@login_required()
def profile(request):

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, f'Your profile is updated!')
            response = redirect('system:profile')
            response.set_cookie(key='django_language', value=request.user.profile.language)
            return response

    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)

    if 'permitted_menu' not in request.session:
        request.session['permitted_menu'] = None
    main_menu = SysMenu.objects.get(name='MAIN')
    main_menu.prepare(request.path, request.user, request.session['permitted_menu'])
    context = {
        'main_menu': main_menu,
        'version': system_settings.VERSION,
        'user_form': user_form,
        'profile_form': profile_form,
        'title': 'Profile'
    }

    response = render(request, 'system/profile.html', context)
    response.set_cookie(key='django_language', value=request.user.profile.language)
    return response

def index(request):
    if 'permitted_menu' not in request.session:
        request.session['permitted_menu'] = None
    main_menu = SysMenu.objects.get(name='MAIN')
    main_menu.prepare(request.path, request.user, request.session['permitted_menu'])
    context = {
        'main_menu': main_menu,
        'version': system_settings.VERSION,
        'title': 'Home',
    }
    response = render(request, 'system/index.html', context)
    if not request.user.is_anonymous:
        try:
            response.set_cookie(key='django_language', value=request.user.profile.language)
        except:
            pass
    return response

def script(request):

    result = None
    script = 'return_value = "OK"'
    if 'script' in request.POST:
        script = request.POST['script']
    if 'confirmed' in request.POST and request.POST['confirmed'] == 'execute' and request.user.is_verified():
        try:
            script = request.POST['script']
            local_dict = locals()
            exec(script, globals(), local_dict)
            if 'return_value' in local_dict:
                result = local_dict['return_value']
        except Exception as error:
            messages.error(request, f"{error}")

    if 'permitted_menu' not in request.session:
        request.session['permitted_menu'] = None
    main_menu = SysMenu.objects.get(name='MAIN')
    main_menu.prepare(request.path, request.user, request.session['permitted_menu'])
    context = {
        'main_menu': main_menu,
        'title': 'Execute Script',
        'version': system_settings.VERSION,
        'script': script,
        'result': result
    }
    response = render(request, 'ttti/script.html', context)
    return response


@user_passes_test(lambda u: u.is_superuser)
def systeminfo(request):

    if 'api_key' not in request.session:
        settings = SysSetting.objects.get(key='gui', parent__isnull=True).settings()
        request.session['api_key'] = settings['api']['api_key']
        request.session['api_url'] = settings['api']['api_url']

    subsystems = []
    sys_subsystems = SysSubsystem.objects.all()
    for sys_subsystem in sys_subsystems:
        subsystem = {
            'name': sys_subsystem.name
        }
        if sys_subsystem.processor == 99:    # For local testing purposes
            url = f"http://127.0.0.1:8080//system/status"
        else:
            if sys_subsystem.processor == 1:
                url = f"{request.session['api_url']}/system/status/request"
            else:
                url = f"{request.session['api_url']}{sys_subsystem.processor}/system/status/request"
        try:
            r = requests.get(
                url=url,
                headers={
                    'Content-Type': 'application/json; charset=utf-8',
                    'x-api-key': request.session['api_key']
                }
            )
            r.raise_for_status()
        except Exception as error:
            subsystem['status'] = _('inactive')
            subsystem['error'] = f"Error connecting to '{url}', error: {error}"
        else:
            try:
                response = json.loads(r.text)
            except Exception as error:
                subsystem['status'] = error
            else:
                if 'errors' in response:
                    subsystem['status'] = response['errors'][0]
                else:
                    subsystem['active'] = True
                    subsystem['active_tasks_count'] = sys_subsystem.tasks_count(
                        ['running', 'waiting', 'started', 'submitted']
                    )
                    status = response['data']['status']
                    subsystem['status'] = _('active since ') + status['start_datetime']
                    subsystem['csx'] = status['csx']
                    subsystem['rbsrov'] = status['rbsrov']
                    subsystem['ttti_version'] = status['ttti_version']
                    subsystem['cpu_percentages'] = status['cpu_percentages']
                    subsystem['memory_total'] = round(status['virtual_memory']['total'] / 1024 / 1024)
                    subsystem['memory_used'] = round(status['virtual_memory']['used'] / 1024 / 1024)
                    subsystem['memory_percentage'] = status['virtual_memory']['percent']
                    subsystem['swap_memory_total'] = round(status['swap_memory']['total'] / 1024 / 1024)
                    subsystem['swap_memory_used'] = round(status['swap_memory']['used'] / 1024 / 1024)
                    subsystem['swap_memory_percentage'] = status['swap_memory']['percent']
        subsystems.append(subsystem)

    if 'permitted_menu' not in request.session:
        request.session['permitted_menu'] = None
    main_menu = SysMenu.objects.get(name='MAIN')
    main_menu.prepare(request.path, request.user, request.session['permitted_menu'])
    context = {
        'main_menu': main_menu,
        'title': 'System Information',
        'version': system_settings.VERSION,
        'application_server': gethostname(),
        'ttti_server': system_settings.DATABASES['default']['HOST'],
        'csx_server': system_settings.DATABASES['csx']['HOST'],
        'csx_database': system_settings.DATABASES['csx']['NAME'],
        'kv17_server': system_settings.DATABASES['kv17']['HOST'],
        'kv17_database': system_settings.DATABASES['kv17']['NAME'],
        'subsystems': subsystems
    }
    response = render(request, 'system/systeminfo.html', context)
    if not request.user.is_anonymous:
        try:
            response.set_cookie(key='django_language', value=request.user.profile.language)
        except:
            pass
    return response


@login_required()
@permission_required('system.view_task', raise_exception=True)
def tasks(request):
    if 'from_datetime' in request.POST:
        request.session['from_datetime_task'] = request.POST['from_datetime']
        if request.session['from_datetime_task'].count(':') == 1:
            request.session['from_datetime_task'] += ':00'
    if 'from_datetime_task' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['from_datetime_task'] = timezone.now().strftime('%Y-%m-%dT00:00:00')
    if 'to_datetime' in request.POST:
        request.session['to_datetime_task'] = request.POST['to_datetime']
        if request.session['to_datetime_task'].count(':') == 1:
            request.session['to_datetime_task'] += ':00'
    if 'to_datetime_task' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['to_datetime_task'] = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT00:00:00')

    if 'task_type_filter' in request.POST:
        request.session['task_type_filter'] = request.POST['task_type_filter']
    if 'task_type_filter' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['task_type_filter'] = ''

    if 'requesting_user_filter' in request.POST:
        request.session['requesting_user_filter'] = request.POST['requesting_user_filter']
    if 'requesting_user_filter' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['requesting_user_filter'] = ''

    if 'task_status_filter' in request.POST:
        request.session['task_status_filter'] = request.POST['task_status_filter']
    if 'task_status_filter' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['task_status_filter'] = ''
    if 'task_order_by_list' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['task_order_by_list'] = ['-id', 'task_type__name', 'status']
    if 'order_by' in request.POST:
        request.session['task_order_by_list'] = order_by_add(
            request.session['task_order_by_list'],
            request.POST['order_by']
        )

    q_filter = Q()
    if request.session['from_datetime_task']:
        q_filter &= Q(
            Q(
                created_dt__gte=timezone.make_aware(
                    datetime.strptime(request.session['from_datetime_task'], '%Y-%m-%dT%H:%M:%S')
                )
            ) | Q(
                status__in=['running', 'waiting', 'started', 'submitted']
            )
        )
    if request.session['to_datetime_task']:
        q_filter &= Q(created_dt__lt=timezone.make_aware(
            datetime.strptime(request.session['to_datetime_task'], '%Y-%m-%dT%H:%M:%S')
        ))

    if request.session['task_type_filter'] != '':
        try:
            selected_type = SysTaskType.objects.get(pk=request.session['task_type_filter'])
            q_filter &= Q(task_type=selected_type)
        except ObjectDoesNotExist:
            pass
    if request.session['task_status_filter'] != '':
        q_filter &= Q(status=request.session['task_status_filter'])
    if request.session['requesting_user_filter'] != '':
        q_filter &= Q(requesting_user__icontains=request.session['requesting_user_filter'])
    tasks = \
        SysTask.objects.filter(q_filter).\
            order_by(request.session['task_order_by_list'][0],
                     request.session['task_order_by_list'][1],
                     request.session['task_order_by_list'][2]
                     )

    task_type_filter_options = []
    task_type_tasks = tasks.distinct('task_type__name').order_by('task_type__name')
    for type_task in task_type_tasks:
        option = {
            'id': type_task.task_type.id,
            'name': type_task.task_type.name,
            'selected': 'selected' if str(type_task.task_type.id) == request.session['task_type_filter'] else ''
        }
        task_type_filter_options.append(option)

    status_filter_options = []
    statuses = tasks.distinct('status').order_by('status')
    for status in statuses:
        option = {
            'status': status.status,
            'selected': 'selected' if status.status == request.session['task_status_filter'] else ''
        }
        status_filter_options.append(option)

    if 'window_innerheight' in request.COOKIES:
        innerheight = request.COOKIES['window_innerheight']
        if int(innerheight) < 300:
            innerheight = 300
    else:
        innerheight = 800
    availableheight = int(innerheight) - 300
    page_lines = availableheight // int(33)
    if page_lines < 1:
        page_lines = 1
    paginator = Paginator(tasks, page_lines)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    if 'permitted_menu' not in request.session:
        request.session['permitted_menu'] = None
    main_menu = SysMenu.objects.get(name='MAIN')
    main_menu.prepare(request.path, request.user, request.session['permitted_menu'])
    context = {
        'main_menu': main_menu,
        'from_datetime': timezone.make_aware(
            datetime.strptime(request.session['from_datetime_task'], '%Y-%m-%dT%H:%M:%S')
                              ) if request.session['from_datetime_task'] else None,
        'to_datetime': timezone.make_aware(
            datetime.strptime(request.session['to_datetime_task'], '%Y-%m-%dT%H:%M:%S')
                              ) if request.session['to_datetime_task'] else None,
        'task_type_filter_options': task_type_filter_options,
        'status_filter_options': status_filter_options,
        'requesting_user_filter': request.session['requesting_user_filter'],
        'page_obj': page_obj,
        'title': 'Tasks',
        'version': system_settings.VERSION,
    }
    response = render(request, 'system/tasks.html', context)
    return response

@login_required()
@permission_required('system.add_task', raise_exception=True)
def task_new(request, copy_task_id=None):

    error_items = {}
    task = None
    if request.method == 'GET':

        if copy_task_id:
            try:
                copy_task = SysTask.objects.get(pk=copy_task_id)
                task = SysTask()
                task.name = copy_task.name
                task.task_type = copy_task.task_type
                task.kwargs = copy_task.kwargs
            except:
                pass
    if not task:
        task = SysTask()
        task.task_type = SysTaskType()

    if request.method == 'POST':

        if 'name' in request.POST:
            task.name = request.POST['name']
        if 'task_type_id' in request.POST:
            task.task_type = SysTaskType.objects.get(pk=request.POST['task_type_id'])

        kwargs = {}
        args = task.full_args()
        for key, arg in args.items():
            if arg['html_type'] == 'radio':
                if 'arg_' + key in request.POST and request.POST['arg_' + key]:
                    kwargs[key] = request.POST['arg_' + key]
                else:
                    kwargs[key] = None
            elif arg['html_type'] == 'checkbox':
                if 'arg_' + key in request.POST:
                    kwargs[key] = True
                else:
                    kwargs[key] = False
            else:
                if 'arg_' + key in request.POST:
                    kwargs[key] = request.POST['arg_' + key]
        task.kwargs = json.dumps(kwargs)

    if 'confirmed' in request.POST and request.POST['confirmed'] == 'submit':
        error_messages = task.validate_submit()
        if not error_messages:
            task.requesting_user = request.user.username
            task.status = 'submitted'
            task.save()
            messages.info(request, _('Task is submitted'))
            return redirect('ttti:task', task.id)
        else:
            for error_message in error_messages:
                error_items[error_message['item']] = 'error'
                messages.error(request, error_message['message'])

    task_types = SysTaskType.objects.filter(selectable=True)
    task_type_options = []

    if not task.task_type.id:
        task_type_options.append({
            'id': None,
            'name': None,
            'selected': 'selected'
        })
    for task_type in task_types:
        task_type_options.append({
            'id': task_type.id,
            'name': task_type.name,
            'selected': 'selected' if task_type.id == task.task_type.id else ''
        })

    if 'permitted_menu' not in request.session:
        request.session['permitted_menu'] = None
    main_menu = SysMenu.objects.get(name='MAIN')
    main_menu.prepare(request.path, request.user, request.session['permitted_menu'])
    context = {
        'task': task,
        'task_type_options': task_type_options,
        'error_items': error_items,
        'main_menu': main_menu,
        'title': 'Task',
        'version': system_settings.VERSION,
    }
    response = render(request, 'system/task_new.html', context)
    return response

@login_required()
def notification_status(request):

    try:
        number_unshown = TttiUserNotification.objects.filter(user=request.user, shown_datetime__isnull=True).count()
        alert_notifications = TttiUserNotification.objects.filter(user=request.user, notification__type='alert', shown_datetime__isnull=True)
        alert = None
        for user_notification in alert_notifications:
            alert = {
                'user_notification_id': user_notification.id,
                'subject': user_notification.notification.subject,
                'content': user_notification.notification.content
            }
            break  # Only one alert per time

        status = {
            'number_unshown': number_unshown,
            'alert': alert
        }
    except:
        return HttpResponse(status=500)

    return HttpResponse(content=json.dumps(status))

@login_required()
def archive_notification(request, user_notification_id):

    try:
        user_notification = TttiUserNotification.objects.get(pk=user_notification_id)
        user_notification.archived = True
        user_notification.save()
    except:
        return HttpResponse(status=500)

    return HttpResponse(content='Notification hidden')

@login_required()
def shown_notification(request, user_notification_id):

    try:
        user_notification = TttiUserNotification.objects.get(pk=user_notification_id)
        user_notification.shown_datetime = timezone.now()
        user_notification.save()
    except:
        return HttpResponse(status=500)

    return HttpResponse(content='Notification set to shown')

@login_required()
def archive_notifications(request, from_datetime, to_datetime):

    try:
        user_notifications = TttiUserNotification.objects.filter(
            user=request.user,
            archived=False,
            created_dt__gte=timezone.make_aware(datetime.strptime(from_datetime, '%Y-%m-%dT%H:%M:%S')),
            created_dt__lte=timezone.make_aware(datetime.strptime(to_datetime, '%Y-%m-%dT%H:%M:%S'))
        )
        for user_notification in user_notifications:
            user_notification.archived = True
            user_notification.save()
    except:
        return HttpResponse(status=500)

    return HttpResponse(content='Notifications archived')

@login_required()
def unarchive_notifications(request, from_datetime, to_datetime):

    try:
        user_notifications = TttiUserNotification.objects.filter(
            user=request.user,
            archived=True,
            created_dt__gte=timezone.make_aware(datetime.strptime(from_datetime, '%Y-%m-%dT%H:%M:%S')),
            created_dt__lte=timezone.make_aware(datetime.strptime(to_datetime, '%Y-%m-%dT%H:%M:%S'))
        )
        for user_notification in user_notifications:
            user_notification.archived = False
            user_notification.save()
    except:
        return HttpResponse(status=500)

    return HttpResponse(content='Notifications restored')

@login_required()
def notifications(request):

    if 'from_datetime' in request.POST:
        request.session['from_datetime_notification'] = request.POST['from_datetime']
        if request.session['from_datetime_notification'].count(':') == 1:
            request.session['from_datetime_notification'] += ':00'
    if 'from_datetime_notification' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['from_datetime_notification'] = timezone.now().strftime('%Y-%m-%dT00:00:00')
    if 'to_datetime' in request.POST:
        request.session['to_datetime_notification'] = request.POST['to_datetime']
        if request.session['to_datetime_notification'].count(':') == 1:
            request.session['to_datetime_notification'] += ':00'
    if 'to_datetime_notification' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['to_datetime_notification'] = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT00:00:00')

    if 'notification_order_by_list' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['notification_order_by_list'] = ['-created_dt', 'notification__subject']
    if 'order_by' in request.POST:
        request.session['notification_order_by_list'] = order_by_add(
            request.session['notification_order_by_list'],
            request.POST['order_by']
        )

    q_list = [
        Q(created_dt__gte=timezone.make_aware(
            datetime.strptime(request.session['from_datetime_notification'], '%Y-%m-%dT%H:%M:%S')
        )) | Q(shown_datetime=None),
        Q(created_dt__lte=timezone.make_aware(
            datetime.strptime(request.session['to_datetime_notification'], '%Y-%m-%dT%H:%M:%S')
        )),
        Q(user=request.user),
        Q(archived=False)
    ]
    user_notifications = \
        TttiUserNotification.objects.filter(reduce(operator.and_, q_list)).\
            order_by(request.session['notification_order_by_list'][0],
                     request.session['notification_order_by_list'][1]
                     )

    if 'window_innerheight' in request.COOKIES:
        innerheight = request.COOKIES['window_innerheight']
        if int(innerheight) < 300:
            innerheight = 300
    else:
        innerheight = 800
    availableheight = int(innerheight) - 300
    page_lines = availableheight // int(33)
    if page_lines < 1:
        page_lines = 1
    paginator = Paginator(user_notifications, page_lines)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    if 'permitted_menu' not in request.session:
        request.session['permitted_menu'] = None
    main_menu = Menu.objects.get(name='TTTI')
    main_menu.prepare(request.path, request.user, request.session['permitted_menu'])
    context = {
        'main_menu': main_menu,
        'from_datetime': timezone.make_aware(datetime.strptime(request.session['from_datetime_notification'],
                        '%Y-%m-%dT%H:%M:%S')) if request.session['from_datetime_notification'] else None,
        'to_datetime': timezone.make_aware(datetime.strptime(request.session['to_datetime_notification'],
                         '%Y-%m-%dT%H:%M:%S')) if request.session['to_datetime_notification'] else None,
        'page_obj': page_obj,
        'title': 'Notifications',
        'version': system_settings.VERSION,
    }
    response = render(request, 'ttti/notifications.html', context)
    return response

@login_required()
def notification(request, notification_id):

    try:
        notification = TttiNotification.objects.get(pk=notification_id)
    except:
        notification = None

    if notification:
        if 'archive' in request.POST:
            try:
                user_notification = TttiUserNotification.objects.get(user=request.user, notification=notification)
                user_notification.archived = True
                user_notification.save()
            except ObjectDoesNotExist:
                pass
            except MultipleObjectsReturned:
                user_notifications = TttiUserNotification.objects.filter(user=request.user, notification=notification)
                for user_notification in user_notifications:
                    user_notification.archived = True
                    user_notification.save()
            return redirect('ttti:notifications')

    if 'permitted_menu' not in request.session:
        request.session['permitted_menu'] = None
    main_menu = Menu.objects.get(name='TTTI')
    main_menu.prepare(request.path, request.user, request.session['permitted_menu'])
    context = {
        'notification': notification,
        'main_menu': main_menu,
        'title': 'Notification',
        'version': system_settings.VERSION,
    }
    response = render(request, 'ttti/notification.html', context)
    return response

@login_required()
@permission_required('ttti.view_task', raise_exception=True)
def task(request, task_id):


    try:
        task = TttiTask.objects.get(pk=task_id)
    except:
        task = None

    if 'confirmed' in request.POST and request.POST['confirmed'] == 'abort' and request.user.is_verified():
        task.control = 'abort'
        task.save()
        messages.info(request, 'Abort request is sent. Refresh page for the current status.')

    if 'duplicate' in request.POST and request.user.is_verified():
        return redirect('ttti:task_copy', task.id)

    active_tab = None

    # Notifications
    if 'task_notification_order_by_list' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['task_notification_order_by_list'] = ['-created_dt', 'subject']
    if 'notification_order_by' in request.POST:
        active_tab = 'notifications'
        request.session['task_notification_order_by_list'] = order_by_add(
            request.session['task_notification_order_by_list'],
            request.POST['notification_order_by']
        )

    notifications = \
        TttiNotification.objects.filter(task__id=task_id).\
            order_by(request.session['task_notification_order_by_list'][0],
                     request.session['task_notification_order_by_list'][1]
                     )

    # Logging
    if 'from_datetime' in request.POST:
        request.session['from_datetime_task_' + task_id] = request.POST['from_datetime']
        if request.session['from_datetime_task_' + task_id].count(':') == 1:
            request.session['from_datetime_task_' + task_id] += ':00'
        active_tab = 'logging'
    if 'from_datetime_task_' + task_id not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['from_datetime_task_' + task_id] = None
    if 'to_datetime' in request.POST:
        request.session['to_datetime_task_' + task_id] = request.POST['to_datetime']
        if request.session['to_datetime_task_' + task_id].count(':') == 1:
            request.session['to_datetime_task_' + task_id] += ':00'
        active_tab = 'logging'
    if 'to_datetime_task_' + task_id not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['to_datetime_task_' + task_id] = None
    if task.datetime_started and not request.session['from_datetime_task_' + task_id]:
        request.session['from_datetime_task_' + task_id] = (task.datetime_started.astimezone(
            pytz.timezone(system_settings.TIME_ZONE)) - timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%S')
    if task.datetime_ended and not request.session['to_datetime_task_' + task_id]:
        request.session['to_datetime_task_' + task_id] = (task.datetime_ended.astimezone(
            pytz.timezone(system_settings.TIME_ZONE)) + timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%S')

    if 'message_filter' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['message_filter'] = ''
    if 'message_filter' in request.POST and request.session['message_filter'] != request.POST['message_filter']:
        request.session['message_filter'] = request.POST['message_filter']
        active_tab = 'logging'
    if 'level_filter' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['level_filter'] = ''
    if 'level_filter' in request.POST and request.session['level_filter'] != request.POST['level_filter']:
        request.session['level_filter'] = request.POST['level_filter']
        active_tab = 'logging'

    if 'logging_order_by_list' not in request.session or (request.method == 'GET' and 'init' in request.GET):
        request.session['logging_order_by_list'] = ['-created_dt', 'message', 'level']
    if 'logging_order_by' in request.POST:
        request.session['logging_order_by_list'] = order_by_add(
            request.session['logging_order_by_list'],
            request.POST['logging_order_by']
        )
        active_tab = 'logging'

    level_filter_options = []
    levels = TttiLogging.objects.distinct('level').order_by('level')
    for level in levels:
        option = {
            'level': level.level,
            'selected': 'selected' if level.level == request.session['level_filter'] else ''
        }
        level_filter_options.append(option)

    filter_kwargs = {'task_id': task_id}
    if request.session['from_datetime_task_' + task_id]:
        filter_kwargs['created_dt__gte'] = timezone.make_aware(
            datetime.strptime(request.session['from_datetime_task_' + task_id], '%Y-%m-%dT%H:%M:%S')
        )
    if request.session['to_datetime_task_' + task_id]:
        filter_kwargs['created_dt__lte'] = timezone.make_aware(
            datetime.strptime(request.session['to_datetime_task_' + task_id], '%Y-%m-%dT%H:%M:%S')
        )
    if request.session['message_filter'] != '':
        filter_kwargs['message__icontains'] = request.session['message_filter']
    if request.session['level_filter'] != '':
        filter_kwargs['level'] = request.session['level_filter']
    logging = \
        TttiLogging.objects.filter(**filter_kwargs).\
            order_by('task_id',
                     request.session['logging_order_by_list'][0],
                     request.session['logging_order_by_list'][1]
                     )

    if 'logging_page' in request.GET:
        active_tab = 'logging'
    if 'notifications_page' in request.GET:
        active_tab = 'notifications'
    if 'window_innerheight' in request.COOKIES:
        innerheight = request.COOKIES['window_innerheight']
        if int(innerheight) < 300:
            innerheight = 300
    else:
        innerheight = 800
    availableheight = int(innerheight) - 510
    page_lines = availableheight // int(33)
    if page_lines < 1:
        page_lines = 1
    paginator = Paginator(notifications, page_lines)
    page_number = request.GET.get('notifications_page')
    notifications_page_obj = paginator.get_page(page_number)

    availableheight = int(innerheight) - 560
    page_lines = availableheight // int(33)
    if page_lines < 1:
        page_lines = 1
    paginator = Paginator(logging, page_lines)
    page_number = request.GET.get('logging_page')
    logging_page_obj = paginator.get_page(page_number)

    if 'permitted_menu' not in request.session:
        request.session['permitted_menu'] = None
    main_menu = Menu.objects.get(name='TTTI')
    main_menu.prepare(request.path, request.user, request.session['permitted_menu'])
    context = {
        'task': task,
        'main_menu': main_menu,
        'notifications_page_obj': notifications_page_obj,
        'logging_page_obj': logging_page_obj,
        'level_filter_options': level_filter_options,
        'from_datetime' : timezone.make_aware(
            datetime.strptime(request.session['from_datetime_task_' + task_id], '%Y-%m-%dT%H:%M:%S')
                              ) if request.session['from_datetime_task_' + task_id] else None,
        'to_datetime' : timezone.make_aware(
            datetime.strptime(request.session['to_datetime_task_' + task_id], '%Y-%m-%dT%H:%M:%S')
                              ) if request.session['to_datetime_task_' + task_id] else None,
        'message_filter': request.session['message_filter'],
        'active_tab': active_tab,
        'title': 'Task',
        'version': system_settings.VERSION,
    }
    response = render(request, 'ttti/task.html', context)
    return response





