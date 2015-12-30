import os
import errno
from django.contrib.gis.db import models
from django.contrib.auth.models import User
from polymorphic_tree.models import PolymorphicMPTTModel, PolymorphicTreeForeignKey
from django.dispatch import receiver
from django.db.models.signals import post_save

@receiver(post_save, sender=User)
def initialize_newUser(sender, **kwargs):
    user = kwargs["instance"]
    if kwargs["created"]:
        root = Folder.objects.create(name=user.username, created_by=user)
        layers_dir = Folder.objects.create(name="Layers", category="layers", parent=root, created_by=user)
        Folder.objects.create(name="Import", parent=layers_dir, created_by=user)
        maps_dir = Folder.objects.create(name="Maps", category="maps", parent=root, created_by=user)
        Folder.objects.create(name="Demos", parent=maps_dir, created_by=user)

        #create dirs
        try:
            os.makedirs("../tilestache/%s/layers/vector/viewer" % user.username)
            os.makedirs("../tilestache/%s/layers/vector/lightViewer" % user.username)
            os.makedirs("../tilestache/%s/layers/raster" % user.username)
            os.makedirs("../tilestache/%s/maps/viewer" % user.username)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise


FOLDER_CATEGORY = (
    ("maps", "Maps"),
    ("layers", "Layers"))

class Folder(PolymorphicMPTTModel):
    parent = PolymorphicTreeForeignKey('self', null=True, blank=True, related_name='children')
    name = models.CharField(max_length=50)
    category = models.CharField(null=True, blank=True, max_length=6, choices=FOLDER_CATEGORY)
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)
    created_by = models.ForeignKey(User)

    def __unicode__(self):
        return self.name