from django import forms
from django.contrib.auth.models import User
from .models import SysProfile, SysOrganisation
from django.utils.translation import gettext as _
from django.conf import settings


class UserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(label=_('First name'))
    last_name = forms.CharField(label=_('Last name'))
    email = forms.EmailField(label=_('Email'))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class ProfileUpdateForm(forms.ModelForm):
    language = forms.ChoiceField(
        label=_('Language'),
        choices=settings.LANGUAGES
    )
    organisation = forms.ModelChoiceField(
        label=('Organisation'),
        queryset=SysOrganisation.objects.all()
    )

    class Meta:
        model = SysProfile
        fields = ['language', 'organisation']


