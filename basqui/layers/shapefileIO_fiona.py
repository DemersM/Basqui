import re
import fiona
from fiona.crs import to_string
import os, os.path, tempfile, zipfile
import shutil, traceback, stat, errno
from django.contrib.gis.geos.geometry import GEOSGeometry
from django.contrib.gis.gdal.srs import CoordTransform, SpatialReference
from django.http import StreamingHttpResponse
from django.core.servers.basehttp import FileWrapper
from osgeo import ogr, osr
from shapefile.models import Folder, Shapefile, Attribute, Feature
from shapefile.wkt import dumps
from collections import defaultdict, Counter
import utils
import time
from django.db import connection

fileExt_dic = {"shp" : ".zip",
                "tab" : ".zip",
                "json" : ".zip",
                "kml" : ".kmz",
                "sqlite": ".zip",
                "csv": ".zip"}

suffixes_dic = {"shp" : [".shp", ".shx", ".dbf", ".prj"],
                "tab": [".id", ".map", ".tab", ".dat"],
                "json" : [".json"],
                "kml" : [".kml"],
                "sqlite" : [".sqlite"],
                "csv": [".csv"]}

ogrDriver_dic = {"shp" : "ESRI Shapefile",
                    "tab" : "MapInfo File",
                    "json" : "GeoJSON",
                    "kml" : "KML",
                    "sqlite" : "SQLite",
                    "csv": "CSV"}

filenameExt_dic = {"shp" : ".shp",
                    "tab" : ".tab",
                    "json" : ".json",
                    "kml" : ".kml",
                    "sqlite" : ".sqlite",
                    "csv": ".csv"}

def handleRemoveReadonly(func, path, exc):
  excvalue = exc[1]
  if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
      os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
      func(path)
  else:
      raise

def importData(file, characterEncoding, format, user, folder):
    cursor = connection.cursor()
    start_time = time.time()
    #manage zipfile
    fd,fname = tempfile.mkstemp(suffix=fileExt_dic[format])
    os.close(fd)
    f = open(fname, "wb")
    for chunk in file.chunks():
        f.write(chunk)
    f.close()

    if not zipfile.is_zipfile(fname):
        os.remove(fname)
        return "Not a valid zip archive.", None
    zip = zipfile.ZipFile(fname)

    hasSuffix = {}
    required_suffixes = suffixes_dic[format]
    for suffix in required_suffixes:
        hasSuffix[suffix] = False
    for info in zip.infolist():
        extension = os.path.splitext(info.filename)[1].lower()
        if extension in required_suffixes:
            hasSuffix[extension] = True
    for suffix in required_suffixes:
        if not hasSuffix[suffix]:
            zip.close()
            os.remove(fname)
            return "Archive missing required %s file." % suffix, None

    zip = zipfile.ZipFile(fname)
    shapefileName = None
    dirname = tempfile.mkdtemp()
    for info in zip.infolist():
        if info.filename.lower().endswith(filenameExt_dic[format]):
            shapefileName = info.filename
        dstFile = os.path.join(dirname, info.filename)
        f = open(dstFile, "wb")
        f.write(zip.read(info.filename))
        f.close()
    zip.close()

    #verify if shapefile is valid
    try:
        srcPath = os.path.join(dirname,shapefileName)
        srcLayers = fiona.listlayers(srcPath)
        shapefileOK = True
    except:
        traceback.print_exc()
        shapefileOK = False
    if not shapefileOK:
        os.remove(fname)
        shutil.rmtree(dirname)
        return "Not a valid vector file.", None

    #add shapefile object to database
    try:
        for i in srcLayers:
            with fiona.open(srcPath) as c:
                srcSpatialRef = to_string(c.crs)
                print srcSpatialRef
                project = CoordTransform(SpatialReference(srcSpatialRef),SpatialReference(3857))
                geometryType = c.schema['geometry']
                shapefile = Shapefile.objects.create(filename=c.name, parent=folder, srs_wkt=srcSpatialRef, geom_type=geometryType, encoding=characterEncoding, created_by=user)

                #define shapefile's attributes
                for keys, values in c.schema['properties'].iteritems():
                    dict = {}
                    dict['name'] = keys
                    props = re.split('\W+', values)
                    dict['type'] = utils.fionaTypeToInt(props[0])
                    try:
                        dict['width'] = int(props[1])
                    except IndexError:
                        dict['width'] = 0
                    if dict['type'] == 2:
                        try:
                            dict['precision'] = int(props[2])
                        except IndexError:
                            dict['precision'] = 15
                    else:
                        dict['precision'] = 0
                    attr = Attribute.objects.create(shapefile=shapefile, **dict)

                #store shapefile's features
                for srcFeature in c:
                    try:
                        wkt = dumps(srcFeature['geometry'])
                        geosGeometry = GEOSGeometry(wkt)
                        geosGeometry.srid = SpatialReference(srcSpatialRef).srid
                        geosGeometry.transform(project)
                    except TypeError:
                        geosGeometry = None

                    geometryField = utils.calcGeometryField(geometryType)

                    args = {}
                    args['shapefile'] = shapefile
                    args[geometryField] = geosGeometry
                    args['attribute_value'] = srcFeature['properties']
                    args['id_relat'] = srcFeature['id']
                    feature = Feature.objects.create(**args)

            print("Temps final: --- %s seconds ---" % str(time.time() - start_time))
            return None, shapefile

    except BaseException, e:
        #cleaning up
        os.remove(fname)
        shutil.rmtree(dirname, ignore_errors=False, onerror=handleRemoveReadonly)
        shapefile.delete()
        return e, None



def exportData(layers, encoding, EPSG, format):
    try:
        dstSpatialRef = osr.SpatialReference()
        dstSpatialRef.ImportFromEPSG(EPSG)
        driver = ogr.GetDriverByName(ogrDriver_dic[format])
        dstDir = tempfile.mkdtemp()
        for layer in layers:
            dstFile = str(os.path.join(dstDir, layer.filename+filenameExt_dic[format]))
            datasource = driver.CreateDataSource(dstFile)
            vlayer = datasource.CreateLayer(str(layer.filename),dstSpatialRef)

            #retrive attributes
            for attr in layer.attribute_set.all():
                field = ogr.FieldDefn(str(attr.name), attr.type)
                field.SetWidth(attr.width)
                field.SetPrecision(attr.precision)
                vlayer.CreateField(field)

            #save features in shapefile
            srcSpatialRef = osr.SpatialReference()
            srcSpatialRef.ImportFromEPSG(3857)
            coordTransform = osr.CoordinateTransformation(srcSpatialRef, dstSpatialRef)
            geomField = utils.calcGeometryField(layer.geom_type)
            for feature in layer.feature_set.all().order_by('id_relat'):
                geometry = getattr(feature, geomField)

                if geometry:
                    geometry = utils.unwrapGEOSGeometry(geometry)
                    dstGeometry = ogr.CreateGeometryFromWkt(geometry.wkt)
                    dstGeometry.Transform(coordTransform)
                else:
                    dstGeometry = None

            #save attributes in the shapefile
                dstFeature = ogr.Feature(vlayer.GetLayerDefn())
                dstFeature.SetGeometry(dstGeometry)
                for attrName, attrValue in feature.attribute_value.iteritems():
                    attribute = Attribute.objects.get(name=str(attrName), shapefile=feature.shapefile)
                    utils.setOGRFeatureAttribute(attribute, attrValue, dstFeature, encoding)
                vlayer.CreateFeature(dstFeature)
                dstFeature.Destroy()
            datasource.Destroy()

        #compress the shapefile
            temp = tempfile.TemporaryFile()
            zip = zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED)
            shapefileBase = os.path.splitext(dstFile)[0]
            shapefileName = os.path.splitext(layer.filename)[0]
            for fName in os.listdir(dstDir):
                zip.write(os.path.join(dstDir, fName), fName)
        zip.close()

        #delete temporary files
        shutil.rmtree(dstDir)

        #return the zip to user
        f = FileWrapper(temp)
        response = StreamingHttpResponse(f, content_type="application/zip")
        response['Content-Disposition'] = "attachment; filename=" + shapefileName + fileExt_dic[format]
        response['Content-Length'] = temp.tell()
        temp.seek(0)
        return None, response
    except BaseException, e:
        print e
        return e, None

def exportMergedData(layers, encoding, EPSG, format):
    try:
        dstSpatialRef = osr.SpatialReference()
        dstSpatialRef.ImportFromEPSG(EPSG)
        driver = ogr.GetDriverByName(ogrDriver_dic[format])
        fields = [attribute for layer in layers for attribute in layer.attribute_set.all()]
        features = [feature for layer in layers for feature in layer.feature_set.all().order_by('id_relat')]

        dstDir = tempfile.mkdtemp()
        dstFile = str(os.path.join(dstDir, layer.filename+filenameExt_dic[format]))
        datasource = driver.CreateDataSource(dstFile)
        vlayer = datasource.CreateLayer(str(layer.filename),dstSpatialRef)
        #retrive attributes
        for attr in fields:
            field = ogr.FieldDefn(str(attr.name), attr.type)
            field.SetWidth(attr.width)
            field.SetPrecision(attr.precision)
            vlayer.CreateField(field)


    #save features in shapefile
        srcSpatialRef = osr.SpatialReference()
        srcSpatialRef.ImportFromEPSG(3857)
        coordTransform = osr.CoordinateTransformation(srcSpatialRef, dstSpatialRef)
        geomField = utils.calcGeometryField(layer.geom_type)
        for feature in features:
            geometry = getattr(feature, geomField)

            if geometry:
                geometry = utils.unwrapGEOSGeometry(geometry)
                dstGeometry = ogr.CreateGeometryFromWkt(geometry.wkt)
                dstGeometry.Transform(coordTransform)
            else:
                dstGeometry = None

        #save attributes in the shapefile
            dstFeature = ogr.Feature(vlayer.GetLayerDefn())
            dstFeature.SetGeometry(dstGeometry)
            for attrName, attrValue in feature.attribute_value.iteritems():
                attribute = Attribute.objects.get(name=str(attrName), shapefile=feature.shapefile)
                utils.setOGRFeatureAttribute(attribute, attrValue, dstFeature, encoding)
            vlayer.CreateFeature(dstFeature)
            dstFeature.Destroy()
        datasource.Destroy()

        #compress the shapefile
        temp = tempfile.TemporaryFile()
        zip = zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED)
        shapefileBase = os.path.splitext(dstFile)[0]
        shapefileName = os.path.splitext(layer.filename)[0]
        for fName in os.listdir(dstDir):
            zip.write(os.path.join(dstDir, fName), fName)

        zip.close()

        #delete temporary files
        shutil.rmtree(dstDir)

        #return the zip to user
        f = FileWrapper(temp)
        response = StreamingHttpResponse(f, content_type="application/zip")
        response['Content-Disposition'] = "attachment; filename=" + shapefileName + fileExt_dic[format]
        response['Content-Length'] = temp.tell()
        temp.seek(0)
        return None, response
    except BaseException, e:
        print e
        return e, None


def exportMultiLayersData(layers, encoding, EPSG, format):
    try:
        dstSpatialRef = osr.SpatialReference()
        dstSpatialRef.ImportFromEPSG(EPSG)
        driver = ogr.GetDriverByName(ogrDriver_dic[format])
        dstDir = tempfile.mkdtemp()
        dstFile = str(os.path.join(dstDir, layers[0].filename+filenameExt_dic[format]))
        datasource = driver.CreateDataSource(dstFile)
        for layer in layers:

            vlayer = datasource.CreateLayer(str(layer.filename),dstSpatialRef)

            #retrive attributes
            for attr in layer.attribute_set.all():
                field = ogr.FieldDefn(str(attr.name), attr.type)
                field.SetWidth(attr.width)
                field.SetPrecision(attr.precision)
                vlayer.CreateField(field)

            #save features in shapefile
            srcSpatialRef = osr.SpatialReference()
            srcSpatialRef.ImportFromEPSG(3857)
            coordTransform = osr.CoordinateTransformation(srcSpatialRef, dstSpatialRef)
            geomField = utils.calcGeometryField(layer.geom_type)
            for feature in layer.feature_set.all().order_by('id_relat'):

                if geometry:
                    geometry = getattr(feature, geomField)
                    geometry = utils.unwrapGEOSGeometry(geometry)
                    dstGeometry = ogr.CreateGeometryFromWkt(geometry.wkt)
                    dstGeometry.Transform(coordTransform)
                else:
                    dstGeometry = None

            #save attributes in the shapefile
                dstFeature = ogr.Feature(vlayer.GetLayerDefn())
                dstFeature.SetGeometry(dstGeometry)
                for attrName, attrValue in feature.attribute_value.iteritems():
                    attribute = Attribute.objects.get(name=str(attrName), shapefile=feature.shapefile)
                    utils.setOGRFeatureAttribute(attribute, attrValue, dstFeature, encoding)
                vlayer.CreateFeature(dstFeature)
                dstFeature.Destroy()
        datasource.Destroy()

        #compress the shapefile
        temp = tempfile.TemporaryFile()
        zip = zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED)
        shapefileBase = os.path.splitext(dstFile)[0]
        shapefileName = os.path.splitext(layer.filename)[0]
        for fName in os.listdir(dstDir):
            zip.write(os.path.join(dstDir, fName), fName)
        zip.close()

        #delete temporary files
        shutil.rmtree(dstDir)

        #return the zip to user
        f = FileWrapper(temp)
        response = StreamingHttpResponse(f, content_type="application/zip")
        response['Content-Disposition'] = "attachment; filename=" + shapefileName + fileExt_dic[format]
        response['Content-Length'] = temp.tell()
        temp.seek(0)

        return None, response

    except BaseException, e:
        print "test" + e
        return e.rstrip('\n'), None




