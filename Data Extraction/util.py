"""
helper functions
"""
import csv
import pandas as pd
import random
import json
from datetime import date, timedelta, datetime
import numpy as np
import os
from shapely.geometry import Point, Polygon

### get variables ##
vars = {'EE_USERNAME':'',
        'EE_PASSWORD':'',
        'SR_DATA':''}
for v in vars.keys():
    try:
        vars[v]
    except KeyError:
        os.environ[v] = input(v+": ")

USERNAME = os.environ['EE_USERNAME']
PASSWORD = os.environ['EE_PASSWORD']
OUTPUT_DIR = os.environ['SR_DATA']

def load_world_lat_lon(file_path):
    df = pd.read_csv(file_path)
    return df

def load_json(file_path):
    f = open(file_path)
    return json.load(f)
'2020-01-01'
def day_time_step(date):
    date = date.fromisoformat('2019-12-04')
    date += timedelta(days=1)
    return str(date)

def convert_to_extension(content):
    conversions = {
        'application/x-hdf':'.hdf'
    }
    return conversions[content]

def compute_difference(coord1, coord2):

    coord1 = np.array(coord1.split(",")).astype("float32")
    coord2 = np.array(coord2.split(",")).astype("float32")

    diff_arr = np.abs

def write_to_json(scenes, datasets, filepath):
    #fs = os.path.join(file_path, str(datetime.now()) + "{}.json").replace("-","_").replace(" ", "_").replace(":", "_")
    mod_dir = "./"
    try:
        os.mkdir(os.path.join(filepath, "metadata"))

    except:
        pass
    filepath = os.path.join(filepath, "metadata")
    path = os.path.join(filepath, "{}_meta.json")

    la_p = path.format(datasets[0])
    mod_p = path.format(datasets[1])
    all = path.format("both")
    scenes = np.array(scenes)
    landsat = {"lsat":list(scenes.T[0])}
    modis = {"modis":list(scenes.T[1])}
    to_dump = {i:list(pair) for i, pair in enumerate(scenes)}

    print("writing Landsat data to {}".format(la_p))
    LS =  open(la_p, 'w')
    json.dump(landsat, LS)
    LS.close()

    print("writing MODIS data to {}".format(mod_p))
    MO = open(mod_p, 'w')
    json.dump(modis, MO)
    MO.close()


    A = open(all, 'w')
    json.dump(to_dump, A)
    A.close()

def get_spatial_polygons():
    """
    Loads last queried set of modis-landsat pairs metadata
    spatial footprints as polygons
    """
    ### load meta-data ###
    data_path = os.path.join(OUTPUT_DIR, "metadata/both_meta.json")
    data = load_json(data_path)
    spatial_foots = []
    for val in list(data.values()):
        ### make polygon objects ###
        lsat = val[0]['spatialFootprint']['coordinates']
        lsat = [Point(v) for v in lsat[0]]
        lsat = Polygon(lsat)

        modis = val[1]['spatialFootprint']['coordinates']
        modis = [Point(v) for v in modis[0]]
        modis = Polygon(modis)

        spatial_foots.append((lsat, modis))
    return spatial_foots

def get_dates():
    ### load meta-data ###
    data_path = os.path.join(OUTPUT_DIR, "metadata/both_meta.json")
    data = load_json(data_path)
    dates = []
    for val in list(data.values()):
        lsat = date.fromisoformat(val[0]["acquisitionDate"])
        modis = date.fromisoformat(val[1]["acquisitionDate"])

        dates.append((lsat, modis))

    return dates

def get_cloud_indexes():
    ### load meta-data ###
    data_path = os.path.join(OUTPUT_DIR, "metadata/both_meta.json")
    data = load_json(data_path)
    lsat_cloudcover = []
    for val in list(data.values()):
        lsat_cloudcover.append(val[0]["cloudCover"])

    return lsat_cloudcover


def compute_approx_center(coord, str=True):

    coord = np.array(coord.split(",")).astype("float32")
    x = np.mean([coord[0],coord[2]])
    y = np.mean([coord[1],coord[3]])
    if str:
        return "{}, {}".format(x, y)
    else:
        return (x, y)