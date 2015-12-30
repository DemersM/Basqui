from layers.models import *


def folderTree_to_json(node):
    if node.name:
        name = node.name
    else:
        name = node.filename

    if type(node) == Shapefile:
        result = {
            'id': node.pk,
            'name': name,
            'type': node.geom_type,
            'leaf': True,
        }
    else:
        result = {
            'id': node.pk,
            'name': name,
            'type': None,
            'loaded': True,
            'leaf': False,
        }
    children = [folderTree_to_json(c) for c in node.get_children()]
    if children:
        result['children'] = children

    return result