import json
from maps.tms import tileMapConfig
from operator import attrgetter
from mptt.templatetags.mptt_tags import cache_tree_children
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import *
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.template.loader import render_to_string
from layers.models import *
from maps.models import *
from maps.forms import *
from trees.models import *
from trees.utils import folderTree_to_json, selectLayersTree_to_json


def home(request):
    return render_to_response('home.html',context_instance=RequestContext(request))


#----------------------------------------------------------------------------------
# Layers Tree functions
#----------------------------------------------------------------------------------


@login_required(login_url='/accounts/login/')
def initLayersTree(request):
    try:
        root_node = Folder.objects.get(created_by=request.user, category='layers')
        nodes = root_node.get_descendants(include_self=True)
        node_tree = cache_tree_children(nodes)
        for n in node_tree:
            data = (folderTree_to_json(n))

        tree = json.dumps(data, indent=4)

        return HttpResponse(tree, content_type="application/json")

    except BaseException, e:
        raise e


def listLayers(request, folder_id):
    try:
        folder = Folder.objects.get(pk=folder_id, created_by=request.user)
        nodes = folder.get_ancestors(include_self=True).exclude(level=0)
        if type(folder) == Folder:
            layers_count = Shapefile.objects.filter(parent=folder, created_by=request.user).count()
        else:
            layers_count = 1

        html = render_to_string("layers/vector//layers_vector_list.html", {'folder': folder, 'nodes': nodes, 'layers_count':layers_count},context_instance=RequestContext(request))
        js = render_to_string("layers/vector/js/layers_vector_list.js", {'folder': folder},context_instance=RequestContext(request))
        response = json.dumps({'html': html, 'js':js})

        return HttpResponse(response, content_type="application/json")

    except BaseException, e:
        raise e

def listLayersLoader(request, folder_id):
    try:
        folder = Folder.objects.get(pk=folder_id, created_by=request.user)

        if type(folder) == Folder:
            layers_list = Shapefile.objects.filter(parent=folder, created_by=request.user).order_by('name')
        else:
            layers_list = Shapefile.objects.filter(pk=folder_id, created_by=request.user).order_by('name')

        data = [{'id': layer.id, 'name': layer.name,
            'maps': [{'map_name': map.name, 'map_id': map.id} for map in layer.basquimap_set.all().order_by('name')],
            'geom_type': layer.geom_type, 'date_created': layer.date_created, 'date_updated': layer.date_updated}
            for layer in layers_list]

        jsonData = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(jsonData, content_type="application/json")

    except BaseException, e:
        raise e


def duplicateNode(request):
    try:
        post_dict = dict(request.POST.copy().iteritems())
        node_id = post_dict['node_id']
        node = Folder.objects.get(pk=node_id, created_by=request.user)

        if type(node) == Folder:
            response = "Folder selected"
            return HttpResponse(response, content_type="application/json")
        else:
            features = Feature.objects.filter(shapefile=node)
            attributes = Attribute.objects.filter(shapefile=node)

            node.pk = None
            node.id = None
            node.lft = None
            node.rght = None
            node.name = node.name + "_copy"
            node.save()
            for feat in features:
                feat.shapefile = node
                feat.pk = None
                feat.save()
            for att in attributes:
                att.shapefile = node
                att.pk = None
                att.save()

        response = json.dumps({'layer': {"pk":node.pk, "name": node.name, "geom_type": node.geom_type}}, cls=DjangoJSONEncoder)

        return HttpResponse(response, content_type="application/json")

    except BaseException, e:
        raise e


def renameNode(request):
    try:
        post_dict = dict(request.POST.copy().iteritems())
        node_id = post_dict['id']
        new_name = post_dict['name']
        node = Folder.objects.get(pk=node_id, created_by=request.user)
        node.name = new_name
        node.save()

        if type(node) == BasquiMap:
            tileMapConfig(node.pk)

        response = json.dumps({'status' : 'success'})

        return HttpResponse(response, content_type="application/json")

    except BaseException, e:
        raise e


def deleteNodes(request):
    try:
        post_dict = dict(request.POST.copy())
        nodes_id = post_dict['nodes_id']
        nodes = Folder.objects.filter(pk__in=nodes_id, created_by=request.user).order_by('-level')
        node_to_delete, nodes_ancestor = zip(*[(node.delete(), node.parent) for node in nodes if not node.is_root_node()])
        ancestor = min(nodes_ancestor, key=attrgetter('level'))

        response = json.dumps({'status' : 'success', 'ancestor_id' : ancestor.pk})

        return HttpResponse(response, content_type="application/json")

    except BaseException, e:
        raise e


def moveNodes(request):
    try:
        post_dict = dict(request.POST.copy())
        nodes_id = post_dict['nodes_id']
        parent_id = post_dict['parent'][0]
        nodes = Folder.objects.filter(pk__in = nodes_id, created_by=request.user)
        parent = Folder.objects.get(pk=parent_id, created_by=request.user)
        if type(parent) == Folder:
            for node in nodes:
                node.move_to(parent)
                node.save()
            response = json.dumps({'success': 'Node(s) were moved correctly'})

        else:
            response = json.dumps({'error': 'Node(s) were not moved correctly'})

        return HttpResponse(response, content_type="application/json")

    except BaseException, e:
        raise e



def insertFolder(request):
    try:
        post_dict = dict(request.POST.copy())
        nodes_id = post_dict['id'][0]

        node = Folder.objects.get(pk=nodes_id, created_by=request.user)
        if type(node) == Shapefile:
            new_folder = Folder.objects.create(name="New Folder", parent=node.parent, created_by=request.user)
        else:
            new_folder = Folder.objects.create(name="New Folder", parent=node, created_by=request.user)

        json_response = json.dumps({'child_id': new_folder.pk, 'parent_id': new_folder.parent.pk})

        return HttpResponse(json_response, content_type="application/json")

    except BaseException, e:
        raise e


#----------------------------------------------------------------------------------
# Maps Tree functions
#----------------------------------------------------------------------------------


def initMapsTree(request):
    try:
        root_node = Folder.objects.get(created_by=request.user, category='maps')
        nodes = root_node.get_descendants(include_self=True)
        node_tree = cache_tree_children(nodes)
        for n in node_tree:
            data = (folderTree_to_json(n))

        tree = json.dumps(data, indent=4)

        return HttpResponse(tree, content_type="application/json")

    except BaseException, e:
        raise e


def listMaps(request):
    try:
        folder_id = request.POST.get('node_id')
        folder = Folder.objects.get(pk=folder_id, created_by=request.user)
        nodes = folder.get_ancestors(include_self=True).exclude(level=0)
        if type(folder) == Folder:
            maps_count = BasquiMap.objects.filter(parent=folder, created_by=request.user).count()
        else:
            maps_count = 1

        html = render_to_string("maps/maps_list.html", {'folder': folder, 'nodes':nodes, 'maps_count':maps_count},context_instance=RequestContext(request))
        js = render_to_string("maps/js/maps_list.js", {'folder': folder},context_instance=RequestContext(request))
        response = json.dumps({'html': html, 'js':js})
        return HttpResponse(response, content_type="application/json")

    except BaseException, e:
        raise e


def listMapsLoader(request, folder_id):
    try:
        folder = Folder.objects.get(pk=folder_id, created_by=request.user)
        if type(folder) == Folder:
            maps_list = BasquiMap.objects.filter(parent=folder, created_by=request.user).order_by('name')
        else:
            maps_list = BasquiMap.objects.filter(pk=folder_id, created_by=request.user).order_by('name')

        data = [{'id': map.id, 'name': map.name,
            'layers': [{'layer_name': layer.name, 'layer_id': layer.id} for layer in map.layers.order_by('name')],
            'date_created': map.date_created, 'date_updated': map.date_updated, 'in_use': map.in_use}
            for map in maps_list]

        jsonData = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(jsonData, content_type="application/json")

    except BaseException, e:
        raise e

def maps_selectLayersTree(request, folder_id):
    try:
        layerMapOptions_ids = LayerMapOptions.objects.filter(basqui_map__id = folder_id).values_list('layer__pk', flat=True)
        root_node = Folder.objects.get(created_by=request.user, category='layers')
        nodes = root_node.get_descendants(include_self=True)
        node_tree = cache_tree_children(nodes)
        for n in node_tree:
            data = (selectLayersTree_to_json(n, layerMapOptions_ids))

        tree = json.dumps(data, indent=4)
        return HttpResponse(tree, content_type="application/json")

    except BaseException, e:
        raise e