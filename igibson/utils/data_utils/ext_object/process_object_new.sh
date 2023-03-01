#!/bin/bash

BASEDIR=$(dirname "$0")
echo "$BASEDIR"
cd $BASEDIR
#########
# The script takes inputs:
# 1. directory to the source files
# 2. category label of the object
#########
IGIBSON_DIR=$(python -c "import igibson; print(igibson.ig_dataset_path)" | tail -1)
SRC_BLEND_FILE=$1
CATEGORY=$2
OBJECT_ID=$3
# OBJECT_EXPORT_DIR=$IGIBSON_DIR/objects/$CATEGORY/$NAME/$OBJECT_ID
BLEND_FILE_FOLDER=$(dirname "$SRC_BLEND_FILE")
OBJECT_EXPORT_DIR=$BLEND_FILE_FOLDER/objects/$CATEGORY/$OBJECT_ID

echo $OBJECT_EXPORT_DIR

echo "Step 1"
cd scripts
##################
# Generate visual meshes
##################
blender -b --python step_1_visual_mesh_multi_uv.py -- --bake --source_blend_file $SRC_BLEND_FILE --dest_dir $OBJECT_EXPORT_DIR

echo "Step 2"
##################
# Generate collision meshes
##################
python step_2_collision_mesh.py \
    --input_dir $OBJECT_EXPORT_DIR/shape/visual \
    --output_dir $OBJECT_EXPORT_DIR/shape/collision \
    --object_name $OBJECT_ID # --split_loose

echo "Step 3"
##################
# Generate misc/*.json
##################
python step_3_metadata.py --input_dir $OBJECT_EXPORT_DIR

echo "Step 4"
##################
# Generate .urdf
##################
python step_4_urdf.py --input_dir $OBJECT_EXPORT_DIR

echo "Step 5"
##################
# Generate visualizations
##################
python step_5_visualizations.py --input_dir $OBJECT_EXPORT_DIR


