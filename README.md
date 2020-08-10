The steps taken to attempt this are:

1. Collect data from the https://openneuro.org/datasets/ds001506/versions/1.3.1 website along with the tsv, json and nii files.
2. Take data from JSON file and correlate it with tsv files to indicate relevant information.
3. There was a problem of correlating this data with the voxel positions in the fMRI images.

When the above mentioned method did not work, we used a pre-trained VGG19 model which was used as a decoder for the f-MRI scans. (https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006633). Using this pre-trained model, we were able to generate the required image using our algorithm as implemented in the python file.

Raw BOLD image of two co-registered runs, and the signal from the same occipital lobe voxel was not successfully completed. We tried some attempts but it not implementating as it need to implement.

## Usage Instructions

1. Make the `download_data.sh` an executable. Change the csv file name in `download_data.sh` to whatever you want to generate images of i.e. natural images, artificial or shapes.
2. The csv files are named are `natural.csv`,`shapes.csv` and `alphabets.csv` for each individual category. The entire dataset csv is `file_list.csv`.
3. Make changes in code too according to the category. This should be done after

```# DNN layer combinations
layers_sets = {'layers-1to1' : ['conv1_1', 'conv1_2'],
               'layers-1to3' : ['conv1_1', 'conv1_2', 'conv2_1', 'conv2_2',
                                'conv3_1', 'conv3_2', 'conv3_3', 'conv3_4'],
               'layers-1to5' : ['conv1_1', 'conv1_2', 'conv2_1', 'conv2_2',
                                'conv3_1', 'conv3_2', 'conv3_3', 'conv3_4',
                                'conv4_1', 'conv4_2', 'conv4_3', 'conv4_4',
                                'conv5_1', 'conv5_2', 'conv5_3', 'conv5_4'],
               'layers-1to7' : ['conv1_1', 'conv1_2', 'conv2_1', 'conv2_2',
                                'conv3_1', 'conv3_2', 'conv3_3', 'conv3_4',
                                'conv4_1', 'conv4_2', 'conv4_3', 'conv4_4',
                                'conv5_1', 'conv5_2', 'conv5_3', 'conv5_4',
                                'fc6', 'fc7']}
```

- For natural image make it

```# Images in figure 4
image_type = 'natural'

image_label_list = ['Img0009',
                    'Img0002',
                    'Img0001',
                    'Img0005',
                    'Img0036',
                    'Img0045',
                    'Img0031',
                    'Img0043']
```

- For shapes, change it to

```
image_type = 'color_shape'
image_label_list = ['Img0001',
                    'Img0002',
                    'Img0003',
                    'Img0004',
                    'Img0005',
                    'Img0006',
                    'Img0007',
                    'Img0008',
                    'Img0009',
                    'Img0010',
                    'Img0011',
                    'Img0012',
                    'Img0013',
                    'Img0014',
                    'Img0015']
```

- For alphabets, change it to

```
image_type = 'alphabet'
image_label_list = ['Img0005',
                    'Img0003',
                    'Img0010',
                    'Img0007',
                    'Img0006']
```
