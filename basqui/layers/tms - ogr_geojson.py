import traceback, math
import mapnik, TileStache, ModestMaps
import utils
from django.conf import settings
from django.http import Http404, HttpResponse
from shapefile.models import *
from basqui.models import *
from datetime import datetime

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
        return HttpResponse("\n".join(xml), mimetype="text/xml")
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
            xml.append(' <TileMap title="' + shapefile.filename + '"')
            xml.append(' srs=3857')
            xml.append(' href="'+baseURL+'/'+id+'"/>')

        xml.append(' </TileMaps>')
        xml.append('</TileMapService>')
        return HttpResponse("\n".join(xml), mimetype="text/xml")
    except:
        traceback.print_exc()
        return HttpResponse("")

##def tileMap(request, version, shapefile_id):
##    try:
##        if version != "1.0":
##            raise Http404
##        try:
##            shapefile = Shapefile.objects.get(id=shapefile_id, created_by=request.user)
##        except Shapefile.DoesNotExist:
##            raise Http404
##        baseURL = request.build_absolute_uri()
##        xml = []
##        xml.append('<?xml version="1.0" encoding="utf-8" ?>')
##        xml.append('<TileMap version="1.0" ' + 'tilemapservice="' + baseURL + '">')
##        xml.append(' <Title>' + shapefile.filename + '</Title>')
##        xml.append(' <Abstract></Abstract>')
##        xml.append(' <SRS>EPSG:3857</SRS>')
##        xml.append(' <BoundingBox minx="-20037508.34" miny="-20037508.34" ' + 'maxx="20037508.34" maxy="20037508.34"/>')
##        xml.append(' <Origin x="0.0" y="0.0"/>')
##        xml.append(' <TileFormat width="' + str(TILE_WIDTH) + '" height="' + str(TILE_HEIGHT) + '" ' + 'mime-type="image/png" extension="png"/>')
##        xml.append(' <TileSets profile="">')
##
##        for zoomLevel in range(0, MAX_ZOOM_LEVEL+1):
##            unitsPerPixel = _unitsPerPixel(zoomLevel)
##            xml.append(' <TileSet href="' + baseURL + '/' + str(zoomLevel) + '" units-per-pixel="'+str(unitsPerPixel) + '" order="' + str(zoomLevel) + '"/>')
##
##        xml.append(' </TileSets>')
##        xml.append('</TileMap>')
##        return HttpResponse("\n".join(xml), mimetype="text/xml")
##    except:
##        traceback.print_exc()
##        return HttpResponse("")

def tileLayer(request, version, shapefile_id, zoom, x, y):
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
        map.background = mapnik.Color("#f2f3f7")
        #defining the feature layer
        geometryField = utils.calcGeometryField(shapefile.geom_type)
        field = "'NOM'"
        field2 = "'CODE'"
        query = '(select ' + geometryField + ', attribute_value->' + field +' as label, id_relat from "shapefile_feature" where' + ' shapefile_id in (' + str(shapefile.id) + ')) as geom'

##        datasource = mapnik.SQLite(file='C:\mygeosite\sqlite3\sql3.db',
##                                        table=query,
##                                        srid=3857,
##                                        geometry_field=geometryField)


##        datasource = mapnik.PostGIS(user=dbSettings['USER'],
##                        password=dbSettings['PASSWORD'],
##                        dbname=dbSettings['NAME'],
##                        table=query,
##                        srid=3857,
##                        geometry_field=geometryField,
##                        simplify_geometries=True,
##                        geometry_table='"shapefile_feature"')

        feature = Feature.objects.filter(shapefile__id=shapefile_id).geojson()
        geoj = feature.geojson
        datasource = mapnik.Ogr(layer_by_index=0, string=geoj)
##
        featureLayer = mapnik.Layer("featureLayer")
        featureLayer.srs = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over"
        featureLayer.datasource = datasource
        featureLayer.styles.append("featureLayerStyle")

        #defining the feature layer styles
        rule = mapnik.Rule()
        if shapefile.geom_type in ["Point", "MultiPoint"]:
            rule.symbols.append(mapnik.PointSymbolizer())
        elif shapefile.geom_type in ["LineString", "MultiLineString"]:
            rule.symbols.append(mapnik.LineSymbolizer(mapnik.Color("#000000"), 0.5))
        elif shapefile.geom_type in ["Polygon", "MultiPolygon"]:
            rule.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color("#f7edee")))
            rule.symbols.append(mapnik.LineSymbolizer(mapnik.Color("#000000"), 0.5))

##        label = mapnik.TextSymbolizer(mapnik.Expression('[label]'), 'DejaVu Sans Book', 10, mapnik.Color('black'))
##        label.halo_fill = mapnik.Color('white')
##        label.halo_radius = 4
##        label.label_placement = mapnik.label_placement.INTERIOR_PLACEMENT
##        label.allow_overlap = True
##        label.avoid_edges = True
##        rule.symbols.append(label)
        style = mapnik.Style()
        style.rules.append(rule)

        #add new feature to the map
        map.append_style("featureLayerStyle", style)
        map.layers.append(featureLayer)

        #rendering the map tile
        mapnik.save_map(map, "../tilestache/%s/%s.xml" % (str(request.user), str(shapefile.filename)))

        config = {
          "cache": {
            "name": "Test",
            "path": "../tilestache/%s" % (request.user),
            "umask": "0000",
            "dirs": "portable"},
          "layers": {
            shapefile.filename: {
                "provider": {"name": "mapnik", "mapfile": "../tilestache/%s/%s.xml" % (request.user, shapefile.filename)},
                "projection": "spherical mercator"
            }
          }
        }

        # like http://tile.openstreetmap.org/1/0/0.png
        #coord = ModestMaps.Core.Coordinate(y, x, zoom)
        path = "/%s/%s/%s/%s.png" % (shapefile.filename,zoom,x,y)
        config = TileStache.Config.buildConfiguration(config)
        #type, bytes = TileStache.getTile(config.layers[shapefile.filename], coord, 'png')
        type, bytes = TileStache.requestHandler(config, path)
        return HttpResponse(bytes, mimetype="image/png")

    except:
        traceback.print_exc()
        return HttpResponse("")


def tileMap(request, version, ezmap_id, zoom, x, y):
    try:
        if version != "1.0":
            raise Http404
        try:
            ezmap = EzMap.objects.get(id=ezmap_id)
            layersMapOptions = LayerMapOptions.objects.filter(ezmap=ezmap, visible=True).order_by('-position')
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

        if ezmap.changed:
        #create de mapnik.map object
            ezmap.changed=False
            ezmap.save()
            map = mapnik.Map(TILE_WIDTH, TILE_HEIGHT, "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over")
            #map.background = mapnik.Color("#ffffff")
            #defining the feature layer
            for layer in layersMapOptions.all():
                label = LayerLabel.objects.get(layerMapOptions=layer)
                for layerStyle in layer.styles.all():
                    shapefile = layer.layer
                    geometryField = utils.calcGeometryField(shapefile.geom_type)
                    query = '(select ' + geometryField + ', attribute_value->\''+ label.field.name +'\' as label, id_relat from "shapefile_feature" where' + ' shapefile_id in (' + str(shapefile.id) + ')) as geom'

##                    datasource = mapnik.SQLite(file='C:\mygeosite\sqlite3\sql3.db',
##                                                    table=query,
##                                                    srid=3857,
##                                                    geometry_field=geometryField,
##                                                    use_spatial_index=False)

                    datasource = mapnik.PostGIS(user=dbSettings['USER'],
                                    password=dbSettings['PASSWORD'],
                                    dbname=dbSettings['NAME'],
                                    table=query,
                                    srid=3857,
                                    geometry_field=geometryField,
                                    geometry_table='"shapefile_feature"')

                    featureLayer = mapnik.Layer(str(shapefile.filename) + str(layerStyle.id))
                    featureLayer.srs = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0.0 +k=1.0 +units=m +nadgrids=@null +no_defs +over"
                    featureLayer.datasource = datasource
                    featureLayer.styles.append(str(shapefile.filename) + '_Style' + str(layerStyle.id))

                    #defining the feature layer styles
                    rule = mapnik.Rule()
                    if shapefile.geom_type in ["Point", "MultiPoint"]:
                        s = mapnik.PointSymbolizer(mapnik.PathExpression(str(layerStyle.iconName)))
                        s.allow_overlap = True
                        rule.symbols.append(s)
                    elif shapefile.geom_type in ["LineString", "MultiLineString"]:
                        rule.symbols.append(mapnik.LineSymbolizer(mapnik.Color(str(layerStyle.strokeColor)), layerStyle.strokeWeight))
                    elif shapefile.geom_type in ["Polygon", "MultiPolygon"]:
                        p = mapnik.PolygonSymbolizer(mapnik.Color(str((layerStyle.fillColor))))
                        p.fill_opacity = layerStyle.fillOpacity
                        rule.symbols.append(p)
                        rule.symbols.append(mapnik.LineSymbolizer(mapnik.Color(str(layerStyle.strokeColor)), layerStyle.strokeWeight))

                    label = mapnik.TextSymbolizer(mapnik.Expression('[label]'), 'DejaVu Sans Book', label.font_size, mapnik.Color(str(label.font_color)))
                    label.halo_fill = mapnik.Color(str(label.halo_color))
                    label.halo_radius = int(label.halo_radius)
                    label.label_placement = mapnik.label_placement.INTERIOR_PLACEMENT
                    label.allow_overlap = False
                    label.avoid_edges = True
                    rule.symbols.append(label)
                    style = mapnik.Style()
                    style.rules.append(rule)

                    #add new feature to the map
                    map.append_style(str(shapefile.filename) + '_Style' + str(layerStyle.id), style)
                    map.layers.append(featureLayer)

            #saving the map mapnik xml
            mapnik.save_map(map, "c:\\mygeosite\\tilestache\\%s\\%s.xml" % (str(request.user), str(ezmap.map_name)))

        config = {
          "cache": {
            "name": "test",
            "path": "../tilestache/%s" % (request.user),
            "umask": "0000",
            "dirs": "portable"},
          "layers": {
            ezmap.map_name: {
                "provider": {"name": "mapnik", "mapfile": "../tilestache/%s/%s.xml" % (request.user, ezmap.map_name)},
                "projection": "spherical mercator"
            }
          }
        }

        # like http://tile.openstreetmap.org/1/0/0.png
        #coord = ModestMaps.Core.Coordinate(y, x, zoom)
        path = "/%s/%s/%s/%s.png" % (ezmap.map_name,zoom,x,y)
        config = TileStache.Config.buildConfiguration(config)
        #type, bytes = TileStache.getTile(config.layers[shapefile.filename], coord, 'png')
        type, bytes = TileStache.requestHandler(config, path)
        return HttpResponse(bytes, mimetype="image/png")

    except:
        traceback.print_exc()
        return HttpResponse("")


def _unitsPerPixel(zoomLevel):
    return  40075016.68 / math.pow(2, zoomLevel)