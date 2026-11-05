from django.contrib import admin

from .models import Forbattring, Lan, Lanesaldo, Tillgang, Vardering

for m in (Tillgang, Vardering, Forbattring, Lan, Lanesaldo):
    admin.site.register(m)
