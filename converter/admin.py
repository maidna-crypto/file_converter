from django.contrib import admin

from django.apps import apps


# Register your models here.
# from store.models import Orders
for model in apps.get_app_config('converter').get_models():
    admin.site.register(model)
