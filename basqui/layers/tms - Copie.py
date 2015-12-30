import traceback
import math
import mapnik
import TileStache
import utils
from django.conf import settings
from django.http import Http404, HttpResponse
from layers.models import *
from maps.models import *
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.gis.db.models import Extent

MAX_ZOOM_LEVEL = 20
TILE_WIDTH = 256
TILE_HEIGHT = 256

dbSettings = settings.DATABASES['default']

def root(request):
    try:
        baseURL = request.build_absolute_uri()
        xml = []
        xml.append('<?xml version="1.0" encoding="utf-8" ?>')
        xml.append('<Services>')
        xml.append(' <TileMapService ' + 'title="ShapeEditor Tile Map Service" ' + 'version="1.0" href="' + baseURL + '/1.0"/>')
        xml.append('</Services>')
        return HttpResponse("\n".join(xml), content_type="text/xml")
    except:
        traceback.print_exc()
        return HttpResponse("")

def service(request, version):
    try:
        if version != "1.0":
            raise Http404
        baseURL = request.build_absolute_uri()
        xml = []
        xml.append('<?xml version="1.0" encoding="utf-8" ?>')
        xml.append('<TileMapService version="1.0" services="' +
        baseURL + '">')
        xml.append(' <Title>ShapeEditor Tile Map Service' + '</Title>')
        xml.append(' <Abstract></Abstract>')
        xml.append(' <TileMaps>')

        for shapefile in Shapefile.objects.filter(created_by=request.user):
            id = str(shapefile.id)
            xml.append(' <TileMap title="' + shapefile.name + '"')
            xml.append(' srs=3857')
            xml.append(' href="'+baseURL+'/'+id+'"/>')

        xml.append(' </TileMaps>')
        xml.append('</TileMapService>')
        return HttpResponse("\n".join(xml), content_type="text/xml")
    except:
        traceback.print_exc()
        return HttpResponse("")


def tileFeature(request, version, shapefile_id, feature_id, zoom, x, y):
    try:
        if version != "1.0":
            raise Http404
        try:
            shapefile = Shapefile.objects.get(id=shapefile_id, created_by=request.user)
        except Shapefile.DoesNotExist:
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

        #create de mapnik.map object
        map = mapnik.Map(TILE_WIDTH, TILE_HEIGHT, "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over")
        map.background = mapnik.Color("#fff")
        #defining the feature layer
        geometryField = utils.calcGeometryField(shapefile.geom_type)
        query = '(select ' + geometryField +', id, id_relat as label from "layers_feature" WHERE shapefile_id = ' + str(shapefile.id) + ' AND id = ' + str(feature_id) + ') as geom'

        datasource = mapnik.PostGIS(user=dbSettings['USER'],
                        password=dbSettings['PASSWORD'],
                        dbname=dbSettings['NAME'],
                        port=dbSettings['PORT'],
                        table=query,
                        srid=3857,
                        geometry_field=geometryField,
                        simplify_geometries=True,
                        geometry_table='"layers_feature"')

        featureLayer = mapnik.Layer("featureLayer")
        featureLayer.srs = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over"
        featureLayer.datasource = datasource
        featureLayer.styles.append("featureLayerStyle")

        #defining the feature layer styles
        rule = mapnik.Rule()
        if shapefile.geom_type in ["Point", "3D Point", "MultiPoint", "3D MultiPoint"]:
            rule.symbols.append(mapnik.PointSymbolizer())
        elif shapefile.geom_type in ["LineString", "3D LineString", "MultiLineString", "3D MultiLineString"]:
            rule.symbols.append(mapnik.LineSymbolizer(mapnik.Color("#000000"), 0.5))
        elif shapefile.geom_type in ["Polygon", "3D Polygon", "MultiPolygon", "3D MultiPolygon"]:
            rule.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color("#f7edee")))
            rule.symbols.append(mapnik.LineSymbolizer(mapnik.Color("#000000"), 0.5))
        style = mapnik.Style()
        style.rules.append(rule)
        map.append_style("featureLayerStyle", style)

        label_rule = mapnik.Rule()
        label = mapnik.TextSymbolizer(mapnik.Expression('[label]'), 'DejaVu Sans Book', 10, mapnik.Color('black'))
        label.halo_radius = 4
        label.allow_overlap = False
        label.avoid_edges = True
        label_rule.symbols.append(label)
        label_style = mapnik.Style()
        label_style.rules.append(label_rule)
        featureLayer.styles.append("featureLayerStyle_label")
        #add label to the map
        map.append_style("featureLayerStyle_label", label_style)


        #add new feature to the map
        map.layers.append(featureLayer)

        #rendering the map tile
        mapnik_xml_path = "../tilestache/%s/layers/vector/lightViewer/%s.xml" % (str(request.user), str(shapefile.name))
        mapnik.save_map(map, mapnik_xml_path)

        config = {
          "cache": {
            "name": "Test",
            "path": "../tilestache/%s" % (request.user),
            "umask": "0000",
            "dirs": "portable"},
          "layers": {
            shapefile.name: {
                "provider": {"name": "mapnik", "mapfile": mapnik_xml_path},
                "metatile":    {
                  "rows": 2,
                  "columns": 2,
                  "buffer": 64
                },
                "projection": "spherical mercator",
                "write cache": False
            }
          }
        }

        path = "/%s/%s/%s/%s.png" % (shapefile.name,zoom,x,y)
        config = TileStache.Config.buildConfiguration(config)
        type, bytes = TileStache.requestHandler(config, path)
        return HttpResponse(bytes, content_type="image/png")

    except:
        traceback.print_exc()
        return HttpResponse("")


def tileLayer(request, version, shapefile_id, zoom, x, y):
    try:
        if version != "1.0":
            raise Http404
        try:
            shapefile = Shapefile.objects.get(id=shapefile_id, created_by=request.user)
            layerExtent = ' '.join(map(str, (shapefile.feature_set.extent(field_name='geom_multipolygon'))))
            print layerExtent

        except Shapefile.DoesNotExist:
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

        #create de mapnik.map object
        mapXML = mapnik.Map(TILE_WIDTH, TILE_HEIGHT, "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over")
        mapXML.background_image = 'c:\\temp\\pattern.png'
        #defining the feature layer
        geometryField = utils.calcGeometryField(shapefile.geom_type)
        query = '(select ' + geometryField +', id_relat as label from "layers_feature" WHERE shapefile_id = ' + str(shapefile.id) + ') as geom'

        datasource = mapnik.PostGIS(user=dbSettings['USER'],
                        password=dbSettings['PASSWORD'],
                        dbname=dbSettings['NAME'],
                        port=dbSettings['PORT'],
                        table=query,
                        srid=3857,
                        estimate_extent=False,
                        extent=layerExtent,
                        geometry_field=geometryField,
                        simplify_geometries=True,
                        geometry_table='"layers_feature"')

        featureLayer = mapnik.Layer("featureLayer")
        featureLayer.srs = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over"
        featureLayer.cache_features = True
        featureLayer.datasource = datasource
        featureLayer.styles.append("featureLayerStyle")

        #defining the feature layer styles
        rule = mapnik.Rule()
        if shapefile.geom_type in ["Point", "3D Point", "MultiPoint", "3D MultiPoint"]:
            rule.symbols.append(mapnik.PointSymbolizer())
        elif shapefile.geom_type in ["LineString", "3D LineString", "MultiLineString", "3D MultiLineString"]:
            rule.symbols.append(mapnik.LineSymbolizer(mapnik.Color("#000000"), 0.5))
        elif shapefile.geom_type in ["Polygon", "3D Polygon", "MultiPolygon", "3D MultiPolygon"]:
            rule.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color("#f7edee")))
            rule.symbols.append(mapnik.LineSymbolizer(mapnik.Color("#000000"), 0.5))
        style = mapnik.Style()
        style.rules.append(rule)
        mapXML.append_style("featureLayerStyle", style)

        label_rule = mapnik.Rule()
        label = mapnik.TextSymbolizer(mapnik.Expression('[label]'), 'DejaVu Sans Book', 10, mapnik.Color('black'))
        label.halo_radius = 4
        label.allow_overlap = False
        label.avoid_edges = True
        label_rule.symbols.append(label)
        label_style = mapnik.Style()
        label_style.rules.append(label_rule)
        featureLayer.styles.append("featureLayerStyle_label")
        #add label to the map
        mapXML.append_style("featureLayerStyle_label", label_style)


        #add new feature to the map
        mapXML.layers.append(featureLayer)

        #rendering the map tile
        mapnik_xml_path = "../tilestache/%s/layers/vector/viewer/%s.xml" % (str(request.user), str(shapefile.name))
        mapnik.save_map(mapXML, mapnik_xml_path)

        config = {
          "cache": {
            "name": "Test",
            "path": "../tilestache/%s" % (request.user),
            "umask": "0000",
            "dirs": "portable"},
          "layers": {
            shapefile.name: {
                "provider": {"name": "mapnik", "mapfile": mapnik_xml_path},
                "metatile":    {
                  "rows": 2,
                  "columns": 2,
                  "buffer": 64
                },
                "projection": "spherical mercator",
                "write cache": False
            }
          }
        }

        # like http://tile.openstreetmap.org/1/0/0.png
        #coord = ModestMaps.Core.Coordinate(y, x, zoom)
        path = "/%s/%s/%s/%s.png" % (shapefile.name,zoom,x,y)
        config = TileStache.Config.buildConfiguration(config)
        #type, bytes = TileStache.getTile(config.layers[shapefile.filename], coord, 'png')
        type, bytes = TileStache.requestHandler(config, path)
        return HttpResponse(bytes, content_type="image/png")

    except:
        traceback.print_exc()
        return HttpResponse("")

def tileRaster(request, version, zoom, x, y):
    try:
        if version != "1.0":
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

        #create de mapnik.map object
        map = mapnik.Map(TILE_WIDTH, TILE_HEIGHT, "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over")
        #defining the feature layer

        datasource = mapnik.Gdal(file="bar_harbour.dem",
                    base="C:\\Temp\\dem\\",
                    band=1)

        featureLayer = mapnik.Layer("RasterLayer")
        featureLayer.srs = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over"
        featureLayer.datasource = datasource
        featureLayer.styles.append("RasterLayerStyle")

        #defining the feature layer styles
        rule = mapnik.Rule()
        rule.symbols.append(mapnik.RasterSymbolizer())
        style = mapnik.Style()
        style.rules.append(rule)

        #add new feature to the map
        map.append_style("RasterLayerStyle", style)
        map.layers.append(featureLayer)

        #rendering the map tile
        #mapnik.save_map(map, "../tilestache/%s/raster.xml" % str(request.user))

        config = {
          "cache": {
            "name": "Test",
            "path": "../tilestache/%s" % (request.user),
            "umask": "0000",
            "dirs": "portable"},
          "layers": {
            "raster": {
                "provider": {"name": "mapnik", "mapfile": "../tilestache/%s/layers/raster/raster.xml" % (request.user)},
                "projection": "spherical mercator",
                "metatile":    {
                  "rows": 2,
                  "columns": 2,
                  "buffer": 64
                },
                "write cache": False
            }
          }
        }

        # like http://tile.openstreetmap.org/1/0/0.png
        #coord = ModestMaps.Core.Coordinate(y, x, zoom)
        path = "/raster/%s/%s/%s.png" % (zoom,x,y)
        config = TileStache.Config.buildConfiguration(config)
        #type, bytes = TileStache.getTile(config.layers[shapefile.filename], coord, 'png')
        type, bytes = TileStache.requestHandler(config, path)
        return HttpResponse(bytes, content_type="image/png")

    except:
        traceback.print_exc()
        return HttpResponse("")


def _unitsPerPixel(zoomLevel):
    return  40075016.68 / math.pow(2, zoomLevel)