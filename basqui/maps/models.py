from datetime import datetime
from maps.mapnik_parameters import *
from trees.models import *
from layers.models import *
from django.db import models
from django.contrib.auth.models import User
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.core.validators import MaxValueValidator, MinValueValidator


class MessageFeed(Feed):
    title = "basqui Message History"
    link = "basqui/message"
    description = "Message history"

    def get_object(self, request, *args, **kwargs):
        return get_object_or_404(User, pk=request.user.pk)

    def item_title(self, obj):
        return "%s , %s" % (obj.message , obj.date_created)

    def items(self, obj):
        return MessageHistory.objects.filter(created_by=obj).order_by('date_created')

class MessageHistory(models.Model):
    created_by = models.ForeignKey(User)
    date_created = models.DateTimeField('date created', auto_now_add=True)
    level = models.IntegerField('Priority level', default=0)
    message = models.CharField('Message', max_length=255)

    @classmethod
    def create(cls, user, level, message):
        message_instance = cls(created_by=user, level=level, message=message)
        message_instance.save()
        return message_instance

    def get_absolute_url(self):
        return 'http://127.0.0.1:8000/basqui/map/'


class BasquiMap(Folder):
    changed = models.BooleanField(default=True)
    center_lat = models.FloatField('Latitude of map center point', default=0, validators = [MinValueValidator(-90), MaxValueValidator(90)])
    center_long = models.FloatField('Longitude of map center point', default=0, validators = [MinValueValidator(-180), MaxValueValidator(180)])
    in_use = models.BooleanField(default=False)
    layers = models.ManyToManyField(Shapefile, through='LayerMapOptions', null=True, blank=True)
    map_height = models.PositiveIntegerField('Map height (in px)', default=768)
    map_width = models.PositiveIntegerField('Map width (in px)', default=800)
    zoom_level = models.IntegerField('Default zoom level', default=0, validators = [MinValueValidator(0), MaxValueValidator(20)])
    wms = models.ManyToManyField(WMS, null=True, blank=True)

    def __unicode__(self):
        return self.name


    class Meta:
        ordering = ['name']


def marker_path(instance, filename):
    return "markers/%s/%s" % (instance.category, filename)


class Marker(models.Model):
    name = models.CharField(max_length=50)
    category = models.CharField(max_length=50)
    svg = models.FileField(upload_to=marker_path)
    created_by = models.ForeignKey(User, blank=True, null=True)

    def __unicode__(self):
        return self.name


class LabelFont(models.Model):
    face_name = models.CharField(max_length=256)
    created_by = models.ForeignKey(User)

    def __unicode__(self):
        return self.face_name


class LayerMapOptions(models.Model):
    layer = models.ForeignKey(Shapefile)
    basqui_map = models.ForeignKey(BasquiMap)
    position = models.IntegerField(max_length=100, blank=True, null=True)
    style_visible = models.BooleanField(default=True)
    label_visible = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        super(LayerMapOptions, self).save(*args, **kwargs)
        self.basqui_map.date_updated = datetime.now()
        self.basqui_map.save()

    def __unicode__(self):
        return self.layer.name


class LayerStyle(models.Model):
    layerMapOptions = models.ForeignKey(LayerMapOptions)
    position = models.IntegerField(max_length=100, blank=True, null=True)
    filter = models.CharField(max_length=254, null=True, blank=True)
    marker = models.ForeignKey(Marker, blank=True, null=True)
    transform = models.CharField(max_length=254, null=True, blank=True)
    allow_overlap = models.BooleanField(default=False)
    spacing = models.FloatField(default=100, blank=True, null=True)
    max_error = models.FloatField(default=0.2, blank=True, null=True, validators = [MinValueValidator(0), MaxValueValidator(1)])
    placement = models.IntegerField(default=0, choices=MARKER_PLACEMENT_CHOICES)
    ignore_placement = models.BooleanField(default=False)
    stroke_offset = models.FloatField(default=0)
    clip = models.BooleanField(default=False) #default to False in Mapnik 3
    stroke_rasterizer = models.IntegerField(default=0, choices=LINE_RASTERIZER_CHOICES)
    stroke_color = models.CharField(max_length=7, default='#ffffff')
    stroke_width = models.FloatField(default=1)
    stroke_opacity = models.FloatField(default=1, validators = [MinValueValidator(0), MaxValueValidator(1)])
    stroke_linejoin = models.IntegerField(choices=STROKE_LINEJOIN_CHOICES, default=0)
    stroke_linecap = models.IntegerField(choices=STROKE_LINECAP_CHOICES, default=0)
    dash_array = models.CharField(max_length=254, null=True, blank=True)
    smooth = models.FloatField(default=0, validators = [MinValueValidator(0), MaxValueValidator(1)])
    fill = models.CharField(max_length=7, default='#ffffff')
    fill_opacity = models.FloatField(default=1, validators = [MinValueValidator(0), MaxValueValidator(1)])
    gamma = models.FloatField(default=1, validators = [MinValueValidator(0), MaxValueValidator(1)])
    gamma_method = models.IntegerField(default=0, choices=GAMMA_METHOD_CHOICES)
    simplify_tolerance = models.FloatField(default=0, validators = [MinValueValidator(0)] )
    #simplify_algorithm dans mapnik > v2.3
    minScale = models.FloatField('Minimum scale denominator', blank=True, null=True)
    maxScale = models.FloatField('Maximum scale denominator', blank=True, null=True)

    def save(self, *args, **kwargs):
        super(LayerStyle, self).save(*args, **kwargs)
        self.layerMapOptions.basqui_map.date_updated = datetime.now()
        self.layerMapOptions.basqui_map.save()


class LayerLabel(models.Model):
    layerMapOptions = models.ForeignKey(LayerMapOptions)
    position = models.IntegerField(max_length=100, blank=True, null=True)
    field = models.ForeignKey(Attribute)
    filter = models.CharField(max_length=254, blank=True, null=True)
    clip = models.BooleanField(default=False) #default to False in Mapnik 3
    face_name = models.CharField(max_length=254, choices=FACE_NAME_CHOICES, default='DejaVu Sans Book', )
    size = models.IntegerField(default=10)
    fill = models.CharField('Text color', max_length=7, default='#000000')
    halo_radius = models.IntegerField(default=0)
    halo_fill = models.CharField('Halo Color', max_length=7, default='#ffffff')
    halo_rasterizer = models.IntegerField(choices=HALO_RASTERIZER_CHOICES, default=0)
    opacity = models.FloatField(default=1)
    character_spacing = models.FloatField(default=0)
    line_spacing = models.FloatField(default=0)
    text_ratio = models.FloatField(default=0)
    text_transform = models.IntegerField(choices=TEXT_TRANSFORM_CHOICES, default=0)
    vertical_alignment = models.IntegerField(choices=VERTICAL_ALIGNMENT_CHOICES, default=3)
    horizontal_alignment = models.IntegerField(choices=HORIZONTAL_ALIGNMENT_CHOICES, default=3)
    justify_alignment = models.IntegerField(choices=JUSTIFY_ALIGNMENT_CHOICES, default=3)
    wrap_width = models.FloatField(default=0)
    wrap_before = models.BooleanField(default=False)
    wrap_character = models.CharField(max_length=1, blank=True, null=True)
    orientation = models.FloatField(default=0)
    rotate_displacement = models.BooleanField(default=True)
    dx = models.FloatField(default=0)
    dy = models.FloatField(default=0)
    label_position_tolerance = models.IntegerField(default=0)
    maximum_angle_char_delta = models.FloatField(default=22.5)
    avoid_edges = models.BooleanField(default=False)
    minimum_padding = models.FloatField(default=0)
    minimum_distance = models.FloatField(default=0)
    repeat_distance = models.FloatField(default=0)
    allow_overlap = models.BooleanField(default=False)
    label_placement = models.IntegerField(default=0, choices=LABEL_PLACEMENT_CHOICES)
    minimum_path_length = models.FloatField(default=0)
    minScale = models.FloatField('Minimum scale denominator', blank=True, null=True)
    maxScale = models.FloatField('Maximum scale denominator', blank=True, null=True)

    def save(self, *args, **kwargs):
        super(LayerLabel, self).save(*args, **kwargs)
        self.layerMapOptions.basqui_map.date_updated = datetime.now()
        self.layerMapOptions.basqui_map.save()