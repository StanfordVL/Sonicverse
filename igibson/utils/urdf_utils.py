import logging
import math
import xml.etree.ElementTree as ET

import numpy as np
import trimesh

from igibson.utils.utils import get_rpy_from_transform, get_transform_from_xyz_rpy

log = logging.getLogger(__name__)


def get_aabb_urdf(tree):
    all_vertices = []
    for mesh in tree.findall("link/collision/geometry/mesh"):
        mesh_obj = trimesh.load(mesh.attrib["filename"])
        all_vertices.append(mesh_obj.vertices)
    all_vertices = np.vstack(all_vertices)
    return all_vertices.min(axis=0), all_vertices.max(axis=0)


def get_base_link_name(tree):
    joints = tree.findall("joint")
    links = tree.findall("link")
    # Find the base link
    children_links = [joint.find("child").attrib["link"] for joint in joints]
    return [link.attrib["name"] for link in links if link.attrib["name"] not in children_links][0]


def parse_urdf(tree):
    """
    Parse URDF for spliting by floating joints later
    """
    # map from name of child to name of its parent, joint name and type of connection
    parent_map = {}
    child_map = {}  # map from name of parent to list of names of children, joint names and types of connection
    joint_map = {}  # map from name of joint to names of parent and child and type
    single_link = []

    single_link_urdf = True
    for joint in tree.iter("joint"):  # We iterate over joints to build maps
        single_link_urdf = False
        parent_name = joint.find("parent").attrib["link"]
        child_name = joint.find("child").attrib["link"]
        joint_name = joint.attrib["name"]
        joint_type = joint.attrib["type"]

        parent_map[child_name] = (parent_name, joint_name, joint_type)
        if parent_name in child_map:
            child_map[parent_name].append((child_name, joint_name, joint_type))
        else:
            child_map[parent_name] = [(child_name, joint_name, joint_type)]

        joint_xyz = np.array([float(val) for val in joint.find("origin").attrib["xyz"].split(" ")])

        if "rpy" in joint.find("origin").attrib:
            joint_rpy = np.array([float(val) for val in joint.find("origin").attrib["rpy"].split(" ")])
        else:
            joint_rpy = np.array([0.0, 0.0, 0.0])

        joint_frame = get_transform_from_xyz_rpy(joint_xyz, joint_rpy)
        joint_map[joint_name] = (parent_name, child_name, joint_type, joint_frame)

    if single_link_urdf:
        single_link = [tree.find("link").attrib["name"]]

    return (parent_map, child_map, joint_map, single_link)


def splitter(parent_map, child_map, joint_map, single_child_link):
    """
    Recursively split URDFs by floating joints
    """
    new_single_child_link = []
    for (joint_name, joint_tuple) in joint_map.items():
        log.debug("Joint: ", joint_name)
        if joint_tuple[2] == "floating":

            log.debug("Splitting floating joint")
            # separate into the two parts and call recursively splitter with each part
            parent_of_floating = joint_tuple[0]
            child_of_floating = joint_tuple[1]

            # If the children of float is not parent of any link, we add it to the sengle_child_link
            if child_of_floating not in child_map.keys():
                new_single_child_link += [child_of_floating]

            parent_map1 = {}
            child_map1 = {}
            joint_map1 = {}
            parent_map2 = {}
            child_map2 = {}
            joint_map2 = {}

            # Find all links "down" the floating joint
            log.debug("Finding children")
            log.debug("Child of floating: " + child_of_floating)
            all_children = [child_of_floating]
            children_rec = [child_of_floating]
            while len(children_rec) != 0:
                new_children_rec = []
                for child in children_rec:
                    if child in child_map:
                        new_children_rec += child_map[child]

                all_children += [new_child[0] for new_child in new_children_rec]
                children_rec = [new_child[0] for new_child in new_children_rec]

            log.debug("All children of the floating joint: " + " ".join(all_children))

            # Separate joints in map1 and map2
            # The ones in map2 are the ones with the child pointing to one of the links "down" the floating joint
            log.debug("Splitting joints")
            for (joint_name2, joint_tuple2) in joint_map.items():
                if joint_name2 != joint_name:
                    if joint_tuple2[1] in all_children:
                        joint_map2[joint_name2] = joint_tuple2
                    else:
                        joint_map1[joint_name2] = joint_tuple2

            # Separate children into map1 and map2
            # Careful with the child_map because every key of the dict (name of parent) points to a list of children
            log.debug("Splitting children")
            for parent in child_map:  # iterate all links that are parent of 1 or more joints
                # for each parent, get the list of children
                child_list = child_map[parent]
                if parent in all_children:  # if the parent link was in the list of all children of the floating joint
                    # save the list as list of children of the parent link in the children floating suburdf
                    child_map2[parent] = child_list
                else:  # otherwise, it is one of the links parents of the floating joint
                    # save the list as the list of
                    child_map1[parent] = [item for item in child_list if item[0] != child_of_floating]
                    # children of the parent in the parent floating suburdf, except the children connected by the floating joint

            # Separate parents into map1 and map2
            for child in parent_map:
                if child != child_of_floating:
                    if child in all_children:
                        parent_map2[child] = parent_map[child]
                    else:
                        parent_map1[child] = parent_map[child]

            ret1 = splitter(parent_map1, child_map1, joint_map1, [])
            ret2 = splitter(parent_map2, child_map2, joint_map2, new_single_child_link)
            ret = ret1 + ret2
            return ret
    return [(parent_map, child_map, joint_map, single_child_link)]


def round_up(n, decimals=0):
    """
    Helper function to round a float
    """
    multiplier = 10 ** decimals
    return math.ceil(n * multiplier) / multiplier


def transform_element_xyzrpy(element, transformation):
    """
    Transform a URDF element by transformation

    :param element: URDF XML element
    :param transformation: transformation that should be applied to the element
    """
    element_xyz = np.array([float(val) for val in element.find("origin").attrib["xyz"].split(" ")])
    if "rpy" in element.find("origin").attrib:
        element_rpy = np.array([float(val) for val in element.find("origin").attrib["rpy"].split(" ")])
    else:
        element_rpy = np.array([0.0, 0.0, 0.0])
    element_transform = get_transform_from_xyz_rpy(element_xyz, element_rpy)
    total_transform = np.dot(transformation, element_transform)
    element.find("origin").attrib["xyz"] = "{0:f} {1:f} {2:f}".format(*total_transform[0:3, 3])
    transform_rpy = get_rpy_from_transform(total_transform)
    element.find("origin").attrib["rpy"] = "{0:f} {1:f} {2:f}".format(*transform_rpy)


def save_urdfs_without_floating_joints(tree, file_prefix):
    """
    Split one URDF into multiple URDFs if there are floating joints and save them
    """
    # Pybullet doesn't read floating joints
    # Find them and separate into different objects
    (parent_map, child_map, joint_map, single_floating_links) = parse_urdf(tree)

    # Call recursively to split the tree into connected parts without floating joints
    splitted_maps = splitter(parent_map, child_map, joint_map, single_floating_links)

    extended_splitted_dict = {}
    for (count, split) in enumerate(splitted_maps):
        all_links = []
        for parent in split[0]:
            if parent not in all_links:
                all_links.append(parent)
        for child in split[1]:
            if child not in all_links:
                all_links.append(child)
        for link in split[3]:
            if link not in all_links:
                all_links.append(link)
        extended_splitted_dict[count] = (split[0], split[1], split[2], all_links, np.eye(4))

    for (joint_name, joint_tuple) in joint_map.items():
        log.debug("Joint: " + joint_name)
        if joint_tuple[2] == "floating":
            log.debug("floating")
            parent_name = joint_tuple[0]
            transformation = joint_tuple[3]

            while parent_name in parent_map.keys():
                # Find the joint where the link with name "parent_name" is child
                joint_up = [
                    joint for joint in tree.findall("joint") if joint.find("child").attrib["link"] == parent_name
                ][0]
                joint_transform = joint_map[joint_up.attrib["name"]][3]
                transformation = np.dot(joint_transform, transformation)
                parent_name = joint_map[joint_up.attrib["name"]][0]

            child_name = joint_tuple[1]
            for esd in extended_splitted_dict:
                if child_name in extended_splitted_dict[esd][3]:
                    extended_splitted_dict[esd] = (
                        extended_splitted_dict[esd][0],
                        extended_splitted_dict[esd][1],
                        extended_splitted_dict[esd][2],
                        extended_splitted_dict[esd][3],
                        transformation,
                    )
    log.debug("Number of splits: " + str(len(extended_splitted_dict)))
    log.debug("Instantiating scene into the following urdfs:")

    main_link_name = get_base_link_name(tree)

    urdfs_no_floating = {}
    for esd_key in extended_splitted_dict:
        xml_tree_parent = ET.ElementTree(ET.fromstring('<robot name="split_' + str(esd_key) + '"></robot>'))
        log.debug("links " + " ".join(extended_splitted_dict[esd_key][3]))

        for link_name in extended_splitted_dict[esd_key][3]:
            link_to_add = [link for link in tree.findall("link") if link.attrib["name"] == link_name][0]
            xml_tree_parent.getroot().append(link_to_add)

        for joint_name in extended_splitted_dict[esd_key][2]:
            joint_to_add = [joint for joint in tree.findall("joint") if joint.attrib["name"] == joint_name][0]
            xml_tree_parent.getroot().append(joint_to_add)

        # Copy the elements that are not joint or link (e.g. material)
        for item in list(tree.getroot()):
            if item.tag not in ["link", "joint"]:
                xml_tree_parent.getroot().append(item)

        urdf_file_name = file_prefix + "_" + str(esd_key) + ".urdf"
        # Change 0 by the pose of this branch

        is_main_body = main_link_name == get_base_link_name(xml_tree_parent)
        transformation = extended_splitted_dict[esd_key][4]
        urdfs_no_floating[esd_key] = (urdf_file_name, transformation, is_main_body)
        xml_tree_parent.write(urdf_file_name, xml_declaration=True)
        log.debug(urdf_file_name)

    # There should be exactly one main body
    assert np.sum([val[2] for val in urdfs_no_floating.values()]) == 1

    return urdfs_no_floating


def add_fixed_link(tree, link_name, link_info):
    """
    Add a fixed link onto a URDF tree.

    :param tree: The URDF tree (ElementTree) to add to.
    :param link_name: The name of the link to add.
    :param link_info: A dict that stores the link info, including geometry
    (box or None), size (for box), xyz and rpy of the origin of the joint
    :return: None
    """
    tree = tree.getroot()
    base_link_name = get_base_link_name(tree)

    # Assert that the link does not exist.
    assert tree.find("link[@name='%s']" % link_name) is None

    # Add the link.
    link = ET.SubElement(tree, "link", {"name": link_name})

    # The below commented code can be used to add a visual to the area.
    # TODO: Either fully remove this or make it possible to toggle this using a global flag.
    # visual = ET.SubElement(link, "visual")
    # ET.SubElement(visual, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
    #
    # geo = ET.SubElement(visual, "geometry")
    # ET.SubElement(geo, "box", {"size": "0.1 0.1 0.1"})
    #
    # mat = ET.SubElement(visual, "material", {"name": "red"})
    # ET.SubElement(mat, "color", {"rgba": "255 0 0 1.0"})

    visual = ET.SubElement(link, "visual")
    visual_origin = ET.SubElement(visual, "origin")
    visual_origin.attrib = {
        "xyz": "0. 0. 0.",
        "rpy": "0. 0. 0.",
    }
    visual_geometry = ET.SubElement(visual, "geometry")
    collision = ET.SubElement(link, "collision")
    collision_origin = ET.SubElement(collision, "origin")
    collision_origin.attrib = {
        "xyz": "0. 0. 0.",
        "rpy": "0. 0. 0.",
    }
    collision_geometry = ET.SubElement(collision, "geometry")
    if link_info["geometry"] == "box":
        # Make the visual box infinitely small so that it won't appear
        # in the renderer
        visual_box = ET.SubElement(visual_geometry, "box")
        visual_box.attrib = {"size": "%.4f %.4f %.4f" % tuple([0.0, 0.0, 0.0])}
        # Uncomment the below to see the actual visual mesh.
        #    'size': "%.4f %.4f %.4f" % tuple(link_info['size'])}
        collision_box = ET.SubElement(collision_geometry, "box")
        collision_box.attrib = {"size": "%.4f %.4f %.4f" % tuple(link_info["size"])}
    else:
        raise ValueError("add_fixed_link only supports box")

    # Add the joint
    joint = ET.SubElement(tree, "joint", {"name": link_name + "_joint", "type": "fixed"})
    ET.SubElement(joint, "parent", {"link": base_link_name})
    ET.SubElement(joint, "child", {"link": link_name})

    # Finally, apply the offset
    xyz = link_info["xyz"] if link_info["xyz"] is not None else [0.0, 0.0, 0.0]
    rpy = link_info["rpy"] if link_info["rpy"] is not None else [0.0, 0.0, 0.0]

    ET.SubElement(joint, "origin", {"rpy": "%.4f %.4f %.4f" % tuple(rpy), "xyz": "%.4f %.4f %.4f" % tuple(xyz)})
