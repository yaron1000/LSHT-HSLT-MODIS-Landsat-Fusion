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
from shapely.geometry import mapping
from shapely.wkt import loads
import rioxarray
import datetime

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
    write a given set of scenes to json, if proj already has metadata, add to previous
    outputs json file to output dir/metadata
    :param scenes: list of scene objects generated by landsat modis pair search
    :param datasets: names of both datasets
    :param filepath: filepath where the files are to be written
    :return:
    """
    try:
        os.mkdir(os.path.join(filepath, "metadata"))
        # nothing to add if empty
        meta = {}
        start = 0
    except:
        meta = load_latest_meta()
        # if there already is meta data #
        if meta:
            # find last int used in keys
            start = max([int(k) for k in meta.keys()])
        else:
            start = 0

    # metadata dir #
    filepath = os.path.join(filepath, "metadata")
    path = os.path.join(filepath, "{}_meta.json")
    all = path.format(datasets[0]+"_"+datasets[1]+"_"+str(date.today()))

    to_dump = {i+start:list(pair) for i, pair in enumerate(scenes)}

    # add previous meta data
    to_dump.update(meta)
    A = open(all, 'w')
    json.dump(to_dump, A)
    A.close()

def load_latest_meta():
    """
    load the latest meta file in output dir
    :return: json dict
    """
    path = os.path.join(OUTPUT_DIR, "metadata\*.json")
    dates = [[], []]
    for f in glob.glob(path):
        # get date of meta data
        try:
            var_date = date.fromisoformat(f[:-10][-10:])
            dates[0].append(var_date)
            dates[1].append(f)
        except:
            continue

    # if any exists return latest file
    if dates[0]:
        # find index of most latest date
        most_recent = np.argmax(dates[0])
        return load_json(dates[1][most_recent])
    else:
        return {}


def get_spatial_polygons(json_fname):
    """
    Loads last queried set of modis-landsat pairs metadata
    spatial footprints as polygons
    """
    ### load meta-data ###
    data = load_latest_meta()
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

def get_polygon(fpath):
    """
    get polygon for specific path
    :param fpath: path of raster
    :return: polygon
    """
    ### load meta-data ###
    data = load_latest_meta()

    raster = rio.open(fpath)
    ind = os.path.basename(fpath)[0]
    conv = {'L':0,'M':1 }
    try:
        index = conv[ind]
    except KeyError:
        raise Exception("Invalid file")

    if ind == "L":
        id = os.path.basename(fpath)[:40]

    elif ind == "M":
        id = os.path.basename(fpath)[:27]

    for val in list(data.values()):
        if id == val[index]["displayId"]:
            coords = val[index]['spatialFootprint']['coordinates']
            poly = [Point(v) for v in coords[0]]
            poly = Polygon(poly)
            return poly

def get_dates():
    """helper function for observations"""
    ### load meta-data ###
    data = load_latest_meta()
    dates = []
    for val in list(data.values()):
        lsat = date.fromisoformat(val[0]["acquisitionDate"])
        modis = date.fromisoformat(val[1]["acquisitionDate"])
        dates.append((lsat, modis))

    return dates

def get_cloud_indexes():
    """helper function for observations"""
    ### load meta-data ###
    data = load_latest_meta()
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

def get_image_pairs():
    """
    get image pairs iterable from downloaded data, based on json
    :param path_to_datasets: str path to json file containing meta data
    :param data_path: str path to being stored
    :return: iterable
    """
    data_pairs = load_latest_meta()

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
            try:
                shutil.unpack_archive(f, f.split(".")[0])
            except shutil.ReadError:
                os.mkdir(f.split(".")[0])
                shutil.unpack_archive(f, f.split(".")[0])
        except EOFError:
            print("error unpacking: {}".format(f.split(".")[0]))
            with open(
                    r"C:\Users\Noah Barrett\Desktop\School\Research 2020\code\super-res\LSHT-HSLT-MODIS-Landsat-Fusion\assets\log.txt",
                    "w") as f:
                f.write("unpack error: {}\n".format(f.split(".")[0]))
            continue


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
    pairs = get_image_pairs()

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
    return full_pairs

def stack_rasters(bands, output_dir, ds_name, stacked_bands=[1,2,3]):
    """
    stacks a given list of rasters
    :param bands: dict of bands generated by get_surface_reflectance_pairs
    :param output_dir: str dir
    :param stacked_bands: list of desired bands
    :return: bool to indicate success or failure of extraction
    """
    # open first band to use to add other bands
    if not len(bands):
        print("no bands found for this file")
        print("Fname: {} \ndataset: {}".format(output_dir, ds_name))
        return False

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

    return True


def build_dataset(output_dir, l_dir, m_dir, stacked_bands, index):
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
    for i, pair in enumerate(pairs):
        l, m = pair
        # dir for pairs
        # i + index to ensure new pairs made each iteration
        dir = os.path.join(output_dir, "pair_{}".format(index))
        if not os.path.isdir(dir):
            os.mkdir(dir)

        # stack landsat
        if not stack_rasters(bands=l[1],
                      output_dir=dir,
                      ds_name=l[0],
                      stacked_bands=stacked_bands):
            print("landsat stack failed")
            shutil.rmtree(dir)
            continue

        # stack modis
        if not stack_rasters(bands=m[1],
                      output_dir=dir,
                      ds_name=m[0],
                      stacked_bands=stacked_bands):
            print("modis stack failed")
            try:
                shutil.rmtree(dir)
                continue
            except PermissionError:
                with open(r"C:\Users\Noah Barrett\Desktop\School\Research 2020\code\super-res\LSHT-HSLT-MODIS-Landsat-Fusion\assets\log.txt", "w") as f:
                    f.write("faulty pair: {}".format(dir))



        # if succesfully stack both images increment #
        index += 1

    os.environ['LS_MD_PAIRS'] = output_dir

    return output_dir, index

def get_landsat_modis_pairs_early(path):
    pairs = []
    for pair in os.listdir(path):
        p = os.path.join(path, pair)
        pair = glob.glob(p + "\*")
        pairs.append(pair)
    return pairs

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
                pair = [glob.glob(p+"\L*")[0],
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
    :return: outpath
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
    try:
        os.remove(inpath)
    except PermissionError:
        try:
            inpath.close()
            os.remove(inpath)
        except:
            print("unable to delete {}:".format(inpath))

    return outpath

def clip_tif_wrt_tif(inpath, outpath, to_copy_from_path):
    """

    :param inpath: path to tif that is to be clipped
    :param outpath: output path for tif
    :param to_copy_from_path: tif to copy from
    :return: outpath
    """
    poly = get_polygon(to_copy_from_path).wkt
    geom = mapping(loads(poly))

    rds = rioxarray.open_rasterio(inpath, parse_coordinates=False)
    try:
        masked = rds.rio.clip([geom], "EPSG:4326", drop=True)
        masked.rio.to_raster(outpath)
        rds.close()
        os.remove(inpath)
    except:
        rds.close()
        print("error clipping img:")
        print("{}".format(inpath))
        base_path = os.path.split(inpath[0])[0]
        shutil.rmtree(base_path)


    return outpath

def all_to_one_NPY(dir, bands=[[3,2,1], [1, 4, 3]]):
    """
    add
    :param dir: str path to file directory (country)
    :param bands: tuple for bands to be recorded from each tiff, defaulted to rgb
    :return: None
    """
    NPY_dir = os.path.join(OUTPUT_DIR, "NPY")
    if not os.path.isdir(NPY_dir):
        os.mkdir(NPY_dir)
    shapes = []
    fname = "Landsat_MODIS.npy"
    f_path = os.path.join(NPY_dir, fname)
    with open(f_path, 'wb') as f:
        for path in get_landsat_modis_pairs_early(dir):

            # landsat and modis pairs #
            l_path = path[0]
            m_path = path[1]

            # get both scene images from file names #
            L_ID = os.path.basename(l_path)[:40]
            M_ID = os.path.basename(m_path)[:27]
            MetaID = np.array([L_ID, M_ID])

            # open landsat #
            l_raster = rio.open(l_path)

            # open MODIS #
            m_raster = rio.open(m_path)
            l_m_bands = [[], []]

            for l_band, m_band in zip(bands[0], bands[1]):
                # read band for both rasters #
                l_m_bands[0].append(l_raster.read(l_band))
                l_m_bands[1].append(m_raster.read(m_band))

            # stack the bands #
            l_stack = np.dstack(l_m_bands[0])
            m_stack = np.dstack(l_m_bands[1])
            arr = np.array([l_stack, m_stack, MetaID])
            shapes.append(arr.shape)
            # save as numpy #
            np.save(f, arr)
        """
        # make memmap #
        fp = np.memmap(os.path.join(NPY_dir,"Landsat_MODIS_memmap.dat"), dtype='float32', mode='w+', shape=shapes)
        # save as memmap #
        for i in range(len(get_landsat_modis_pairs_early(dir))):
            fp[i] = np.load(f)

        # flush fp #
        del fp
        """



def load_NPY(fpath):
    """
    open NPY follwoing format used in saving as NPY
        -> Landsat scene
        -> MODIS scene
        -> Tuple containing Landsat ID, MODIS ID for associated scene
    :param fpath:
    :return: Lsat scene, modis scence, ID tuple
    """
    with open(fpath, 'rb') as f:
        landsat_scene = np.load(f)
        MODIS_scene = np.load(f)
        ID = np.load(f)

    return landsat_scene, MODIS_scene, ID

def save_pairs_to_text(scenes, datasets, outdir):
    """written_scenes, self.Datasets, self.OUTPUT_DIR"""
    file = os.path.join(outdir, "metadata_{}.txt".format(str(date.today())))
    with open(file, "w") as f:
        title = "Datasets: {}, {}".format(datasets[0], datasets[1])
        f.write(title)
        for l, m  in scenes:
            f.write("{}, {}".format(l["displayId"], m["displayId"]))
