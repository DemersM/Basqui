import os
import django
import shutil

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "basqui.settings")
django.setup()
from subprocess import call
from django.contrib.auth.models import User

print os.getcwd()

call("python manage.py loaddata markers.json", shell=True)

#flush superuser tilestache directories
folder =  '../tilestache/burton449'

try:
    shutil.rmtree(folder)
except Exception:
    pass

#create superuser
u = User(username='burton449')
u.set_password('*****')
u.is_superuser = True
u.is_staff = True
u.save()
