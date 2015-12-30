import os, os.path, tempfile, zipfile
import shutil, traceback, stat, errno
import time
import utils
from django.contrib.gis.geos.geometry import GEOSGeometry
from django.http import StreamingHttpResponse
from django.core.servers.basehttp import FileWrapper
from layers.wkt import dumps
from osgeo import ogr, osr
from layers.models import Shapefile, Attribute, Feature
from collections import defaultdict


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
    start_time = time.time()
    try:
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
            if info.filename.endswith(filenameExt_dic[format]):
                shapefileName = info.filename
            dstFile = os.path.join(dirname, info.filename)
            f = open(dstFile, "wb")
            f.write(zip.read(info.filename))
            f.close()
        zip.close()

        #verify if shapefile is valid
        driver = ogr.GetDriverByName(ogrDriver_dic[format])
        datasource = driver.Open(os.path.join(dirname,shapefileName))

        for i in range(datasource.GetLayerCount()):
            layer = datasource.GetLayer(i)
            srcSpatialRef = layer.GetSpatialRef()
            geometryType = layer.GetGeomType()
            geometryName = utils.ogrTypeToGeometryName(geometryType)
            print "geometry type:" + str(geometryType), geometryName
            srs_wkt=srcSpatialRef.ExportToWkt()
            shapefile = Shapefile.objects.create(name=layer.GetName(), parent=folder, srs_wkt=srs_wkt, geom_type=geometryName, encoding=characterEncoding, created_by=user)

            #define shapefile's attributes
            attributes = []
            layerDef = layer.GetLayerDefn()
            for i in range(layerDef.GetFieldCount()):
                fieldDef = layerDef.GetFieldDefn(i)
                attr = Attribute(shapefile=shapefile, name=fieldDef.GetName(), type=fieldDef.GetType(), width=fieldDef.GetWidth(), precision=fieldDef.GetPrecision())
                attributes.append(attr)
            Attribute.objects.bulk_create(attributes)

            #store shapefile's features
            dstSpatialRef = osr.SpatialReference()
            dstSpatialRef.ImportFromEPSG(3857)
            coordTransform = osr.CoordinateTransformation(srcSpatialRef, dstSpatialRef)

            features = []
            for i in range(layer.GetFeatureCount()):
                srcFeature = layer.GetNextFeature()
                id = srcFeature.GetFID()
                srcGeometry = srcFeature.GetGeometryRef()
                srcGeometry.Transform(coordTransform)
                if srcGeometry.GetCoordinateDimension() == 3:
                    srcGeometry
                #geometry = GEOSGeometry(srcGeometry.ExportToWkt())
                #geometry = utils.wrapGEOSGeometry(geometry)
                #geometryField = utils.calcGeometryField(geometryName)
                multi_geom = ogr.ForceToMultiPolygon(srcGeometry)

                #Store shapefile"s attributes
                hash_attributeValue = defaultdict(dict)
                attribute_value = {}
                attributes.sort(key=lambda x:x.name.lower())
                for attr in attributes:
                    success,result = utils.getOGRFeatureAttribute(attr, srcFeature, characterEncoding)
                    if not success:
                        datasource.Destroy()
                        os.remove(fname)
                        shutil.rmtree(dirname)
                        shapefile.delete()
                        return 'Wrong character encoding', None
                    hash_attributeValue.setdefault(attr.name,result)

                feature = Feature(shapefile=shapefile, attribute_value=hash_attributeValue, id_relat=id)
                setattr(feature, 'geom_multipolygon', multi_geom.ExportToWkt() )
                features.append(feature)

            Feature.objects.bulk_create(features)

        print("Temps final: --- %s seconds ---" % str(time.time() - start_time))
        return None, shapefile

    except Exception, e:
        return e, None

    #cleaning up
    datasource.Destroy()
    os.remove(fname)
    shutil.rmtree(dirname, ignore_errors=False, onerror=handleRemoveReadonly)
    return None


def exportData(layers, encoding, EPSG, format):
    try:
        dstSpatialRef = osr.SpatialReference()
        dstSpatialRef.ImportFromEPSG(EPSG)
        driver = ogr.GetDriverByName(ogrDriver_dic[format])
        dstDir = tempfile.mkdtemp()
        for layer in layers:
            dstFile = str(os.path.join(dstDir, layer.name+filenameExt_dic[format]))
            datasource = driver.CreateDataSource(dstFile)
            vlayer = datasource.CreateLayer(str(layer.name),dstSpatialRef)

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
            shapefileName = os.path.splitext(layer.name)[0]
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
        return e, None

def exportMergedData(layers, encoding, EPSG, format):
    start_time = time.time()
    try:
        dstSpatialRef = osr.SpatialReference()
        dstSpatialRef.ImportFromEPSG(EPSG)
        driver = ogr.GetDriverByName(ogrDriver_dic[format])
        layer_name = '_'.join([layer.name for layer in layers])+"_merged"
        attributes = [attribute for layer in layers for attribute in layer.attribute_set.all()]
        features = tuple([(feature, layer.geom_type) for layer in layers for feature in layer.feature_set.all().order_by('id_relat')])

        if format == "shp":
            if len({g for f, g in features}) != 1:
                return "Shapefile format does not support different geometry types in the same layer", None

        dstDir = tempfile.mkdtemp()
        dstFile = str(os.path.join(dstDir, layer_name+filenameExt_dic[format]))
        datasource = driver.CreateDataSource(dstFile)
        vlayer = datasource.CreateLayer(str(layer.name),dstSpatialRef)

        #retrive attributes
        for attr in attributes:
            field = ogr.FieldDefn(str(attr.name), attr.type)
            field.SetWidth(attr.width)
            field.SetPrecision(attr.precision)
            fields.append(field)
            vlayer.CreateField(field)

    #save features in shapefile
        srcSpatialRef = osr.SpatialReference()
        srcSpatialRef.ImportFromEPSG(3857)
        coordTransform = osr.CoordinateTransformation(srcSpatialRef, dstSpatialRef)
        for feature, geom_type in features:
            geometry = getattr(feature, utils.calcGeometryField(geom_type))

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
        shapefileName = os.path.splitext(layer_name)[0]
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
        print("Temps final: --- %s seconds ---" % str(time.time() - start_time))
        return None, response
    except BaseException, e:
        return e, None


def exportMultiLayersData(layers, encoding, EPSG, format):
    try:
        dstSpatialRef = osr.SpatialReference()
        dstSpatialRef.ImportFromEPSG(EPSG)
        driver = ogr.GetDriverByName(ogrDriver_dic[format])
        dstDir = tempfile.mkdtemp()
        dstFile = str(os.path.join(dstDir, layers[0].name+filenameExt_dic[format]))
        datasource = driver.CreateDataSource(dstFile)

        for layer in layers:
            vlayer = datasource.CreateLayer(str(layer.name),dstSpatialRef)

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
        shapefileName = os.path.splitext(layer.name)[0]
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
        return e.rstrip('\n'), None




