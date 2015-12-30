from maps.models import *
from layers.models import *
from django.contrib import admin
from django.contrib.auth.models import User

class MessageHistoryAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields':['message', 'level']}),
        ('User Info', {'fields': ['created_by']}),
    ]
    list_display = ['created_by','level', 'date_created']

##class LayerMapOptionsInline(admin.TabularInline):
##    model = LayerMapOptions
##    extra = 1

class MarkerAdmin(admin.ModelAdmin):
    fieldsets = [
            (None, {'fields': ['svg']}),
        ]

    list_display = ['svg', 'category', 'name', 'created_by' ]
    list_filter = ('created_by', 'category')


class BasquiMapAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields':['name', 'changed']}),
        ('User Info', {'fields': ['created_by', 'date_created', 'date_updated', 'in_use']}),
        ('Map information', {'fields': ['zoom_level', 'center_lat', 'center_long', 'map_width', 'map_height'], 'classes':['collapse']}),
        ('WMS Layer', {'fields': ['wms',]}),
    ]
    #inlines = [LayerMapOptionsInline]
    list_display = ['name', 'date_created', 'date_updated', 'created_by', 'in_use']
    list_filter = ('created_by',)
    search_fields =('user__username',)
    readonly_fields = ('date_created', 'date_updated')


class LayerStyleAdmin(admin.ModelAdmin):
    fieldsets = [
            ('Style Option', {'fields': ['conditionStyle', 'icon', 'fillColor', 'fillOpacity', 'strokeColor', 'strokeWeight'], 'classes':['collapse']}),
        ]
    #inlines = [LayerMapOptionsInline,]



class LayerLabelAdmin(admin.ModelAdmin):
    fieldsets = [
            (None, {'fields': ['field']}),
            ('Label Option', {'fields': ['font', 'font_size', 'font_color', 'halo_radius', 'halo_color', 'offset_x', 'offset_y'], 'classes':['collapse']}),
        ]
    #inlines = [LayerMapOptionsInline,]
    list_display = ['field',]


class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'date_joined', 'last_login')


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(BasquiMap, BasquiMapAdmin)
admin.site.register(Marker,MarkerAdmin)
admin.site.register(LayerStyle, LayerStyleAdmin)
admin.site.register(LayerLabel, LayerLabelAdmin)
admin.site.register(MessageHistory,MessageHistoryAdmin)
