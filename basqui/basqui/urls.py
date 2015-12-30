import maps.models
from django.conf.urls import patterns, include, url
from django.contrib.gis import admin
from django.conf import settings
from django.conf.urls import *
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


admin.autodiscover()

# Trees urls
trees_patterns = patterns('trees.views',
    url(r'^maps$', 'initMapsTree', name='initMapsTree'),
    url(r'^maps/list/$', 'listMaps', name='listMaps'),
    url(r'^maps/list/loader/(?P<folder_id>\d+)/$', 'listMapsLoader', name='listMapsLoader'),
    url(r'^maps/layersSelect/(?P<folder_id>\d+)/$', 'maps_selectLayersTree', name='maps_selectLayersTree'),
    url(r'^layers/list/(?P<folder_id>\d+)/$', 'listLayers', name='listLayers'),
    url(r'^layers$', 'initLayersTree', name='initLayersTree'),
    url(r'^layers/list/loader/(?P<folder_id>\d+)/', 'listLayersLoader', name='listLayersLoader'),
    url(r'^moveNodes$', 'moveNodes', name='moveNodes'),
    url(r'^insertFolder$', 'insertFolder', name='insertFolder'),
    url(r'^renameNode$', 'renameNode', name='renameNode'),
    url(r'^deleteNodes$', 'deleteNodes', name='deleteNodes'),
    url(r'^duplicateNode$', 'duplicateNode', name='duplicateNode'),
)

# Map patterns
maps_patterns = patterns('maps.views',
    url(r'^$', 'initMapsLayout', name='initMapsLayout'),
    url(r'^create/$', 'createMap', name='createMap'),
    url(r'^view/$', 'initMapViewer', name='initMapViewer'),
    url(r'^saveMapOptions/$', 'saveMapOptions', name='saveMapOptions'),
    url(r'^saveLayerMapOptions/(?P<map_id>[-\w]+)/$', 'saveLayerMapOptions', name='saveLayerMapOptions'),
    url(r'^selectLayers/(?P<map_id>[-\w]+)/$', 'selectLayers', name='selectLayers'),
    url(r'^saveSelectedLayers/(?P<map_id>[-\w]+)/$', 'saveSelectedLayers', name='saveSelectedLayers'),
    url(r'^layerStyle/$', 'setLayerStyle', name='setLayerStyle'),
    url(r'^layerLabel/$', 'setLayerLabel', name='setLayerLabel'),
    url(r'^publish/(?P<user_id>[-\w]+)(?P<map_id>[-\w]+)/$', 'publishMap', name='publishMap'),
    url(r'^fixMap/$', 'fixMap', name='fixMap'),
)

# Layers patterns
layers_patterns = patterns('layers.views',
    # Shapefile urls
    url(r'^$', 'listLayers', name='listLayers'),
    url(r'^shapefile/$', 'initLayersLayout', name='initLayersLayout'),
    url(r'^shapefile/create/(?P<folder_id>\d+)/$', 'createVectorLayer', name='createVectorLayer'),
    url(r'^shapefile/import/(?P<folder_id>\d+)/$', 'importVector', name='importVector'),
    url(r'^shapefile/importOSM/(?P<folder_id>\d+)/$', 'importOSM', name='importOSM'),
    url(r'^shapefile/export/(?P<folder_id>\d+)/$', 'exportVector', name='exportVector'),
    url(r'^shapefile/selectFeature$', 'selectFeature', name='selectFeature'),
    url(r'^shapefile/hoverFeature$', 'hoverFeature', name='hoverFeature'),
    url(r'^shapefile/simplify$', 'simplifyVectorLayer', name='simplifyVectorLayer'),
    url(r'^shapefile/split/', 'splitFeature', name='splitFeature'),
    url(r'^shapefile/erase$', 'eraseFeature', name='eraseFeature'),
    url(r'^shapefile/union$', 'unionFeature', name='unionFeature'),
    url(r'^shapefile/saveEdits$', 'saveEdits', name='saveEdits'),
    url(r'^shapefile/view/(?P<shapefile_id>\d+)/$', 'initVectorViewer', name='initVectorViewer'),
    url(r'^shapefile/attributesTable/(?P<shapefile_id>\d+)/$', 'attributesTable', name='attributesTable'),
    url(r'^shapefile/attributesTable/loader/(?P<shapefile_id>\d+)/$', 'attributeTableLoader', name='attributeTableLoader'),
    url(r'^shapefile/attributesTable/(?P<shapefile_id>\d+)/update/$', 'updateAttributesTable', name='updateAttributesTable'),
    url(r'^shapefile/attributesTable/(?P<shapefile_id>\d+)/addFeature/$', 'addFeatureToTable', name='addFeatureToTable'),
    url(r'^shapefile/attributesTable/(?P<shapefile_id>\d+)/deleteFeature/$', 'deleteFeatureToTable', name='deleteFeatureToTable'),
    url(r'^shapefile/attributesTable/editField/(?P<shapefile_id>\d+)/$', 'editField', name='editField'),
    url(r'^shapefile/attributesTable/(?P<shapefile_id>\d+)/lightViewer/$', 'initLightVectorViewer', name='initLightVectorViewer'),

    # Raster urls
    url(r'^raster/view/$', 'viewerRaster', name='viewerRaster'),

    # WMS urls
    url(r'^wms/$', 'listWMS', name='listWMS'),
    url(r'^wms/new/$', 'newWMS', name='newWMS'),
    url(r'^wms/edit/(?P<wms_id>\d+)$', 'editWMS', name='editWMS'),
)


# General patterns
urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^basqui/$', 'trees.views.home'),
    url(r'^basqui/tree/', include(trees_patterns, namespace='trees', app_name='basqui')),
    url(r'^basqui/map/', include(maps_patterns, namespace='maps', app_name='basqui')),
    url(r'^basqui/layer/', include(layers_patterns, namespace='layers', app_name='basqui')),
    url(r'^media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
    url(r'^accounts/', include('registration.backends.default.urls')),
    url(r'^basqui/message/$', maps.models.MessageFeed()),
)

# Maps and features server patterns
urlpatterns += patterns('',
    url(r'^basqui/tms$', 'root'), # "shape-editor/tms" calls root()
    url(r'^basqui/tms/(?P<version>[0-9.]+)$', 'service', name='service'), # eg, "shape-editor/tms/1.0" calls service(version=1.0)
    #url(r'^basqui/tms/(?P<version>[0-9.]+)/' + r'(?P<shapefile_id>\d+)$', 'tileMap'), # eg, "shape-editor/tms/1.0/2" calls tileMap(version=1.0, shapefile_id=2)
    url(r'^basqui/tms/(?P<version>[0-9.]+)/layer/' + r'(?P<shapefile_id>\d+)/(?P<zoom>\d+)/' + r'(?P<x>\d+)/(?P<y>\d+)\.png$', 'layers.tms.tileLayer', name='tileLayer'),
    url(r'^basqui/tms/(?P<version>[0-9.]+)/feature/' + r'(?P<shapefile_id>\d+)/(?P<feature_id>\d+)/(?P<zoom>\d+)/' + r'(?P<x>\d+)/(?P<y>\d+)\.png$', 'layers.tms.tileFeature', name='tileFeature'),
    url(r'^basqui/tms/(?P<version>[0-9.]+)/raster/' + r'(?P<zoom>\d+)/' + r'(?P<x>\d+)/(?P<y>\d+)\.png$', 'tileRaster', name='tileRaster'),
    url(r'^basqui/tms/map/' + r'(?P<map_id>\d+)/(?P<zoom>\d+)/' + r'(?P<x>\d+)/(?P<y>\d+)\.png$', 'maps.tms.tileMap', name='tileMap'), # eg, "shape-editor/tms/1.0/2/3/4/5" calls tile(version=1.0, shapefile_id=2, zoom=3, x=4, y=5)
)

urlpatterns += staticfiles_urlpatterns()