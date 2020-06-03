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
import shutil
import glob
from osgeo import gdal
import rasterio as rio


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
    """
    loads csv into df
    :param file_path: str
    :return: df
    """
    df = pd.read_csv(file_path)
    return df

def load_json(file_path):
    """
    loads json file
    :param file_path: str
    :return: dict
    """
    f = open(file_path)
    return json.load(f)

def day_time_step(date):
    """
    increment date
    :param date: datetime obj
    :return: incremented datetime obj
    """
    date = date.fromisoformat('2019-12-04')
    date += timedelta(days=1)
    return str(date)

def convert_to_extension(content):
    """
    to handle downloads from redirects
    :param content:
    :return:
    """
    conversions = {
        'application/x-hdf':'.hdf'
    }
    return conversions[content]

def write_to_json(scenes, datasets, filepath):
    """
    write a given set of scenes to json
    outputs three files: modis_meta.json, landsat_meta.json and both_meta.json
    :param scenes: list of scene objects generated by landsat modis pair search
    :param datasets: names of both datasets
    :param filepath: filepath where the files are to be written
    :return:
    """
    try:
        os.mkdir(os.path.join(filepath, "metadata"))

    except:
        pass
    filepath = os.path.join(filepath, "metadata")
    path = os.path.join(filepath, "{}_meta.json")

    la_p = path.format(datasets[0])
    mod_p = path.format(datasets[1])
    all = path.format(datasets[0]+"_"+datasets[1]+"_both")
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
    """helper function for observations"""
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
    """helper function for observations"""
    ### load meta-data ###
    data_path = os.path.join(OUTPUT_DIR, "metadata/both_meta.json")
    data = load_json(data_path)
    lsat_cloudcover = []
    for val in list(data.values()):
        lsat_cloudcover.append(val[0]["cloudCover"])

    return lsat_cloudcover


def compute_approx_center(coord, str=True):
    """
    compute the center of a a scenes bounding box
    :param coord: coord in scene object
    :param str: bool to toggle output to str or float32
    :return: center of bounding box
    """
    coord = np.array(coord.split(",")).astype("float32")
    x = np.mean([coord[0],coord[2]])
    y = np.mean([coord[1],coord[3]])
    if str:
        return "{}, {}".format(x, y)
    else:
        return (x, y)

def get_image_pairs(path_to_datasets):
    """
    get image pairs iterable from downloaded data, based on json
    :param path_to_datasets: str path to json file containing meta data
    :param data_path: str path to being stored
    :return: iterable
    """
    data_pairs = load_json(path_to_datasets)
    fnames = []
    for i in range(len(data_pairs)):
        # this data is saved so that there are indexes for each pair
        # it is loaded as string so we must convert int to str
        l, m = data_pairs[str(i)]
        fnames.append((l["displayId"], m["displayId"]))

    return fnames

def unzip_targz(fpath):
    """
    unzip a gzip file
    :param fpath: str glob path
    :return: none
    """
    fpath = fpath + "\*.tar.gz"
    files = glob.glob(fpath)
    for f in files:
        try:
            shutil.unpack_archive(f, f.split(".")[0])
        except shutil.ReadError:
            os.mkdir(f.split(".")[0])
            shutil.unpack_archive(f, f.split(".")[0])

def organize_dir(fpath):
    """
    designed for after hfds_to_tiff call
    :param fpath: str path of directory
    :return:
    """
    fpath_ext = fpath + "\*.tiff"
    files = glob.glob(fpath_ext)
    file_names = [os.path.basename(f) for f in files]

    # make original folder dirs
    bandless = set([f[:-12] for f in file_names])

    for img in bandless:
        new_dir = fpath+ "\{}".format(img)
        os.mkdir(new_dir)
        to_remove = []
        for f in files:
            # move to corresponding dir
            if os.path.basename(f)[:-12] == img:
                shutil.move(f, new_dir)
                to_remove.append(f)

        for f in to_remove:
            files.remove(f)

    return files

def hdf_to_TIF(fpath):
    """
    convert hdf to TIF using gdal
    :param fpath: str path of directory
    :return:
    """
    files = glob.glob(fpath+"\*.hdf")

    for f in files:
        new_dir = os.path.join(fpath, os.path.basename(f)[:-4])
        os.mkdir(new_dir)
        # open file
        sds = gdal.Open(f, gdal.GA_ReadOnly).GetSubDatasets()
        # iterate through each band
        for band in sds:
            ds = gdal.Open(band[0])
            open_band = ds.GetRasterBand(1)
            open_band = open_band.ReadAsArray()
            # get meta data
            [cols, rows] = open_band.shape
            driver = gdal.GetDriverByName("GTiff")
            outFileName = os.path.join(new_dir, band[1].split(" ")[1]+".TIF")
            outdata = driver.Create(outFileName, rows, cols, 1, gdal.GDT_UInt16)
            # sets same geotransform as input
            outdata.SetGeoTransform(ds.GetGeoTransform())
            # sets same projection as input
            outdata.SetProjection(ds.GetProjection())
            outdata.GetRasterBand(1).WriteArray(open_band)
            # save to disk
            outdata.FlushCache()


def get_surface_reflectance_bands(l_dir, m_dir):
    """
    given a pair of landsat, modis image dirs retireve the refl bands (1-7)
    :param l_dir: str dir
    :param m_dir: str dir
    :return: return list of file paths, if pair does not exist return empty lists
    """
    l_files, m_files = {}, {}

    # get landsat bands
    for i in range(1, 8):
        files = glob.glob(l_dir + r"/*B{}.TIF".format(str(i)))
        l_files[i] = files[0]

    # get modis bands
    m_files = glob.glob(m_dir + r"/*sur_refl_b*.TIF")
    # ensure accuracy of band access by refering to file name
    m_files = {int(path[-7]): path for path in m_files}
    files = [l_files, m_files]

    return files

def get_surface_reflectance_pairs(l_dir, m_dir):
    """
    get the actual file paths for each exisiting pair
    :param l_dir: str dir
    :param m_dir: str dir
    :return:
    """
    # get the image pairs from json data
    pairs = get_image_pairs(OUTPUT_DIR + r"\metadata\both_meta.json")

    # return pairs
    full_pairs = []

    # for each pair of images
    for l, m in pairs:
        landsat_dir = os.path.join(l_dir, l)
        modis_dir = os.path.join(m_dir, m)

        # get surface reflectance bands
        try:
            srb = get_surface_reflectance_bands(landsat_dir, modis_dir)

            img_pair = ((l, srb[0]), (m, srb[1]))
        except IndexError:
            # if there is no match for the pair move onto next set of pairs
            continue
        # add to full set
        full_pairs.append(img_pair)
    print(len(full_pairs))
    return full_pairs

def stack_rasters(bands, output_dir, ds_name, stacked_bands=[1,2,3]):
    """
    stacks a given list of rasters
    :param bands: dict of bands generated by get_surface_reflectance_pairs
    :param output_dir: str dir
    :param stacked_bands: list of desired bands
    :return: None
    """
    # open first band to use to add other bands
    with rio.open(bands[stacked_bands[0]]) as b1:
        meta = b1.meta

    # Update meta to reflect the number of bands
    meta.update(count=len(stacked_bands))

    # make new raster for stacked bands
    s = ds_name
    for i in stacked_bands:
        s += "_{}".format(i)
    s += ".TIF"
    output_file = os.path.join(output_dir, s)
    with rio.open(output_file, 'w', **meta) as dst:

        # set color interpretation to RGB
        if stacked_bands == [1,2,3]:
            dst.profile['photometric'] = "RGB"
        # Read each layer and write it to stack
        for band_num in stacked_bands:
            with rio.open(bands[band_num]) as src1:
                dst.write_band(band_num, src1.read(1))



def build_dataset(output_dir, l_dir, m_dir, stacked_bands):
    """
    build dataset given dirs and desired bandss
    :param output_dir: str dir
    :param l_dir:str dir
    :param m_dir:str dir
    :param stacked_bands:list of ints for desired bands
    :return: None
    """
    # get band pairs
    pairs = get_surface_reflectance_pairs(l_dir, m_dir)
    print(len(pairs))
    for i, pair in enumerate(pairs):
        l, m = pair
        # dir for pairs
        dir = os.path.join(output_dir, "pair_{}".format(i))
        if not os.path.isdir(dir):
            os.mkdir(dir)

        # stack landsat
        stack_rasters(bands=l[1],
                      output_dir=dir,
                      ds_name=l[0],
                      stacked_bands=stacked_bands)
        # stack modis
        stack_rasters(bands=m[1],
                      output_dir=dir,
                      ds_name=m[0],
                      stacked_bands=stacked_bands)
    os.environ['LS_MD_PAIRS'] = output_dir

    return output_dir

def get_landsat_modis_pairs(dir, transform=False, both_modis=False):
    """
    helper function for observations
    :param dir: str dir
    :return: list of pairs
    """
    pairs = []
    if not transform:
        for pair in os.listdir(dir):
            p = os.path.join(dir, pair)
            #print(p+"\*")
            pair = glob.glob(p+"\*")
            pair.remove(glob.glob(p+"\*_transformed*")[0])
            pairs.append(pair)

    else:
        if both_modis:
            specifier = "M"
        else:
            specifier = "L"
        for pair in os.listdir(dir):
            p = os.path.join(dir, pair)

            if both_modis:
                pair = glob.glob(p+"\M*")
            else:
                pair = [glob.glob(p+"\L*")[0].format(specifier),
                        glob.glob(p+"\*_transformed*")[0]]
            pairs.append(pair)

    return pairs


def reproject_on_tif(inpath, outpath, to_copy_from_path):
    """
    taken from https://www.earthdatascience.org/courses
    /use-data-open-source-python/intro-raster-data-python
    /raster-data-processing/
    :param inpath:dir for input
    :param outpath:dir for output
    :param to_copy_from_path:path for raster to copy from
    :return:None
    """
    new_src = rio.open(to_copy_from_path)
    dst_crs = new_src.crs
    # inpath = modis

    with rio.open(inpath) as src:
        # transform src to new_src do not change size & resolution
        transform, width, height = rio.warp.calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': dst_crs,
            'transform': transform,
            'width': width,
            'height': height
        })

        with rio.open(outpath, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                rio.warp.reproject(
                    source=rio.band(src, i),
                    destination=rio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=rio.warp.Resampling.bilinear)
