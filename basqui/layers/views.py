import traceback
import json
import datetime
import numpy as np
from osgeo import ogr
from trees.models import *
from maps.models import *
from maps.views import *
from maps.forms import *
from layers.models import *
from layers.shapefileIO import importData, importOSMData, exportData, exportMergedData, exportMultiLayersData
from layers.utils import getMapForm, calcGeometryField, wrapGEOSGeometry, findFeature, calcSearchRadius, updateTiles, extentArea, geometryNameToOgrType, forceOgrMulti
from polysimplify import GDALSimplifier, VWSimplifier
from owslib.wms import WebMapService
from django.db import connection
from django.contrib.gis.gdal import OGRGeometry
from django.contrib.gis.geos.geometry import MultiPolygon, MultiLineString
from django.db.models import Max
from django.shortcuts import *
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ObjectDoesNotExist
from django.template import RequestContext
from django.template.loader import render_to_string
from django.forms.models import modelformset_factory, inlineformset_factory
from django.contrib import messages


@login_required(login_url='/accounts/login/')
def listWMS(request):
    wms_list = WMS.objects.filter(created_by=request.user)
    if request.POST.get('delete'):
        WMS.objects.filter(pk__in=request.POST.getlist('selection')).delete()
    for wms in wms_list:
        instance = WebMapService(wms.url)
        wms.title = instance.identification.title
        wms.type = instance.identification.type
        wms.version = instance.identification.version

    wms_table = WMSListTable(wms_list)
    RequestConfig(request).configure(wms_table)
    return render(request,"layers/wms/layers_wms_list.html", {'wms_table':wms_table},context_instance=RequestContext(request))


##@login_required(login_url='/accounts/login/')
##def listLayers(request):
##    shapefiles = Shapefile.objects.filter(created_by=request.user)
##    wms = WMS.objects.filter(created_by=request.user)
##    map_shapefiles = BasquiMap.objects.filter(created_by=request.user).annotate(Count('layers')).filter(layers__count__gte=1)
##    map_wms = BasquiMap.objects.filter(created_by=request.user).annotate(Count('wms')).filter(wms__count__gte=1)
##
##    shapefiles_data = {'type':'shapefile',
##                        'instance': shapefiles.count(),
##                        'map_instance': map_shapefiles.count(),
##                        'last_created_instance': shapefiles.latest('date_created'),
##                        'last_created': shapefiles.latest('date_created').date_created,
##                        'last_edited_instance': shapefiles.latest('date_updated'),
##                        'last_edited': shapefiles.latest('date_updated').date_updated,
##                        'messages':''}
##
##    wms_data = {'type':'wms',
##                'instance': wms.count(),
##                'map_instance': map_wms.count(),
##                'last_created_instance': wms.latest('date_created'),
##                'last_created': wms.latest('date_created').date_created,
##                'last_edited_instance': wms.latest('date_updated'),
##                'last_edited': wms.latest('date_updated').date_updated,
##                'messages':''}
##
##    data = []
##    data.extend((shapefiles_data, wms_data))
##    layers_table = LayersTable(data)
##
##    RequestConfig(request).configure(layers_table)
##    return render(request,"basqui/manage_layer_list.html", {'layers_table':layers_table},context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def initLayersLayout(request):
    root_folder = Folder.objects.get(level=0, created_by=request.user)
    return render(request,"layers/layers_layout.html", {'folder':root_folder},context_instance=RequestContext(request))


#----------------------------------------------------------------------------------
# Attributes Table functions
#----------------------------------------------------------------------------------

def attributeTableLoader(request, shapefile_id):
    features_selected = Feature.objects.filter(shapefile__pk=shapefile_id).order_by('id_relat')
    data = [dict(feature.attribute_value, **{"id":str(feature.id_relat)}) for feature in features_selected]
    jsonData = json.dumps(data)
    return HttpResponse(jsonData, content_type="application/json")


@login_required(login_url='/accounts/login/')
def attributesTable(request, shapefile_id):
    layer = Shapefile.objects.get(pk=shapefile_id, created_by=request.user)
    nodes = layer.get_ancestors(include_self=True).exclude(level=0)
    features_count = Feature.objects.filter(shapefile__pk=shapefile_id).count()
    attributes = Attribute.objects.filter(shapefile__pk=shapefile_id).order_by('name')
    tmsURL = "http://" + request.get_host() + "/basqui/tms/"

    html = render_to_string("layers/vector/layers_vector_attributesTable.html", {'columns':attributes, 'layer':layer,'features_count':features_count, 'nodes':nodes}, context_instance=RequestContext(request))
    js = render_to_string("layers/vector/js/layers_vector_attributesTable.js", {'columns':attributes, 'layer':layer, 'tmsURL': tmsURL}, context_instance=RequestContext(request))

    response = json.dumps({'html': html, 'js':js})
    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def editField(request, shapefile_id):
    layer = Shapefile.objects.get(pk=shapefile_id, created_by=request.user)
    attributes = Attribute.objects.filter(shapefile=layer)
    nodes = layer.get_ancestors(include_self=True).exclude(level=0)
    attributesFormset = modelformset_factory(Attribute, form=AttributeForm, extra=1, can_delete=True)
    formset = attributesFormset(queryset=attributes)
    helper = AttributesFormSetHelper()

    if request.POST:
        formset = attributesFormset(request.POST)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                try:
                    original = instance._meta.model.objects.get(pk=instance.pk)
                except ObjectDoesNotExist:
                    original = None

                try:
                    instance.shapefile = layer
                    instance.save()

                except IntegrityError:
                    errMsg = "Attribute with name %s already exists for this layer" % instance.name
                    html = render_to_string("layers/vector/layers_vector_editField.html", {'layer': layer, 'nodes': nodes, 'formset':formset, 'helper':helper, 'errMsg':errMsg}, context_instance=RequestContext(request))
                    js = render_to_string("layers/vector/js/layers_vector_editField.js", context_instance=RequestContext(request))
                    response = json.dumps({'html': html, 'js':js})
                    return HttpResponse(response, content_type="application/json")

                else:
                    if original and original.name != instance.name:
                        features_selected = Feature.objects.filter(shapefile=layer, attribute_value__contains=[original.name])
                        for feature in features_selected:
                                print feature
                                feature.attribute_value[instance.name] = feature.attribute_value.pop(original.name)
                                feature.save(update_fields=['attribute_value'])


    html = render_to_string("layers/vector/layers_vector_editField.html", {'layer': layer, 'nodes': nodes, 'formset':formset, 'helper': helper}, context_instance=RequestContext(request))
    js = render_to_string("layers/vector/js/layers_vector_editField.js", context_instance=RequestContext(request))
    response = json.dumps({'html': html, 'js':js})
    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def updateAttributesTable(request, shapefile_id):
    try:
        post_dict = dict(request.POST.copy().iteritems())
        feature_id = post_dict['id']

        del post_dict['id']
        feature_selected = Feature.objects.get(id_relat=feature_id, shapefile__pk=shapefile_id, shapefile__created_by=request.user)


    except BaseException, e:
        return HttpResponse('error')

    data = []
    for key, value in post_dict.iteritems():
        print key
        attribute_selected = Attribute.objects.get(shapefile__pk=shapefile_id, name=key)
        if value == '':
            post_dict[key] = None
        elif attribute_selected.type == 0:
            try:
                int(value)
            except ValueError:
                json_error = json.dumps({"error": "Type error in column: %s. Value must be an integer." % (attribute_selected.name)})
                return HttpResponse(json_error, content_type="application/json")
            else:
                if int(value) >= 10 ** attribute_selected.width:
                    json_error = json.dumps({"error": "Type error in column: %s. Value's width must be maximum %s." % (attribute_selected.name, attribute_selected.width)})
                    return HttpResponse(json_error, content_type="application/json")
        elif attribute_selected.type == 2:
            try:
                if float(value) < 10** attribute_selected.width:
                    value = "{value:{width}.{precision}f}".format(value=float(value), width=attribute_selected.width, precision=attribute_selected.precision)
                    post_dict[key]= value.lstrip()
                else:
                    json_error = json.dumps({"error": "Type error in column: %s. Value's width must be %s maximum." % (attribute_selected.name, attribute_selected.width)})
                    return HttpResponse(json_error, content_type="application/json")
            except:
                json_error = json.dumps({"error": "Type error in column: %s. Value must be a float." % (attribute_selected.name)})
                return HttpResponse(json_error, content_type="application/json")
        elif attribute_selected.type == 9:
            try:
                datetime.datetime.strptime(value, '%Y-%m-%d')
            except:
                json_error = json.dumps({"error": "Value type error in column: %s.\n Value must be a valid date in iso format (YYYY-MM-DD)." % (attribute_selected.name)})
                return HttpResponse(json_error, content_type="application/json")
        elif attribute_selected.type == 10:
            try:
                datetime.datetime.strptime(value, '%H:%M:%S')
            except:
                json_error = json.dumps({"error": "Value type error in column: %s.\n Value must be a valid date in iso format (HH:MM:SS)." % (attribute_selected.name)})
                return HttpResponse(json_error, content_type="application/json")
        elif len(value) > attribute_selected.width:
                json_error = json.dumps({"error": "Type error in column: %s. Value's width must be %s maximum." % (attribute_selected.name, attribute_selected.width)})
                return HttpResponse(json_error, content_type="application/json")

    feature_selected.attribute_value = post_dict
    feature_selected.save(update_fields=['attribute_value'])
    post_dict['id'] = feature_id
    response = json.dumps({"saved":"Change has been saved in feature (ID:%s)." % feature_id, 'data': post_dict})
    return HttpResponse(response, content_type="application/json")


def addFeatureToTable(request, shapefile_id):
    try:
        shapefile = Shapefile.objects.get(pk=shapefile_id, created_by=request.user)
        feature = Feature.objects.create(shapefile=shapefile)
        response = json.dumps({"saved": "New feature (ID: %s) added into %s." % (feature.id_relat, shapefile.name), 'data' : {'id': feature.id_relat} })
        return HttpResponse(response, content_type="application/json")
    except:
        json_error = json.dumps({"error":"Error creating new feature."})
        return HttpResponse(json_error, content_type="application/json")


def deleteFeatureToTable(request, shapefile_id):
    try:
        shapefile = Shapefile.objects.get(pk=shapefile_id, created_by=request.user)
        post_list = map(int, request.POST.getlist("feat_id[]"))
        post_list.sort()
        for features_id in post_list:
            features_selected = Feature.objects.get(shapefile=shapefile, id_relat=features_id)
            features_selected.delete()
        json_saved = json.dumps({"saved": "%s feature(s) (ID: %s) deleted sucessfully from %s." % (len(post_list), ','.join(map(str, post_list)), shapefile.name) })

        return HttpResponse(json_saved, content_type="application/json")
    except:
        json_error = json.dumps({"error":"Error deleting feature(s)."})
        return HttpResponse(json_error, content_type="application/json")


#----------------------------------------------------------------------------------
# Vector viewer functions (attributes, geometry and mapping)
#----------------------------------------------------------------------------------

@login_required(login_url='/accounts/login/')
def initVectorViewer(request, shapefile_id):
    try:
        shapefile = Shapefile.objects.get(id=shapefile_id, created_by=request.user)
        nodes = shapefile.get_ancestors(include_self=True).exclude(level=0)
        features = Feature.objects.filter(shapefile=shapefile)
        geometryField = calcGeometryField(shapefile.geom_type)
    except Shapefile.DoesNotExist or Feature.DoesNotExist:
        raise Http404

    bounds = list(features.extent(field_name=geometryField))
    tmsURL = "http://" + request.get_host() + "/basqui/tms/"
    html = render_to_string("layers/vector/layers_vector_viewer.html", {'nodes': nodes, 'shapefile': shapefile },context_instance=RequestContext(request))
    js = render_to_string("layers/vector/js/layers_vector_viewer.js", {'bounds': bounds, 'shapefile' : shapefile, 'tmsURL' : tmsURL},context_instance=RequestContext(request))

    response = json.dumps({'html': html, 'js':js})
    return HttpResponse(response, content_type="application/json")


def initLightVectorViewer(request, shapefile_id):
    try:
        post_dict = dict(request.POST.copy().iteritems())
        x = int(post_dict['position[right]']) + 5
        y = int(post_dict['position[top]'])
        id_relat = post_dict['id']
        shapefile = Shapefile.objects.get(id=shapefile_id, created_by=request.user)
        feature = Feature.objects.get(shapefile=shapefile, id_relat=id_relat)
        geometryField = calcGeometryField(shapefile.geom_type)
        geometry = getattr(feature, geometryField)
        bounds = list(geometry.extent)

    except Shapefile.DoesNotExist or Feature.DoesNotExist:
        raise Http404
    except AttributeError:
        bounds = []

    response = json.dumps({'feat_id': feature.pk, 'x': x, 'y': y, 'bounds': bounds})
    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def createVectorLayer(request, folder_id):
    folder = Folder.objects.get(pk=folder_id, created_by=request.user)

    if type(folder) != Folder:
        folder = folder.parent

    nodes = folder.get_ancestors(include_self=True).exclude(level=0)

    form = CreateVectorLayerForm()
    attributesFormset = modelformset_factory(Attribute, form=AttributeForm)
    formset = attributesFormset(queryset=Attribute.objects.none())
    helper = AttributesFormSetHelper()
    html = render_to_string("layers/vector/layers_vector_create.html", {'nodes': nodes, 'folder': folder, 'form': form, 'formset': formset, 'helper': helper}, context_instance=RequestContext(request))
    js = render_to_string("layers/vector/js/layers_vector_editField.js", context_instance=RequestContext(request))
    response = json.dumps({'html': html, 'js':js})

    if request.POST:
        form = CreateVectorLayerForm(request.POST)
        formset = attributesFormset(request.POST)
        if formset.is_valid() & form.is_valid():
            layer_instance = form.save(commit=False)
            attr_instances = formset.save(commit=False)

            layer_instance.parent = folder
            layer_instance.created_by = request.user
            layer_instance.save()
            for attr in attr_instances:
                attr.shapefile = layer_instance
                attr.save()

            response = json.dumps({'layer': {"pk":layer_instance.pk, "name":layer_instance.name, "geom_type": layer_instance.geom_type}}, cls=DjangoJSONEncoder)

        else:
            html = render_to_string("layers/vector/layers_vector_create.html", {'nodes': nodes, 'folder': folder, 'form': form, 'formset': formset, 'helper': helper}, context_instance=RequestContext(request))
            response = json.dumps({'html': html, 'js':js})

    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def selectFeature(request):
    try:
        post_dict = dict(request.POST.copy().iteritems())
        layer_id = int(post_dict['layer_id'])
        latitude = float(post_dict['latitude'])
        longitude = float(post_dict['longitude'])
        layer = Shapefile.objects.get(id=layer_id, created_by=request.user)
        query = findFeature(layer, longitude, latitude)
        if query:
            geometryField = calcGeometryField(layer.geom_type)
            SQLQuery = "SELECT row_to_json(f) As %s \
                            FROM (SELECT 'Feature' As type \
                            , ST_AsGeoJSON(%s)::json As geometry \
                            , row_to_json((SELECT l FROM (SELECT id_relat AS feat_id) As l)) As properties \
                            FROM layers_feature As l WHERE l.id = %s ) As f;" % (layer.geom_type, geometryField, query.pk)
            cursor = connection.cursor()
            cursor.execute(SQLQuery)
            row = cursor.fetchone()[0]
            response = json.dumps({'geojson':row, 'feat_id':query.pk})
            return HttpResponse(response,content_type="application/json")
        else: return HttpResponse("")
    except:
        traceback.print_exc()
        return HttpResponse("")


@login_required(login_url='/accounts/login/')
def splitFeature(request):
    try:
        post_dict = dict(request.POST.copy().iteritems())
        featureCollection = json.loads(post_dict['feature'])
        blade = post_dict['blade']
        #ogrBlade = ogr.CreateGeometryFromJson(json.dumps(blade))
        layer_id = int(post_dict['layer_id'])
        layer = Shapefile.objects.get(pk=layer_id, created_by=request.user)
        output = []
        for feature in featureCollection['features']:
            SQLQuery = '''SELECT ST_AsGeoJSON(ST_Collect(ST_MULTI(geom)))::json FROM (SELECT (ST_Split(ST_GeomFromGeoJSON('%s'),ST_GeomFromGeoJSON('%s')))) As f''' % (json.dumps(feature['geometry']),blade)
            cursor = connection.cursor()
            cursor.execute(SQLQuery)
            row = cursor.fetchone()[0]
            print row
            feature['geometry'] = row['geometries'][0]
            output.append(({"type": "feature", "geometry": row['geometries'][1]}))
        featureCollection['features'].extend(output)
        response = json.dumps(featureCollection)
        return HttpResponse(response,content_type="application/json")

    except:
        traceback.print_exc()
        return HttpResponse("")


@login_required(login_url='/accounts/login/')
def eraseFeature(request):
    try:
        post_dict = dict(request.POST.copy().iteritems())
        featureCollection = json.loads(post_dict['feature'])
        mask =  json.loads(post_dict['mask'])
        ogrMask = ogr.CreateGeometryFromJson(json.dumps(mask))
        layer_id = int(post_dict['layer_id'])
        layer = Shapefile.objects.get(pk=layer_id, created_by=request.user)
        for feature in featureCollection['features']:
            geometry = ogr.CreateGeometryFromJson(json.dumps(feature['geometry']))
            output = geometry.Difference(ogrMask)
            output = forceOgrMulti(output, layer.geom_type)
            feature['geometry'] = json.loads(output.ExportToJson())

        response = json.dumps(featureCollection)
        return HttpResponse(response,content_type="application/json")

    except:
        traceback.print_exc()
        return HttpResponse("")


@login_required(login_url='/accounts/login/')
def unionFeature(request):
    try:
        post_dict = dict(request.POST.copy().iteritems())
        layer_id = int(post_dict['layer_id'])
        featureCollection = json.loads(post_dict['feature'])
        layer = Shapefile.objects.get(pk=layer_id, created_by=request.user)
        output = ogr.Geometry(geometryNameToOgrType(layer.geom_type))
        for feature in featureCollection['features']:
            geometry = ogr.CreateGeometryFromJson(json.dumps(feature['geometry']))
            feature['geometry'] = None
            output = output.Union(geometry)

        output = forceOgrMulti(output, layer.geom_type)
        featureCollection['features'][0]['geometry'] = json.loads(output.ExportToJson())
        response = json.dumps(featureCollection)
        return HttpResponse(response,content_type="application/json")

    except:
        traceback.print_exc()
        return HttpResponse("")

@login_required(login_url='/accounts/login/')
def saveEdits(request):
    try:
        post_dict = dict(request.POST.copy().iteritems())
        layer_id = post_dict['layer_id']
        layer = Shapefile.objects.get(id=layer_id, created_by=request.user)
        geometryField = calcGeometryField(layer.geom_type)
        featureCollection = json.loads(post_dict['feature'])
        for feature in featureCollection['features']:
            try:
                feat_id = feature['properties']['feat_id']
                feat = Feature.objects.get(id_relat=int(feat_id), shapefile=layer)
            except KeyError:
                feat = Feature.objects.create(shapefile=layer)

            setattr(feat, geometryField, json.dumps(feature['geometry']))
            feat.save()

        return HttpResponse('')

    except:
        traceback.print_exc()
        return HttpResponse("")


@login_required(login_url='/accounts/login/')
def hoverFeature(request):
    try:
        layer_id = int(request.GET['shapefile_id'])
        latitude = float(request.GET['latitude'])
        longitude = float(request.GET['longitude'])
        layer = Shapefile.objects.get(id=layer_id, created_by=request.user)
        query = findFeature(layer,longitude,latitude)
        attributes = Attribute.objects.filter(shapefile=layer).order_by('name')

        if query:
            feat_data={}
            for attribute in attributes:
                try:
                    value = query.attribute_value[attribute.name]
                except:
                    value = None
                feat_data[attribute.name] = value

            formset = HoverFeatureAttributeForm(feat_data=feat_data, feat_id_relat=query.id_relat)
            return render_to_response("layers/vector/layers_vector_featureAttributes.html", {'formset': formset },context_instance=RequestContext(request))
        else:
            return HttpResponse('<i>No feature</i>')
    except:
        traceback.print_exc()
        return HttpResponse("")


@login_required(login_url='/accounts/login/')
def simplifyVectorLayer(request):
    post_dict = dict(request.POST.copy().iteritems())
    layer_id = post_dict['id']
    ratio = post_dict['ratio']
    layer = Shapefile.objects.get(pk=layer_id)
    features = Feature.objects.filter(shapefile=layer)
    geometryField = calcGeometryField(layer.geom_type)
    for feat in features:
        geometry = getattr(feat, geometryField)
        simplifier = GDALSimplifier(geometry.ogr)
        VWGeometry = simplifier.from_ratio(float(ratio))
        setattr(feat, geometryField, VWGeometry.wkt)
        feat.save()

    response = "Layer simplified"

    return HttpResponse(response, content_type="application/json")

@login_required(login_url='/accounts/login/')
def importVector(request, folder_id):
    folder = Folder.objects.get(pk=folder_id, created_by=request.user)

    if type(folder) != Folder:
        folder = folder.parent

    nodes = folder.get_ancestors(include_self=True).exclude(level=0)
    form = ImportVectorForm()

    if request.POST:
        form = ImportVectorForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            encoding = request.POST['character_encoding']
            format = request.POST['format']
            errMsg, layer = importData(file, encoding, format, request.user, folder)

            if not errMsg:
                messages.success(request, "%s imported successfully as %s." % (file, layer.name))
                html = render_to_string("layers/vector/layers_vector_import.html", {'form': form, 'folder':folder, 'nodes':nodes},context_instance=RequestContext(request))
                response = json.dumps({'html': html, 'layer': {"pk":layer.pk, "name": layer.name, "geom_type": layer.geom_type}}, cls=DjangoJSONEncoder)
                return HttpResponse(response, content_type="application/json")

            else:
                messages.error(request, errMsg)


    html = render_to_string("layers/vector/layers_vector_import.html", {'form': form, 'folder':folder, 'nodes':nodes},context_instance=RequestContext(request))
    response = json.dumps({'html': html})
    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def importOSM(request, folder_id):
    folder = Folder.objects.get(pk=folder_id, created_by=request.user)

    if type(folder) != Folder:
        folder = folder.parent

    nodes = folder.get_ancestors(include_self=True).exclude(level=0)
    form = ImportOSMForm()

    if request.POST:
        query = request.POST['query']
        layer_name = request.POST['name']
        errMsg, layer = importOSMData(query, layer_name, request.user, folder)

    html = render_to_string("layers/vector/layers_vector_importOSM.html", {'form': form, 'folder':folder, 'nodes': nodes},context_instance=RequestContext(request))
    js = render_to_string("layers/vector/js/layers_vector_drawBBox.js",context_instance=RequestContext(request))

    response = json.dumps({'html': html, 'js':js})
    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def exportVector(request, folder_id):
    folder = Folder.objects.get(pk=folder_id, created_by=request.user)

    if type(folder) != Folder:
        folder = folder.parent

    nodes = folder.get_ancestors(include_self=True).exclude(level=0)
    form = ExportVectorForm(user=request.user, parent=folder)

    if request.POST:
        form = ExportVectorForm(request.POST, user=request.user, parent=folder)
        if form.is_valid():
            layers = form.cleaned_data.get('layers')
            merge = form.cleaned_data.get('merge')
            encoding = request.POST['character_encoding']
            EPSG = int(request.POST['EPSG'])
            format = request.POST['format']

            if merge:
                errMsg, output = exportMergedData(layers, encoding, EPSG, format)
            elif format == "sqlite" or format == "kml":
                errMsg, output = exportMultiLayersData(layers, encoding, EPSG, format)
            else:
                errMsg, output = exportData(layers, encoding, EPSG, format)

            if errMsg == None:
                messages.success(request, "%s.%s (EPSG:%s) exported successfully." % ("test", format, EPSG))
                return output
            else:
                messages.error(request, errMsg)

    html = render_to_string("layers/vector/layers_vector_export.html", {'form': form, 'folder':folder, 'nodes':nodes},context_instance=RequestContext(request))
    response = json.dumps({'html': html})
    return HttpResponse(response, content_type="application/json")


#----------------------------------------------------------------------------------
# Raster layers functions
#----------------------------------------------------------------------------------

@login_required(login_url='/accounts/login/')
def viewerRaster(request):
    findFeatureURL = "http://" + request.get_host() + "/basqui/layer/shapefile/findFeature"
    tmsURL = "http://" + request.get_host() + "/basqui/tms/"
    return render_to_response("layers/raster/layers_raster_viewer.html", {'tmsURL' : tmsURL},context_instance=RequestContext(request))


#----------------------------------------------------------------------------------
# WMS layers functions
#----------------------------------------------------------------------------------

@login_required(login_url='/accounts/login/')
def newWMS(request):
    form = NewWMSForm()
    if request.POST.get('find'):
        form = NewWMSForm(request.POST)
        if form.is_valid():
            srs = "EPSG:%s" % request.POST['srs']
            try:
                ows = WebMapService(request.POST['url'])
            except:
                form._errors["url"] = ErrorList([u"This is not a valid WMS url."])
                return render_to_response("layers/wms/layers_wms_new.html", {'form': form}, context_instance=RequestContext(request))

            wmsLayers = [ wmsLayer for wmsLayer in ows.contents if srs in ows[wmsLayer].crsOptions ]
            return render_to_response("layers/wms/layers_wms_new.html", {'form': form, 'wmsLayers':wmsLayers, 'srs':srs}, context_instance=RequestContext(request))

    if request.POST:
        form = NewWMSForm(request.POST)
        if form.is_valid():
            wmsInstance = form.save(commit=False)
            wmsInstance.created_by = request.user
            try:
                ows = WebMapService(wmsInstance.url)
            except:
                form._errors["url"] = ErrorList([u"This is not a valid WMS url."])
                return render_to_response("layers/wms/layers_wms_new.html", {'form': form}, context_instance=RequestContext(request))
            try:
                wmsInstance.save()
            except IntegrityError:
                form._errors["alias"] = ErrorList([u"This name is already used."])
                return render_to_response("layers/wms/layers_wms_new.html", {'form': form}, context_instance=RequestContext(request))
            else:
                srs = "EPSG:%s" % wmsInstance.srs
                for idx,layer in enumerate(ows.contents):
                    if srs in ows[layer].crsOptions:
                        instance = WMSLayer(wms=wmsInstance, position=idx, layer_name=str(layer))
                        instance.save()

            return HttpResponseRedirect(u"/basqui/layer/wms/edit/%s" % wmsInstance.pk)

    return render_to_response("layers/wms/layers_wms_new.html", {'form': form}, context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def editWMS(request, wms_id):
    wms = WMS.objects.get(id=wms_id, created_by=request.user)
    wmsLayers = WMSLayer.objects.filter(wms=wms).order_by('position')
    wmsLayers_in_use = wmsLayers.filter(in_use=True).order_by('-position')
    wmsLayerFormset = modelformset_factory(WMSLayer, form=WMSLayerForm, extra=0)

    try:
        ows = WebMapService(wms.url)
        bounds_list = [ows[wmsLayer.layer_name].boundingBoxWGS84
                    for wmsLayer in wmsLayers_in_use]
        bounds = max(bounds_list, key=extentArea)
    except:
        bounds = (-180, -90, 180, 90)

    formset = wmsLayerFormset(queryset=wmsLayers)
    form = EditWMSForm(instance=wms)

    if request.POST:
        try:
            pk_list = [int(x) for x in request.POST.get("layersOrder").split(',')]
        except:
            pass
        form = EditWMSForm(request.POST,instance=wms)
        formset = wmsLayerFormset(request.POST,queryset=wmsLayers)
        if form.is_valid() and formset.is_valid():
            for wmsLayerForm in formset:
                instance = wmsLayerForm.instance
                instance.position = pk_list.index(instance.pk)
                instance.save()
            try:
                form.save()
            except IntegrityError:
                form._errors["alias"] = ErrorList([u"This name is already used."])
                return render_to_response("layers/wms/layers_wms_edit.html", {'form': form, 'formset':formset, 'wms':wms, 'wmsLayers_in_use': wmsLayers_in_use, 'bounds':bounds}, context_instance=RequestContext(request))

            return HttpResponseRedirect("/basqui/layer/wms/edit/%s" % (wms.pk))

    return render_to_response("layers/wms/layers_wms_edit.html", {'form': form, 'formset':formset, 'wms':wms, 'wmsLayers_in_use': wmsLayers_in_use, 'bounds':bounds}, context_instance=RequestContext(request))
