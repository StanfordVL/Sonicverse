import argparse
import glob
import json
import os

import numpy as np
from PIL import Image

import igibson

parser = argparse.ArgumentParser("Generate Mesh meta-data...")
parser.add_argument("--input_dir", dest="input_dir")
parser.add_argument("--material", dest="material", default="wood")

use_mat = "mtllib default.mtl\nusemtl default\n"
default_mtl = """newmtl default
Ns 225.000000
Ka 1.000000 1.000000 1.000000
Kd 0.800000 0.800000 0.800000
Ks 0.500000 0.500000 0.500000
Ke 0.000000 0.000000 0.000000
Ni 1.450000
d 1.000000
illum 2
map_Kd ../../material/DIFFUSE.png
map_Pm ../../material/METALLIC.png
map_Pr ../../material/ROUGHNESS.png
map_bump ../../material/NORMAL.png
"""


def add_mat(input_mesh, output_mesh):
    with open(input_mesh, "r") as fin:
        lines = fin.readlines()
    for l in lines:
        if l == "mtllib default.mtl\n":
            return
    with open(output_mesh, "w") as fout:
        fout.write(use_mat)
        for line in lines:
            if not line.startswith("o") and not line.startswith("s"):
                fout.write(line)


def gen_object_mtl(model_dir):
    mesh_dir = os.path.join(model_dir, "shape", "visual")
    if not os.path.isdir(mesh_dir):
        return
    objs = glob.glob("{}/*.obj".format(mesh_dir))
    for o in objs:
        add_mat(o, o)
    mtl_path = os.path.join(mesh_dir, "default.mtl")
    with open(mtl_path, "w") as fp:
        fp.write(default_mtl)


def load_obj(fn):
    fin = open(fn, "r")
    lines = [line.rstrip() for line in fin]
    fin.close()

    vertices = []
    for line in lines:
        if line.startswith("v "):
            vertices.append(np.float32(line.split()[1:4]))
    if len(vertices) <= 1:
        return None
    v = np.vstack(vertices)
    return v


def get_min_max(input_dir):
    mins = []
    maxs = []
    mesh_dir = os.path.join(input_dir, "shape", "collision")
    objs = glob.glob("{}/*.obj".format(mesh_dir))
    for o in objs:
        mverts = load_obj(o)
        if mverts is None:
            continue
        mins.append(mverts.min(axis=0))
        maxs.append(mverts.max(axis=0))

    if len(mins) == 1:
        min_v = mins[0]
        max_v = maxs[0]
    else:
        min_v = np.vstack(mins).min(axis=0)
        max_v = np.vstack(maxs).max(axis=0)
    return min_v.astype(float), max_v.astype(float)


def gen_bbox(input_dir):
    min_c, max_c = get_min_max(input_dir)
    save_dict = {"base_link_offset": tuple((max_c + min_c) / 2.0), "bbox_size": tuple(max_c - min_c)}
    save_path = os.path.join(input_dir, "misc", "metadata.json")
    with open(save_path, "w") as fp:
        json.dump(save_dict, fp)


def gen_material(input_dir, material_string):
    materials = material_string.split(",")
    material_dir = os.path.join(igibson.ig_dataset_path, "materials")
    material_json_file = os.path.join(material_dir, "materials.json")
    assert os.path.isfile(material_json_file), "cannot find material files: {}".format(material_json_file)
    with open(material_json_file) as f:
        all_materials = json.load(f)
    for m in materials:
        assert m in all_materials, "unknown material class: {}".format(m)
    material_entry = {"1": materials}
    mesh_to_material = {}
    mesh_dir = os.path.join(input_dir, "shape", "visual")
    meshes = [o for o in os.listdir(mesh_dir) if os.path.splitext(o)[-1] == ".obj"]
    for m in meshes:
        mesh_to_material[m] = 1
    save_path = os.path.join(input_dir, "misc", "material_groups.json")
    with open(save_path, "w") as fp:
        json.dump([material_entry, mesh_to_material], fp)


def composite_transmission_material(input_dir):
    # run some composition on transmission
    transmissio_fn = os.path.join(input_dir, "material", "TRANSMISSION.png")
    transmission = np.array(Image.open(transmissio_fn))
    transmission_mask = np.sum(transmission, axis=2) > 0

    # assume transmission has the same resolution as diffuse
    # and higher resolution than metallic, roughness

    diffuse_fn = os.path.join(input_dir, "material", "DIFFUSE.png")
    diffuse = np.array(Image.open(diffuse_fn))
    diffuse[transmission_mask] = transmission[transmission_mask]
    Image.fromarray(diffuse).save(diffuse_fn)

    metallic_fn = os.path.join(input_dir, "material", "METALLIC.png")
    metallic = np.array(Image.open(metallic_fn))

    roughness_fn = os.path.join(input_dir, "material", "ROUGHNESS.png")
    roughness = np.array(Image.open(roughness_fn))

    normal_fn = os.path.join(input_dir, "material", "NORMAL.png")
    normal = np.array(Image.open(normal_fn))

    transmission_low_res = np.array(Image.open(transmissio_fn).resize(metallic.shape[:2]))
    transmission_mask_low_res = np.sum(transmission_low_res, axis=2) > 0

    metallic[transmission_mask_low_res] = 127
    roughness[transmission_mask_low_res] = 127
    normal[transmission_mask_low_res] = np.array([127, 127, 255])

    Image.fromarray(metallic).save(metallic_fn)
    Image.fromarray(roughness).save(roughness_fn)
    Image.fromarray(normal).save(normal_fn)


args = parser.parse_args()
if os.path.isdir(args.input_dir):
    misc_dir = os.path.join(args.input_dir, "misc")
    os.makedirs(misc_dir, exist_ok=True)
    gen_bbox(args.input_dir)
    gen_material(args.input_dir, args.material)
    bake_dir = os.path.join(args.input_dir, "material")
    if os.path.isdir(bake_dir) and len(os.listdir(bake_dir)) >= 4:
        gen_object_mtl(args.input_dir)
    if os.path.isfile(os.path.join(bake_dir, "TRANSMISSION.png")):
        composite_transmission_material(args.input_dir)
