import os
import json

idx=0
fixture_path = os.path.dirname(os.path.abspath(__file__)) + "/markers.json"
content = []
for subdir, dirs, files in os.walk("../media/markers"):
    cat = os.path.split(subdir)[1]
    for file in files:
        idx += 1
        name = file.split('.')[0]
        path = "markers/%s/%s" % (cat,file)

        content1 = json.dumps( {
                    "pk": "%s",
                    "model": "maps.Marker",
                    "fields": { "name": "%s", "svg": "%s", "category": "%s"}
        }) % (idx, name, path, cat)
        content.append(content1)

myfile = open(fixture_path, "w")
myfile.write(str(content))
myfile.close()