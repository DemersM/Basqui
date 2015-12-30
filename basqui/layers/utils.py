import os
import pyproj
from time import clock
from osgeo import ogr
from django.contrib.gis.geos import Point
from django.contrib.gis.geos.collections import MultiPolygon, MultiLineString, MultiPoint
from django import forms
from django.contrib.gis import admin
from layers.models import Shapefile, Feature
from django.db import connection
import datetime


def chunks(l, n):
    n = max(1, n)
    return [l[i:i + n] for i in range(0, len(l), n)]


def check_geomType(tuple):
    for item in tuple:
        if item[1] != tuple[0][1]:
            return True
    return False


def extentArea(extent):
    #Unpack extent tuple to coordinates
    minX, minY, maxX, maxY = extent #unpack the tuple
    #Create empty geometry and add vertices
    geom = ogr.Geometry(type = ogr.wkbLinearRing)
    geom.AddPoint_2D(minX,minY)
    geom.AddPoint_2D(minX,maxY)
    geom.AddPoint_2D(maxX,maxY)
    geom.AddPoint_2D(maxX,minY)
    geom.AddPoint_2D(minX,minY)
    # Plan to return area, but destroy geometry first
    area = geom.GetArea()
    geom.Destroy()
    return area


def findFeature(shapefile, longitude, latitude, buffer=20000, distance=2):
    pt = Point(longitude, latitude)
    circle = pt.buffer(buffer)
    radius = calcSearchRadius(latitude, longitude, distance)

##    if shapefile.geom_type in ["Point", "3D Point"]:
##        try:
##            return Feature.objects.filter(geom_point__intersects=circle, shapefile=shapefile)[:1].get()
##        except Feature.DoesNotExist:
##            return None
    if shapefile.geom_type in ["LineString", "3D LineString", "MultiLineString", "3D MultiLineString"]:
        try:
            return Feature.objects.get(geom_multilinestring__intersects=circle, shapefile=shapefile)[:1].get()
        except Feature.DoesNotExist:
            return None
    elif shapefile.geom_type in ["Polygon", "3D Polygon", "MultiPolygon", "3D MultiPolygon" ]:
        try:
            return Feature.objects.get(geom_multipolygon__contains=pt, shapefile=shapefile)
        except Feature.DoesNotExist:
            return None
    elif shapefile.geom_type in ["Point", "MultiPoint", "3D MultiPoint"]:
        try:
            return Feature.objects.filter(geom_multipoint__intersects=circle, shapefile=shapefile)[:1].get()
        except Feature.DoesNotExist:
             return None
    elif shapefile.geom_type in ["GeometryCollection", "3D GeometryCollection"]:
        try:
            return feature.objects.get(geom_geometrycollection__dwithin=(pt, radius))
        except Feature.DoesNotExist:
            return None
    else:
        print "Unsupported geometry: " + shapefile.geom_type
        return None


def updateTiles(request, shapefile, feature):
    config = {
          "cache": {
            "name": "Disk",
            "path": "../tilestache/%s" % (request.user),
            "umask": "0000",
            "dirs": "portable"},
          "layers": {
            "test": {
                "provider": {"name": "mapnik", "mapfile": "../tilestache/%s/%s.xml" % (request.user, request.user)},
                "projection": "spherical mercator"
            }
          }
        }
    bounds = Feature.objects.filter(id=feature.id).area()
    print(bounds.area)
    geom_field = calcGeometryField(shapefile.geom_type)
    #cursor = connection.cursor()
    #cursor.execute('SELECT Min(MbrMinY(transform(%s, 4326))), Min(MbrMinX(transform(%s,4326))), Max(MbrMaxY(transform(%s,4326))), Max(MbrMaxX(transform(%s,4326))) FROM shapefile_feature where id=%s;' % (geom_field,geom_field,geom_field,geom_field,feature.id) )
    #mettre en lat/lon
    #bounds = ' '.join(map(str, (cursor.fetchone())))
    #print bounds
    #bounds = "45.768742829 -72.0376639155 47.341383122 -69.62529744"
    #os.system("tilestache-seed.py -c test.txt -l ra_general.shp -b %s -e png 0 1 2 3 4 8 9 10" % bounds)


def getMapForm(shapefile): #, zoomLevel, centerLon, centerLat):
    geometryField = calcGeometryField(shapefile.geom_type)
    adminInstance = admin.OSMGeoAdmin(Feature, admin.site)
    field = Feature._meta.get_field(geometryField)
    widgetType = adminInstance.get_map_widget(field)
    widgetType.params.update({'map_width':1000, 'map_height': 500}) #  'default_lon':centerLon, 'default_lat':centerLat, 'default_zoom': zoomLevel})

    class MapForm(forms.Form):
        geometry = forms.CharField(widget=widgetType(), label="")

    return MapForm


def calcSearchRadius(latitude, longitude, distance):
    geod = pyproj.Geod(ellps="WGS84")
    x,y,angle = geod.fwd(longitude, latitude, 0, distance)
    radius = y-latitude
    x,y,angle = geod.fwd(longitude, latitude, 90, distance)
    radius = max(radius, x-longitude)
    x,y,angle = geod.fwd(longitude, latitude, 180, distance)
    radius = max(radius, latitude-y)
    x,y,angle = geod.fwd(longitude, latitude, 270, distance)
    radius = max(radius, longitude-x)
    return radius


def forceOgrMulti(output, geom_type):
    if geom_type == "Point":
        output = ogr.ForceToMultiPolygon(output)
    elif geom_type == "LineString":
        output = ogr.ForceToMultiLineString(output)
    elif geom_type == "Polygon":
        output = ogr.ForceToMultiPolygon(output)
    return output


def ogrTypeToGeometryName(ogrType):
    return {ogr.wkbUnknown : 'MultiPolygon',
            ogr.wkbPoint : 'Point',
            ogr.wkbLineString : 'LineString',
            ogr.wkbPolygon : 'Polygon',
            ogr.wkbMultiPoint : 'MultiPoint',
            ogr.wkbMultiLineString : 'MultiLineString',
            ogr.wkbMultiPolygon : 'MultiPolygon',
            ogr.wkbPolygon25D : 'Polygon',
            ogr.wkbGeometryCollection : 'GeometryCollection',
            ogr.wkbNone : 'None',
            ogr.wkbLinearRing : 'LinearRing'}.get(ogrType)


def geometryNameToOgrType(geometryName):
    return {'MultiPolygon' : ogr.wkbUnknown,
            'Point' : ogr.wkbPoint,
            'LineString' : ogr.wkbLineString,
            'Polygon' : ogr.wkbPolygon,
            'MultiPoint' : ogr.wkbMultiPoint,
            'MultiLineString' : ogr.wkbMultiLineString,
            'MultiPolygon' : ogr.wkbMultiPolygon,
            'Polygon' : ogr.wkbPolygon25D,
            'GeometryCollection' : ogr.wkbGeometryCollection,
            'None' : ogr.wkbNone,
            'LinearRing' : ogr.wkbLinearRing}.get(geometryName)


def wrapGEOSGeometry(geometry):
    if geometry.geom_type == "Polygon":
        return MultiPolygon(geometry)
    elif geometry.geom_type == "LineString":
        return MultiLineString(geometry)
    elif geometry.geom_type == "Point":
        return MultiPoint(geometry)
    else:
        return geometry


def calcGeometryField(geometryType):
    if geometryType in ["Unknown", "Polygon", "3D Polygon", "MultiPolygon", "3D MultiPolygon"]:
        return "geom_multipolygon"
    elif geometryType in ["LineString", "3D LineString", "MultiLineString", "3D MultiLineString"]:
        return "geom_multilinestring"
    elif geometryType in ["GeometryCollection", "3D GeometryCollection"]:
        return "geom_geometrycollection"
    else:
        return "geom_multipoint"


def getOGRFeatureAttribute(attr, feature, encoding):
    attrName = str(attr.name)
    if not feature.IsFieldSet(attrName):
        return (True, None)
    needsEncoding = False
    if attr.type == ogr.OFTInteger:
        value = str(feature.GetFieldAsInteger(attrName))
    elif attr.type == ogr.OFTIntegerList:
        value = repr(feature.GetFieldAsIntegerList(attrName))
    elif attr.type == ogr.OFTReal:
        value = feature.GetFieldAsDouble(attrName)
        value = "%*.*f" % (attr.width, attr.precision, value)
        value = value.lstrip()
    elif attr.type == ogr.OFTRealList:
        values = feature.GetFieldAsDoubleList(attrName)
        sValues = []
        for value in values:
            sValues.append("%*.*f" % (attr.width,attr.precision, value))
        value = repr(sValues)
    elif attr.type == ogr.OFTString:
        value = feature.GetFieldAsString(attrName)
        needsEncoding = True
    elif attr.type == ogr.OFTStringList:
        value = repr(feature.GetFieldAsStringList(attrName))
        needsEncoding = True
    elif attr.type == ogr.OFTDate:
        fieldIndex = feature.GetFieldIndex(attrName)
        parts = feature.GetFieldAsDateTime(fieldIndex)
        year,month,day,hour,minute,second,tzone = parts
        value = str(datetime.date(year,month,day))
    elif attr.type == ogr.OFTTime:
        fieldIndex = feature.GetFieldIndex(attrName)
        parts = feature.GetFieldAsDateTime(fieldIndex)
        year,month,day,hour,minute,second,tzone = parts
        value = str(datetime.time(hour,minute,second))
    elif attr.type == ogr.OFTDateTime:
        fieldIndex = feature.GetFieldIndex(attrName)
        parts = feature.GetFieldAsDateTime(fieldIndex)
        year,month,day,hour,minute,second,tzone = parts
        value = str(datetime.datetime(year,month,day,hour,minute,second))
    else:
        return (False, "Unsupported attribute type: " + str(attr.type))
    if needsEncoding:
        try:
            value = value.decode(encoding)
        except UnicodeDecodeError:
            return (False, "Unable to decode value in " + repr(attrName) + " attribute.&nbsp; " + "Are you sure you're using the right character encoding?")
    return (True, value)


def unwrapGEOSGeometry(geometry):
    if geometry.geom_type in ["MultiPolygon", "3D MultiPolygon", "MultiLineString", "3D MultiLineString"]:
        if len(geometry) == 1:
            geometry = geometry[0]
    return geometry


def setOGRFeatureAttribute(attr, value, feature, encoding):
    attrName = str(attr.name)
    if value == None:
        #feature.UnsetField(attrName)
        return
    if attr.type == ogr.OFTInteger:
        feature.SetField(attrName, int(value))
    elif attr.type == ogr.OFTIntegerList:
        integers = eval(value)
        feature.SetFieldIntegerList(attrName, integers)
    elif attr.type == ogr.OFTReal:
        feature.SetField(attrName, float(value))
    elif attr.type == ogr.OFTRealList:
        floats = []
        for s in eval(value):
            floats.append(eval(s))
        feature.SetFieldDoubleList(attrName, floats)
    elif attr.type == ogr.OFTString:
        feature.SetField(attrName, value.encode(encoding))
    elif attr.type == ogr.OFTStringList:
        strings = []
        for s in eval(value):
            strings.append(s.encode(encoding))
        feature.SetFieldStringList(attrName, strings)
    elif attr.type == ogr.OFTDate:
        parts = value.split("-")
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        feature.SetField(attrName, year, month, day)
    elif attr.type == ogr.OFTTime:
        parts = value.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2])
        feature.SetField(attrName, hour, minute, second)
    elif attr.type == ogr.OFTDateTime:
        parts = value.split(":")
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        hour = int(parts[3])
        minute = int(parts[4])
        second = int(parts[5])
        feature.SetField(attrName, year, month, day, hour, minute, second)