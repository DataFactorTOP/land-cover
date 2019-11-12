'''
utils.py
Author: Lucas Hu
SEN12MS Land-Cover util functions
'''

import os
import numpy as np
from sklearn.preprocessing import LabelEncoder
from skimage.util.shape import view_as_blocks
import keras
from sen12ms_dataLoader import SEN12MSDataset, \
    Seasons, Sensor, S1Bands, S2Bands, LCBands

def json_keys_to_int(x):
    '''
    Helper function to parse JSON with ints as keys
    '''
    try:
        return {int(k):v for k,v in x.items()}
    except:
        return x

def get_label_encoder(config):
    '''
    Uses config_dict's landuse_class info to get an sklearn label_encoder
    Output: sklearn label_encoder
    '''
    # get remaining classes after merging
    merged_classes = set(config['landuse_class_mappings'].keys())
    all_classes = set(config['landuse_class_descriptions'].keys())
    remaining_classes = all_classes - merged_classes
    # sort class_nums
    class_nums_sorted = sorted(list(remaining_classes))
    # get label_encoder
    label_encoder = LabelEncoder()
    label_encoder.classes_ = np.array(class_nums_sorted)
    return label_encoder

def patch_to_subpatches(patch, config):
    '''
    Input: single patch: B, W, H
    Output: N, B, subpatch_size, subpatch_size
    '''
    subpatch_size = config['training_params']['subpatch_size']
    subpatches = view_as_blocks(patch, \
        block_shape=(subpatch_size, subpatch_size, patch.shape[-1]))
    subpatches = np.squeeze(subpatches)
    subpatches = np.concatenate(subpatches, axis=0)
    return subpatches

def scene_to_subpatches(patches, config):
    '''
    Split square patches into smaller squre sub-patches
    Input: patches of shape D, B, W, H
    Output: patches of shape N, B, subpatch_size, subpatch_size
        N = D * (W / subpatch_size)
    '''
    subpatch_size = config['training_params']['subpatch_size']
    all_subpatches = [] # list of each patch's subpatch array
    for i, patch in enumerate(patches):
        subpatches = patch_to_subpatches(patch, config)
        all_subpatches.append(subpatches)
    # concat all subpatches
    return np.concatenate(all_subpatches, axis=0)

def combine_landuse_classes(landuse, config):
    '''
    Input: land use patches (Shape: D, W, H), config
    Output: land use patches with combined classes (see Section 5 of SEN12MS paper)
    '''
    landuse_class_mappings = config['landuse_class_mappings']
    for from_class, to_class in landuse_class_mappings.items():
        landuse = np.where(landuse==from_class, to_class, landuse)
    return landuse

def get_landuse_labels(lc, config):
    '''
    Input: lc (land cover bands, Shape: D, W, H, B=4), config
    Output: majority LCCS land-use class, Shape: D
    '''
    land_use_patches = lc[:, :, :, LCBands.landuse.value-1]
    land_use_patches = combine_landuse_classes(land_use_patches, config)
    land_use_flattened = land_use_patches.reshape(land_use_patches.shape[0], -1)
    modes, counts = stats.mode(land_use_flattened, axis=1)
    return np.ravel(modes)

def get_represented_landuse_classes_from_onehot_labels(y, label_encoder):
    '''
    Input: y (one-hot labels, 2D array), label_encoder
    Output: list of landuse class numbers that do appear in y
    '''
    labels = np.argmax(y, axis=1)
    landuse_classes = label_encoder.inverse_transform(labels)
    represented_classes = set(np.unique(landuse_classes).tolist())
    all_classes = set(label_encoder.classes_.tolist())
    missing_classes = all_classes - represented_classes
    return list(represented_classes)

def get_missing_landuse_classes_from_onehot_labels(y, label_encoder):
    '''
    Input: y (one-hot labels, 2D array), label_encoder
    Output: list of landuse class numbers that do not appear in y
    '''
    all_classes = set(label_encoder.classes_.tolist())
    represented_classes = get_represented_landuse_classes_from_onehot_labels(y)
    represented_classes = set(represented_classes)
    missing_classes = all_classes - represented_classes
    return list(missing_classes)

def get_scene_dirs_for_continent(continent, config):
    '''
    Input: continent (e.g. North_America), config
    Output: list of scene directories for that continent
    '''
    # get directories for this continent
    continent_season_subdirs = [entry.path \
        for entry in os.scandir(config['subpatches_dataset_dir']) \
        if entry.is_dir() and \
        continent in entry.name]
    # traverse 1 level down to get scene directories
    all_scene_dirs = []
    for continent_season_subdir in continent_season_subdirs:
        scene_dirs = [entry.path for entry in os.scandir(continent_season_subdir) \
            if entry.is_dir() and 'scene' in entry.name]
        all_scene_dirs += scene_dirs
    return all_scene_dirs

def get_scene_dirs_for_season(season, config):
    '''
    Input: season (e.g. fall), config
    Output: list of scene directories for that continent
    '''
    # get directories for this continent
    continent_season_subdirs = [entry.path \
        for entry in os.scandir(config['subpatches_dataset_dir']) \
        if entry.is_dir() and \
        season in entry.name]
    # traverse 1 level down to get scene directories
    all_scene_dirs = []
    for continent_season_subdir in continent_season_subdirs:
        scene_dirs = [entry.path for entry in os.scandir(continent_season_subdir) \
            if entry.is_dir() and 'scene' in entry.name]
        all_scene_dirs += scene_dirs
    return all_scene_dirs

def get_segmentation_patch_paths_for_scene_dir(scene_dir):
    '''
    Input: single scene_dir
    Output: list of segmentation data patch paths
    '''
    all_subpatch_paths = []
    patch_dirs = [entry.path for entry in os.scandir(scene_dir) \
        if entry.is_dir() and 'patch' in entry.name]
    return patch_dirs

def get_segmentation_patch_paths_for_scene_dirs(scene_dirs):
    '''
    Input: scene_dirs (list)
    Output: list of subpatch .npy paths
    '''
    all_patch_paths = []
    # traverse scenes
    for scene_dir in scene_dirs:
        all_patch_paths += get_segmentation_patch_paths_for_scene_dir(scene_dir)
    return all_patch_paths

def get_subpatch_paths_for_scene_dir(scene_dir):
    '''
    Input: single scene_dir
    Output: list of subpatch .npy paths
    '''
    all_subpatch_paths = []
    patch_dirs = [entry.path for entry in os.scandir(scene_dir) \
        if entry.is_dir() and 'patch' in entry.name]
    # traverse patches
    for patch_dir in patch_dirs:
        # get subpatch files
        subpatch_npy_paths = [entry.path for entry in os.scandir(patch_dir) \
            if entry.is_file() and 'subpatch' in entry.name and entry.name.endswith('.npy')]
        all_subpatch_paths += subpatch_npy_paths
    return all_subpatch_paths

def get_subpatch_paths_for_scene_dirs(scene_dirs):
    '''
    Input: scene_dirs (list)
    Output: list of subpatch .npy paths
    '''
    all_subpatch_paths = []
    # traverse scenes
    for scene_dir in scene_dirs:
        all_subpatch_paths += get_subpatch_paths_for_scene_dir(scene_dir)
    return all_subpatch_paths










