import traceback
import re
import os
import math
import mapnik
import TileStache
from maps.models import BasquiMap, LayerStyle, LayerMapOptions, LayerLabel
from layers.models import Shapefile, Attribute, Feature
from layers.utils import calcGeometryField
from django.conf import settings
from django.http import Http404, HttpResponse
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

MAX_ZOOM_LEVEL = 20
TILE_WIDTH = 256
TILE_HEIGHT = 256

dbSettings = settings.DATABASES['default']


def tileMap(request, map_id, zoom, x, y):
    try:
        try:
            basqui_map = BasquiMap.objects.get(id=map_id, created_by=request.user)
        except Shapefile.DoesNotExist or Feature.DoesNotExist:
            raise Http404
        zoom = int(zoom)
        x = int(x)
        y = int(y)
        if zoom < 0 or zoom > MAX_ZOOM_LEVEL:
            raise Http404
        xExtent = _unitsPerPixel(zoom)
        yExtent = _unitsPerPixel(zoom)
        minLong = x * xExtent - 20037508.34
        minLat = y * yExtent - 20037508.34
        maxLong = minLong + xExtent
        maxLat = minLat + yExtent
        if (minLong < -20037508.34 or maxLong > 20037508.34 or minLat < -20037508.34 or maxLat > 20037508.34):
            raise Http404

        map_name = "%s_%s" % (basqui_map.name, basqui_map.pk)
        config = {
          "cache": {
            "name": "test",
            "path": "../tilestache/%s/cache/" % (request.user),
            "umask": "0000",
            "dirs": "portable"},
          "layers": {
            map_name: {
                "provider": {"name": "mapnik", "mapfile": "../tilestache/%s/maps/viewer/%s.xml" % (request.user, map_name)},
                "metatile":    {
                                  "rows": 2,
                                  "columns": 2,
                                  "buffer": 64
                                },
                "projection": "spherical mercator",
            }
          }
        }

        path = "/%s/%s/%s/%s.png" % (map_name,zoom,x,y)
        config = TileStache.Config.buildConfiguration(config)
        type, bytes = TileStache.requestHandler(config, path)
        return HttpResponse(bytes, content_type="image/png")

    except:
        traceback.print_exc()
        return HttpResponse("")


def tileMapConfig(map_id):

    map_selected = BasquiMap.objects.get(pk=map_id)
    layersMapOptions = LayerMapOptions.objects.filter(basqui_map=map_selected).order_by('-position')
    layers_used = Shapefile.objects.filter(Q(layermapoptions__basqui_map=map_selected), Q(layermapoptions__style_visible=True) | Q(layermapoptions__label_visible=True))

    mapXML = mapnik.Map(TILE_WIDTH, TILE_HEIGHT, "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over")
    mapXML.buffer_size=128

    if len(layers_used) >0:
        query = """(SELECT shapefile_id, coalesce(geom_multipoint, geom_multilinestring, geom_multipolygon) as g
                    %s
                    FROM layers_feature WHERE shapefile_id IN (%s)
                    AND (geom_multipoint && !bbox! OR geom_multilinestring && !bbox! OR geom_multipolygon && !bbox! )
                    ) as geom""" % (
                    ''.join([",attribute_value->'" + label.field.name +"' as " +  str(label.field.name).lower() +"_" +  str(label.pk) for x in layersMapOptions.filter(label_visible=True) for label in x.layerlabel_set.all()]).replace(',None',''),
                    ','.join([str(x.pk) for x in layers_used ]))

    #','.join(["attribute_value->'" + x.label.field.name +"'" if x.label is not None else 'None' for x in layersMapOptions ]).replace(',None',''),

        datasource = mapnik.PostGIS(
                        host=dbSettings['HOST'],
                        user=dbSettings['USER'],
                        password=dbSettings['PASSWORD'],
                        dbname=dbSettings['NAME'],
                        port=dbSettings['PORT'],
                        table=query,
                        geometry_field = 'g',
                        #extent_from_subquery=True,
                        estimate_extent=False,
                        srid=3857,
                        extent='-20037508.34, -20037508.34, 20037508.34, 20037508.34',
                        simplify_geometries=True,
                        geometry_table='layers_feature')

        featureLayer = mapnik.Layer("tiled_layer")
        featureLayer.srs = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over"
        featureLayer.datasource = datasource
        featureLayer.cache_features = True

        #defining the feature layer styles
        for layerMapOptions in layersMapOptions.filter(style_visible=True):
            layerStyles = layerMapOptions.layerstyle_set.all().order_by('-position')
            layer = layerMapOptions.layer
            featureLayer.styles.append(str(layer.name) + '_Styles_' + str(layerMapOptions.pk))
            layer_style = mapnik.Style()
            for layerStyle in layerStyles:
                style_rule = mapnik.Rule()
                if layerStyle.filter:
                    style_rule.filter = mapnik.Filter("[shapefile_id] = %s and (%s)" % (layer.pk, str(layerStyle.filter)))
                else:
                    style_rule.filter = mapnik.Filter("[shapefile_id] = %s" % layer.pk)
                if layerStyle.minScale:
                    style_rule.min_scale = layerStyle.minScale
                if layerStyle.maxScale:
                    style_rule.max_scale = layerStyle.maxScale
                if layer.geom_type in ["Point", "MultiPoint"]:
                    m = mapnik.MarkersSymbolizer()
                    m.filename = os.path.abspath("../media/%s" % layerStyle.marker.svg)
                    m.fill = mapnik.Color(str(layerStyle.fill))
                    m.fill_opacity = layerStyle.fill_opacity
                    s = mapnik.Stroke()
                    s.color = mapnik.Color(str(layerStyle.stroke_color))
                    s.width = layerStyle.stroke_width
                    s.opacity = layerStyle.stroke_opacity
                    m.stroke = s
                    if layerStyle.transform:
                        m.transform = str(layerStyle.transform)
                    m.allow_overlap = layerStyle.allow_overlap
                    m.spacing = layerStyle.spacing
                    m.max_error = layerStyle.max_error
                    #m.placement = mapnik.marker_placement(layerStyle.placement)
                    #m.ignore_placement = layerStyle.ignore_placement
                    style_rule.symbols.append(m)
                elif layer.geom_type in ["LineString", "MultiLineString"]:
                    l = mapnik.LineSymbolizer()
                    l.stroke.color = mapnik.Color(str(layerStyle.stroke_color))
                    l.stroke.width = layerStyle.stroke_width
                    l.stroke.opacity = layerStyle.stroke_opacity
                    l.stroke.line_join = mapnik.line_join(layerStyle.stroke_linejoin)
                    l.stroke.line_cap = mapnik.line_cap(layerStyle.stroke_linecap)
                    if layerStyle.dash_array:
                        dash_array = [tuple(float(i) for i in el.strip('()').split(',')) for el in layerStyle.dash_array.split('),(')]
                        for d in dash_array:
                            l.stroke.add_dash(d[0],d[1])
                    l.stroke.gamma = layerStyle.gamma
                    l.stroke.gamma_method = mapnik.gamma_method(layerStyle.gamma_method)
                    l.smooth = layerStyle.smooth
                    l.simplify_tolerance = layerStyle.simplify_tolerance
                    l.offset = layerStyle.stroke_offset
                    l.clip = layerStyle.clip
                    l.rasterizer = mapnik.line_rasterizer(layerStyle.stroke_rasterizer)
                    style_rule.symbols.append(l)
                elif layer.geom_type in ["Polygon", "MultiPolygon"]:
                    p = mapnik.PolygonSymbolizer()
                    p.fill = mapnik.Color(str(layerStyle.fill))
                    p.fill_opacity = layerStyle.fill_opacity
                    p.clip = layerStyle.clip
                    p.gamma = layerStyle.gamma
                    p.gamme_method = mapnik.gamma_method(layerStyle.gamma_method)
                    p.smooth = layerStyle.smooth
                    p.simplify_tolerance = layerStyle.simplify_tolerance
                    l = mapnik.LineSymbolizer()
                    l.stroke.color = mapnik.Color(str(layerStyle.stroke_color))
                    l.stroke.opacity = layerStyle.stroke_opacity
                    l.stroke.width = layerStyle.stroke_width
                    if layerStyle.dash_array:
                        dash_array = [tuple(float(i) for i in el.strip('()').split(',')) for el in layerStyle.dash_array.split('),(')]
                        for d in dash_array:
                            l.stroke.add_dash(d[0],d[1])
                    l.offset = layerStyle.stroke_offset
                    l.clip = layerStyle.clip
                    l.stroke.gamma = layerStyle.gamma
                    l.smooth = layerStyle.smooth
                    l.simplify_tolerance = layerStyle.simplify_tolerance
                    style_rule.symbols.append(p)
                    style_rule.symbols.append(l)
                layer_style.rules.append(style_rule)
            mapXML.append_style(str(layer.name) + '_Styles_' + str(layerMapOptions.pk), layer_style)

            #defining label styles
        for layerMapOptions in layersMapOptions.filter(label_visible=True):
            layerLabels = layerMapOptions.layerlabel_set.all().order_by('-position')
            layer = layerMapOptions.layer
            featureLayer.styles.append(str(layer.name) + '_Label_' + str(layerMapOptions.pk))
            label_style = mapnik.Style()
            for layerLabel in layerLabels:
                label_rule = mapnik.Rule()
                if layerLabel.filter:
                    label_rule.filter = mapnik.Filter("[shapefile_id] = %s and (%s)" % (layer.pk, str(layerLabel.filter)))
                else:
                    label_rule.filter = mapnik.Filter("[shapefile_id] = %s" % layer.pk)
                if layerLabel.minScale:
                    label_rule.min_scale = layerLabel.minScale
                if layerLabel.maxScale:
                    label_rule.max_scale = layerLabel.maxScale
                label_column = '[%s_%s]' % (str(layerLabel.field).lower(), str(layerLabel.pk))
                t = mapnik.TextSymbolizer(mapnik.Expression(label_column), str(layerLabel.face_name), layerLabel.size, mapnik.Color(str(layerLabel.fill)))
                t.halo_fill = mapnik.Color(str(layerLabel.halo_fill))
                t.halo_radius = layerLabel.halo_radius
                t.halo_rasterizer = mapnik.halo_rasterizer(layerLabel.halo_rasterizer)
                t.opacity = layerLabel.opacity
                t.character_spacing = layerLabel.character_spacing
                t.line_spacing = layerLabel.line_spacing
                t.text_ratio = layerLabel.text_ratio
                t.text_transform = mapnik.text_transform(layerLabel.text_transform)
                t.clip = layerLabel.clip
                t.label_placement = mapnik.label_placement(layerLabel.label_placement)
                t.vertical_alignment = mapnik.vertical_alignment(layerLabel.vertical_alignment)
                t.horizontal_alignment = mapnik.horizontal_alignment(layerLabel.horizontal_alignment)
                t.justify_alignment = mapnik.justify_alignment(layerLabel.justify_alignment)
                t.displacement = (layerLabel.dx, layerLabel.dy)
                t.orientation = mapnik.Expression(str(layerLabel.orientation))
                t.rotate_displacement = layerLabel.rotate_displacement
                t.label_position_tolerance = layerLabel.label_position_tolerance
                t.avoid_edges = layerLabel.avoid_edges
                t.minimum_padding = layerLabel.minimum_padding
                t.allow_overlap = layerLabel.allow_overlap
                t.minimum_distance = layerLabel.minimum_distance
                t.repeat_distance = mapnik.Expression(str(layerLabel.repeat_distance))
                t.minimum_path_length = layerLabel.minimum_path_length
                t.maximum_angle_char_delta = layerLabel.maximum_angle_char_delta
                t.wrap_width = layerLabel.wrap_width
                if layerLabel.wrap_character:
                    t.wrap_character = ord(layerLabel.wrap_character)
                t.wrap_before = layerLabel.wrap_before
                label_rule.symbols.append(t)
                label_style.rules.append(label_rule)
            mapXML.append_style(str(layer.name) + '_Label_' + str(layerMapOptions.pk), label_style)

        mapXML.layers.append(featureLayer)

    #saving the map mapnik xml
    mapnik_xml_path = "../tilestache/%s/maps/viewer/%s_%s.xml" % (str(map_selected.created_by.username), str(map_selected.name), str(map_selected.pk))
    mapnik.save_map(mapXML, mapnik_xml_path)


def _unitsPerPixel(zoomLevel):
    return  40075016.68 / math.pow(2, zoomLevel)