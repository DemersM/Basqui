import json
from django.utils.functional import curry
from maps.models import *
from maps.forms import *
from maps.tms import tileMapConfig
from layers.models import *
from layers.utils import extentArea
from owslib.wms import WebMapService
from django.contrib.gis.geos import Point
from django.shortcuts import *
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count
from django.template import RequestContext
from django.forms.models import modelformset_factory
from django.forms.util import ErrorList
from django.template.loader import render_to_string
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib import messages



@login_required(login_url='/accounts/login/')
def initMapsLayout(request):
    root_folder = Folder.objects.get(level=0, created_by=request.user)
    return render(request,"maps/maps_layout.html", {'folder':root_folder},context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def fixMap(request):
    post_dict = dict(request.POST.copy().iteritems())
    pnt = Point(float(post_dict['center_lon']), float(post_dict['center_lat']), srid=3857)
    pnt.transform('4326')
    map_selected = BasquiMap.objects.get(id=post_dict['map_id'])
    map_selected.zoom_level = post_dict['zoom']
    map_selected.center_lat = round(pnt.y,2)
    map_selected.center_long = round(pnt.x,2)
    map_selected.map_height = post_dict['map_height']
    map_selected.map_width = post_dict['map_width']
    map_selected.save()
    layers_ordered = LayerMapOptions.objects.filter(basqui_map=map_selected).order_by('position')
    layerForm = modelformset_factory(LayerMapOptions, form=LayerMapOptionsForm, extra=0, can_delete=True)
    form = MapOptionsForm(instance=map_selected)
    formset = layerForm(queryset=layers_ordered)
    messages.success(request, "Map fixed at current size and position.")

    return render_to_response("maps/maps_optionsForms.html", {'form': form, 'formset': formset, 'map': map_selected, 'layersOrder': layers_ordered,},context_instance=RequestContext(request))


#----------------------------------------------------------------------------------
# Message Board functions
#----------------------------------------------------------------------------------


def publishMap(request, user_id, map_id):
    map_published = get_object_or_404(BasquiMap, id=map_id)
    if map_published.in_use:
        return render_to_response('maps/maps_publish.html', {'map': map_published})
    return Http404


#----------------------------------------------------------------------------------
# Map functions
#----------------------------------------------------------------------------------

@login_required(login_url='/accounts/login/')
def selectLayers(request, map_id):
    root_folder = Folder.objects.get(level=0, created_by=request.user)
    js = render_to_string("maps/js/maps_selectLayers.js", {'folder':root_folder, 'map_id': map_id},context_instance=RequestContext(request))
    response = json.dumps(js)
    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def saveSelectedLayers(request, map_id):
    map_selected = BasquiMap.objects.get(pk=map_id, created_by=request.user)
    layers_selected_ids = request.POST.getlist('layers_ids')
    layerMapOptions = LayerMapOptions.objects.filter(basqui_map=map_selected)
    helper = LayerMapOptionsFormSetHelper()

    try:
        layers_selected = Shapefile.objects.filter(pk__in = layers_selected_ids)
        count = layerMapOptions.count()
        added_layers = [layer for layer in layers_selected if layer.pk not in layerMapOptions.values_list('layer', flat=True)]
        removed_layers = [layer for layer in layerMapOptions if layer.layer not in layers_selected]
        for idx,layer in enumerate(added_layers):
            LayerMapOptions.objects.create(basqui_map=map_selected, layer=layer, position=idx+count)
        for layer in removed_layers:
            layer.delete()
        messages.success(request, "Layers selection updated.")
    except Exception, e: #no layer selected
        layerMapOptions.delete()

    tileMapConfig(map_id)
    layers_ordered = LayerMapOptions.objects.filter(basqui_map=map_selected).order_by('position')
    layerForm = modelformset_factory(LayerMapOptions, form=LayerMapOptionsForm, extra=0)
    formset = layerForm(queryset=layers_ordered)
    html =  render_to_string("maps/maps_layerMapOptionsFormset.html", {'formset': formset, 'helper': helper},context_instance=RequestContext(request))
    response = json.dumps(html)
    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def initMapViewer(request):
    map_id = request.POST.get('node_id')
    map_selected = BasquiMap.objects.get(pk=map_id, created_by=request.user)
    nodes = map_selected.get_ancestors(include_self=True).exclude(level=0)

    layers_ordered = LayerMapOptions.objects.filter(basqui_map=map_selected).order_by('position')

    layerForm = modelformset_factory(LayerMapOptions, form=LayerMapOptionsForm, extra=0)
    form = MapOptionsForm(instance=map_selected)
    formset = layerForm(queryset=layers_ordered)
    helper = LayerMapOptionsFormSetHelper()

    tmsURL = "/basqui/tms/map/%s/${z}/${x}/${y}.png" % str(map_id)
    html = render_to_string("maps/maps_viewer.html", {'form': form, 'formset': formset, 'helper': helper, 'map': map_selected, 'nodes': nodes}, context_instance=RequestContext(request))
    js = render_to_string("maps/js/maps_viewer.js", {'map': map_selected, 'tmsURL' : tmsURL, }, context_instance=RequestContext(request))
    response = json.dumps({"html":html, "js":js})
    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def saveMapOptions(request):
    map_id = request.POST.get('map_id')
    map_selected = BasquiMap.objects.get(pk=map_id, created_by=request.user)
    layerForm = modelformset_factory(LayerMapOptions, form=LayerMapOptionsForm, extra=0)
    helper = LayerMapOptionsFormSetHelper()

    try:
        pk_list = [int(x) for x in request.POST.get("layersOrder").split(',')]
    except ValueError:
        pk_list = []

    form = MapOptionsForm(request.POST, instance=map_selected)
    formset = layerForm(request.POST)
    if form.is_valid() and formset.is_valid():
        form.save()
        for _form in formset:
            instance = _form.instance
            instance.position = pk_list.index(instance.pk)
            instance.save()
        formset.save()
        tileMapConfig(map_id)
        messages.success(request, "Change(s) saved successfully.")
    else:
        messages.error(request, "Form error(s)")

    layers_ordered = LayerMapOptions.objects.filter(basqui_map=map_selected).order_by('position')
    formset = layerForm(queryset=layers_ordered)

    return render_to_response("maps/maps_optionsForms.html", {'form': form, 'formset': formset, 'helper': helper, 'map': map_selected},context_instance=RequestContext(request))


@login_required(login_url='/accounts/login/')
def saveLayerMapOptions(request, map_id):
    map_selected = BasquiMap.objects.get(pk=map_id, created_by=request.user)
    layerForm = modelformset_factory(LayerMapOptions, form=LayerMapOptionsForm, extra=0)
    helper = LayerMapOptionsFormSetHelper()

    try:
        pk_list = [int(x) for x in request.POST.get("layersOrder").split(',')]
    except ValueError:
        pk_list = []

    formset = layerForm(request.POST)
    if formset.is_valid():
        for form in formset:
            instance = form.instance
            instance.position = pk_list.index(instance.pk)
            instance.save()
        formset.save()
        tileMapConfig(map_id)

    layers_ordered = LayerMapOptions.objects.filter(basqui_map=map_selected).order_by('position')
    formset = layerForm(queryset=layers_ordered)

    return render_to_response("maps/maps_layerMapOptionsFormset.html", {'formset': formset, 'helper': helper},context_instance=RequestContext(request))



@login_required(login_url='/accounts/login/')
def createMap(request):
    folder_id = request.POST.get('node_id')
    folder = Folder.objects.get(pk=folder_id, created_by=request.user)

    if type(folder) != Folder:
        folder = folder.parent

    nodes = folder.get_ancestors(include_self=True).exclude(level=0)
    form = CreateMapForm()
    html = render_to_string("maps/maps_create.html", {'folder': folder, 'nodes': nodes, 'form': form}, context_instance=RequestContext(request))
    response = json.dumps({'html': html})

    if len(request.POST) > 1:
        form = CreateMapForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.created_by = request.user
            instance.parent = folder
            instance.save()

            for idx, layer in enumerate(form.cleaned_data.get('layers')):
                layer_instance = LayerMapOptions(layer=layer, basqui_map=instance, position=idx)
                layer_instance.save()

            tileMapConfig(instance.pk)
            response = json.dumps({"map": {"pk": instance.pk, "name": instance.name}}, cls=DjangoJSONEncoder)

    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def setLayerStyle(request):
    layerMapOptions_id = request.POST.get('layer_id')
    layerMapOptions = LayerMapOptions.objects.get(pk=layerMapOptions_id)
    saveStatus = None
    markers = Marker.objects.all()

    if layerMapOptions.layer.geom_type == 'Point':
        styleForm = modelformset_factory(LayerStyle, form=PointLayerStyleForm, extra=1, can_delete=True)
    elif layerMapOptions.layer.geom_type == 'LineString':
        styleForm = modelformset_factory(LayerStyle, form=PolylineLayerStyleForm, extra=1, can_delete=True)
    else:
        styleForm = modelformset_factory(LayerStyle, form=PolygonLayerStyleForm, extra=1, can_delete=True)

    if len(request.POST) > 1:

        pk_list = request.POST.get("layerStyleOrder").split(',')

        formset = styleForm(request.POST)
        print formset.errors
        if formset.is_valid():
            for form in formset:
                instance = form.save(commit=False)
                instance.layerMapOptions = layerMapOptions
                instance.position = pk_list.index(str(instance.pk))
                if instance.pk:
                    instance.save()

            formset.save()
            tileMapConfig(layerMapOptions.basqui_map.pk)
            saveStatus = 'success'
        else:
            html = render_to_string("maps/maps_layerStyle.html", {'layerStyleFormset': formset, 'layer': layerMapOptions}, context_instance=RequestContext(request))
            response = json.dumps({'save': 'error', 'html': html})
            return HttpResponse(response, content_type="application/json")

    layerStyles = LayerStyle.objects.filter(layerMapOptions=layerMapOptions).order_by('position')
    formset = styleForm(queryset=layerStyles)
    html = render_to_string("maps/maps_layerStyle.html", {'markers': markers, 'layerStyleFormset': formset, 'layer': layerMapOptions}, context_instance=RequestContext(request))
    response = json.dumps({'save': saveStatus, 'html': html})
    return HttpResponse(response, content_type="application/json")


@login_required(login_url='/accounts/login/')
def setLayerLabel(request):
    layerMapOptions_id = request.POST.get('layer_id')
    layerMapOptions = LayerMapOptions.objects.get(pk=layerMapOptions_id)
    attributes = Attribute.objects.filter(shapefile=layerMapOptions.layer)
    labelForm = modelformset_factory(LayerLabel, form=LayerLabelForm, extra=1, can_delete=True)
    labelForm.form = staticmethod(curry(LayerLabelForm, attributes=attributes))
    saveStatus = None

    if len(request.POST) > 1:

        pk_list = request.POST.get("layerLabelOrder").split(',')
        print pk_list
        formset = labelForm(request.POST)
        print formset.errors
        if formset.is_valid():
            for form in formset:
                instance = form.save(commit=False)
                instance.layerMapOptions = layerMapOptions
                instance.position = pk_list.index(str(instance.pk))
                if instance.pk:
                    instance.save()
            formset.save()
            tileMapConfig(layerMapOptions.basqui_map.pk)
            saveStatus = 'success'
        else:
            html = render_to_string("maps/maps_layerLabel.html", {'layerLabelFormset': formset, 'layer': layerMapOptions}, context_instance=RequestContext(request))
            response = json.dumps({'save': 'error', 'html': html})
            return HttpResponse(response, content_type="application/json")

    layerLabels = LayerLabel.objects.filter(layerMapOptions=layerMapOptions)
    formset = labelForm(queryset=layerLabels)
    html = render_to_string("maps/maps_layerLabel.html", {'layerLabelFormset': formset, 'layer': layerMapOptions}, context_instance=RequestContext(request))
    response = json.dumps({'save': saveStatus, 'html': html})
    return HttpResponse(response, content_type="application/json")