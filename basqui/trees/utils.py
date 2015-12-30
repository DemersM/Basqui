from trees.models import *
from layers.models import *
from maps.models import *

def folderTree_to_json(node):

    name = node.name

    if type(node) == Shapefile:
        result = {
            'id': node.pk,
            'name': node.name,
            'type': node.geom_type,
            'leaf': True,
        }
    elif type(node) == BasquiMap:
        result = {
            'id': node.pk,
            'name': node.name,
            'type': node.in_use,
            'leaf': True,
        }
    else:
        result = {
            'id': node.pk,
            'name': node.name,
            'type': None,
            'loaded': True,
            'leaf': False,
        }
    children = [folderTree_to_json(c) for c in node.get_children()]
    if children:
        result['children'] = children

    return result


def selectLayersTree_to_json(node, layerMapOptions_ids):
    name = node.name

    if type(node) == Shapefile:
        if node.pk in layerMapOptions_ids:
            result = {
                'id': node.pk,
                'name': node.name,
                'checked' : True,
                'type': node.geom_type,
                'leaf': True,
            }
        else:
            result = {
                'id': node.pk,
                'name': node.name,
                'checked' : False,
                'type': node.geom_type,
                'leaf': True,
            }
    else:
        result = {
            'id': node.pk,
            'name': node.name,
            'type': None,
            'loaded': True,
            'leaf': False,
        }

    children = [selectLayersTree_to_json(c, layerMapOptions_ids) for c in node.get_children()]
    if children:
        result['children'] = children

    return result