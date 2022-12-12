from time import time
import json

new_json = {'time': time()}
print(new_json)

#with open("index.json", "w") as index_file:
#    json.dump(new_json, index_file)