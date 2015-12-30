import os
import datetime
from trees.models import *
from django.contrib.gis.db import models
from django.contrib.auth.models import User
from datetime import datetime
from django.core.exceptions import ValidationError
from django_hstore import hstore
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Max


class Shapefile(Folder):
    srs_wkt = models.CharField(max_length=1000, blank=True, null=True)
    geom_type = models.CharField(max_length=50)
    encoding = models.CharField(max_length=20)

    def __unicode__(self):
        return self.name


class Attribute(models.Model):
    shapefile = models.ForeignKey(Shapefile)
    name = models.CharField(max_length=80, db_index=True)
    type = models.CharField(max_length=255)
    width = models.IntegerField(default=0, validators = [MinValueValidator(0), MaxValueValidator(254)])
    precision = models.IntegerField(default=0, validators = [MinValueValidator(0), MaxValueValidator(15)])

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        super(Attribute, self).save(*args, **kwargs)
        self.shapefile.date_updated = datetime.now()
        self.shapefile.save()

    def delete(self):
        feature_selected = Feature.objects.filter(shapefile=self.shapefile,attribute_value__contains=[self.name]).hremove('attribute_value', self.name)
        super(Attribute, self).delete()

    class Meta:
        unique_together = (('name', 'shapefile'),)

def cal_id_relat(shapefile):
    feature = Feature.objects.filter(shapefile=shapefile).aggregate(Max('id_relat'))
    if feature['id_relat__max'] is not None:
        return feature['id_relat__max'] + 1
    else:
        return 0

class Feature(models.Model):
    shapefile = models.ForeignKey(Shapefile)
    id_relat = models.PositiveIntegerField(db_index=True)
    geom_point = models.PointField(srid=3857, blank=True, null=True)
    geom_multipoint = models.MultiPointField(srid=3857, blank=True, null=True)
    geom_multilinestring = models.MultiLineStringField(srid=3857, blank=True, null=True)
    geom_multipolygon = models.MultiPolygonField(srid=3857, blank=True, null=True)
    geom_geometrycollection = models.GeometryCollectionField(srid=3857, blank=True, null=True)
    attribute_value = hstore.DictionaryField(db_index=True)
    objects = hstore.HStoreGeoManager()

    @classmethod
    def generate_id_relat(cls, self):
        try:
            # note: you could also implement 'lastest' which is more readable
            return int(cls.objects.filter(shapefile=self.shapefile).order_by('-id')[0].id) + 1
        except (IndexError, cls.DoesNotExist):
            return 9999999

    def clean(self):
        if not self.id:
            self.id_relat = self.generate_id_relat()
        return super(Feature, self).clean()

    def __unicode__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        if self.id_relat is None:
            self.id_relat = cal_id_relat(self.shapefile)
        self.shapefile.date_updated = datetime.now()
        self.shapefile.save()
        super(Feature, self).save(*args, **kwargs)


class WMS(models.Model):
    alias = models.SlugField(max_length=50)
    created_by = models.ForeignKey(User)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    srs = models.IntegerField(default= 900913, verbose_name='EPSG')
    url = models.CharField(max_length=255)

    class Meta:
        unique_together = (('alias', 'created_by'),)

    def __unicode__(self):
        return self.alias


class WMSLayer(models.Model):
    in_use = models.BooleanField(default=False)
    layer_name = models.CharField('layer name', max_length=50)
    position = models.IntegerField(max_length=100)
    wms = models.ForeignKey(WMS)

    class Meta:
        unique_together = (('layer_name', 'wms'),)

    def __unicode__(self):
        return self.wms.alias,self.layer_name

    def save(self, *args, **kwargs):
        super(WMSLayer, self).save(*args, **kwargs)
        self.wms.date_updated = datetime.now()
        self.wms.save()