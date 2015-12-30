from django import forms
from django.contrib.gis import admin
from models import *
from utils import calcGeometryField
import copy


class WMSLayerInline(admin.TabularInline):
    model = WMSLayer
    fk_name = "wms"

class WMSAdmin(admin.ModelAdmin):
    inlines = [WMSLayerInline]

    fieldsets = [
        (None, {'fields':['alias', 'created_by', 'date_created', 'date_updated']}),
        ('WMS info',{'fields':['url', 'max_x', 'max_y', 'min_x', 'min_y']})
    ]
    list_display = ['alias', 'url', 'date_created', 'date_updated', 'created_by']
    list_filter = ('created_by',)
    readonly_fields = ('date_created', 'date_updated')

class AttributeInline(admin.TabularInline):
    model = Attribute
    fk_name = "shapefile"


class ShapefileAdmin(admin.ModelAdmin):
    inlines = [AttributeInline]

    fieldsets = [
        (None, {'fields':['name', 'created_by', 'date_created', 'date_updated']}),
        ('Shapefile info',{'fields':['geom_type', 'srs_wkt', 'encoding']})
    ]
    list_display = ['name', 'geom_type', 'date_created', 'date_updated', 'created_by']
    list_filter = ('created_by',)
    readonly_fields = ('date_created', 'date_updated')

class FeatureAdmin(admin.OSMGeoAdmin):
    fieldsets = (
        (None, {'fields':['shapefile', 'id_relat', 'attribute_value']}),
    )
    list_display = ['shapefile', 'id_relat']
    list_filter = ('shapefile', ('shapefile__created_by'))

    def get_fieldsets(self, request, obj=None):
        fieldsets = copy.deepcopy(super(FeatureAdmin, self).get_fieldsets(request, obj))
        if not obj:
            return fieldsets
        else:
            fieldsets[0][1]['fields'].insert(2, calcGeometryField(obj.shapefile.geom_type))
            return fieldsets

class AttributeAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields':['shapefile', 'name', 'type', 'width', 'precision']}),
    ]
    list_display = ['shapefile', 'name', 'type']
    list_filter = ('shapefile',)



admin.site.register(Shapefile, ShapefileAdmin)
admin.site.register(WMS, WMSAdmin)
admin.site.register(Feature, FeatureAdmin)
admin.site.register(Attribute, AttributeAdmin)
