from time import time
import json
import fsspec
import re
import json
from collections import Counter
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time
import timeit
import nbformat

MAX_WORKERS = 10

new_json = {'time': time()}
print(new_json)

def parse_adsbib_format(text: str) -> dict:
    """Parse the adsbib format into a dictionary. On error return an empty dict"""

    result = {
        k: ""
        for k in ["filename", "title", "summary", "developed on", "keywords", "license"]
    }

    # Set valid prefix and return if string does not start with it.
    prefix = "@notebook"
    text = text.strip("\n\t ")

    if not text.startswith(prefix):
        return {}

    # Strip out the field/value strings
    text = text[len(prefix) :].strip("{}")

    field_value_list = [l.strip(",\t") for l in text.split("\n") if len(l) > 0]

    if len(field_value_list) == 0:
        return {}

    # Get the filename and then the field/value pairs
    result["filename"] = field_value_list[0].strip(",")
    for item in field_value_list[1:]:
        if ":" not in item:
            print(f"Unable to parse: {item}")
        else:
            field, value = item.split(":", 1)

        result[field.strip(" ")] = value.strip(" ")

    if "keywords" in result:
        result["keywords"] = [
            k.strip() for k in result["keywords"].split(",") if len(k.strip()) > 0
        ]
    return result

def extract_curly_braces(string: str):
    return re.sub("[^\}\{]+", "", string)

def parse_file(
    uri: str, block_size:int, auth: dict = None, skip_first_lines: int = 0, max_lines_to_read: int = 20
) -> dict:
    auth = auth or {}
    PREFIX = "@notebook"
    CURLY_BRACES = Counter()
    add_line_to_res = False
    line_number = 0
    res = []

    with open(uri, "r", block_size, **auth ) as f:
        for line in f:
            line_number += 1
            if skip_first_lines and line_number <= skip_first_lines:
                continue

            if PREFIX in line.strip().lower():
                add_line_to_res = True

            if add_line_to_res:
                formated_line = (
                    line.replace('"', "")
                    .replace(",\\n", "")
                    .replace("\\n", "")
                    .strip(" ")
                )
                if formated_line.replace(" ", ""):
                    res.append(formated_line)
                    CURLY_BRACES.update(extract_curly_braces(formated_line))

            if line_number > max_lines_to_read or (
                CURLY_BRACES["{"] == CURLY_BRACES["}"] and CURLY_BRACES["{"] > 0
            ):
                break

    return parse_adsbib_format("".join(res))

def parse_nb(
    uri: str, block_size:int, auth: dict = None, 
) -> dict:
    auth = auth or {}
    #print("block_size in parse_nb: ", block_size)
    bib:str = ""

    with open(uri, "r", block_size, **auth) as f:
        nb = nbformat.read(f, nbformat.NO_CONVERT)
        for cell in nb.cells:
            if cell.cell_type == "raw":
                bib = cell["source"]
                
    if(bib == ""):
        return ""

    return parse_adsbib_format(bib)

def parse_notebooks(uri: str, block_size:int, auth: dict = None, parse_by_line:bool = True,  max_workers:int = MAX_WORKERS, execute_times:int = 1 ):
    start_time = time()
    i=0
    while i < execute_times:
        i+= 1
        auth = auth or {}
        scheme = urlparse(uri).scheme or "file"
        
        file_system = fsspec.filesystem(scheme, **auth)
        files = [
            file for file in file_system.ls(uri) if file.endswith(".ipynb")
        ]
        print("files", files)
        method = parse_file if parse_by_line else parse_nb

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(method, f"{file}", block_size, auth): file
                for file in files
            }
            result = {futures[task]: task.result() for task in as_completed(futures)}
        

    duration = (time() - start_time)/execute_times
 
    print("max_workers:", max_workers, " ", "block_size:", block_size, " " "duration:", duration, "sec")
    return result

json_content = parse_notebooks("/home/notebooks", block_size=1000, parse_by_line = True, max_workers=10)
print(json_content)

with open("index.json", "w") as index_file:
    json.dump(json_content, index_file)